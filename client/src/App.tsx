import { FormEvent, ReactNode, useCallback, useEffect, useRef, useState } from "react";

type Message = { role: "user" | "assistant"; content: string; ts?: string };
type Policy = { id: string; title: string; text?: string };
type Session = { session_id: string; title: string; updated_at: string };
type WsEvent = { type: string; history?: Message[]; token?: string; text?: string; error?: string };

const USER_ID = "portfolio-demo";
const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/\/$/, "");
const WS_BASE = (import.meta.env.VITE_WS_BASE || API_BASE.replace(/^http/, "ws")).replace(/\/$/, "");
const prompts = [
  "What does a certificate of insurance prove?",
  "When should a renewal process begin?",
  "What is a waiver of subrogation?",
];

function renderCitations(content: string, policies: Policy[], onSelect: (policy: Policy) => void): ReactNode[] {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return part;
    const policy = policies.find((item) => item.id === match[1]);
    return policy ? (
      <button className="citation" key={`${part}-${index}`} onClick={() => onSelect(policy)} title={policy.title}>{part}</button>
    ) : part;
  });
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [draft, setDraft] = useState("");
  const [partial, setPartial] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);

  const loadSessions = useCallback(async () => {
    const response = await fetch(`${API_BASE}/chat/sessions?user_id=${USER_ID}`);
    if (response.ok) setSessions(await response.json());
  }, []);

  const connect = useCallback((id: string) => {
    socket.current?.close();
    const ws = new WebSocket(`${WS_BASE}/chat/ws/${id}?user_id=${USER_ID}`);
    socket.current = ws;
    ws.onopen = () => { setConnected(true); setError(null); };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setError("The streaming connection could not be established.");
    ws.onmessage = (event) => {
      const data: WsEvent = JSON.parse(event.data);
      if (data.type === "history") setMessages(data.history || []);
      if (data.type === "ack") { setStreaming(true); setPartial(""); }
      if (data.type === "token") setPartial((current) => current + (data.token || ""));
      if (data.type === "final") setPartial(data.text || "");
      if (data.type === "complete") {
        setPartial((answer) => {
          setMessages((current) => [...current, { role: "assistant", content: answer }]);
          return "";
        });
        setStreaming(false);
        loadSessions().catch(() => undefined);
      }
      if (data.type === "error") { setError(data.error || "Streaming failed"); setStreaming(false); }
    };
  }, [loadSessions]);

  const startSession = useCallback(async () => {
    setMessages([]);
    setPartial("");
    setSelectedPolicy(null);
    const response = await fetch(`${API_BASE}/chat/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID }),
    });
    if (!response.ok) throw new Error("Unable to create a chat session");
    const data = await response.json();
    setSessionId(data.session_id);
    connect(data.session_id);
  }, [connect]);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/chat/policies`).then((response) => response.json()),
      fetch(`${API_BASE}/chat/sessions?user_id=${USER_ID}`).then((response) => response.json()),
    ]).then(([policyData, sessionData]) => {
      setPolicies(policyData.policies || []);
      setSessions(sessionData || []);
    }).catch(() => setError("The API is unavailable. Start the backend and refresh."));
    startSession().catch((reason) => setError(reason.message));
    return () => socket.current?.close();
  }, [startSession]);

  useEffect(() => bottom.current?.scrollIntoView?.({ behavior: "smooth" }), [messages, partial]);

  const openSession = async (id: string) => {
    const response = await fetch(`${API_BASE}/chat/session/${id}?user_id=${USER_ID}`);
    if (!response.ok) return;
    const data = await response.json();
    setSessionId(id);
    setMessages(data.chat_history || []);
    setPartial("");
    connect(id);
  };

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || !sessionId || !connected || streaming) return;
    setMessages((current) => [...current, { role: "user", content }]);
    socket.current?.send(JSON.stringify({ type: "user_message", content }));
    setDraft("");
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo"><span>P</span><strong>PolicyLens</strong></div>
        <button className="new-chat" onClick={() => startSession().catch((reason) => setError(reason.message))}><span>＋</span> New conversation</button>
        <div className="sidebar-label">Recent</div>
        <nav className="sessions">
          {sessions.length === 0 && <p>No saved conversations yet.</p>}
          {sessions.map((session) => (
            <button key={session.session_id} className={session.session_id === sessionId ? "active" : ""} onClick={() => openSession(session.session_id)}>
              <span className="session-icon">◌</span><span>{session.title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer"><span className={connected ? "connection online" : "connection"} />{connected ? "Streaming connected" : "Connecting…"}</div>
      </aside>

      <main className="chat-shell">
        <header>
          <div><div className="kicker">Grounded policy assistant</div><h1>Ask a policy question</h1></div>
          <button className="library-button" onClick={() => setSelectedPolicy({ id: "library", title: "Source library", text: `${policies.length} policy documents are available for retrieval.` })}>Source library <span>{policies.length}</span></button>
        </header>

        <section className="conversation" aria-live="polite">
          {messages.length === 0 && !partial && (
            <div className="welcome">
              <div className="lens-mark">◎</div>
              <h2>Answers that show their work.</h2>
              <p>PolicyLens retrieves relevant passages, streams a grounded answer, and links every citation back to its source.</p>
              <div className="prompt-grid">
                {prompts.map((prompt) => <button key={prompt} onClick={() => setDraft(prompt)}><span>{prompt}</span><span>↗</span></button>)}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <article className={`message ${message.role}`} key={`${message.ts || "message"}-${index}`}>
              <div className="avatar">{message.role === "assistant" ? "P" : "You"}</div>
              <div><div className="message-author">{message.role === "assistant" ? "PolicyLens" : "You"}</div><p>{message.role === "assistant" ? renderCitations(message.content, policies, setSelectedPolicy) : message.content}</p></div>
            </article>
          ))}

          {streaming && (
            <article className="message assistant">
              <div className="avatar">P</div>
              <div><div className="message-author">PolicyLens <span className="thinking">retrieving</span></div><p>{partial ? renderCitations(partial, policies, setSelectedPolicy) : <span className="typing">● ● ●</span>}</p></div>
            </article>
          )}
          <div ref={bottom} />
        </section>

        {error && <div className="error-banner">{error}<button onClick={() => setError(null)}>Dismiss</button></div>}

        <form className="composer" onSubmit={submit}>
          <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } }} placeholder="Ask about coverage, documents, or process…" rows={1} />
          <button type="submit" disabled={!draft.trim() || !connected || streaming} aria-label="Send message">↑</button>
          <div className="composer-note">Responses are grounded in the sample source library. Verify policy details before acting.</div>
        </form>
      </main>

      {selectedPolicy && (
        <aside className="source-drawer">
          <button className="drawer-close" onClick={() => setSelectedPolicy(null)}>×</button>
          <div className="drawer-label">Source {selectedPolicy.id !== "library" && `[${selectedPolicy.id}]`}</div>
          <h2>{selectedPolicy.title}</h2>
          <p>{selectedPolicy.text}</p>
          {selectedPolicy.id !== "library" && <div className="source-meta"><span>Retrieved passage</span><span>Sample corpus</span></div>}
        </aside>
      )}
    </div>
  );
}
