import { useState, useEffect, useRef, useCallback } from 'react'

const API_BASE = '/api/v1'

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// ── Sub-components ────────────────────────────────────────────────────────────
function StatusBadge({ label, status }) {
  const up = status === 'up'
  return (
    <span className={`badge ${up ? 'badge-up' : 'badge-down'}`}>
      <span className="badge-dot" />
      {label}: {status}
    </span>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`message-row ${isUser ? 'user-row' : 'ai-row'}`}>
      <div className={`message-bubble ${isUser ? 'user-bubble' : 'ai-bubble'}`}>
        {msg.content}
        {msg.sources && msg.sources.length > 0 && (
          <p className="sources">Sources: {msg.sources.join(', ')}</p>
        )}
        <div className="message-meta">
          {msg.time}
          {!isUser && msg.model && (
            <span className="model-tag">{msg.model}</span>
          )}
          {!isUser && msg.cache_hit && (
            <span className="cache-tag">⚡ cached</span>
          )}
          {!isUser && msg.fallback && (
            <span className="fallback-tag">⚠ fallback</span>
          )}
        </div>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="message-row ai-row">
      <div className="message-bubble ai-bubble typing">
        <span /><span /><span />
      </div>
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Hello! I am your production-grade AI assistant. Ask me anything, or upload a document first to enable RAG.', time: formatTime(), model: '', cache_hit: false, fallback: false }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [modelType, setModelType] = useState('gemini')
  const [useRag, setUseRag] = useState(true)
  const [health, setHealth] = useState({ redis: '…', ollama: '…' })
  const [uploadStatus, setUploadStatus] = useState(null)
  const [temperature, setTemperature] = useState(0.7)

  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Poll health every 10s
  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      if (res.ok) {
        const data = await res.json()
        setHealth({ redis: data.redis, ollama: data.ollama })
      }
    } catch {
      setHealth({ redis: 'down', ollama: 'down' })
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 10000)
    return () => clearInterval(id)
  }, [fetchHealth])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text, time: formatTime() }])
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, model_type: modelType, temperature, use_rag: useRag })
      })
      if (res.status === 429) {
        setMessages(prev => [...prev, { role: 'ai', content: '⛔ Rate limit exceeded. Please wait a moment before sending more messages.', time: formatTime(), model: '', cache_hit: false, fallback: false }])
        return
      }
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Unknown error')
      setMessages(prev => [...prev, {
        role: 'ai',
        content: data.reply,
        time: formatTime(),
        model: data.model_used,
        cache_hit: data.cache_hit,
        fallback: data.fallback_used,
        sources: data.sources
      }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'ai', content: `❌ Error: ${e.message}`, time: formatTime(), model: '', cache_hit: false, fallback: false }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const uploadFile = async () => {
    const file = fileRef.current?.files[0]
    if (!file) return
    setUploadStatus('uploading')
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/ingest/file`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setUploadStatus('success')
    } catch (e) {
      setUploadStatus('error')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
      setTimeout(() => setUploadStatus(null), 3000)
    }
  }

  return (
    <div className="layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">✦</span>
          <span className="logo-text">AI Studio</span>
        </div>

        <div className="section-label">System Status</div>
        <div className="health-row">
          <StatusBadge label="Redis" status={health.redis} />
          <StatusBadge label="Ollama" status={health.ollama} />
        </div>

        <div className="section-label">Model</div>
        <select className="select" value={modelType} onChange={e => setModelType(e.target.value)}>
          <option value="gemini">☁ Gemini API (Cloud)</option>
          <option value="ollama">🖥 Ollama (Local CPU)</option>
        </select>

        <div className="section-label">Temperature: {temperature}</div>
        <input type="range" min="0" max="1" step="0.1" value={temperature} onChange={e => setTemperature(parseFloat(e.target.value))} className="slider" />

        <div className="toggle-row">
          <label>Enable RAG</label>
          <div className={`toggle ${useRag ? 'toggle-on' : ''}`} onClick={() => setUseRag(v => !v)}>
            <div className="toggle-thumb" />
          </div>
        </div>

        <div className="section-label">Knowledge Base</div>
        <input ref={fileRef} type="file" accept=".pdf,.txt" className="file-input" />
        <button className="btn btn-secondary" onClick={uploadFile}>
          {uploadStatus === 'uploading' ? 'Ingesting…' : 'Ingest File'}
        </button>
        {uploadStatus === 'success' && <p className="status-ok">✓ Ingested successfully</p>}
        {uploadStatus === 'error' && <p className="status-err">✗ Ingestion failed</p>}
      </aside>

      {/* ── Main Chat ── */}
      <main className="chat-area">
        <div className="chat-header">
          <h1>AI Assistant</h1>
          <span className="sub">Production-grade · Cached · Resilient</span>
        </div>

        <div className="messages">
          {messages.map((m, i) => <Message key={i} msg={m} />)}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        <div className="input-bar">
          <textarea
            className="input-field"
            rows={1}
            placeholder="Type your message… (Enter to send)"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button className="btn btn-primary" onClick={sendMessage} disabled={loading || !input.trim()}>
            {loading ? '…' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  )
}
