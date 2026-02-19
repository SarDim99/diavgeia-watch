"use client";

import { useState, useRef, useEffect } from "react";
import { askQuestion, formatCurrency } from "@/lib/api";
import { Search, Loader2, Database, ChevronDown, ChevronUp, MessageSquare } from "lucide-react";

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
  "Top 5 οργανισμοί σε δαπάνη",
  "Top 10 contractors by amount",
  "How much was spent on cleaning?",
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
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: q };
    const loadingMsg: Message = { id: (Date.now() + 1).toString(), role: "assistant", content: "", loading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setLoading(true);

    try {
      const res = await askQuestion(q);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: res.answer, sql: res.sql, data: res.data, thinking: res.thinking, loading: false }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id ? { ...m, content: "Could not fetch results. Please try again.", loading: false } : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2 text-slate-800">
          <MessageSquare className="w-4 h-4 text-blue-600" />
          <h2 className="font-semibold text-sm">Data Assistant</h2>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth bg-slate-50/30">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-sm mx-auto">
            <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Database className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800 mb-2">Explore the Database</h3>
            <p className="text-sm text-slate-500 mb-8">Ask natural language questions to filter and summarize spending records.</p>
            
            <div className="flex flex-col w-full gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => handleSubmit(ex)}
                  className="text-left text-sm px-4 py-3 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:border-blue-300 transition-all shadow-sm"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} className="h-2" />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-100">
        <div className="relative flex items-end gap-2 bg-slate-50 border border-slate-200 rounded-xl p-2 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-200 transition-all shadow-sm">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Ask a question..."
            className="flex-1 bg-transparent border-none resize-none max-h-32 min-h-[40px] px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-0"
            rows={1}
            disabled={loading}
          />
          <button
            onClick={() => handleSubmit()}
            disabled={loading || !input.trim()}
            className="mb-0.5 p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors shadow-sm"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
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
        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
          <Database className="w-4 h-4 text-slate-400" />
        </div>
        <div className="flex items-center text-sm text-slate-500 font-medium">Searching records...</div>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="max-w-[85%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-5 py-3 text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const hasTableData = message.data && message.data.length > 0;
  
  // Clean up the response text: If we are rendering an HTML table, 
  // remove the raw ASCII text table generated by the backend.
  let displayContent = message.content;
  if (hasTableData) {
    displayContent = message.content
      .split('\n')
      .filter(line => !line.includes(' | ') && !line.includes('-+-') && !line.match(/^[-\s]+$/))
      .join('\n')
      .trim();
  }

  return (
    <div className="flex gap-4 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-white border border-slate-200 shadow-sm flex items-center justify-center shrink-0 mt-1">
        <Database className="w-4 h-4 text-blue-600" />
      </div>
      <div className="flex-1 min-w-0 space-y-3">
        
        {/* Only render text if there's conversational text left after stripping the ASCII table */}
        {displayContent && (
          <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {displayContent}
          </div>
        )}

        {/* HTML Table Render */}
        {hasTableData && message.data && (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  {Object.keys(message.data[0]).map((key) => (
                    <th key={key} className="px-4 py-3 font-semibold text-slate-600 capitalize">
                      {key.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {message.data.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                    {Object.values(row).map((val, j) => (
                      <td key={j} className="px-4 py-3 text-slate-700">
                        {typeof val === "number" ? (val > 1000 ? formatCurrency(val) : val.toLocaleString()) : String(val ?? "-")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* View Underlying Query Toggle */}
        {message.sql && (
          <div className="pt-1">
            <button
              onClick={() => setShowSql(!showSql)}
              className="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-600 transition-colors"
            >
              <Database className="w-3 h-3" />
              {showSql ? "Hide underlying query" : "View underlying query"}
              {showSql ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showSql && (
              <pre className="mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 font-mono overflow-x-auto">
                {message.sql}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}