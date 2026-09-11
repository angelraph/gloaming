"use client";

import { useState } from "react";

type Message = { role: "user" | "assistant"; content: string };

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      const answer = res.ok ? data.answer : `Error: ${data.error}`;
      setMessages((m) => [...m, { role: "assistant", content: answer }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `Request failed: ${String(err)}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto">
        {messages.length === 0 && (
          <p className="text-sm text-text-tertiary">
            Ask about the overnight book - e.g. &quot;why did AAPL trade rich overnight?&quot;
            The answer is grounded in the real portfolio and decision data on this page,
            never invented. This never places a trade - you stay in control.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-[85%] rounded-lg bg-brand px-3 py-2 text-sm text-white"
                : "mr-auto max-w-[85%] rounded-lg bg-layer-2 px-3 py-2 text-sm text-text-primary"
            }
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-1.5 text-xs text-text-tertiary">
            <span className="inline-flex gap-0.5">
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.3s]" />
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.15s]" />
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary" />
            </span>
            Thinking
          </div>
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about the overnight book"
          className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <button
          onClick={send}
          disabled={loading}
          className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-hover disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
