import type { Verdict, SignalType, Conviction } from "../types";

interface Props {
  verdict: Verdict;
}

const SIGNAL_CONFIG: Record<SignalType, { label: string; color: string; bg: string; border: string; icon: string }> = {
  accumulation: {
    label: "Accumulation",
    color: "text-green-300",
    bg: "bg-green-900/30",
    border: "border-green-500",
    icon: "▲",
  },
  distribution: {
    label: "Distribution",
    color: "text-red-300",
    bg: "bg-red-900/30",
    border: "border-red-500",
    icon: "▼",
  },
  hedge: {
    label: "Hedge",
    color: "text-yellow-300",
    bg: "bg-yellow-900/30",
    border: "border-yellow-500",
    icon: "⚡",
  },
  noise: {
    label: "No Signal",
    color: "text-gray-400",
    bg: "bg-gray-800/50",
    border: "border-gray-600",
    icon: "—",
  },
};

const CONVICTION_BARS: Record<Conviction, number> = {
  low: 1,
  medium: 2,
  high: 3,
};

function ConvictionMeter({ level }: { level: Conviction }) {
  const filled = CONVICTION_BARS[level] ?? 1;
  const colors: Record<Conviction, string> = {
    low: "bg-yellow-500",
    medium: "bg-orange-500",
    high: "bg-green-500",
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-gray-400 mr-1">Conviction</span>
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className={`h-2.5 w-6 rounded-sm ${i <= filled ? colors[level] : "bg-gray-700"}`}
        />
      ))}
      <span className={`text-xs font-semibold ml-1 capitalize ${colors[level].replace("bg-", "text-")}`}>
        {level}
      </span>
    </div>
  );
}

export function VerdictCard({ verdict }: Props) {
  const cfg = SIGNAL_CONFIG[verdict.signal_type] ?? SIGNAL_CONFIG["noise"];

  return (
    <div className={`rounded-xl border-2 ${cfg.border} ${cfg.bg} p-5 mt-4 space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-2xl font-bold ${cfg.color}`}>{cfg.icon}</span>
          <span className={`text-xl font-bold ${cfg.color}`}>{cfg.label}</span>
        </div>
        <ConvictionMeter level={verdict.conviction} />
      </div>

      {/* Explanation */}
      <p className="text-gray-200 text-sm leading-relaxed">{verdict.explanation}</p>

      {/* Watch for */}
      {verdict.watch_for && (
        <div className="bg-gray-800 rounded-lg px-4 py-2.5">
          <span className="text-xs text-gray-400 font-semibold uppercase tracking-wider">Watch For</span>
          <p className="text-gray-300 text-sm mt-1">{verdict.watch_for}</p>
        </div>
      )}

      {/* Skills used */}
      <div className="flex flex-wrap gap-2 pt-1">
        {(verdict.skills_used ?? []).map((s) => (
          <span key={s} className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded-md border border-gray-700">
            {s.replace(/_/g, " ")}
          </span>
        ))}
      </div>

      <p className="text-xs text-gray-600 italic">For informational purposes only. Not investment advice.</p>
    </div>
  );
}
