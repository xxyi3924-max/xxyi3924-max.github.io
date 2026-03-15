import { useState } from "react";
import type { FormEvent } from "react";
import { useAgentStream } from "./hooks/useAgentStream";
import { SkillStep } from "./components/SkillStep";
import { ReasoningStream } from "./components/ReasoningStream";
import { VerdictCard } from "./components/VerdictCard";
import { Terminal } from "./components/Terminal";

const QUICK_TICKERS = ["NVDA", "TSLA", "AAPL"];
type Tab = "analysis" | "terminal";

export default function App() {
  const [input, setInput] = useState("");
  const [tab, setTab] = useState<Tab>("analysis");
  const { state, analyze, cancel } = useAgentStream();
  const hasActivity = state.skills.length > 0 || state.loading;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (ticker) {
      analyze(ticker);
      setTab("analysis");
    }
  };

  const handleQuick = (ticker: string) => {
    setInput(ticker);
    analyze(ticker);
    setTab("analysis");
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Top bar */}
      <div className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-green-400 via-emerald-300 to-cyan-400 bg-clip-text text-transparent">
            Smart Money
          </h1>
          <p className="text-xs text-gray-500">Institutional signal detector</p>
        </div>
        <div className="flex items-center gap-4">
          {state.loading && (
            <div className="flex items-center gap-2 text-sm text-yellow-400 animate-pulse">
              <span className="w-2 h-2 rounded-full bg-yellow-400" />
              Analyzing…
            </div>
          )}
          {/* Tabs */}
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
            {(["analysis", "terminal"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${
                  tab === t
                    ? "bg-gray-700 text-white"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {t}
                {t === "terminal" && state.loading && (
                  <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-green-400 inline-block animate-pulse" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col max-w-4xl w-full mx-auto px-4 py-8 gap-6">
        {/* Search — always visible */}
        <form onSubmit={handleSubmit}>
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value.toUpperCase())}
              placeholder="Enter ticker symbol…"
              className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-5 py-3.5 text-white placeholder-gray-500 focus:outline-none focus:border-green-500 font-mono text-xl uppercase tracking-widest"
              disabled={state.loading}
            />
            {state.loading ? (
              <button
                type="button"
                onClick={cancel}
                className="bg-red-700 hover:bg-red-600 px-6 py-3.5 rounded-xl font-semibold transition-colors"
              >
                Cancel
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="bg-green-600 hover:bg-green-500 disabled:opacity-40 px-6 py-3.5 rounded-xl font-semibold transition-colors"
              >
                Analyze
              </button>
            )}
          </div>
          <div className="flex gap-2 mt-3">
            <span className="text-xs text-gray-600 self-center mr-1">Quick:</span>
            {QUICK_TICKERS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => handleQuick(t)}
                disabled={state.loading}
                className="text-xs border border-gray-700 hover:border-green-500 hover:text-green-400 text-gray-400 px-3 py-1.5 rounded-lg transition-colors font-mono disabled:opacity-40"
              >
                {t}
              </button>
            ))}
          </div>
        </form>

        {/* Tab content */}
        {tab === "analysis" && (
          <>
            {hasActivity && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Left — steps */}
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
                    Analysis Steps
                  </p>
                  {state.skills.length === 0 && state.loading && (
                    <p className="text-sm text-gray-600 animate-pulse pl-4">Starting agent…</p>
                  )}
                  {state.skills.map((s, i) => (
                    <SkillStep key={s.name} skill={s} index={i} />
                  ))}
                </div>

                {/* Right — reasoning + verdict */}
                <div className="space-y-4">
                  <ReasoningStream
                    lines={state.reasoning}
                    loading={state.loading && state.skills.length > 0}
                  />
                  {state.verdict && <VerdictCard verdict={state.verdict} />}
                  {state.error && (
                    <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
                      {state.error}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!hasActivity && (
              <div className="text-center py-16 space-y-3">
                <p className="text-gray-600 text-sm max-w-sm mx-auto leading-relaxed">
                  Enter a ticker to correlate options flow, insider filings, price action,
                  and social sentiment into a single institutional signal.
                </p>
                <p className="text-gray-700 text-xs">
                  Institutions move first. The crowd follows. Find the gap.
                </p>
              </div>
            )}
          </>
        )}

        {tab === "terminal" && (
          <div className="flex-1" style={{ height: "calc(100vh - 280px)" }}>
            <Terminal />
          </div>
        )}
      </div>
    </div>
  );
}
