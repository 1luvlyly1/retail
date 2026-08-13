import { useState } from 'react'
import { api } from '../utils/api'

const STATUS_META = {
  done: {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M20 6 9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    bg: 'bg-status-done-bg',
    fg: 'text-status-done',
    label: 'Đã chụp',
  },
  pending: {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="animate-spin">
        <path d="M21 12a9 9 0 1 1-6.219-8.56" strokeLinecap="round" />
      </svg>
    ),
    bg: 'bg-status-pending-bg',
    fg: 'text-status-pending',
    label: 'Đang xử lý',
  },
  missing: {
    icon: (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <path d="M12 9v4M12 17h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    bg: 'bg-status-missing-bg',
    fg: 'text-status-missing',
    label: 'Còn thiếu',
  },
}

// Strip ```json ... ``` fences and parse JSON, return null on failure
function parseAiJson(raw) {
  if (!raw) return null
  try {
    const cleaned = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```\s*$/m, '').trim()
    const m = cleaned.match(/\{[\s\S]*\}/)
    if (m) return JSON.parse(m[0])
  } catch (_) {}
  // Fallback: extract individual fields via regex
  const get = (key) => {
    const m = raw.match(new RegExp(`"${key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`, 's'))
    return m ? m[1].replace(/\\n/g, '\n') : null
  }
  const phan_loai = get('phan_loai')
  if (!phan_loai) return null
  return { phan_loai, mo_ta: get('mo_ta'), ocr_text: get('ocr_text'), bat_thuong: get('bat_thuong') }
}

// Extract comparison result from raw judge text
function parseCompare(raw) {
  if (!raw) return null
  try {
    const m = raw.match(/\{[\s\S]*\}/)
    if (m) return JSON.parse(m[0])
  } catch (_) {}
  return null
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

function CompareBlock({ raw, agreed, confidence }) {
  const color = agreed ? 'border-green-200 bg-green-50' : 'border-yellow-200 bg-yellow-50'
  return (
    <div className={`rounded border ${color} p-2.5 space-y-1.5`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Bước 3 — So sánh (Judge)</span>
        <span className={`text-[10px] font-medium ${agreed ? 'text-green-700' : 'text-yellow-700'}`}>
          {agreed ? '✓ Đồng thuận' : '✗ Không đồng thuận → Opus xử lý'}
        </span>
      </div>
      {confidence != null && (
        <p className="text-xs text-gray-600">Độ tin cậy: {Math.round(confidence * 100)}%</p>
      )}
      {raw && <p className="text-xs text-gray-600 italic">{raw}</p>}
    </div>
  )
}

export default function ChecklistItem({ item }) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const meta = STATUS_META[item.is_completed ? 'done' : item.status === 'pending' ? 'pending' : 'missing']

  const handleExpand = async () => {
    if (!expanded && item.photo_id && !detail) {
      setLoading(true)
      try {
        const d = await api.getPhotoDetail(item.photo_id)
        setDetail(d)
      } catch (_) {}
      setLoading(false)
    }
    setExpanded(v => !v)
  }

  const canExpand = item.is_completed && item.photo_id

  return (
    <div className="rounded-lg bg-white border border-gray-200 overflow-hidden">
      <div className="flex items-center gap-3 px-3 py-2.5">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${meta.bg} ${meta.fg}`}>
          {meta.icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-900 truncate">{item.description || item.photo_type}</p>
          <p className="text-xs text-gray-500 truncate">{item.photo_type}</p>
        </div>
        <div className="text-right flex-shrink-0 flex items-center gap-2">
          <div>
            <span className={`text-xs ${meta.fg}`}>{meta.label}</span>
            {item.confidence_score != null && (
              <p className="text-[11px] text-gray-400 mt-0.5">
                {Math.round(item.confidence_score * 100)}% tin cậy
              </p>
            )}
          </div>
          {canExpand && (
            <button
              onClick={handleExpand}
              className="text-gray-400 hover:text-gray-600 p-1 rounded"
              title={expanded ? 'Ẩn chi tiết AI' : 'Xem toàn bộ xử lý AI'}
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
      </div>

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
            <CompareBlock
              raw={detail.comparison_notes}
              agreed={detail.models_agreed}
              confidence={detail.confidence_score}
            />
          )}
          {detail.opus_description && (
            <AiBlock
              step="Bước 4 — Opus (tiebreaker)"
              model="claude-opus"
              raw={detail.opus_description}
              highlight={true}
            />
          )}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[10px] text-gray-400 uppercase tracking-wide">Kết quả cuối:</span>
            <span className="text-xs font-semibold text-gray-900 bg-gray-200 px-2 py-0.5 rounded">
              {detail.photo_type}
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
