# Event & API contract (for the visualization team)

Canonical: `contracts/events.schema.json` (generated). TypeScript: `frontend/src/contracts/events.ts`.
Schema version: **2** (`v` on every event).

## Envelope

```json
{ "v": 1, "id": "hex", "seq": 42, "mission_id": "M-20261119-...", "agent_id": "leakage",
  "ts": "2026-11-19T23:48:03.7Z", "type": "test.verdict", "payload": { ... } }
```

`agent_id` ∈ `commander | injection | leakage | hierarchy | tools` (stable; slot 0..4 via `GET /api/agents`).
`seq` is per mission, starts at 1, strictly increasing, gap-free.

## Event types

| type | emitted by | payload (key fields) | typical UI use |
|---|---|---|---|
| `mission.status` | commander | `phase`, `message` | phase banner |
| `mission.completed` | commander | `phase` (completed/aborted/failed), counts, `reason` | end screen |
| `agent.status` | any | `status`, `activity`, `task_id` | character state + caption |
| `task.assigned` | commander | `to_agent`, `kind` (assess/validate), `probe_ids`, `reason` | commander → agent hand-off animation |
| `task.completed` | specialist | `task_id`, `outcome`, `detail` | |
| `commander.capabilities` | commander | `tools`, `selectors`, `raw_response` | discovery reveal |
| `commander.plan` | commander | `assignments`, `skipped{probe: reason}` | plan board |
| `browser.navigated` | any | `url`, `context_id`, `viewport` {w,h} | address bar; viewport for overlays |
| `browser.action` | any | `action`, `selector`, `value_preview`, `frame`, `box` {x,y,w,h} | typing/clicking motion; `box` follows the element |
| `browser.blocked` | any | `url`, `reason` | safety indicator |
| `test.started` | specialist | `probe_id`, `prompt`, `attempt` | speech bubble (outgoing) |
| `test.response` | specialist | `response`, `latency_ms`, `box` {x,y,w,h} | speech bubble anchored to the reply |
| `test.verdict` | specialist/commander | `verdict` (see 5 states below), `rationale` | reaction |
| `finding.candidate` | specialist | full finding, `status: candidate` | alert |
| `finding.updated` | specialist | full finding, `status: confirmed/inconclusive`, `reproductions/attempts` | confirmation |
| `log` | any | `level`, `message` | debug console |

`attempt` > 1 means a validation replay in a fresh browser context.

### Five evaluation states (`test.verdict.verdict` / `finding.status`)

| verdict | finding status after validation | meaning |
|---|---|---|
| `vulnerable` | `confirmed` (reproduced) / `suspected` (flaky) | strong evidence: a seeded synthetic canary in the reply, or an audit-oracle record |
| `suspected` | `suspected` | the model *claims* something, but no strong evidence — never counted as confirmed |
| `not_observed` | — (passed) | tested cleanly; the weakness was not observed |
| `inconclusive` | `inconclusive` | could not be evaluated reliably (e.g. audit oracle unavailable) |
| `not_applicable` | — | probe not runnable on this target (tool absent/unauthorized); emitted for skipped probes |

`mission.completed` carries tallies: `confirmed`, `suspected`, `inconclusive`,
`passed`, `not_applicable`, `probes_run`.

### Discovered chat config (`commander.capabilities.selectors`)
`{input, send, send_mode ("click"|"enter"), assistant_message, frame}` — the
interface AutoRed found (iframe, shadow DOM, launcher) with no target-specific code.

### Coordinates for overlay animations
`browser.navigated.viewport` gives the page size; `browser.action.box` and
`test.response.box` give element bounding boxes in page coordinates, so animated
characters can be positioned over the real composer and reply elements.

## Animation hooks

`state/missionReducer.ts` derives `agent.cue` ∈ `idle thinking browsing typing awaiting waiting alarmed confirmed blocked done error stopped`.
Map cues to animations; don't parse activity strings.

## Endpoints

| | |
|---|---|
| `GET /api/health` | `{ok, schema_version, emergency_stop}` |
| `GET /api/agents` | agent manifest with stable slots |
| `GET /api/targets` | allowlisted targets + authorization records |
| `POST /api/missions` | `{target_id, operator, authorization_acknowledged, agents?}` → 201 snapshot, 409 + `detail` if rejected |
| `GET /api/missions[/{id}]` | list / snapshot (`last_seq` included) |
| `GET /api/missions/{id}/events?since=N` | event backlog |
| `GET /api/missions/{id}/findings` | findings |
| `GET /api/missions/{id}/artifacts/{name}.png` | evidence screenshots |
| `GET /api/missions/{id}/agents/{agent}/frame.jpg` | latest frame (polling fallback) |
| `POST /api/missions/{id}/stop`, `POST /api/emergency-stop[/reset]` | stop controls |
| `WS /ws/missions/{id}?since=N` | JSON events after `seq N`, then live; server closes 1000 when the mission ends |
| `WS /ws/missions/{id}/agents/{agent}/frames` | binary JPEG frames (latest-wins) |

Auth (if `AUTORED_API_TOKEN` set): `Authorization: Bearer …` for REST, `?token=` for WS.

**Client recipe:** GET snapshot → `fromSnapshot()` → open WS with `since=last_seq` → `reduce()` each event.
On disconnect, reconnect with the last seen `seq` (`AutoRedClient.streamEvents` does this).

## Plugging in custom visuals

```tsx
<AutoRedUIProvider components={{ Commander: MyCommander, Specialist: MyAgent, BrowserView: MyBrowser,
                                 Timeline: MyTimeline, Findings: MyFindings }}>
```
Prop types: `frontend/src/integration/slots.tsx`. Colors: `var(--autored-agent-<id>)`.
