import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../utils/api'

const QUICK_ACTIONS = [
  'Tóm tắt kết quả visit',
  'Điểm còn thiếu và rủi ro',
  'Nhận xét về giấy tờ pháp lý',
  'Ghi chú điểm bất thường',
]

function ModelBadge({ model }) {
  const isGpt = model?.startsWith('gpt')
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
      isGpt ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
    }`}>
      {isGpt ? 'GPT-4' : 'Sonnet'}
    </span>
  )
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'
  const gpt4 = msg.metadata_?.gpt4

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white text-sm rounded-2xl rounded-tr-sm px-3.5 py-2.5 leading-relaxed">
          {msg.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Sonnet */}
      <div className="flex items-start gap-2">
        <ModelBadge model="claude-sonnet" />
        <div className="flex-1 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {msg.content || <span className="text-gray-400 italic">Đang nhận...</span>}
        </div>
      </div>
      {/* GPT4 */}
      {gpt4 && (
        <div className="flex items-start gap-2">
          <ModelBadge model="gpt-4" />
          <div className="flex-1 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
            {gpt4}
          </div>
        </div>
      )}
    </div>
  )
}

// Streaming message — Sonnet token-by-token, GPT4 arrives later
function StreamingMessage({ sonnetText, gpt4Text }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <ModelBadge model="claude-sonnet" />
        <div className="flex-1 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
          {sonnetText || <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse rounded-sm" />}
        </div>
      </div>
      <div className="flex items-start gap-2">
        <ModelBadge model="gpt-4" />
        <div className="flex-1 bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm text-gray-500 leading-relaxed">
          {gpt4Text || <span className="italic text-gray-400">Đang chờ GPT-4...</span>}
        </div>
      </div>
    </div>
  )
}

function ExpandIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CollapseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M8 3v5H3M21 8h-5V3M3 16h5v5M16 21v-5h5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChatBody({ messages, streaming, sonnetStream, gpt4Stream, error, bottomRef, input, setInput, send, expanded }) {
  return (
    <>
      <div className={`overflow-y-auto px-1 py-2 space-y-4 ${expanded ? 'flex-1' : 'h-80'}`}>
        {messages.length === 0 && !streaming && !error && (
          <p className="text-xs text-gray-400 text-center mt-8">Chưa có tin nhắn nào</p>
        )}
        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        {streaming && <StreamingMessage sonnetText={sonnetStream} gpt4Text={gpt4Stream} />}
        {error && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length === 0 && !streaming && (
        <div className="flex flex-wrap gap-1.5 mt-3 mb-2">
          {QUICK_ACTIONS.map(q => (
            <button
              key={q}
              onClick={() => send(q)}
              className="text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full px-3 py-1.5 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
        <textarea
          rows={2}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Nhập câu hỏi... (Enter để gửi, Shift+Enter xuống dòng)"
          disabled={streaming}
          className="flex-1 text-sm border border-gray-200 rounded-xl px-3 py-2 resize-none focus:outline-none focus:border-blue-400 disabled:opacity-50"
        />
        <button
          onClick={() => send()}
          disabled={streaming || !input.trim()}
          className="flex-shrink-0 self-end bg-blue-600 hover:bg-blue-700 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 transition-colors"
        >
          {streaming ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
            </svg>
          ) : 'Gửi'}
        </button>
      </div>
    </>
  )
}

export default function ChatPanel({ conversationId, onMessageDone }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sonnetStream, setSonnetStream] = useState('')
  const [gpt4Stream, setGpt4Stream] = useState('')
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)
  const bottomRef = useRef(null)
  const abortRef = useRef(null)

  const loadMessages = useCallback(async () => {
    if (!conversationId) return
    try {
      const data = await api.listMessages(conversationId)
      setMessages(data)
    } catch (_) {}
  }, [conversationId])

  useEffect(() => {
    setMessages([])
    setSonnetStream('')
    setGpt4Stream('')
    setError('')
    loadMessages()
  }, [conversationId, loadMessages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sonnetStream, gpt4Stream])

  const send = async (text) => {
    const content = text || input.trim()
    if (!content || streaming || !conversationId) return
    setInput('')
    setError('')
    setStreaming(true)
    setSonnetStream('')
    setGpt4Stream('')

    // Optimistic user message
    const tempUser = { id: Date.now(), role: 'user', content, created_at: new Date().toISOString() }
    setMessages(prev => [...prev, tempUser])

    try {
      const ctrl = new AbortController()
      abortRef.current = ctrl
      const res = await fetch(`/api/v1/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
        signal: ctrl.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Lỗi ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let sonnet = ''
      let gpt4 = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'sonnet_token') { sonnet += evt.content; setSonnetStream(sonnet) }
          else if (evt.type === 'gpt4_done') { gpt4 = evt.content; setGpt4Stream(gpt4) }
          else if (evt.type === 'error') throw new Error(evt.message)
        }
      }

      await loadMessages()
      onMessageDone?.()
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      setStreaming(false)
      setSonnetStream('')
      setGpt4Stream('')
    }
  }

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && expanded) setExpanded(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

  if (!conversationId) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-gray-400">
        Chọn hoặc tạo hội thoại để bắt đầu
      </div>
    )
  }

  const sharedProps = { messages, streaming, sonnetStream, gpt4Stream, error, bottomRef, input, setInput, send }

  return (
    <>
      {/* Inline panel */}
      <div className="flex flex-col">
        <div className="flex justify-end mb-1">
          <button
            onClick={() => setExpanded(true)}
            title="Mở rộng"
            className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ExpandIcon /> Mở rộng
          </button>
        </div>
        <ChatBody {...sharedProps} expanded={false} />
      </div>

      {/* Overlay */}
      {expanded && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white rounded-2xl shadow-2xl flex flex-col w-full max-w-2xl h-[85vh]">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0">
              <span className="text-sm font-medium text-gray-700">Hội thoại với AI</span>
              <button
                onClick={() => setExpanded(false)}
                title="Thu gọn (Esc)"
                className="flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
              >
                <CollapseIcon /> Thu gọn
              </button>
            </div>
            <div className="flex flex-col flex-1 min-h-0 px-5 py-3">
              <ChatBody {...sharedProps} expanded={true} />
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
