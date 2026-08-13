import { useEffect, useState, useCallback } from 'react'
import { useVisitSocket } from '../hooks/useVisitSocket'
import { api } from '../utils/api'
import ChecklistItem from '../components/ChecklistItem'
import PhotoCard from '../components/PhotoCard'
import UploadZone from '../components/UploadZone'
import ConversationSidebar from '../components/ConversationSidebar'
import ChatPanel from '../components/ChatPanel'

const CONNECTION_META = {
  connected:    { color: 'bg-status-done',    label: 'Đang theo dõi' },
  connecting:   { color: 'bg-status-pending', label: 'Đang kết nối...' },
  disconnected: { color: 'bg-status-missing', label: 'Mất kết nối — đang thử lại' },
}

function VisitMain({ visitId }) {
  const [checklist, setChecklist] = useState(null)
  const [visit, setVisit]         = useState(null)
  const [photos, setPhotos]       = useState([])
  const { connectionStatus, lastEvent } = useVisitSocket(visitId)

  const refreshChecklist = useCallback(async () => {
    try { setChecklist(await api.getChecklist(visitId)) } catch (_) {}
  }, [visitId])

  const refreshPhotos = useCallback(async () => {
    try { setPhotos(await api.listPhotos(visitId)) } catch (_) {}
  }, [visitId])

  useEffect(() => {
    refreshChecklist()
    refreshPhotos()
    api.getVisit(visitId).then(setVisit).catch(() => {})
  }, [visitId, refreshChecklist, refreshPhotos])

  useEffect(() => {
    if (!lastEvent) return
    if (lastEvent.type === 'checklist_update' || lastEvent.type === 'photo_processed') {
      refreshChecklist()
      refreshPhotos()
    }
  }, [lastEvent, refreshChecklist, refreshPhotos])

  useEffect(() => {
    const id = setInterval(() => { refreshChecklist(); refreshPhotos() }, 30000)
    return () => clearInterval(id)
  }, [refreshChecklist, refreshPhotos])

  const conn = CONNECTION_META[connectionStatus]
  const total = checklist ? checklist.completed.length + checklist.missing.length + checklist.optional_missing.length : 0
  const pct   = checklist && total > 0 ? Math.round((checklist.completed.length / total) * 100) : 0

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-base text-gray-900">
            Site visit — {checklist?.visit_type || '...'}
          </p>
          <p className="text-sm text-gray-500 mt-0.5">
            {visit ? new Date(visit.visit_date).toLocaleDateString('vi-VN') : '...'}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${conn.color}`} />
          <span className="text-xs text-gray-500">{conn.label}</span>
        </div>
      </div>

      <UploadZone visitId={visitId} />

      {/* Progress */}
      {checklist && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-sm text-gray-500">Tiến độ checklist</span>
            <span className="text-xl font-medium">{checklist.progress}</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-status-done rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {/* Checklist */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Checklist yêu cầu</p>
        <div className="flex flex-col gap-2">
          {checklist?.items.map(item => <ChecklistItem key={item.photo_type} item={item} />)}
          {!checklist && <p className="text-sm text-gray-400 text-center py-6">Đang tải...</p>}
        </div>
      </div>

      {/* Photos */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Ảnh đã upload</p>
          <span className="text-xs text-gray-400">{photos.length} ảnh</span>
        </div>
        <div className="flex flex-col gap-2">
          {photos.map(photo => <PhotoCard key={photo.id} photo={photo} />)}
          {photos.length === 0 && <p className="text-sm text-gray-400 text-center py-6">Chưa có ảnh nào</p>}
        </div>
      </div>
    </div>
  )
}

export default function VisitChecklist({ visitId, convId }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <ConversationSidebar visitId={visitId} activeId={convId} />

      <main className="flex-1 overflow-y-auto">
        {convId ? (
          /* Chế độ hội thoại — chỉ hiện chat */
          <div className="max-w-2xl mx-auto px-4 py-6">
            <ChatPanel conversationId={convId} />
          </div>
        ) : (
          /* Chế độ visit — hiện checklist + ảnh */
          <VisitMain visitId={visitId} />
        )}
      </main>
    </div>
  )
}
