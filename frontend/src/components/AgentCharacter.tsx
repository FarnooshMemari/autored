import type { AnimationCue } from "../state/animationCues";

/** Expressive SVG agent character. Color + state drive a friendly, "3D-inspired"
 * look via gradients/shadows and CSS animation — no heavy 3D, keeps it fast and
 * accessible (animation is disabled under prefers-reduced-motion by theme.css). */
const MOOD: Record<AnimationCue, { eyes: string; aura: number; label: string }> = {
  idle: { eyes: "·", aura: 0.25, label: "Idle" },
  thinking: { eyes: "◦", aura: 0.5, label: "Thinking" },
  browsing: { eyes: "•", aura: 0.55, label: "Browsing" },
  typing: { eyes: "•", aura: 0.7, label: "Typing" },
  awaiting: { eyes: "–", aura: 0.8, label: "Awaiting reply" },
  waiting: { eyes: "–", aura: 0.4, label: "Waiting" },
  alarmed: { eyes: "!", aura: 1, label: "Alarmed" },
  confirmed: { eyes: "✓", aura: 1, label: "Confirmed" },
  blocked: { eyes: "✕", aura: 0.3, label: "Blocked" },
  done: { eyes: "◡", aura: 0.3, label: "Done" },
  error: { eyes: "×", aura: 0.4, label: "Error" },
  stopped: { eyes: "–", aura: 0.2, label: "Stopped" },
};

export function AgentCharacter({ color, cue, size = 76, name }:
  { color: string; cue: AnimationCue; size?: number; name?: string }) {
  const m = MOOD[cue] ?? MOOD.idle;
  const busy = ["typing", "awaiting", "browsing", "thinking"].includes(cue);
  return (
    <div className={`char char-${cue}`} style={{ width: size, height: size }} aria-label={`${name ?? "agent"}: ${m.label}`}>
      <div className="char-aura" style={{ background: color, opacity: m.aura }} />
      <svg viewBox="0 0 100 100" width={size} height={size} className={busy ? "char-bob" : ""}>
        <defs>
          <radialGradient id={`g-${color}`} cx="38%" cy="30%" r="80%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity=".55" />
            <stop offset="35%" stopColor={color} />
            <stop offset="100%" stopColor={color} stopOpacity=".65" />
          </radialGradient>
          <filter id="soft"><feGaussianBlur stdDeviation="0.6" /></filter>
        </defs>
        {/* body: rounded dome with a soft wavy base */}
        <path d="M50 10 C72 10 84 28 84 50 L84 78 C84 84 78 84 74 80 C70 76 66 84 62 84 C58 84 54 76 50 84
                 C46 76 42 84 38 84 C34 84 30 76 26 80 C22 84 16 84 16 78 L16 50 C16 28 28 10 50 10 Z"
              fill={`url(#g-${color})`} filter="url(#soft)" />
        {/* visor */}
        <ellipse cx="50" cy="46" rx="26" ry="19" fill="#0b0e14" opacity=".9" />
        {/* eyes */}
        <text x="50" y="52" textAnchor="middle" fontSize="18" fontWeight="800" fill="#fff"
              style={{ filter: `drop-shadow(0 0 6px ${color})` }}>{m.eyes} {m.eyes}</text>
        {/* highlight */}
        <ellipse cx="36" cy="26" rx="9" ry="6" fill="#fff" opacity=".35" />
      </svg>
    </div>
  );
}
