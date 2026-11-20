import { useEffect, useReducer, useRef, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AutoRedEvent } from "../contracts/events";
import { emptyMission, fromSnapshot, reduce, type MissionState } from "./missionReducer";

type Action = { kind: "reset"; state: MissionState } | { kind: "event"; e: AutoRedEvent };

const reducer = (s: MissionState, a: Action) => (a.kind === "reset" ? a.state : reduce(s, a.e));

/** Snapshot first, then live events from last_seq; no gaps, no duplicates. */
export function useMission(client: AutoRedClient, missionId: string | null) {
  const [state, dispatch] = useReducer(reducer, emptyMission(""));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!missionId) return;
    let stop: (() => void) | undefined, cancelled = false;
    client.mission(missionId).then((snap) => {
      if (cancelled) return;
      const s = fromSnapshot(snap);
      dispatch({ kind: "reset", state: s });
      stop = client.streamEvents(missionId, s.last_seq, (e) => dispatch({ kind: "event", e }));
    }).catch((e) => setError(String(e)));
    return () => { cancelled = true; stop?.(); };
  }, [client, missionId]);
  return { state, error };
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
