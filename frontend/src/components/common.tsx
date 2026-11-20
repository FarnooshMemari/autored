import React, { type ReactNode } from "react";

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

/** Labeled grouped bar chart (HTML/CSS, crisp labels, no deps). */
export function BarChart({ series, groups, colors, height = 180, unit = "", yLabel }:
  { series: { label: string; values: number[] }[]; groups: string[]; colors: string[]; height?: number; unit?: string; yLabel?: string }) {
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {yLabel && <div style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", fontSize: 10.5, color: "var(--faint)", textTransform: "uppercase", letterSpacing: ".08em", alignSelf: "center" }}>{yLabel}</div>}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 14, height, borderBottom: "1px solid var(--border)", padding: "0 6px" }}>
          {groups.map((g, gi) => (
            <div key={g} style={{ flex: 1, display: "flex", gap: 6, alignItems: "flex-end", justifyContent: "center", height: "100%" }}>
              {series.map((s, si) => (
                <div key={si} title={`${s.label} / ${g}: ${s.values[gi]}${unit}`}
                     style={{ width: 26, height: `${Math.max(2, (s.values[gi] / max) * 100)}%`, background: `linear-gradient(180deg, ${colors[si]}, ${colors[si]}99)`,
                       borderRadius: "4px 4px 0 0", position: "relative", transition: "height .5s" }}>
                  <span style={{ position: "absolute", top: -17, left: "50%", transform: "translateX(-50%)", fontSize: 11, fontWeight: 700, color: "var(--text)" }}>{s.values[gi]}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 14, padding: "6px 6px 0" }}>
          {groups.map((g) => <div key={g} style={{ flex: 1, textAlign: "center", fontSize: 11.5, color: "var(--muted)", fontWeight: 600 }}>{g}</div>)}
        </div>
      </div>
    </div>
  );
}

export function KpiRow({ items }: { items: { label: string; value: React.ReactNode; color?: string }[] }) {
  return <div style={{ display: "grid", gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: 10 }}>
    {items.map((i) => <div key={i.label} className="card pad" style={{ padding: "12px 14px" }}>
      <div className="kpi small" style={i.color ? { color: i.color } : undefined}>{i.value}</div>
      <div className="sub" style={{ fontSize: 11.5, marginTop: 1 }}>{i.label}</div>
    </div>)}
  </div>;
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return <div className="row wrap" style={{ gap: 14, fontSize: 12.5 }}>
    {items.map((i) => <span key={i.label} className="row" style={{ gap: 6 }}><span style={{ width: 11, height: 11, borderRadius: 3, background: i.color }} />{i.label}</span>)}
  </div>;
}
