import { useRef, useState } from 'react'
import { api } from '../utils/api'

const QUEUE_STATUS_META = {
  uploading: { text: 'Đang gửi...', color: 'text-gray-500' },
  processing: { text: 'AI đang phân tích...', color: 'text-status-pending' },
  done: { text: 'Hoàn tất', color: 'text-status-done' },
  error: { text: 'Lỗi tải lên', color: 'text-status-missing' },
}

export default function UploadZone({ visitId, onUploaded, doneFilenames }) {
  const inputRef = useRef(null)
  const [queue, setQueue] = useState([])

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || [])
    if (files.length === 0) return

    const entries = files.map((file) => ({
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      name: file.name,
      url: URL.createObjectURL(file),
      status: 'uploading',
    }))
    setQueue((prev) => [...entries, ...prev])

    try {
      const uploaded = await api.uploadPhotos(visitId, files)
      setQueue((prev) =>
        prev.map((e) => (entries.find((ne) => ne.id === e.id) ? { ...e, status: 'processing' } : e))
      )
      onUploaded?.(uploaded)
      setTimeout(() => {
        setQueue((prev) =>
          prev.map((e) =>
            entries.find((ne) => ne.id === e.id) && e.status === 'processing'
              ? { ...e, status: 'done' }
              : e
          )
        )
      }, 30000)
    } catch (err) {
      setQueue((prev) =>
        prev.map((e) => (entries.find((ne) => ne.id === e.id) ? { ...e, status: 'error', error: err.message } : e))
      )
    }
  }

  return (
    <div className="mb-5">
      <label
        htmlFor="photo-input"
        className="flex flex-col items-center justify-center gap-1.5 px-4 py-6 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer text-center hover:border-gray-400 transition-colors"
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-gray-500">
          <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="12" cy="13" r="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-sm text-gray-900">Chụp ảnh hoặc chọn từ thư viện</span>
        <span className="text-xs text-gray-400">JPG, PNG, HEIC — tối đa 20MB mỗi ảnh</span>
        <input
          ref={inputRef}
          id="photo-input"
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </label>

      {queue.length > 0 && (
        <div className="flex flex-col gap-2 mt-3">
          {queue.map((entry) => {
            const isDone = entry.status === 'processing' && doneFilenames?.has(entry.name)
            const effectiveStatus = isDone ? 'done' : entry.status
            const meta = QUEUE_STATUS_META[effectiveStatus]
            return (
              <div
                key={entry.id}
                className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-white border border-gray-200"
              >
                <img src={entry.url} alt={entry.name} className="w-9 h-9 rounded object-cover flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{entry.name}</p>
                  <p className={`text-xs mt-0.5 ${meta.color}`}>{meta.text}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
