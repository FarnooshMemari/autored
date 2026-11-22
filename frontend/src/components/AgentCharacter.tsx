import type { AnimationCue } from "../state/animationCues";
import type { AgentId } from "../contracts/events";

/** Five role-distinct, expressive agent characters. Each has its OWN silhouette,
 * visor and emblem (readable apart even in one colour) plus drawn eyes that take
 * a real facial expression from the live cue — thinking, working, alarmed,
 * confirmed, blocked. Pure CSS/SVG; all motion disabled under
 * prefers-reduced-motion (theme.css). */

type Mood = "calm" | "focus" | "think" | "await" | "wide" | "happy" | "x";
const CUE_MOOD: Record<AnimationCue, Mood> = {
  idle: "calm", thinking: "think", browsing: "focus", typing: "focus",
  awaiting: "await", waiting: "await", alarmed: "wide", confirmed: "happy",
  blocked: "x", done: "happy", error: "x", stopped: "await",
};
const AURA: Record<AnimationCue, number> = {
  idle: .18, thinking: .5, browsing: .58, typing: .72, awaiting: .82, waiting: .38,
  alarmed: 1, confirmed: 1, blocked: .3, done: .32, error: .4, stopped: .2,
};
const LABEL: Record<AnimationCue, string> = {
  idle: "Idle", thinking: "Thinking", browsing: "Investigating", typing: "Working",
  awaiting: "Awaiting reply", waiting: "Waiting", alarmed: "Alarmed", confirmed: "Confirmed",
  blocked: "Blocked", done: "Done", error: "Error", stopped: "Stopped",
};

/** Expressive eye pair, positioned per character, shaped by mood. */
function Eyes({ cx, cy, gap, s, color, mood }:
  { cx: number; cy: number; gap: number; s: number; color: string; mood: Mood }) {
  const dark = "#0a0d14";
  const eye = (ex: number, key: string) => {
    if (mood === "happy")
      return <path key={key} d={`M${ex - 2.7 * s} ${cy + 0.8 * s} Q${ex} ${cy - 2.9 * s} ${ex + 2.7 * s} ${cy + 0.8 * s}`}
        stroke="#fff" strokeWidth={1.7 * s} fill="none" strokeLinecap="round" />;
    if (mood === "x")
      return <g key={key} stroke="#fff" strokeWidth={1.6 * s} strokeLinecap="round">
        <path d={`M${ex - 2.1 * s} ${cy - 2.1 * s} L${ex + 2.1 * s} ${cy + 2.1 * s}`} />
        <path d={`M${ex + 2.1 * s} ${cy - 2.1 * s} L${ex - 2.1 * s} ${cy + 2.1 * s}`} /></g>;
    if (mood === "await")
      return <rect key={key} x={ex - 2.6 * s} y={cy - 0.6 * s} width={5.2 * s} height={1.5 * s} rx={0.75 * s} fill="#fff" />;
    const ry = mood === "wide" ? 3.3 : mood === "think" ? 1.7 : mood === "focus" ? 2.8 : 2.5;
    const py = mood === "think" ? -1 * s : 0;
    return <g key={key}>
      <ellipse cx={ex} cy={cy} rx={2.2 * s} ry={ry * s} fill="#fff" />
      <circle cx={ex} cy={cy + py} r={1.15 * s} fill={dark} />
      <circle cx={ex - 0.65 * s} cy={cy - 0.8 * s + py} r={0.45 * s} fill="#fff" />
    </g>;
  };
  const glow = (mood === "wide" || mood === "x") ? `drop-shadow(0 0 3px ${color})` : undefined;
  return <g style={{ filter: glow }}>{eye(cx - gap, "l")}{eye(cx + gap, "r")}</g>;
}

const EYE: Record<string, { cx: number; cy: number; gap: number; s: number }> = {
  commander: { cx: 50, cy: 57, gap: 8, s: 1.3 },
  injection: { cx: 50, cy: 62, gap: 6.5, s: 1.05 },
  leakage: { cx: 50, cy: 59, gap: 7, s: 1.1 },
  hierarchy: { cx: 50, cy: 41, gap: 7, s: 1.1 },
  tools: { cx: 50, cy: 48, gap: 7, s: 1.15 },
};

/** Body + visor + role emblem only; eyes are drawn on top by the component. */
const SHAPES: Record<string, (a: { color: string; gid: string }) => JSX.Element> = {
  commander: ({ color, gid }) => (
    <g>
      <path d="M34 24 L39 11 L46 20 L50 8 L54 20 L61 11 L66 24 Z" fill={color} stroke={color} strokeWidth="1.5" strokeLinejoin="round" opacity=".95" />
      <circle cx="39" cy="11" r="2.4" fill="#fff" opacity=".9" /><circle cx="50" cy="8" r="2.9" fill="#fff" /><circle cx="61" cy="11" r="2.4" fill="#fff" opacity=".9" />
      <path d="M50 22 L78 37 L78 67 Q78 72 73 75 L54 86 Q50 88 46 86 L27 75 Q22 72 22 67 L22 37 Z"
            fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".55" strokeWidth="1.2" />
      <path d="M50 22 L78 37 L78 50 Q78 38 50 34 Q22 38 22 50 L22 37 Z" fill={`url(#rim-${gid})`} />
      <rect x="29" y="46" width="42" height="22" rx="11" fill="#070a10" opacity=".95" />
      <rect x="29" y="46" width="42" height="22" rx="11" fill="none" stroke={color} strokeOpacity=".45" strokeWidth="1" />
      <g fill={color} opacity=".9"><circle cx="43" cy="74" r="1.7" /><circle cx="50" cy="74" r="1.7" /><circle cx="57" cy="74" r="1.7" /></g>
    </g>
  ),
  injection: ({ color, gid }) => (
    <g>
      <path d="M50 6 C53 18 56 26 61 36 C68 49 72 58 72 69 C72 81 62 90 50 90 C38 90 28 81 28 69 C28 58 32 49 39 36 C44 26 47 18 50 6 Z"
            fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".55" strokeWidth="1.2" />
      <path d="M50 6 C53 18 56 26 61 36 C64 42 66 46 67 51 C60 44 56 42 50 42 C44 42 40 44 33 51 C34 46 36 42 39 36 C44 26 47 18 50 6 Z" fill={`url(#rim-${gid})`} />
      <path d="M50 46 L67 62 L50 80 L33 62 Z" fill="#070a10" opacity=".95" />
      <path d="M50 46 L67 62 L50 80 L33 62 Z" fill="none" stroke={color} strokeOpacity=".5" strokeWidth="1" />
      <path d="M50 9 L52 23 L48 23 Z" fill="#fff" opacity=".6" />
    </g>
  ),
  leakage: ({ color, gid }) => (
    <g>
      <path d="M28 30 Q28 16 42 16 L58 16 Q72 16 72 30 L72 72 Q72 86 58 86 L42 86 Q28 86 28 72 Z"
            fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".55" strokeWidth="1.2" />
      <path d="M28 30 Q28 16 42 16 L58 16 Q72 16 72 30 L72 44 Q72 32 50 32 Q28 32 28 44 Z" fill={`url(#rim-${gid})`} />
      <circle cx="50" cy="54" r="23" fill="#070a10" opacity=".95" />
      <circle cx="50" cy="54" r="23" fill="none" stroke={color} strokeOpacity=".4" strokeWidth="1" />
      <circle cx="50" cy="54" r="23" fill="none" stroke={color} strokeOpacity=".5" strokeWidth="1.6" strokeDasharray="2 5" />
      <g fill={color} opacity=".9"><circle cx="50" cy="40" r="3.3" /><path d="M48.2 43 L51.8 43 L52.6 49 L47.4 49 Z" /></g>
    </g>
  ),
  hierarchy: ({ color, gid }) => (
    <g>
      <path d="M38 18 Q38 11 50 11 Q62 11 62 18 L67 42 L73 64 L79 86 Q65 88 50 88 Q35 88 21 86 L27 64 L33 42 Z"
            fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".55" strokeWidth="1.2" />
      <path d="M38 18 Q38 11 50 11 Q62 11 62 18 L65 32 Q50 28 35 32 Z" fill={`url(#rim-${gid})`} />
      <g stroke={color} strokeOpacity=".4" strokeWidth="1.4"><path d="M32 56 L68 56" /><path d="M26 73 L74 73" /></g>
      <ellipse cx="50" cy="40" rx="19" ry="16" fill="#070a10" opacity=".95" />
      <ellipse cx="50" cy="40" rx="19" ry="16" fill="none" stroke={color} strokeOpacity=".42" strokeWidth="1" />
      <g fill={color} opacity=".82"><rect x="42" y="79" width="16" height="2.4" rx="1" /><rect x="45" y="83" width="10" height="2.2" rx="1" /></g>
    </g>
  ),
  tools: ({ color, gid }) => (
    <g>
      <path d="M24 22 Q50 13 76 22 L76 48 Q76 72 50 90 Q24 72 24 48 Z"
            fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".55" strokeWidth="1.2" />
      <path d="M24 22 Q50 13 76 22 L76 40 Q50 32 24 40 Z" fill={`url(#rim-${gid})`} />
      <path d="M33 29 Q50 23 67 29 L67 49 Q67 65 50 78 Q33 65 33 49 Z" fill="#070a10" opacity=".93" />
      <path d="M33 29 Q50 23 67 29 L67 49 Q67 65 50 78 Q33 65 33 49 Z" fill="none" stroke={color} strokeOpacity=".42" strokeWidth="1" />
      <path d="M50 64 Q44 60 44 54 M50 64 Q56 60 56 54" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" opacity=".5" />
    </g>
  ),
};

export function AgentCharacter({ color, cue, size = 76, name, agentId }:
  { color: string; cue: AnimationCue; size?: number; name?: string; agentId?: AgentId }) {
  const busy = ["typing", "awaiting", "browsing", "thinking"].includes(cue);
  const gid = (agentId ?? color).replace(/[^a-z0-9]/gi, "");
  const key = agentId && SHAPES[agentId] ? agentId : "commander";
  const shape = SHAPES[key]; const ec = EYE[key];
  return (
    <div className={`char char-${cue}`} style={{ width: size, height: size }} aria-label={`${name ?? "agent"}: ${LABEL[cue]}`}>
      <div className="char-ring" style={{ color }} />
      <div className="char-aura" style={{ background: color, opacity: AURA[cue] }} />
      <div className="char-shadow" />
      <svg viewBox="0 0 100 100" width={size} height={size} className={busy ? "char-bob" : ""}>
        <defs>
          <radialGradient id={`body-${gid}`} cx="38%" cy="24%" r="92%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity=".58" />
            <stop offset="34%" stopColor={color} />
            <stop offset="100%" stopColor={color} stopOpacity=".48" />
          </radialGradient>
          <linearGradient id={`rim-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity=".55" /><stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {shape({ color, gid })}
        <Eyes {...ec} color={color} mood={CUE_MOOD[cue]} />
      </svg>
    </div>
  );
}
