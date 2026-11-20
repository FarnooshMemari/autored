"""Generalization: the SAME discovery + orchestration core must assess
structurally different chat UIs with no target-specific orchestration changes.

  * Globex  — chat widget inside an IFRAME, opened by a launcher button,
              contenteditable composer, icon send button, STREAMING replies.
  * Initech — chat as a SHADOW-DOM web component, textarea, Enter-to-send,
              async 'typing…' indicator.

Only the scope file differs between targets; no code path here names a target.
AcmeHelp's vulnerable/hardened runs remain the regression tests (test_e2e.py).
"""
from __future__ import annotations

import asyncio

import pytest

from autored.browser.runtime import BrowserRuntime, FrameHub
from autored.events.schema import FindingStatus, MissionPhase, Verdict
from autored.missions.manager import MissionManager
from conftest import requires_browser

pytestmark = [pytest.mark.e2e, requires_browser]

CONFIRMABLE = {"PI-001", "PI-002", "DL-001", "DL-002", "IH-001", "TP-001"}


@pytest.fixture
async def runtime():
    rt = BrowserRuntime(headless=True)
    yield rt
    await rt.close()


async def _run(scopes_for, srv, runtime, tmp_path):
    mgr = MissionManager(scopes_for(srv.url, scope_id=srv.scope_id), runtime, FrameHub(), tmp_path)
    m = mgr.create(srv.scope_id, "pytest", True)
    await asyncio.wait_for(m.task, 150)
    return m


def _assert_generalized(m, expect_frame: bool):
    s = m.snapshot
    assert s.phase == MissionPhase.completed, s.summary
    # discovery worked on a non-AcmeHelp layout
    assert s.capabilities.assistant_detected
    assert set(s.capabilities.tools) == {"lookup_order", "search_kb", "issue_refund"}
    in_frame = s.capabilities.selectors["frame"] != "(main document)"
    assert in_frame is expect_frame, s.capabilities.selectors
    # same evidence-based outcomes as AcmeHelp, reached through a different UI
    confirmed = {f.probe_id for f in s.findings.values() if f.status == FindingStatus.confirmed}
    assert confirmed == CONFIRMABLE, confirmed
    for f in s.findings.values():
        if f.status == FindingStatus.confirmed:
            assert f.reproductions >= 2 and any(e.kind in ("canary", "oracle") for e in f.evidence)
    # each specialist drove its OWN isolated context
    ctxs = [a.context_id for a in s.agents.values() if a.context_id]
    assert len(ctxs) == len(set(ctxs))
    # viz fields present: viewport on navigation, bounding boxes on replies
    evs = m.ctx.log.events
    assert any(e.type == "browser.navigated" and e.payload.get("viewport") for e in evs)
    assert any(e.type == "test.response" and e.payload.get("box") for e in evs)


async def test_globex_iframe_widget(globex_target, scopes_for, runtime, tmp_path):
    m = await _run(scopes_for, globex_target, runtime, tmp_path)
    _assert_generalized(m, expect_frame=True)


async def test_initech_shadow_dom(initech_target, scopes_for, runtime, tmp_path):
    m = await _run(scopes_for, initech_target, runtime, tmp_path)
    _assert_generalized(m, expect_frame=False)
    # Initech's composer is inside an open shadow root; discovery still found it
    assert m.snapshot.capabilities.selectors["input"].startswith("textarea")


async def test_five_state_reporting(globex_target, scopes_for, runtime, tmp_path):
    """A full run exercises every evaluation state the UI must distinguish."""
    m = await _run(scopes_for, globex_target, runtime, tmp_path)
    verdicts = {e.payload["probe_id"]: e.payload["verdict"] for e in m.ctx.log.events
                if e.type == "test.verdict" and e.payload["attempt"] == 1}
    assert verdicts["PI-001"] == Verdict.vulnerable.value       # strong evidence
    assert verdicts["PI-003"] == Verdict.not_observed.value     # passed
    assert verdicts["TP-002"] == Verdict.not_applicable.value   # tool not authorized -> skipped
    sm = m.snapshot.summary
    assert sm.confirmed == 6 and sm.passed >= 1 and sm.not_applicable >= 1
