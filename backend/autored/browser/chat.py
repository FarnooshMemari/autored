"""Driving a website's chat assistant through the real UI."""
from __future__ import annotations

import time

from pydantic import BaseModel

from ..events.schema import BrowserActionPayload
from ..safety.scope import Account, ChatHints, LoginConfig, Target
from .runtime import AgentBrowser

INPUT_CANDIDATES = ["textarea", "input[type=text]:not([name*=user]):not([id*=user])", "[contenteditable=true]"]
SEND_CANDIDATES = ['button:has-text("Send")', "#send", "button[type=submit]", '[aria-label*="send" i]']
ASSISTANT_CANDIDATES = [".msg.assistant", '[data-role="assistant"]', '[class*="assistant"]', '[class*="bot"]']


class ChatSelectors(BaseModel):
    input: str
    send: str
    assistant_message: str


class ChatError(Exception):
    pass


class ChatSession:
    def __init__(self, browser: AgentBrowser, target: Target):
        self.b, self.target = browser, target
        self.selectors: ChatSelectors | None = None

    async def login(self, account: Account, cfg: LoginConfig | None) -> None:
        if cfg is None:
            return
        await self.b.goto(self.target.url(cfg.path))
        await self.b.fill(cfg.username_selector, account.username)
        await self.b.fill(cfg.password_selector, account.password, secret=True)
        await self.b.click(cfg.submit_selector)
        await self.b.page.wait_for_load_state("domcontentloaded")
        if cfg.path in self.b.page.url:
            raise ChatError(f"login failed for test account {account.username}")

    async def open(self) -> None:
        if self.target.chat.path not in self.b.page.url:
            await self.b.goto(self.target.url(self.target.chat.path))

    async def _first_visible(self, candidates: list[str]) -> str | None:
        for sel in candidates:
            loc = self.b.page.locator(sel)
            if await loc.count() > 0 and await loc.first.is_visible():
                return sel
        return None

    async def discover(self, hints: ChatHints, greeting: str, timeout_s: float) -> tuple[ChatSelectors, str]:
        """Find the chat input/send/reply elements, then prove them by sending
        a real greeting and seeing which reply element appeared."""
        inp = hints.input or await self._first_visible(INPUT_CANDIDATES)
        send = hints.send or await self._first_visible(SEND_CANDIDATES)
        if not inp or not send:
            raise ChatError("no chat assistant UI found on the chat page")
        cands = [hints.assistant_message] if hints.assistant_message else ASSISTANT_CANDIDATES
        before = {s: await self.b.page.locator(s).count() for s in cands}
        await self.b.fill(inp, greeting)
        await self.b.click(send)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for s in cands:
                if await self.b.page.locator(s).count() > before[s]:
                    self.selectors = ChatSelectors(input=inp, send=send, assistant_message=s)
                    text = await self.b.page.locator(s).nth(before[s]).inner_text()
                    return self.selectors, text
            await self.b.page.wait_for_timeout(150)
        raise ChatError("sent a greeting but no assistant reply element appeared")

    async def send(self, text: str, timeout_s: float) -> tuple[str, int]:
        if self.selectors is None:
            raise ChatError("chat selectors not set")
        s = self.selectors
        n = await self.b.page.locator(s.assistant_message).count()
        t0 = time.monotonic()
        await self.b.fill(s.input, text)
        await self.b.click(s.send)
        self.b.emit("browser.action", BrowserActionPayload(action="wait", selector=s.assistant_message))
        await self.b.page.wait_for_function(
            "([sel, n]) => document.querySelectorAll(sel).length > n", arg=[s.assistant_message, n],
            timeout=timeout_s * 1000)
        reply = await self.b.page.locator(s.assistant_message).nth(n).inner_text()
        return reply, int((time.monotonic() - t0) * 1000)

    async def fetch_json(self, path: str):
        """Same-origin GET using this agent's isolated cookies (oracle reads)."""
        url = self.target.url(path)
        if not self.b.guard.is_allowed(url):
            raise PermissionError(url)
        resp = await self.b.context.request.get(url)
        return await resp.json() if resp.ok else None
