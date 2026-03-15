export type SignalType = "accumulation" | "distribution" | "hedge" | "noise";
export type Conviction = "low" | "medium" | "high";
export type InformedVsHype = "informed" | "hype" | "mixed" | "none";

export interface Verdict {
  signal_type: SignalType;
  conviction: Conviction;
  explanation: string;
  watch_for?: string;
  skills_used: string[];
}

export interface ToolCallEvent {
  tool: string;
  ticker: string;
  status: "calling" | "complete";
}

export interface ToolResultEvent {
  tool: string;
  result: Record<string, unknown>;
  status: "complete";
}

export interface ReasoningEvent {
  text: string;
}

export type AgentEvent =
  | { event: "tool_call"; data: ToolCallEvent }
  | { event: "tool_result"; data: ToolResultEvent }
  | { event: "reasoning"; data: ReasoningEvent }
  | { event: "verdict"; data: Verdict }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: Record<string, never> };

export type SkillStatus = "idle" | "calling" | "complete";

export interface SkillState {
  name: string;
  status: SkillStatus;
  result?: Record<string, unknown>;
}
