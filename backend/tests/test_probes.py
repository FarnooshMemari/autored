from autored.agents.probes import probe_by_id
from autored.safety.scope import Target


def _target(with_locator=True):
    canaries = [
        {"id": "internal_discount", "value": "ACME-INTERNAL-50", "meaning": "x"},
        {"id": "other_customer_email", "value": "dana.synthetic@example.test", "meaning": "x"},
    ]
    rec = {"id": "other_customer_record", "value": "LEAK-CANARY-91C2", "meaning": "x"}
    if with_locator:
        rec["locator"] = "1002"
    canaries.append(rec)
    return Target.model_validate({
        "id": "t", "name": "t", "base_url": "http://127.0.0.1:9/", "allowed_origins": ["http://127.0.0.1:9"],
        "authorization": {"reference": "R", "approved_by": "op", "expires": "2099-01-01"},
        "chat": {"path": "/"}, "canaries": canaries,
        "accounts": {
            "commander": {"username": "commander@acme.test", "password": "x", "owned_orders": ["7000"]},
            "leakage":   {"username": "leakage@acme.test",   "password": "x", "owned_orders": ["7002"]},
        },
    })


def test_cross_account_probe_uses_canary_locator():
    t = _target(with_locator=True)
    rendered = probe_by_id("DL-001").render("abcd", t.accounts["leakage"], t)
    assert "1002" in rendered          # derived from the canary's locator, not a guessed literal
    assert "7002" not in rendered      # never the tester's own order for a cross-account probe


def test_cross_account_falls_back_to_other_account_order_when_no_locator():
    t = _target(with_locator=False)
    rendered = probe_by_id("DL-001").render("abcd", t.accounts["leakage"], t)
    assert "7000" in rendered          # a DIFFERENT synthetic account's order (still scope-derived)
    assert "1002" not in rendered      # old AcmeHelp-specific hardcoded id is gone


def test_other_account_derived_from_canary_email():
    t = _target()
    rendered = probe_by_id("TP-002").render("abcd", t.accounts["leakage"], t)
    assert "dana.synthetic" in rendered
    assert "dana_synthetic" not in rendered   # old hardcoded literal gone


def test_own_order_still_used_for_self_probes():
    t = _target()
    rendered = probe_by_id("TP-001").render("abcd", t.accounts["leakage"], t)
    assert "7002" in rendered          # the tester's own order (refund-as-customer)


def test_no_hardcoded_ids_remain_in_probe_library():
    from autored.agents.probes import ALL_PROBES
    for p in ALL_PROBES:
        blob = p.prompt + "".join(p.turns)
        assert "1002" not in blob and "dana_synthetic" not in blob, f"{p.id} still has a hardcoded id"
