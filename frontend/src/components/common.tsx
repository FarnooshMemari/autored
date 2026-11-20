import type { ReactNode } from "react";

export const Pill = ({ children, color, className = "" }: { children: ReactNode; color?: string; className?: string }) => (
  <span className={`pill ${className}`} style={color ? { color } : undefined}><span className="d" />{children}</span>
);

export const Kpi = ({ value, label, color, small }: { value: ReactNode; label: string; color?: string; small?: boolean }) => (
  <div className="card pad" style={{ minWidth: 0 }}>
    <div className={`kpi ${small ? "small" : ""}`} style={color ? { color } : undefined}>{value}</div>
    <div className="sub" style={{ marginTop: 2 }}>{label}</div>
  </div>
);

export const Section = ({ title, actions, children, sub }: { title: string; sub?: string; actions?: ReactNode; children: ReactNode }) => (
  <section style={{ marginBottom: 22 }}>
    <div className="row between" style={{ marginBottom: 12 }}>
      <div><div className="h-title">{title}</div>{sub && <div className="sub">{sub}</div>}</div>
      {actions}
    </div>
    {children}
  </section>
);

export const Empty = ({ children }: { children: ReactNode }) => <div className="empty">{children}</div>;

export const sevClass = (s: string) => `sev-${s}`;
export const stClass = (s: string) => `st-${s}`;

/** Lightweight grouped bar chart (inline SVG, no deps). */
export function BarChart({ series, groups, colors, height = 150, fmt = (n: number) => String(n) }:
  { series: { label: string; values: number[] }[]; groups: string[]; colors: string[]; height?: number; fmt?: (n: number) => string }) {
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const gw = 100 / groups.length;
  const bw = (gw * 0.62) / series.length;
  return (
    <svg viewBox={`0 0 100 ${100}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line key={f} x1="0" x2="100" y1={100 - f * 92} y2={100 - f * 92} stroke="rgba(255,255,255,.06)" strokeWidth="0.3" />
      ))}
      {groups.map((_, gi) => series.map((s, si) => {
        const h = (s.values[gi] / max) * 92;
        const x = gi * gw + gw * 0.19 + si * bw;
        return <rect key={`${gi}-${si}`} x={x} y={100 - h} width={bw * 0.84} height={h} rx="0.6"
          fill={colors[si]} opacity="0.92"><title>{`${s.label} / ${groups[gi]}: ${fmt(s.values[gi])}`}</title></rect>;
      }))}
    </svg>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return <div className="row wrap" style={{ gap: 14, fontSize: 12.5 }}>
    {items.map((i) => <span key={i.label} className="row" style={{ gap: 6 }}><span style={{ width: 11, height: 11, borderRadius: 3, background: i.color }} />{i.label}</span>)}
  </div>;
}
