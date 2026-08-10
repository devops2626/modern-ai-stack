"use client";

import { useState, FormEvent, useRef, useEffect, useCallback } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useRag, setUseRag] = useState(false);
  const [docsCount, setDocsCount] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const refreshDocsCount = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/docs-count`);
      if (res.ok) {
        const data = await res.json();
        setDocsCount(data.count ?? 0);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/health`);
        setOnline(res.ok);
        if (res.ok) refreshDocsCount();
      } catch {
        setOnline(false);
      }
    };
    check();
    const id = setInterval(check, 20000);
    return () => clearInterval(id);
  }, [refreshDocsCount]);

  const ingestFile = async (file: File) => {
    const allowed = [".txt", ".md", ".markdown", ".csv", ".json", ".py", ".js", ".ts", ".tsx", ".yml", ".yaml"];
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!allowed.includes(ext) && !file.type.startsWith("text/")) {
      setUploadMsg("Unsupported file type. Use .txt, .md, .csv, .json, or source code.");
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    setError(null);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/api/ingest-file`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed (${res.status})`);
      }
      const data = await res.json();
      setUploadMsg(
        `✓ Ingested “${data.filename}” → ${data.chunks} chunk${data.chunks === 1 ? "" : "s"} (total: ${data.total_docs})`
      );
      setDocsCount(data.total_docs);
      setUseRag(true);
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) ingestFile(file);
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) ingestFile(file);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || loading) return;

    setError(null);
    setLoading(true);

    const historyForApi = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setPrompt("");
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch(`${API_URL}/api/generate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: trimmed,
          use_rag: useRag,
          history: historyForApi,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (!payload) continue;

          try {
            const event = JSON.parse(payload);
            if (event.type === "token" && event.content) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last?.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + event.content,
                  };
                }
                return updated;
              });
            } else if (event.type === "error") {
              throw new Error(event.message || "Stream error");
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== "Stream error") {
              continue;
            }
            throw parseErr;
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(msg);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content === "") {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <main className="flex min-h-screen flex-col bg-[#0b0f19] text-gray-100">
      <div className="mx-auto flex h-screen w-full max-w-3xl flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-gray-800 bg-[#111827] px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold tracking-tight text-white">
              Modern AI Stack
            </h1>
            <p className="text-xs text-gray-400">
              FastAPI · SSE · RAG · Next.js
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                online
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-rose-500/15 text-rose-400"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  online ? "bg-emerald-400" : "bg-rose-400"
                }`}
              />
              {online === null ? "…" : online ? "Online" : "Offline"}
            </div>
            <button
              type="button"
              onClick={() => setShowUpload((v) => !v)}
              className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 transition hover:border-sky-500/50 hover:text-sky-400"
            >
              {showUpload ? "Hide" : "Upload"}
            </button>
            <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-gray-400">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="rounded border-gray-600 bg-gray-800 text-sky-500 focus:ring-sky-500"
              />
              RAG
              {docsCount !== null && (
                <span className="text-xs text-gray-500">({docsCount})</span>
              )}
            </label>
          </div>
        </header>

        {showUpload && (
          <div className="border-b border-gray-800 bg-[#0f1520] px-4 py-4 sm:px-6">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 transition ${
                dragOver
                  ? "border-sky-500 bg-sky-500/10"
                  : "border-gray-700 hover:border-gray-500 hover:bg-gray-900/50"
              } ${uploading ? "pointer-events-none opacity-60" : ""}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.markdown,.csv,.json,.py,.js,.ts,.tsx,.yml,.yaml,text/*"
                className="hidden"
                onChange={handleFileSelect}
              />
              {uploading ? (
                <p className="animate-pulse text-sm text-gray-400">
                  Uploading & chunking…
                </p>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-300">
                    Drop a file here or click to browse
                  </p>
                  <p className="text-xs text-gray-500">
                    .txt · .md · .csv · .json · code
                  </p>
                </>
              )}
            </div>
            {uploadMsg && (
              <p
                className={`mt-3 text-sm ${
                  uploadMsg.startsWith("✓")
                    ? "text-emerald-400"
                    : "text-rose-400"
                }`}
              >
                {uploadMsg}
              </p>
            )}
          </div>
        )}

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6 sm:px-6">
          {messages.length === 0 && (
            <div className="mt-16 space-y-3 text-center text-gray-500">
              <p className="text-base text-gray-400">
                Ask anything — responses stream in real time.
              </p>
              <p className="text-sm">
                Upload documents and enable <strong className="text-gray-300">RAG</strong> to
                chat with your files.
              </p>
              <div className="mx-auto mt-6 flex max-w-md flex-wrap justify-center gap-2">
                {[
                  "Summarize the uploaded docs",
                  "What are the key points?",
                  "Explain the architecture",
                ].map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setPrompt(q)}
                    className="rounded-xl border border-gray-800 bg-gray-900/60 px-3 py-2 text-left text-xs text-gray-400 transition hover:border-sky-500/40 hover:text-gray-200"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-sky-600 text-white"
                    : "border border-gray-800 bg-gray-900 text-gray-100"
                }`}
              >
                {m.content}
                {loading &&
                  i === messages.length - 1 &&
                  m.role === "assistant" && (
                    <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-sky-400 align-middle" />
                  )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="border-t border-rose-900/50 bg-rose-950/40 px-4 py-2 text-sm text-rose-300">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="flex gap-2 border-t border-gray-800 bg-[#111827] p-4"
        >
          <textarea
            className="flex-1 resize-none rounded-xl border border-gray-700 bg-gray-900 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none transition focus:border-sky-500/60 focus:ring-1 focus:ring-sky-500/30 disabled:opacity-60"
            rows={2}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              useRag && docsCount
                ? "Ask about your documents…"
                : "Ask something…"
            }
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as FormEvent);
              }
            }}
          />
          <div className="flex flex-col gap-2">
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="rounded-xl bg-sky-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-gray-700"
            >
              {loading ? "…" : "Send"}
            </button>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearChat}
                className="rounded-xl border border-gray-700 px-3 py-1.5 text-xs text-gray-400 transition hover:border-rose-500/50 hover:text-rose-400"
              >
                Clear
              </button>
            )}
          </div>
        </form>
      </div>
    </main>
  );
}
