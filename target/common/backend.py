"""Shared HTTP backend (login form, chat API, audit oracle) for the
generalization targets. Each target supplies only its own chat-page HTML and
any widget assets, so the DOM/transport differs while the evaluable behavior
stays identical.
"""
from __future__ import annotations

import asyncio
import os
import random
import secrets

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .assistant import USERS, State, assistant_reply


def attach_backend(app: FastAPI, state: State, mode: str, latency: tuple[float, float]):
    hardened = mode == "hardened"

    def user_of(req: Request) -> str | None:
        return state.sessions.get(req.cookies.get("session", ""))

    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        return """<!doctype html><html><head><title>Sign in</title></head><body>
<h1>Sign in</h1><form method="post" action="/login">
<input id="username" name="username" placeholder="Username">
<input id="password" name="password" type="password" placeholder="Password">
<button id="login-submit" type="submit">Sign in</button></form></body></html>"""

    @app.post("/login")
    async def login(username: str = Form(...), password: str = Form(...)):
        if USERS.get(username, (None,))[0] != password:
            return HTMLResponse("<p>Invalid login <a href='/login'>retry</a></p>", status_code=401)
        token = secrets.token_urlsafe(16)
        state.sessions[token] = username
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", token, httponly=True, samesite="lax")
        return resp

    @app.post("/api/chat")
    async def chat(req: Request):
        who = user_of(req)
        if not who:
            raise HTTPException(401, "not signed in")
        body = await req.json()
        msg = str(body.get("message", ""))[:2000]
        await asyncio.sleep(random.uniform(*latency))
        return {"reply": assistant_reply(state, who, msg, hardened)}

    @app.get("/__test__/audit")
    async def audit(req: Request):
        who = user_of(req)
        if not who:
            raise HTTPException(401, "not signed in")
        with state.lock:
            return JSONResponse([a for a in state.audit if a["user"] == who])

    app.state.brain = state
    app.state.mode = mode
    return user_of
