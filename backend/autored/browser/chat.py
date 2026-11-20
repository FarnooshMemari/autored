"""Driving a website's chat assistant through the real UI, via the
target-independent discovery layer. Keeps per-agent multi-turn history and
emits viewport/box info for overlay animations.
"""
from __future__ import annotations

import time

from ..events.schema import Box, BrowserActionPayload, LogPayload
from ..safety.scope import Account, LoginConfig, Target
from . import discovery
from .discovery import ChatError, ChatHandle
from .runtime import AgentBrowser


class ChatTurn:
    __slots__ = ("role", "text", "ts")

    def __init__(self, role: str, text: str):
        self.role, self.text, self.ts = role, text, time.time()


class ChatSession:
    def __init__(self, browser: AgentBrowser, target: Target):
        self.b, self.target = browser, target
        self.handle: ChatHandle | None = None
        self.history: list[ChatTurn] = []   # this agent's own conversation

    async def login(self, account: Account, cfg: LoginConfig | None) -> None:
        if cfg is None:
            return
        await self.b.goto(self.target.url(cfg.path))
        if cfg.mode == "assisted":
            await self._assisted_login(cfg)
            return
        await self.b.fill(cfg.username_selector, account.username)
        await self.b.fill(cfg.password_selector, account.password, secret=True)
        await self.b.click(cfg.submit_selector)
        # SPA logins redirect client-side; wait for the login path to go away.
        login_path = cfg.path.rstrip("/")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            await self.b.page.wait_for_timeout(300)
            if login_path not in self.b.page.url.rstrip("/"):
                return
        raise ChatError(f"login failed for test account {account.username}")

    async def _assisted_login(self, cfg: LoginConfig) -> None:
        """Operator completes login (SSO/MFA) in the browser; we only wait and
        verify. We never type credentials or bypass an auth step."""
        self.b.emit("log", LogPayload(level="info",
                    message=f"Assisted login: waiting up to {cfg.wait_timeout_s:.0f}s for operator to sign in"))
        if not cfg.success_selector:
            raise ChatError("assisted login requires success_selector in scope")
        try:
            await self.b.page.wait_for_selector(cfg.success_selector, timeout=cfg.wait_timeout_s * 1000)
        except Exception as e:
            raise ChatError(f"assisted login not completed in time: {e}") from None

    async def open(self) -> None:
        if self.target.chat.path and self.target.chat.path not in self.b.page.url:
            await self.b.goto(self.target.url(self.target.chat.path))

    async def discover(self, greeting: str, timeout_s: float) -> tuple[dict, str]:
        handle, reply, _ = await discovery.discover(self.b.page, self.target.chat, greeting, timeout_s)
        self.handle = handle
        self.history.append(ChatTurn("assistant", reply))
        box = await discovery.box_of(handle.scope, handle.input_sel)
        self.b.emit("browser.action", BrowserActionPayload(action="read", selector=handle.input_sel,
                    value_preview="chat composer located", frame=handle.frame_sel,
                    box=Box(**box) if box else None))
        return handle.as_dict(), reply

    async def attach(self, hints, timeout_s: float) -> None:
        """Reconstruct the chat handle in THIS agent's own context from the
        Commander's discovered config (no re-greeting)."""
        self.handle = await discovery.attach(self.b.page, hints, timeout_s)

    async def send(self, text: str, timeout_s: float) -> tuple[str, int, dict | None]:
        if self.handle is None:
            raise ChatError("chat handle not set (discovery did not run)")
        self.history.append(ChatTurn("user", text))
        box_in = await discovery.box_of(self.handle.scope, self.handle.input_sel)
        self.b.emit("browser.action", BrowserActionPayload(action="fill", selector=self.handle.input_sel,
                    value_preview=text[:120], frame=self.handle.frame_sel, box=box_in and Box(**box_in)))
        self.b.emit("browser.action", BrowserActionPayload(action="wait", selector=self.handle.assistant_sel,
                    frame=self.handle.frame_sel))
        t0 = time.monotonic()
        reply, box = await discovery.send_message(self.handle, text, timeout_s)
        self.history.append(ChatTurn("assistant", reply))
        return reply, int((time.monotonic() - t0) * 1000), box

    async def fetch_json(self, path: str):
        """Same-origin GET using this agent's isolated cookies (oracle reads)."""
        url = self.target.url(path)
        if not self.b.guard.is_allowed(url):
            raise PermissionError(url)
        resp = await self.b.context.request.get(url)
        return await resp.json() if resp.ok else None
