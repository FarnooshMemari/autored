"""Globex: chat widget mounted in an IFRAME behind a launcher button, with a
contenteditable composer, an icon send button (aria-label), and word-by-word
STREAMING replies. Structurally unlike AcmeHelp on purpose.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..common.assistant import State
from ..common.backend import attach_backend

HOST = """<!doctype html><html><head><title>Globex</title></head><body>
<h1>Globex Logistics</h1><p>Signed in as <span id="who">{who}</span></p>
<button id="chat-launcher" aria-label="Open support chat"
        style="position:fixed;right:16px;bottom:16px">Chat with us</button>
<script>
document.getElementById('chat-launcher').onclick = () => {
  if (document.getElementById('widget')) return;
  const f = document.createElement('iframe');
  f.id = 'widget'; f.src = '/widget'; f.title = 'Support chat';
  f.style = 'position:fixed;right:16px;bottom:64px;width:360px;height:460px;border:1px solid #888';
  document.body.appendChild(f);
};
</script></body></html>"""

WIDGET = """<!doctype html><html><head><title>Support</title></head><body>
<div id="log" data-state="idle" aria-live="polite"></div>
<div id="composer" contenteditable="true" role="textbox" aria-label="Message"></div>
<button id="send" aria-label="Send message">&#10148;</button>
<script>
const log=document.getElementById('log'), box=document.getElementById('composer');
function bubble(cls){const d=document.createElement('div');d.className='bubble '+cls;log.appendChild(d);return d;}
async function send(){
  const text=box.innerText.trim(); if(!text) return; box.innerText='';
  bubble('user').textContent=text; log.dataset.state='busy';
  const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
  const j=await r.json(); const out=bubble('assistant'); const words=(j.reply||('Error '+r.status)).split(' ');
  let i=0; const t=setInterval(()=>{ out.textContent += (i?' ':'')+words[i++];
    if(i>=words.length){clearInterval(t); log.dataset.state='idle';} }, 40);  // streamed
}
document.getElementById('send').onclick=send;
</script></body></html>"""


def create_app(mode: str | None = None, latency: tuple[float, float] = (0.15, 0.4)) -> FastAPI:
    mode = mode or os.environ.get("TARGET_MODE", "vulnerable")
    state = State()
    app = FastAPI(title="Globex widget target")
    user_of = attach_backend(app, state, mode, latency)

    @app.get("/", response_class=HTMLResponse)
    async def home(req: Request):
        who = user_of(req)
        return RedirectResponse("/login", 303) if not who else HOST.replace("{who}", who)

    @app.get("/widget", response_class=HTMLResponse)
    async def widget(req: Request):
        if not user_of(req):
            return HTMLResponse("<p>sign in first</p>", status_code=401)
        return WIDGET

    return app


app = create_app()
