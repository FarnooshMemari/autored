"""Target-independent chat discovery and interaction.

Works across structurally different sites with no per-target code:
  * main-page chat, full-page chat, and widgets inside IFRAMES
  * open SHADOW DOM (Playwright CSS pierces open shadow roots)
  * launcher buttons that mount the chat on click
  * dynamically rendered / async interfaces (polling with budgets)
  * textarea / input / contenteditable composers
  * send via button OR Enter key
  * streaming replies (wait until the reply text stops growing)

Configuration & fallback: a target may pin any of input/send/assistant/frame/
launcher/send_mode via scope ChatHints; whatever is omitted is discovered.
If discovery fails and nothing is pinned, ChatError is raised with context so an
operator can supply selectors manually.

A `ChatScope` is a Playwright Page or FrameLocator; both expose `.locator()`,
so interaction is frame-agnostic and we poll locator counts in Python rather
than injecting frame-specific JS.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from playwright.async_api import FrameLocator, Locator, Page

from ..safety.scope import ChatHints

INPUT_CANDIDATES = [
    "textarea:not([readonly])",
    "input[type=text]:not([name*=user i]):not([id*=user i]):not([name*=pass i])",
    "[contenteditable=true]",
    "[role=textbox]",
]
SEND_CANDIDATES = [
    'button:has-text("Send")',
    '[aria-label*="send" i]',
    "button[type=submit]",
    "#send",
    'button:has-text("Ask")',
]
ASSISTANT_CANDIDATES = [
    ".msg.assistant", ".bubble.assistant", '[data-role="assistant"]',
    '[class*="assistant" i]', '[class*="bot" i]', ".a-msg", ".message",
]
LAUNCHER_CANDIDATES = [
    '[aria-label*="chat" i]', '[aria-label*="support" i]', '[aria-label*="help" i]',
    'button:has-text("Chat")', 'button:has-text("Help")', 'button:has-text("Support")',
    'button:has-text("Message")',
]

ChatScope = Page | FrameLocator


@dataclass
class ChatHandle:
    scope: ChatScope
    input_sel: str
    assistant_sel: str
    send_sel: str | None          # None => send via Enter
    send_mode: str                # "click" | "enter"
    frame_sel: str | None         # iframe CSS if the chat is inside one, else None
    frame_index: int = 0          # which match of frame_sel
    launcher_sel: str | None = None  # button that mounts the widget, if any

    def as_dict(self) -> dict[str, str]:
        return {"input": self.input_sel, "assistant_message": self.assistant_sel,
                "send": self.send_sel or "(Enter key)", "send_mode": self.send_mode,
                "frame": self.frame_sel or "(main document)"}

    def to_hints(self, path: str, launcher: str | None):
        from ..safety.scope import ChatHints
        return ChatHints(path=path, input=self.input_sel, send=self.send_sel, send_mode=self.send_mode,
                         assistant_message=self.assistant_sel, frame=self.frame_sel,
                         launcher=self.launcher_sel or launcher)


def build_scope(page: Page, frame_sel: str | None, frame_index: int = 0) -> ChatScope:
    return page.frame_locator(frame_sel).nth(frame_index) if frame_sel else page


class ChatError(Exception):
    pass


async def _first_visible(scope: ChatScope, candidates: list[str]) -> str | None:
    for sel in candidates:
        loc = scope.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                return sel
        except Exception:
            continue
    return None


async def _wait_for_any_input(scope: ChatScope, pinned: str | None, budget_s: float) -> str | None:
    deadline = time.monotonic() + budget_s
    cands = [pinned] if pinned else INPUT_CANDIDATES
    while time.monotonic() < deadline:
        sel = await _first_visible(scope, [c for c in cands if c])
        if sel:
            return sel
        await _sleep(scope, 200)
    return None


async def _sleep(scope: ChatScope, ms: int) -> None:
    page = scope if isinstance(scope, Page) else None
    if page:
        await page.wait_for_timeout(ms)
    else:
        import asyncio
        await asyncio.sleep(ms / 1000)


async def _scopes(page: Page, hints: ChatHints) -> list[tuple[ChatScope, str | None, int]]:
    """Main document first, then each iframe (pinned frame first if given)."""
    out: list[tuple[ChatScope, str | None, int]] = [(page, None, 0)]
    if hints.frame:
        out.insert(0, (page.frame_locator(hints.frame).nth(0), hints.frame, 0))
    try:
        n = await page.locator("iframe").count()
    except Exception:
        n = 0
    for i in range(n):
        out.append((page.frame_locator("iframe").nth(i), "iframe", i))
    return out


async def box_of(scope: ChatScope, selector: str, index: int = 0) -> dict | None:
    try:
        b = await scope.locator(selector).nth(index).bounding_box()
        return b and {"x": b["x"], "y": b["y"], "width": b["width"], "height": b["height"]}
    except Exception:
        return None


async def discover(page: Page, hints: ChatHints, greeting: str, timeout_s: float) -> tuple[ChatHandle, str, dict | None]:
    # 1. let dynamic UIs render; 2. open a launcher if the composer is hidden behind one.
    used_launcher = None
    if not await _wait_for_any_input(page, hints.input, min(2.0, timeout_s)):
        launcher = hints.launcher or await _first_visible(page, LAUNCHER_CANDIDATES)
        if launcher:
            try:
                await page.locator(launcher).first.click()
                used_launcher = launcher
            except Exception:
                pass

    last_err = "no chat input found in the page, any iframe, or the shadow DOM"
    for scope, frame_sel, frame_index in await _scopes(page, hints):
        input_sel = await _wait_for_any_input(scope, hints.input, 3.0)
        if not input_sel:
            continue
        send_sel = hints.send or await _first_visible(scope, SEND_CANDIDATES)
        send_mode = hints.send_mode or ("click" if send_sel else "enter")
        if send_mode == "enter":
            send_sel = None
        assistant_cands = [hints.assistant_message] if hints.assistant_message else ASSISTANT_CANDIDATES
        try:
            handle, reply, box = await _verify(scope, input_sel, send_sel, send_mode, frame_sel, frame_index, assistant_cands, greeting, timeout_s)
            handle.launcher_sel = used_launcher
            return handle, reply, box
        except ChatError as e:
            last_err = str(e)
            continue
    raise ChatError(last_err)


async def _verify(scope, input_sel, send_sel, send_mode, frame_sel, frame_index, assistant_cands, greeting, timeout_s):
    before = {}
    for s in assistant_cands:
        try:
            before[s] = await scope.locator(s).count()
        except Exception:
            before[s] = 0
    await _send_text(scope, input_sel, send_sel, send_mode, greeting)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for s in assistant_cands:
            try:
                now = await scope.locator(s).count()
            except Exception:
                now = before[s]
            if now > before[s]:
                reply = await _read_stable(scope, s, before[s], deadline)
                if reply.strip():
                    handle = ChatHandle(scope, input_sel, s, send_sel, send_mode, frame_sel, frame_index)
                    box = await box_of(scope, s, before[s])
                    return handle, reply, box
        await _sleep(scope, 150)
    raise ChatError(f"composer '{input_sel}' accepted a greeting but no reply element appeared")


async def _send_text(scope: ChatScope, input_sel: str, send_sel: str | None, send_mode: str, text: str) -> None:
    box = scope.locator(input_sel).first
    await box.fill(text)
    if send_mode == "click" and send_sel:
        await scope.locator(send_sel).first.click()
    else:
        await box.press("Enter")


async def _read_stable(scope: ChatScope, selector: str, index: int, deadline: float, stable_ms: int = 450) -> str:
    """Wait until the reply text stops growing (handles streamed responses)."""
    loc = scope.locator(selector).nth(index)
    prev, stable_since = "", 0.0
    while time.monotonic() < deadline:
        try:
            text = await loc.inner_text()
        except Exception:
            text = prev
        now = time.monotonic()
        if text != prev:
            prev, stable_since = text, now
        elif prev and (now - stable_since) * 1000 >= stable_ms:
            break
        await _sleep(scope, 120)
    return prev


async def attach(page: Page, hints: ChatHints, timeout_s: float) -> ChatHandle:
    """Deterministically reconstruct a handle from fully-pinned hints (the
    Commander already discovered and verified them), without greeting again."""
    if not (hints.input and hints.assistant_message):
        raise ChatError("attach requires pinned input and assistant_message")
    if hints.launcher:
        try:
            await page.locator(hints.launcher).first.click()
        except Exception:
            pass
    scope = build_scope(page, hints.frame, 0)
    if not await _wait_for_any_input(scope, hints.input, timeout_s):
        raise ChatError(f"composer '{hints.input}' did not appear in this context")
    send_mode = hints.send_mode or ("click" if hints.send else "enter")
    send_sel = None if send_mode == "enter" else hints.send
    return ChatHandle(scope, hints.input, hints.assistant_message, send_sel, send_mode, hints.frame, 0)


async def send_message(handle: ChatHandle, text: str, timeout_s: float) -> tuple[str, dict | None]:
    before = await handle.scope.locator(handle.assistant_sel).count()
    await _send_text(handle.scope, handle.input_sel, handle.send_sel, handle.send_mode, text)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if await handle.scope.locator(handle.assistant_sel).count() > before:
            reply = await _read_stable(handle.scope, handle.assistant_sel, before, deadline)
            box = await box_of(handle.scope, handle.assistant_sel, before)
            return reply, box
        await _sleep(handle.scope, 120)
    raise ChatError(f"no reply after sending to '{handle.input_sel}'")
