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
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Fetch document count on mount and after uploads
  const refreshDocsCount = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/docs-count`);
      if (res.ok) {
        const data = await res.json();
        setDocsCount(data.count ?? 0);
      }
    } catch {
      // Chroma may not be up yet — ignore
    }
  }, []);

  useEffect(() => {
    refreshDocsCount();
  }, [refreshDocsCount]);

  const ingestFile = async (file: File) => {
    const allowed = [".txt", ".md", ".markdown", ".csv", ".json"];
    const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
    if (!allowed.includes(ext) && !file.type.startsWith("text/")) {
      setUploadMsg("Only text / markdown files are supported for now.");
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
        `Ingested “${data.filename}” → ${data.chunks} chunk${data.chunks === 1 ? "" : "s"} (total: ${data.total_docs})`
      );
      setDocsCount(data.total_docs);
      // Auto-enable RAG after a successful upload
      setUseRag(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setUploadMsg(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) ingestFile(file);
    // reset so the same file can be re-selected
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
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setPrompt("");

    // Placeholder for the streaming assistant message
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch(`${API_URL}/api/generate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: trimmed, use_rag: useRag }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      if (!res.body) {
        throw new Error("No response body");
      }

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

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6 bg-gray-50 text-gray-900">
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-lg overflow-hidden flex flex-col h-[85vh]">
        {/* Header */}
        <header className="px-6 py-4 border-b bg-white flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-bold tracking-tight">Modern AI Stack</h1>
            <p className="text-sm text-gray-500 truncate">
              FastAPI + OpenAI + Next.js · SSE · RAG
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() => setShowUpload((v) => !v)}
              className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition"
            >
              {showUpload ? "Hide upload" : "Upload docs"}
            </button>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              Use RAG
              {docsCount !== null && (
                <span className="text-xs text-gray-400">({docsCount})</span>
              )}
            </label>
          </div>
        </header>

        {/* Upload panel */}
        {showUpload && (
          <div className="px-6 py-4 border-b bg-gray-50">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                relative flex flex-col items-center justify-center gap-2
                rounded-xl border-2 border-dashed px-4 py-8 cursor-pointer transition
                ${
                  dragOver
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-300 hover:border-gray-400 hover:bg-white"
                }
                ${uploading ? "opacity-60 pointer-events-none" : ""}
              `}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.markdown,.csv,.json,text/*"
                className="hidden"
                onChange={handleFileSelect}
              />
              {uploading ? (
                <p className="text-sm text-gray-500 animate-pulse">Uploading & ingesting…</p>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-700">
                    Drop a file here or click to browse
                  </p>
                  <p className="text-xs text-gray-400">
                    .txt · .md · .csv · .json
                  </p>
                </>
              )}
            </div>

            {uploadMsg && (
              <p
                className={`mt-3 text-sm ${
                  uploadMsg.toLowerCase().includes("ingest") ||
                  uploadMsg.toLowerCase().includes("chunk")
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {uploadMsg}
              </p>
            )}

            {docsCount !== null && docsCount > 0 && (
              <p className="mt-2 text-xs text-gray-500">
                Vector store has <strong>{docsCount}</strong> chunk
                {docsCount === 1 ? "" : "s"}. Toggle “Use RAG” to query them.
              </p>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-12 space-y-2">
              <p>Ask anything — responses stream in real time.</p>
              <p className="text-sm">
                Upload documents and enable <strong>Use RAG</strong> to chat with your files.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${
                m.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-800"
                }`}
              >
                {m.content}
                {loading &&
                  i === messages.length - 1 &&
                  m.role === "assistant" && (
                    <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-500 animate-pulse align-middle" />
                  )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="px-6 py-2 bg-red-50 text-red-600 text-sm border-t">
            {error}
          </div>
        )}

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="p-4 border-t bg-white flex gap-3"
        >
          <textarea
            className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
          <button
            type="submit"
            disabled={loading || !prompt.trim()}
            className="self-end px-5 py-3 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
          >
            {loading ? "…" : "Send"}
          </button>
        </form>
      </div>
    </main>
  );
}
