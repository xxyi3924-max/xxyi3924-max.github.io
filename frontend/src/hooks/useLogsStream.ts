import { useState, useCallback, useRef } from "react";

export function useLogsStream() {
  const [lines, setLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) return;

    const apiKey = import.meta.env.VITE_API_KEY ?? "";
    const backendUrl = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
    const url = `${backendUrl}/logs${apiKey ? `?api_key=${apiKey}` : ""}`;

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("log", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setLines((prev) => [...prev.slice(-500), data.text]); // keep last 500 lines
    });

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
  }, []);

  const disconnect = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setConnected(false);
  }, []);

  const clear = useCallback(() => setLines([]), []);

  return { lines, connected, connect, disconnect, clear };
}
