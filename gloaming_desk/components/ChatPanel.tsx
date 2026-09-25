"use client";

import { useState } from "react";

type Message = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "What did the agent do tonight, and why?",
  "Why did the agent hold most symbols?",
  "How close is the book to its risk caps?",
];

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send(override?: string) {
    const text = (override ?? input).trim();
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
          <div>
            <p className="text-sm leading-relaxed text-text-secondary">
              Ask about the overnight book. Answers are grounded in the real portfolio and decision
              data on this page, never invented, and this never places a trade.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-border px-3.5 py-2 text-left text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-heading"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "ml-auto max-w-[85%] rounded-2xl rounded-br-md border border-border bg-layer-2 px-4 py-2.5 text-sm text-heading"
                : "mr-auto max-w-[92%] rounded-2xl rounded-bl-md border border-border-subtle px-4 py-2.5 text-sm leading-relaxed text-text-primary"
            }
          >
            {m.content}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-tertiary">
            <span className="inline-flex gap-0.5">
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.3s]" />
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.15s]" />
              <span className="h-1 w-1 animate-bounce rounded-full bg-text-tertiary" />
            </span>
            Thinking
          </div>
        )}
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about the overnight book"
          aria-label="Ask about the overnight book"
          className="min-w-0 flex-1 rounded-full border border-border bg-transparent px-5 py-2.5 text-sm text-heading placeholder:text-text-tertiary focus:border-border-strong focus:outline-none"
        />
        <button
          onClick={() => send()}
          disabled={loading}
          className="rounded-full bg-mint px-5 py-2.5 text-sm font-medium tracking-wide text-background transition-colors hover:bg-brand-hover disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
