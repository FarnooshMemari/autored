# Recovery & continuation (compliant)

Investigated: officially supported Claude Code mechanisms for resuming work across
sessions, background execution, and scheduled continuation — and what is safe to
automate without bypassing usage limits or creating an uncontrolled retry loop.

## What exists and is used here
- **Durable checkpoint:** [`AUTONOMOUS_PROGRESS.md`](../AUTONOMOUS_PROGRESS.md) records
  the current milestone, completed/pending work, known failures, last successful commit,
  and the *exact next action*. A fresh session reads it and continues.
- **Git is the recovery substrate:** every verified increment is committed and pushed,
  so the last good state is always `git log`/CI. Nothing in-flight is lost.
- **Idempotency guard for experiments:** `scripts/experiment_guard.py` records which
  experiments have completed (by name + input hash) so a resumed run does not repeat a
  finished experiment or a destructive step.
- **Session resume:** Claude Code supports resuming a prior session (`claude --continue`
  / `claude --resume`) and running tasks in the background; scheduled *cloud routines*
  (cron) can re-invoke a prompt on a schedule.

## What is deliberately NOT automated
A supervisor that **auto-restarts across a usage limit** would either poll/retry against
the provider (an uncontrolled retry loop) or attempt to bypass a quota — both are
explicitly out of bounds. So resumption is **operator-triggered**, not a background loop
that games limits.

## The one manual action to resume after an interruption / usage limit
When usage is available again, start a session and say **"continue from
AUTONOMOUS_PROGRESS.md"** (or `claude --continue`). The model reads the checkpoint,
runs `scripts/experiment_guard.py --status` to see what already finished, and proceeds
from *Exact next action* without repeating completed work.

This is the most reliable compliant recovery available: durable state + git + an
idempotency guard + an explicit, auditable resume trigger. It has been exercised across
the multiple sessions that built M1–M6.
