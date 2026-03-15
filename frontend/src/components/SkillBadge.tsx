import type { SkillState } from "../types";

const SKILL_LABELS: Record<string, string> = {
  options_flow_scanner: "Options Flow",
  social_buzz_scanner: "Social Buzz",
  insider_tracker: "Insider Tracker",
  price_action_context: "Price Action",
};

const SKILL_ICONS: Record<string, string> = {
  options_flow_scanner: "📊",
  social_buzz_scanner: "💬",
  insider_tracker: "🏛",
  price_action_context: "📈",
};

interface Props {
  skill: SkillState;
}

export function SkillBadge({ skill }: Props) {
  const label = SKILL_LABELS[skill.name] ?? skill.name;
  const icon = SKILL_ICONS[skill.name] ?? "🔧";

  const statusStyles: Record<string, string> = {
    idle: "bg-gray-800 text-gray-400 border-gray-700",
    calling: "bg-yellow-900/40 text-yellow-300 border-yellow-600 animate-pulse",
    complete: "bg-green-900/40 text-green-300 border-green-600",
  };

  const dotStyles: Record<string, string> = {
    idle: "bg-gray-600",
    calling: "bg-yellow-400 animate-ping",
    complete: "bg-green-400",
  };

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium ${statusStyles[skill.status]}`}>
      <span>{icon}</span>
      <span>{label}</span>
      <span className={`w-2 h-2 rounded-full ml-1 ${dotStyles[skill.status]}`} />
    </div>
  );
}
