import type { SkillState } from "../types";

const SKILL_META: Record<string, { label: string; icon: string; step: number }> = {
  options_flow_scanner:  { label: "Options Flow",     icon: "📊", step: 1 },
  social_buzz_scanner:   { label: "Social Buzz",      icon: "💬", step: 2 },
  insider_tracker:       { label: "Insider Tracker",  icon: "🏛",  step: 3 },
  price_action_context:  { label: "Price Action",     icon: "📈", step: 4 },
};

function summarize(name: string, result: Record<string, unknown>): string[] {
  const lines: string[] = [];

  if (name === "options_flow_scanner") {
    const unusual = result.unusual as boolean;
    const lean = result.sentiment_lean as string;
    const premium = result.total_unusual_premium as number;
    const sweep = result.sweep_detected as boolean;
    lines.push(unusual ? `Unusual activity detected` : "No unusual activity");
    if (unusual) {
      lines.push(`Sentiment lean: ${lean}`);
      lines.push(`Premium: $${(premium / 1_000_000).toFixed(2)}M`);
      if (sweep) lines.push("⚡ Sweep detected");
    }
  }

  if (name === "social_buzz_scanner") {
    const aware = result.crowd_aware as boolean;
    const type = result.informed_vs_hype as string;
    const interp = result.interpretation as string;
    lines.push(aware ? "Crowd is aware" : "Crowd not yet aware");
    lines.push(`Chatter type: ${type}`);
    if (interp) lines.push(interp.slice(0, 100) + (interp.length > 100 ? "…" : ""));
  }

  if (name === "insider_tracker") {
    const dir = result.net_institutional_direction as string;
    const funds = result.notable_funds as string[];
    lines.push(`Direction: ${dir}`);
    if (funds?.length) lines.push(`Funds: ${funds.slice(0, 3).join(", ")}`);
  }

  if (name === "price_action_context") {
    const trend = result.trend as string;
    const vol = result.volume_ratio as number;
    const pct = result.pct_from_52w_high as number;
    const catalyst = result.recent_catalyst as boolean;
    lines.push(`Trend: ${trend}`);
    lines.push(`Volume: ${vol}x avg`);
    lines.push(`${pct.toFixed(1)}% from 52w high`);
    if (catalyst) lines.push("Recent catalyst detected");
  }

  return lines;
}

interface Props {
  skill: SkillState;
  index: number;
}

export function SkillStep({ skill, index }: Props) {
  const meta = SKILL_META[skill.name] ?? { label: skill.name, icon: "🔧", step: index + 1 };
  const lines = skill.result ? summarize(skill.name, skill.result) : [];

  const borderColor = {
    idle:     "border-gray-800",
    calling:  "border-yellow-500",
    complete: "border-green-600",
  }[skill.status];

  const dotColor = {
    idle:     "bg-gray-700 text-gray-500",
    calling:  "bg-yellow-500 text-black animate-pulse",
    complete: "bg-green-500 text-black",
  }[skill.status];

  return (
    <div className={`border-l-2 ${borderColor} pl-4 py-2 transition-all duration-300`}>
      <div className="flex items-center gap-3">
        {/* Step number dot */}
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${dotColor}`}>
          {skill.status === "complete" ? "✓" : meta.step}
        </span>

        {/* Label + icon */}
        <span className="text-sm font-semibold text-white">
          {meta.icon} {meta.label}
        </span>

        {/* Status pill */}
        {skill.status === "calling" && (
          <span className="text-xs text-yellow-400 animate-pulse ml-auto">running…</span>
        )}
        {skill.status === "complete" && (
          <span className="text-xs text-green-400 ml-auto">done</span>
        )}
      </div>

      {/* Result summary */}
      {lines.length > 0 && (
        <div className="mt-2 ml-9 space-y-0.5">
          {lines.map((line, i) => (
            <p key={i} className="text-xs text-gray-400">{line}</p>
          ))}
        </div>
      )}
    </div>
  );
}
