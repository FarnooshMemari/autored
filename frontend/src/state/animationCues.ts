/**
 * Semantic animation intents. The visualization team maps these to
 * character animations; the backend never sends visual instructions.
 */
import type { AgentStatus } from "../contracts/events";

export type AnimationCue =
  | "idle" | "thinking" | "browsing" | "typing" | "awaiting" | "waiting"
  | "alarmed" | "confirmed" | "blocked" | "done" | "error" | "stopped";

export function cueFor(status: AgentStatus): AnimationCue {
  switch (status) {
    case "idle": return "idle";
    case "discovering": case "planning": case "monitoring": return "thinking";
    case "starting": case "authenticating": case "navigating": return "browsing";
    case "testing": case "validating": return "awaiting";
    case "waiting": return "waiting";
    case "done": return "done";
    case "error": return "error";
    case "stopped": return "stopped";
  }
}
