# M3 — Real-World Validation Pilot: plan & status

**Objective:** demonstrate AutoRed on an independently developed AI assistant,
not a target we authored. **A bug-bounty program's existence is never treated as
authorization for automated testing** (confirmed by current program rules:
platforms vary — some cap automated tooling with an identifying header and rate
limit, some prohibit it; AI-chatbot programs separate "program scope" from
"testing scope").

## Status: NOT complete — blocked on verified authorization (reported, not claimed)

- **Built & verified:** a Phase-0 **connectivity harness** (`connectivity-check`
  CLI / `mode="connectivity"`) that discovers a chat UI, sends ONE benign message,
  captures the reply + a screenshot, streams real browser events, and runs **zero
  security probes**. An **authorization gate** (`authorized_methods`) refuses the
  four-agent suite unless `security_probes` is explicitly authorized. RoE traffic
  attribution (`identify_as` → User-Agent / `X-Bug-Bounty`) and assisted login
  (operator completes SSO/MFA; AutoRed never types credentials) are implemented.
  Self-tested mechanically on a synthetic target (harness check, *not* the pilot).
- **Not done:** no third-party production target has been discovered or messaged.
  I did not point automation at Copilot or any external production assistant,
  because the specific automated-testing permission could not be verified here.

## Candidate targets (ranked), with the authorization each needs

### 1. (Recommended) Self-host an independently-developed vulnerable LLM app
Deploy a third-party open-source AI assistant on infrastructure you control:
- **OWASP PromptMe** — intentionally vulnerable LLM app, CTF-style (Apache-2.0).
- **Damn Vulnerable LLM Agent** — LangChain ReAct agent, prompt-injection teaching tool.
- **LLMVault** / **OWASP FinBot CTF** — self-hostable OWASP LLM Top-10 ranges.

Why suitable: *independently developed* (not authored by us), yet you **own the
instance**, so authorization is unambiguous and you may seed canaries + an audit
oracle → findings are **confirmable** to AutoRed's strong-evidence bar. This is
the fastest path to proving AutoRed works on software it did not write.
Need from you: a host + an LLM backend API key for the app (AutoRed itself needs
no key). Then set a scope entry with `authorized_methods: [connectivity, security_probes]`.

### 2. Vendor engagement on an externally-hosted assistant
Written permission + a **test tenant** + **test accounts** + a stated rate cap and
test window. Record as the scope `authorization` block; begin connectivity-only,
enable probes on sign-off.

### 3. Public AI-chatbot bug-bounty program that explicitly permits automated browser testing
Rare. Only if the program's Rules of Engagement state automated testing is allowed
at a given rate, with an identifying header and test accounts. Confirm in writing
with the program first; set `identify_as`, 1 agent, low `requests_per_second`,
and `authorized_methods: [connectivity]` until methods are approved.

### Not suitable now
`copilot.microsoft.com` and arbitrary public assistants: product Terms of Use
typically forbid automated access; current RoE/automation rules are unverifiable
from here; driving a personal account via automation risks that account; and
without a seeded test tenant, any "finding" would be unconfirmable and could touch
real user data.

## Authorization checklist (what unblocks a real run)
- [ ] Written authorization naming the asset, the permitted **methods**, and expiry
- [ ] Documented **rate cap** and whether automated/AI testing is allowed
- [ ] **Test accounts / test tenant** with synthetic data (no real users)
- [ ] Seeded **canaries** or a test-only **audit oracle** (required for `confirmed`)
- [ ] Required **identifying header / contact** for attributable traffic
- [ ] A **stop contact** and test window

## Phased execution (once a candidate is authorized)
- **Phase 0 — connectivity (this is built):** `authorized_methods: [connectivity]`,
  1 agent, low rate. Verify discover → send → receive → streamed events on the real UI.
- **Phase 1 — probes (needs written method sign-off):** add `security_probes`, enable
  the agreed probe subset on the test tenant with seeded evidence. Rate limits,
  concurrency cap, and emergency stop apply throughout.

## Three distinctions, kept explicit in every report
| Distinction | How AutoRed separates them |
|---|---|
| **Planned vs executed** | `commander.plan` lists planned probes; `test.started`/`test.verdict` mark executed ones; skipped → `not_applicable`. Connectivity runs execute **no** probes. |
| **Synthetic vs real-world findings** | Findings carry the target id + authorization reference; only self-hosted/synthetic targets have seeded canaries. This doc records that **no real-world findings exist yet**. |
| **Browser interaction vs confirmed vulnerability** | Connectivity success = discovery + one round-trip (interaction only). A vulnerability is `confirmed` only via seeded canary / audit oracle reproduced in fresh contexts — impossible on a bare production site. |

## How to run Phase 0 against an authorized target
```bash
cp scope/external-target.example.yaml scope/mypilot.local.yaml   # edit; git-ignored
AUTORED_SCOPE=scope/mypilot.local.yaml \
  backend/.venv/bin/python -m autored connectivity-check external-pilot --operator you --i-am-authorized
```
This performs discovery + one benign message only. It cannot run security probes
unless the scope's `authorized_methods` includes `security_probes`.
