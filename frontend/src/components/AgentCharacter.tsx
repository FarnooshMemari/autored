import type { AnimationCue } from "../state/animationCues";
import type { AgentId } from "../contracts/events";

/** Expressive, role-distinct SVG agent character. Color + per-agent emblem give
 * each a unique identity; cue drives eyes/aura/animation. Performant (CSS/SVG),
 * accessible (animation disabled under prefers-reduced-motion in theme.css). */
const MOOD: Record<AnimationCue, { eyes: string; aura: number; label: string }> = {
  idle: { eyes: "· ·", aura: 0.22, label: "Idle" },
  thinking: { eyes: "◦ ◦", aura: 0.5, label: "Thinking" },
  browsing: { eyes: "• •", aura: 0.55, label: "Browsing" },
  typing: { eyes: "• •", aura: 0.7, label: "Typing" },
  awaiting: { eyes: "– –", aura: 0.82, label: "Awaiting reply" },
  waiting: { eyes: "– –", aura: 0.4, label: "Waiting" },
  alarmed: { eyes: "! !", aura: 1, label: "Alarmed" },
  confirmed: { eyes: "✓ ✓", aura: 1, label: "Confirmed" },
  blocked: { eyes: "✕ ✕", aura: 0.3, label: "Blocked" },
  done: { eyes: "◡ ◡", aura: 0.32, label: "Done" },
  error: { eyes: "× ×", aura: 0.4, label: "Error" },
  stopped: { eyes: "– –", aura: 0.2, label: "Stopped" },
};

// a distinctive emblem per agent, drawn in white on the visor
const EMBLEM: Record<string, JSX.Element> = {
  commander: <path d="M42 38 L50 30 L58 38 L54 44 L46 44 Z" fill="#fff" opacity=".9" />,            // crown
  injection: <g fill="#fff" opacity=".9"><rect x="48" y="30" width="4" height="12" rx="1" /><path d="M50 42 l-3 5 h6 Z" /></g>, // needle
  leakage: <g fill="none" stroke="#fff" strokeWidth="2.4" opacity=".9"><circle cx="50" cy="35" r="4.5" /><path d="M50 39 v6" strokeLinecap="round" /></g>, // keyhole
  hierarchy: <g fill="#fff" opacity=".9"><rect x="43" y="31" width="14" height="3" rx="1" /><rect x="45" y="37" width="10" height="3" rx="1" /><rect x="47" y="43" width="6" height="3" rx="1" /></g>, // layers
  tools: <path d="M50 29 l8 3 v6 c0 6 -4 9 -8 11 c-4 -2 -8 -5 -8 -11 v-6 Z" fill="none" stroke="#fff" strokeWidth="2.2" opacity=".9" />, // shield
};

export function AgentCharacter({ color, cue, size = 76, name, agentId }:
  { color: string; cue: AnimationCue; size?: number; name?: string; agentId?: AgentId }) {
  const m = MOOD[cue] ?? MOOD.idle;
  const busy = ["typing", "awaiting", "browsing", "thinking"].includes(cue);
  const gid = (agentId ?? color).replace(/[^a-z0-9]/gi, "");
  return (
    <div className={`char char-${cue}`} style={{ width: size, height: size }} aria-label={`${name ?? "agent"}: ${m.label}`}>
      <div className="char-aura" style={{ background: color, opacity: m.aura }} />
      <div className="char-shadow" />
      <svg viewBox="0 0 100 100" width={size} height={size} className={busy ? "char-bob" : ""}>
        <defs>
          <radialGradient id={`body-${gid}`} cx="36%" cy="26%" r="85%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity=".6" />
            <stop offset="30%" stopColor={color} />
            <stop offset="100%" stopColor={color} stopOpacity=".55" />
          </radialGradient>
          <linearGradient id={`rim-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fff" stopOpacity=".5" /><stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* body: rounded dome with a soft wavy base */}
        <path d="M50 8 C74 8 86 27 86 50 L86 80 C86 86 80 86 76 82 C72 78 68 86 64 86 C60 86 56 78 50 86
                 C44 78 40 86 36 86 C32 86 28 78 24 82 C20 86 14 86 14 80 L14 50 C14 27 26 8 50 8 Z"
              fill={`url(#body-${gid})`} stroke={color} strokeOpacity=".5" strokeWidth="1" />
        <path d="M50 8 C74 8 86 27 86 50 L86 60 C86 40 72 24 50 24 C28 24 14 40 14 60 L14 50 C14 27 26 8 50 8 Z"
              fill={`url(#rim-${gid})`} />
        {/* visor */}
        <ellipse cx="50" cy="50" rx="27" ry="21" fill="#090c12" opacity=".92" />
        <ellipse cx="50" cy="50" rx="27" ry="21" fill="none" stroke={color} strokeOpacity=".35" strokeWidth="1" />
        {/* emblem (role identity) */}
        {agentId && EMBLEM[agentId]}
        {/* eyes */}
        <text x="50" y="62" textAnchor="middle" fontSize="15" fontWeight="800" fill="#fff"
              style={{ filter: `drop-shadow(0 0 7px ${color})`, letterSpacing: "2px" }}>{m.eyes}</text>
        {/* gloss highlight */}
        <ellipse cx="35" cy="24" rx="10" ry="6.5" fill="#fff" opacity=".4" transform="rotate(-18 35 24)" />
      </svg>
    </div>
  );
}
