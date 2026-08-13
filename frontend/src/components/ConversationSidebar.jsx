import { useState, useEffect, useCallback } from 'react'
import { api } from '../utils/api'

const VISIT_TYPE_LABELS = {
  standard:  'Tiêu chuẩn',
  warehouse: 'Kho',
  factory:   'Nhà máy',
}

function formatTime(iso) {
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Ho_Chi_Minh',
  })
}

export default function ConversationSidebar({ activeId }) {
  const [conversations, setConversations] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [visitType, setVisitType] = useState('standard')
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    try { setConversations(await api.listConversations()) } catch (_) {}
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    setCreating(true)
    try {
      const conv = await api.createConversation(title.trim(), visitType)
      window.location.href = `?conv_id=${conv.id}`
    } catch (e) {
      alert(e.message)
      setCreating(false)
    }
  }

  return (
    <aside className="w-56 flex-shrink-0 bg-gray-50 border-r border-gray-200 flex flex-col min-h-screen">
      {/* New conversation */}
      <div className="p-3 border-b border-gray-200">
        {showForm ? (
          <div className="space-y-2">
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Escape') { setShowForm(false); setTitle('') } }}
              placeholder="Tên hội thoại (tùy chọn)"
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:border-blue-400"
            />
            <select
              value={visitType}
              onChange={e => setVisitType(e.target.value)}
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:border-blue-400 bg-white"
            >
              {Object.entries(VISIT_TYPE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <div className="flex gap-1.5">
              <button
                onClick={handleCreate}
                disabled={creating}
                className="flex-1 text-xs bg-blue-600 text-white rounded px-2 py-1.5 hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? 'Đang tạo...' : 'Tạo'}
              </button>
              <button
                onClick={() => { setShowForm(false); setTitle('') }}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5"
              >
                Hủy
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowForm(true)}
            className="w-full flex items-center gap-2 text-xs font-medium text-blue-600 hover:text-blue-800 py-1"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
            Hội thoại mới
          </button>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 && (
          <p className="text-[11px] text-gray-400 text-center mt-8 px-3">Chưa có hội thoại nào</p>
        )}
        {conversations.map(conv => (
          <a
            key={conv.id}
            href={`?conv_id=${conv.id}`}
            className={`block px-3 py-2.5 border-b border-gray-100 hover:bg-gray-100 transition-colors no-underline ${
              activeId === conv.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
            }`}
          >
            <p className={`text-xs font-medium truncate ${activeId === conv.id ? 'text-blue-700' : 'text-gray-800'}`}>
              {conv.title || 'Hội thoại'}
            </p>
            <div className="flex items-center gap-1.5 mt-0.5">
              {conv.visit_type && (
                <span className="text-[9px] bg-gray-200 text-gray-500 px-1 rounded">
                  {VISIT_TYPE_LABELS[conv.visit_type] || conv.visit_type}
                </span>
              )}
              <span className="text-[10px] text-gray-400">{formatTime(conv.updated_at)}</span>
            </div>
          </a>
        ))}
      </div>
    </aside>
  )
}
