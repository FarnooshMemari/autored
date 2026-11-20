"""Browser automation with strict per-agent isolation.

Isolation model (do not "optimize" this into shared tabs):
* One Chromium process per AutoRed process.
* One BrowserContext per agent (separate cookies, storage, cache), never a
  tab in a shared context. Tabs in one context share the session cookie, so
  four agents in four tabs would be one user on the server.
* Each agent signs in with its own synthetic test account, so server-side
  session state is separate too. State the server shares across users (ledgers,
  global memory) is handled by named locks in the mission context.
* Validation replays run in a fresh context, so a reproduction does not depend
  on conversation history left over from the first attempt.
"""
from __future__ import annotations

import asyncio
import base64
import uuid
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Route, async_playwright

from ..events.schema import BrowserActionPayload, BrowserBlockedPayload, BrowserNavigatedPayload
from ..safety.scope import OriginGuard


class BrowserRuntime:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def browser(self) -> Browser:
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                if self._pw is None:
                    self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=self.headless)
            return self._browser

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._pw = None


class FrameHub:
    """Latest JPEG frame per (mission, agent) plus live subscribers. Kept off the
    JSON event stream so frames don't swamp it."""

    def __init__(self) -> None:
        self._latest: dict[tuple[str, str], bytes] = {}
        self._subs: dict[tuple[str, str], set[asyncio.Queue[bytes]]] = defaultdict(set)

    def push(self, mission_id: str, agent_id: str, jpeg: bytes) -> None:
        key = (mission_id, agent_id)
        self._latest[key] = jpeg
        for q in list(self._subs[key]):
            if q.full():
                try:
                    q.get_nowait()  # drop the stale frame, keep the newest
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(jpeg)

    def latest(self, mission_id: str, agent_id: str) -> bytes | None:
        return self._latest.get((mission_id, agent_id))

    def subscribe(self, mission_id: str, agent_id: str) -> asyncio.Queue[bytes]:
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._subs[(mission_id, agent_id)].add(q)
        if (f := self.latest(mission_id, agent_id)) is not None:
            q.put_nowait(f)
        return q

    def unsubscribe(self, mission_id: str, agent_id: str, q: asyncio.Queue[bytes]) -> None:
        self._subs[(mission_id, agent_id)].discard(q)


Emit = Callable[[str, object], None]


class AgentBrowser:
    def __init__(self, runtime: BrowserRuntime, frames: FrameHub, mission_id: str, agent_id: str,
                 guard: OriginGuard, emit: Emit, action_timeout_ms: int = 15000):
        self.runtime, self.frames, self.guard, self.emit = runtime, frames, guard, emit
        self.mission_id, self.agent_id = mission_id, agent_id
        self.action_timeout_ms = action_timeout_ms
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.context_id = ""
        self._cdp = None

    async def open(self) -> Page:
        browser = await self.runtime.browser()
        self.context = await browser.new_context(viewport={"width": 1100, "height": 720})
        self.context.set_default_timeout(self.action_timeout_ms)
        self.context_id = f"{self.agent_id}-{uuid.uuid4().hex[:8]}"
        await self.context.route("**/*", self._enforce_scope)
        self.page = await self.context.new_page()
        self.page.on("framenavigated", self._on_nav)
        await self._start_screencast()
        return self.page

    async def reset(self) -> Page:
        """Fresh, isolated context (used for validation replays)."""
        await self.close()
        return await self.open()

    async def close(self) -> None:
        if self.context is not None:
            try:
                await self.context.close()
            except Exception:
                pass
        self.context = self.page = self._cdp = None

    # -- safety ---------------------------------------------------------
    async def _enforce_scope(self, route: Route) -> None:
        url = route.request.url
        if self.guard.is_allowed(url):
            await route.continue_()
        else:
            self.emit("browser.blocked", BrowserBlockedPayload(url=url, reason="origin not in allowlist"))
            await route.abort("blockedbyclient")

    # -- live view --------------------------------------------------------
    async def _start_screencast(self) -> None:
        try:
            self._cdp = await self.context.new_cdp_session(self.page)
            cdp = self._cdp

            async def on_frame(params: dict) -> None:
                self.frames.push(self.mission_id, self.agent_id, base64.b64decode(params["data"]))
                try:
                    await cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
                except Exception:
                    pass

            cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(on_frame(p)))
            await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 55, "maxWidth": 960, "maxHeight": 640})
        except Exception as e:  # non-Chromium or CDP unavailable: live view degrades, testing continues
            self.emit_log("warning", f"live view unavailable: {e}")

    def emit_log(self, level: str, message: str) -> None:
        from ..events.schema import LogPayload
        self.emit("log", LogPayload(level=level, message=message))

    def _on_nav(self, frame) -> None:
        if self.page is not None and frame == self.page.main_frame:
            vp = self.page.viewport_size
            self.emit("browser.navigated", BrowserNavigatedPayload(
                url=frame.url, context_id=self.context_id,
                viewport={"width": vp["width"], "height": vp["height"]} if vp else None))

    # -- instrumented actions --------------------------------------------
    async def goto(self, url: str) -> None:
        if not self.guard.is_allowed(url):
            raise PermissionError(f"refusing to navigate outside scope: {url}")
        await self.page.goto(url, wait_until="domcontentloaded")

    async def fill(self, selector: str, value: str, secret: bool = False) -> None:
        preview = "••••" if secret else value[:120]
        self.emit("browser.action", BrowserActionPayload(action="fill", selector=selector, value_preview=preview))
        await self.page.fill(selector, value)

    async def click(self, selector: str) -> None:
        self.emit("browser.action", BrowserActionPayload(action="click", selector=selector))
        await self.page.click(selector)

    async def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=str(path))
        return path
