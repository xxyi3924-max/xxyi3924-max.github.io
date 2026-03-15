import { useState, useCallback, useRef } from "react";
import type { Verdict, SkillState, SkillStatus } from "../types";

const SKILL_LABELS: Record<string, string> = {
  options_flow_scanner: "Options Flow",
  social_buzz_scanner: "Social Buzz",
  insider_tracker: "Insider Tracker",
  price_action_context: "Price Action",
};

export interface StreamState {
  loading: boolean;
  reasoning: string[];
  skills: SkillState[];
  verdict: Verdict | null;
  error: string | null;
}

export function useAgentStream() {
  const [state, setState] = useState<StreamState>({
    loading: false,
    reasoning: [],
    skills: [],
    verdict: null,
    error: null,
  });

  const abortRef = useRef<(() => void) | null>(null);

  const analyze = useCallback((ticker: string) => {
    // Reset state
    setState({ loading: true, reasoning: [], skills: [], verdict: null, error: null });

    const apiKey = import.meta.env.VITE_API_KEY ?? "";
    const backendUrl = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
    const url = `${backendUrl}/analyze?ticker=${encodeURIComponent(ticker)}${apiKey ? `&api_key=${apiKey}` : ""}`;
    const eventSource = new EventSource(url);
    abortRef.current = () => eventSource.close();

    const updateSkill = (tool: string, status: SkillStatus, result?: Record<string, unknown>) => {
      setState((prev) => {
        const existing = prev.skills.find((s) => s.name === tool);
        if (existing) {
          return {
            ...prev,
            skills: prev.skills.map((s) =>
              s.name === tool ? { ...s, status, ...(result ? { result } : {}) } : s
            ),
          };
        }
        return {
          ...prev,
          skills: [...prev.skills, { name: tool, status, result }],
        };
      });
    };

    eventSource.addEventListener("tool_call", (e) => {
      const data = JSON.parse(e.data);
      updateSkill(data.tool, "calling");
    });

    eventSource.addEventListener("tool_result", (e) => {
      const data = JSON.parse(e.data);
      updateSkill(data.tool, "complete", data.result);
    });

    eventSource.addEventListener("reasoning", (e) => {
      const data = JSON.parse(e.data);
      // Strip markdown code fences if present
      const text = data.text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
      if (text) {
        setState((prev) => ({ ...prev, reasoning: [...prev.reasoning, text] }));
      }
    });

    eventSource.addEventListener("verdict", (e) => {
      const raw = JSON.parse(e.data);
      const verdict: Verdict = {
        signal_type: ["accumulation", "distribution", "hedge", "noise"].includes(raw.signal_type)
          ? raw.signal_type
          : "noise",
        conviction: ["low", "medium", "high"].includes(raw.conviction) ? raw.conviction : "low",
        explanation: raw.explanation ?? "No explanation provided.",
        watch_for: raw.watch_for,
        skills_used: Array.isArray(raw.skills_used) ? raw.skills_used : [],
      };
      setState((prev) => ({ ...prev, verdict }));
    });

    eventSource.addEventListener("error", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setState((prev) => ({ ...prev, error: data.message, loading: false }));
      eventSource.close();
    });

    eventSource.addEventListener("done", () => {
      setState((prev) => ({ ...prev, loading: false }));
      eventSource.close();
    });

    eventSource.onerror = () => {
      setState((prev) => ({
        ...prev,
        error: "Connection lost. Is the backend running?",
        loading: false,
      }));
      eventSource.close();
    };
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.();
    setState((prev) => ({ ...prev, loading: false }));
  }, []);

  return { state, analyze, cancel, SKILL_LABELS };
}
