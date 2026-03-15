import { useEffect, useRef } from "react";
import { useLogsStream } from "../hooks/useLogsStream";

export function Terminal() {
  const { lines, connected, connect, disconnect, clear } = useLogsStream();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  const lineColor = (text: string) => {
    if (text.includes("✖") || text.includes("ERROR")) return "text-red-400";
    if (text.includes("⚠")) return "text-yellow-400";
    if (text.includes("VERDICT") || text.includes("═")) return "text-green-400";
    if (text.includes("🧠")) return "text-blue-400";
    if (text.includes("🌐")) return "text-cyan-400";
    if (text.includes("✔")) return "text-green-300";
    if (text.includes("▶")) return "text-yellow-300";
    if (text.includes("◀")) return "text-purple-300";
    return "text-gray-300";
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-gray-600"}`} />
          <span className="text-xs text-gray-400 font-mono">
            backend logs {connected ? "— live" : "— disconnected"}
          </span>
        </div>
        <button
          onClick={clear}
          className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
        >
          clear
        </button>
      </div>

      {/* Log lines */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed space-y-0.5 min-h-0">
        {lines.length === 0 && (
          <p className="text-gray-600">Waiting for analysis requests…</p>
        )}
        {lines.map((line, i) => (
          <div key={i} className={lineColor(line)}>
            {line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
