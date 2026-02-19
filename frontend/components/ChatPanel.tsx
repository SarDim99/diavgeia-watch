"use client";

import { useState, useRef, useEffect } from "react";
import { askQuestion, formatCurrency } from "@/lib/api";
import { Send, Loader2, Database, Sparkles, ChevronDown, ChevronUp } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sql?: string;
  data?: any[];
  thinking?: string;
  loading?: boolean;
}

const EXAMPLES = [
  "Ποιοι είναι οι top 5 οργανισμοί σε δαπάνη;",
  "Show top 10 contractors by total amount",
  "How much was spent on cleaning services?",
  "Πόσες αποφάσεις υπάρχουν στη βάση;",
];

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (question?: string) => {
    const q = question || input.trim();
    if (!q || loading) return;

    setInput("");

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: q,
    };

    const loadingMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setLoading(true);

    try {
      const res = await askQuestion(q);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: res.answer,
                sql: res.sql,
                data: res.data,
                thinking: res.thinking,
                loading: false,
              }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: "Error connecting to the server. Is the API running?",
                loading: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full rounded-xl border border-navy-600 bg-navy-800 overflow-hidden">
      {/* Header */}
      <div className="gradient-border flex items-center gap-2 px-5 py-3 border-b border-navy-600">
        <Sparkles className="w-4 h-4 text-accent-cyan" />
        <h2 className="font-semibold text-sm">Ask about spending</h2>
        <span className="ml-auto text-xs text-slate-500 font-mono">
          AI-powered queries
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px] max-h-[500px]">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div className="p-3 rounded-full bg-accent-blue/10">
              <Database className="w-6 h-6 text-accent-blue" />
            </div>
            <div>
              <p className="text-slate-400 text-sm mb-4">
                Ask a question in Greek or English
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => handleSubmit(ex)}
                    className="text-xs px-3 py-1.5 rounded-full border border-navy-600 
                               text-slate-400 hover:text-white hover:border-accent-blue/50 
                               hover:bg-accent-blue/10 transition-all duration-200"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-navy-600">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="π.χ. Πόσο κόστισε η καθαριότητα;"
            className="flex-1 bg-navy-700 border border-navy-600 rounded-lg px-4 py-2.5
                       text-sm text-white placeholder:text-slate-500
                       focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/20
                       transition-all duration-200"
            disabled={loading}
          />
          <button
            onClick={() => handleSubmit()}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-lg bg-accent-blue text-white text-sm font-medium
                       hover:bg-accent-blue/90 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-200 flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const [showSql, setShowSql] = useState(false);

  if (message.loading) {
    return (
      <div className="flex gap-3 animate-fade-in">
        <div className="w-7 h-7 rounded-full bg-accent-blue/20 flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-accent-blue" />
        </div>
        <div className="flex items-center gap-2 text-slate-400 text-sm">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Analyzing...
        </div>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[80%] bg-accent-blue/15 border border-accent-blue/20 rounded-xl px-4 py-2.5 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-7 h-7 rounded-full bg-accent-blue/20 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Sparkles className="w-3.5 h-3.5 text-accent-blue" />
      </div>
      <div className="flex-1 min-w-0">
        {/* Answer text */}
        <div className="text-sm whitespace-pre-wrap leading-relaxed">
          {message.content}
        </div>

        {/* Data table */}
        {message.data && message.data.length > 0 && (
          <div className="mt-3 overflow-x-auto rounded-lg border border-navy-600">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="bg-navy-700 text-slate-400">
                  {Object.keys(message.data[0]).map((key) => (
                    <th key={key} className="px-3 py-2 text-left font-medium">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {message.data.map((row, i) => (
                  <tr
                    key={i}
                    className="border-t border-navy-600 hover:bg-navy-700/50"
                  >
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="px-3 py-1.5 text-slate-300">
                        {typeof val === "number"
                          ? val > 1000
                            ? formatCurrency(val)
                            : val.toLocaleString()
                          : String(val ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* SQL toggle */}
        {message.sql && (
          <button
            onClick={() => setShowSql(!showSql)}
            className="mt-2 flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            <Database className="w-3 h-3" />
            SQL
            {showSql ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </button>
        )}
        {showSql && message.sql && (
          <pre className="mt-1 p-3 rounded-lg bg-navy-900 border border-navy-600 text-xs text-accent-cyan font-mono overflow-x-auto">
            {message.sql}
          </pre>
        )}
      </div>
    </div>
  );
}