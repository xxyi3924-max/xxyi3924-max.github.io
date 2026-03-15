import { useEffect, useRef } from "react";

interface Props {
  lines: string[];
  loading: boolean;
}

export function ReasoningStream({ lines, loading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  if (lines.length === 0 && !loading) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
          Agent Reasoning
        </span>
        {loading && (
          <span className="flex gap-1 ml-1">
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
          </span>
        )}
      </div>
      <div className="max-h-40 overflow-y-auto space-y-2 font-mono text-xs text-gray-300 leading-relaxed">
        {lines.map((line, i) => (
          <p key={i} className="border-l-2 border-blue-800 pl-3">{line}</p>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
