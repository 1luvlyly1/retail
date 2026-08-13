import { useEffect, useState, useCallback } from 'react'
import { useVisitSocket } from '../hooks/useVisitSocket'
import { api } from '../utils/api'
import ChecklistItem from '../components/ChecklistItem'
import PhotoCard from '../components/PhotoCard'
import UploadZone from '../components/UploadZone'
import ChatPanel from '../components/ChatPanel'
import TaxSearchPanel from '../components/TaxSearchPanel'
import CostBadge from '../components/CostBadge'

const CONNECTION_META = {
  connected:    { color: 'bg-status-done',    label: 'Đang theo dõi' },
  connecting:   { color: 'bg-status-pending', label: 'Đang kết nối...' },
  disconnected: { color: 'bg-status-missing', label: 'Mất kết nối — đang thử lại' },
}

export default function ConversationPage({ convId }) {
  const [conv, setConv]           = useState(null)
  const [checklist, setChecklist] = useState(null)
  const [photos, setPhotos]       = useState([])
  const [loading, setLoading]     = useState(true)
  const [costKey, setCostKey]     = useState(0)

  const visitId = conv?.visit_id

  const refreshChecklist = useCallback(async () => {
    if (!visitId) return
    try { setChecklist(await api.getChecklist(visitId)) } catch (_) {}
  }, [visitId])

  const refreshPhotos = useCallback(async () => {
    if (!visitId) return
    try { setPhotos(await api.listPhotos(visitId)) } catch (_) {}
  }, [visitId])

  // Load conversation → lấy visitId
  useEffect(() => {
    setLoading(true)
    api.getConversation(convId)
      .then(setConv)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [convId])

  // Load checklist + photos khi có visitId
  useEffect(() => {
    if (!visitId) return
    refreshChecklist()
    refreshPhotos()
  }, [visitId, refreshChecklist, refreshPhotos])

  const { connectionStatus, lastEvent } = useVisitSocket(visitId || '')

  useEffect(() => {
    if (!lastEvent) return
    if (lastEvent.type === 'photo_processed' || lastEvent.type === 'checklist_update') {
      refreshChecklist()
      refreshPhotos()
    }
  }, [lastEvent, refreshChecklist, refreshPhotos])

  useEffect(() => {
    const id = setInterval(() => { refreshChecklist(); refreshPhotos() }, 30000)
    return () => clearInterval(id)
  }, [refreshChecklist, refreshPhotos])

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-sm text-gray-400">Đang tải...</div>
  }

  if (!conv) {
    return <div className="flex items-center justify-center h-64 text-sm text-red-500">Không tìm thấy hội thoại</div>
  }

  const conn = CONNECTION_META[connectionStatus]
  const total = checklist ? checklist.completed.length + checklist.missing.length + checklist.optional_missing.length : 0
  const pct   = checklist && total > 0 ? Math.round((checklist.completed.length / total) * 100) : 0
  const hasVerified = checklist && checklist.completed.length > 0

  return (
    <>
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-base text-gray-900">{conv.title}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {conv.visit_type} · {new Date(conv.created_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })}
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0 mt-1">
          <span className={`w-2 h-2 rounded-full ${conn.color}`} />
          <span className="text-xs text-gray-500">{conn.label}</span>
        </div>
      </div>

      {/* 1. Upload */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Upload ảnh</p>
        <UploadZone visitId={visitId} />
      </div>

      {/* 2. Checklist */}
      {checklist && (
        <div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-3">
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm text-gray-500">Tiến độ checklist</span>
              <span className="text-xl font-medium">{checklist.progress}</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-status-done rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            {checklist.items.map(item => <ChecklistItem key={item.photo_type} item={item} />)}
          </div>
        </div>
      )}

      {/* 3. Chat */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Hỏi AI về kết quả phân tích
        </p>
        {hasVerified ? (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <ChatPanel conversationId={convId} onMessageDone={() => setCostKey(k => k + 1)} />
          </div>
        ) : (
          <div className="bg-gray-50 border border-dashed border-gray-300 rounded-lg px-4 py-6 text-center">
            <p className="text-sm text-gray-500">
              Cần ít nhất 1 mục trong checklist được xác thực trước khi chat với AI
            </p>
            <p className="text-xs text-gray-400 mt-1">Upload ảnh và chờ AI phân tích</p>
          </div>
        )}
      </div>

      {/* 4. Kết quả tìm kiếm MST */}
      <TaxSearchPanel visitId={visitId} />

      {/* 5. Phân tích pipeline từng ảnh */}
      {photos.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Phân tích hình ảnh</p>
            <span className="text-xs text-gray-400">{photos.length} ảnh</span>
          </div>
          <div className="h-96 overflow-y-auto px-4 py-3 space-y-3">
            {photos.map(photo => <PhotoCard key={photo.id} photo={photo} />)}
          </div>
        </div>
      )}

    </div>

    <CostBadge conversationId={convId} refreshKey={costKey} />
    </>
  )
}
