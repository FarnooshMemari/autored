import { useEffect, useReducer, useRef, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AutoRedEvent } from "../contracts/events";
import { emptyMission, fromSnapshot, reduce, type MissionState } from "./missionReducer";

type Action = { kind: "reset"; state: MissionState } | { kind: "event"; e: AutoRedEvent };

const reducer = (s: MissionState, a: Action) => (a.kind === "reset" ? a.state : reduce(s, a.e));

/** Loads a mission. Live missions stream from last_seq; completed/interrupted
 * ("recorded") missions are rebuilt fully from the persisted event log. */
export function useMission(client: AutoRedClient, missionId: string | null) {
  const [state, dispatch] = useReducer(reducer, emptyMission(""));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!missionId) return;
    let stop: (() => void) | undefined, cancelled = false;
    setLoading(true); setError(null);
    client.mission(missionId).then(async (snap) => {
      if (cancelled) return;
      if (snap.live) {
        const s = fromSnapshot(snap);
        dispatch({ kind: "reset", state: s });
        setLoading(false);
        stop = client.streamEvents(missionId, s.last_seq, (e) => dispatch({ kind: "event", e }));
      } else {
        // recorded: replay the durable event log to rebuild timeline + agent states;
        // if the log is unavailable (store-only mission) fall back to stored findings.
        let s: MissionState;
        try {
          const events = await client.events(missionId);
          s = { ...emptyMission(missionId), target_id: snap.target_id, operator: snap.operator };
          for (const e of events) s = reduce(s, e);
        } catch {
          s = fromSnapshot(snap);
        }
        if (cancelled) return;
        // The backend holds the authoritative phase + summary (the event log of an
        // interrupted mission has no mission.completed, so the replayed phase is stale).
        s.phase = snap.phase;
        s.summary = snap.summary ?? s.summary;
        s.live = false;
        dispatch({ kind: "reset", state: s });
        setLoading(false);
      }
    }).catch((e) => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; stop?.(); };
  }, [client, missionId]);
  return { state, error, loading };
}

/** Latest live browser frame for one agent. */
export function useAgentFrame(client: AutoRedClient, missionId: string | null, agentId: string) {
  const [src, setSrc] = useState<string | null>(null);
  const prev = useRef<string | null>(null);
  useEffect(() => {
    if (!missionId) return;
    const stop = client.streamFrames(missionId, agentId, (url) => {
      if (prev.current) URL.revokeObjectURL(prev.current);
      prev.current = url;
      setSrc(url);
    });
    return () => stop();
  }, [client, missionId, agentId]);
  return src;
}
