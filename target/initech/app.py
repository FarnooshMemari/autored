"""Initech: chat implemented as a SHADOW-DOM web component (<support-bot>) with
a textarea, ENTER-to-send (no visible send button needed), and an async
'typing…' indicator before each reply. Structurally unlike AcmeHelp and Globex.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..common.assistant import State
from ..common.backend import attach_backend

PAGE = """<!doctype html><html><head><title>Initech</title></head><body>
<h1>Initech Helpdesk</h1><p>Signed in as <span id="who">{who}</span></p>
<support-bot></support-bot>
<script>
class SupportBot extends HTMLElement {
  connectedCallback(){
    const s=this.attachShadow({mode:'open'});
    s.innerHTML=`<style>.msg{margin:4px 0}.typing{display:none;color:#888}</style>
      <div class="thread" aria-live="polite"></div>
      <div class="typing">assistant is typing…</div>
      <textarea class="composer" aria-label="Ask a question" rows="2"></textarea>
      <button class="send">Send</button>`;
    const thread=s.querySelector('.thread'), ta=s.querySelector('.composer'), typing=s.querySelector('.typing');
    const add=(cls,txt)=>{const d=document.createElement('div');d.className='msg '+cls;d.textContent=txt;thread.appendChild(d);};
    const send=async()=>{
      const text=ta.value.trim(); if(!text) return; ta.value=''; add('user',text);
      typing.style.display='block';                                   // async indicator
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
      const j=await r.json();
      setTimeout(()=>{ typing.style.display='none'; add('assistant', j.reply||('Error '+r.status)); }, 350);
    };
    s.querySelector('.send').onclick=send;
    ta.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} });  // Enter-to-send
  }
}
customElements.define('support-bot', SupportBot);
</script></body></html>"""


def create_app(mode: str | None = None, latency: tuple[float, float] = (0.1, 0.3)) -> FastAPI:
    mode = mode or os.environ.get("TARGET_MODE", "vulnerable")
    state = State()
    app = FastAPI(title="Initech shadow-DOM target")
    user_of = attach_backend(app, state, mode, latency)

    @app.get("/", response_class=HTMLResponse)
    async def home(req: Request):
        who = user_of(req)
        return RedirectResponse("/login", 303) if not who else PAGE.replace("{who}", who)

    return app


app = create_app()
