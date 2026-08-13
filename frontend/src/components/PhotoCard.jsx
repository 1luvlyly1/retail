import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../utils/api'

function Lightbox({ src, alt, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <img
        src={src}
        alt={alt}
        className="max-w-[90vw] max-h-[90vh] object-contain rounded shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>,
    document.body
  )
}

const STATUS_META = {
  pending: { label: 'Đang xử lý', color: 'bg-status-pending-bg text-status-pending', spin: true },
  done:    { label: 'Xong',        color: 'bg-status-done-bg text-status-done',    spin: false },
  failed:  { label: 'Lỗi',         color: 'bg-red-100 text-red-600',               spin: false },
}

function parseAiJson(raw) {
  if (!raw) return null
  try {
    const cleaned = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```\s*$/m, '').trim()
    const m = cleaned.match(/\{[\s\S]*\}/)
    if (m) return JSON.parse(m[0])
  } catch (_) {}
  const get = (key) => {
    const m = raw.match(new RegExp(`"${key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`, 's'))
    return m ? m[1].replace(/\\n/g, '\n') : null
  }
  const phan_loai = get('phan_loai')
  if (!phan_loai) return null
  return { phan_loai, mo_ta: get('mo_ta'), ocr_text: get('ocr_text'), bat_thuong: get('bat_thuong') }
}

function AiBlock({ step, model, raw, highlight }) {
  const parsed = parseAiJson(raw)
  return (
    <div className={`rounded border ${highlight ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-white'} p-2.5 space-y-1.5`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">{step}</span>
        <span className="text-[10px] text-gray-400">{model}</span>
      </div>
      {parsed ? (
        <>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-400">Phân loại:</span>
            <span className="text-xs font-medium text-gray-900 bg-gray-100 px-1.5 py-0.5 rounded">
              {parsed.phan_loai || '—'}
            </span>
          </div>
          {parsed.mo_ta && (
            <div>
              <p className="text-[10px] text-gray-400 mb-0.5">Mô tả</p>
              <p className="text-xs text-gray-700 leading-relaxed">{parsed.mo_ta}</p>
            </div>
          )}
          {parsed.ocr_text && (
            <div>
              <p className="text-[10px] text-gray-400 mb-0.5">OCR</p>
              <p className="text-xs text-gray-600 font-mono leading-relaxed whitespace-pre-wrap">{parsed.ocr_text}</p>
            </div>
          )}
          {parsed.bat_thuong && (
            <p className="text-xs text-amber-700">⚠ {parsed.bat_thuong}</p>
          )}
        </>
      ) : (
        <pre className="text-[10px] text-gray-500 whitespace-pre-wrap break-all leading-relaxed max-h-32 overflow-y-auto">{raw}</pre>
      )}
    </div>
  )
}

export default function PhotoCard({ photo }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [lightbox, setLightbox] = useState(false)

  const statusMeta = STATUS_META[photo.processing_status] || STATUS_META.pending

  const handleExpand = async () => {
    if (!expanded && !detail) {
      setLoading(true)
      try {
        const d = await api.getPhotoDetail(photo.id)
        setDetail(d)
      } catch (_) {}
      setLoading(false)
    }
    setExpanded(v => !v)
  }

  const canExpand = photo.processing_status === 'done'

  return (
    <div className="rounded-lg bg-white border border-gray-200 overflow-hidden">
      <div className="flex items-start gap-3 p-3">
        {/* Thumbnail */}
        <div className="flex-shrink-0 w-16 h-16 rounded-md overflow-hidden bg-gray-100 border border-gray-200">
          {photo.gdrive_url ? (
            <img
              src={photo.gdrive_url}
              alt={photo.original_filename}
              className="w-full h-full object-cover hover:opacity-80 transition-opacity cursor-zoom-in"
              loading="lazy"
              onClick={() => setLightbox(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="m21 15-5-5L5 21" />
              </svg>
            </div>
          )}
        </div>

        {lightbox && (
          <Lightbox
            src={photo.gdrive_url}
            alt={photo.original_filename}
            onClose={() => setLightbox(false)}
          />
        )}

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs font-medium text-gray-900 truncate">{photo.original_filename}</p>
            {canExpand && (
              <button
                onClick={handleExpand}
                className="flex-shrink-0 text-gray-400 hover:text-gray-600 p-0.5 rounded"
                title="Xem toàn bộ xử lý AI"
              >
                {loading ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    className={`transition-transform ${expanded ? 'rotate-180' : ''}`}>
                    <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            )}
          </div>

          <div className="flex items-center flex-wrap gap-1.5 mt-1">
            <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded ${statusMeta.color}`}>
              {statusMeta.spin && (
                <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
                </svg>
              )}
              {statusMeta.label}
            </span>
            {photo.photo_type && (
              <span className="text-[10px] bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded font-medium">
                {photo.photo_type}
              </span>
            )}
            {photo.confidence_score != null && (
              <span className="text-[10px] text-gray-400">{Math.round(photo.confidence_score * 100)}% tin cậy</span>
            )}
            {photo.models_agreed === false && (
              <span className="text-[10px] text-purple-600 font-medium">Opus</span>
            )}
            {photo.processing_time_s != null && (
              <span className="text-[10px] text-gray-400">{photo.processing_time_s}s</span>
            )}
          </div>

          {photo.final_description && (
            <p className="text-[11px] text-gray-500 mt-1 leading-relaxed line-clamp-2">
              {photo.final_description}
            </p>
          )}
        </div>
      </div>

      {/* AI pipeline detail */}
      {expanded && detail && (
        <div className="border-t border-gray-100 bg-gray-50 px-3 py-3 space-y-2">
          <AiBlock
            step="Bước 1 — Sonnet"
            model="claude-sonnet"
            raw={detail.sonnet_description}
            highlight={detail.models_agreed !== false}
          />
          <AiBlock
            step="Bước 2 — GPT-4o"
            model="gpt-4o"
            raw={detail.gpt4_description}
            highlight={false}
          />
          {detail.models_agreed != null && (
            <div className={`rounded border p-2.5 space-y-1.5 ${detail.models_agreed ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50'}`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Bước 3 — So sánh</span>
                <span className={`text-[10px] font-medium ${detail.models_agreed ? 'text-green-700' : 'text-yellow-700'}`}>
                  {detail.models_agreed ? '✓ Đồng thuận' : '✗ Không đồng thuận → Opus'}
                </span>
              </div>
              {detail.confidence_score != null && (
                <p className="text-xs text-gray-600">Độ tin cậy: {Math.round(detail.confidence_score * 100)}%</p>
              )}
              {detail.comparison_notes && (
                <p className="text-xs text-gray-600 italic">{detail.comparison_notes}</p>
              )}
            </div>
          )}
          {detail.opus_description && (
            <AiBlock
              step="Bước 4 — Opus (tiebreaker)"
              model="claude-opus"
              raw={detail.opus_description}
              highlight
            />
          )}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">Kết quả cuối:</span>
            <span className="text-xs font-semibold text-gray-900 bg-gray-200 px-2 py-0.5 rounded">
              {detail.photo_type || 'khác'}
            </span>
            {detail.models_agreed != null && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${detail.models_agreed ? 'bg-green-100 text-green-700' : 'bg-purple-100 text-purple-700'}`}>
                {detail.models_agreed ? 'từ Sonnet' : 'từ Opus'}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
