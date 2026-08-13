import { useEffect, useRef, useState } from 'react'
import { api } from '../utils/api'

function fmt(usd) {
  if (usd === 0)    return '$0.000000'
  if (usd < 0.001)  return `$${usd.toFixed(6)}`
  if (usd < 0.01)   return `$${usd.toFixed(5)}`
  return `$${usd.toFixed(4)}`
}

function shortModel(name) {
  if (!name) return name
  if (name.startsWith('claude-sonnet')) return 'Sonnet'
  if (name.startsWith('claude-opus'))   return 'Opus'
  if (name.startsWith('claude-haiku'))  return 'Haiku'
  if (name.startsWith('gpt-4o-mini'))   return 'GPT-4o mini'
  if (name.startsWith('gpt-4o'))        return 'GPT-4o'
  if (name.startsWith('gpt-4'))         return 'GPT-4'
  return name
}

export default function CostBadge({ conversationId, refreshKey }) {
  const [data, setData]     = useState(null)
  const [open, setOpen]     = useState(false)
  const [pulse, setPulse]   = useState(false)
  const prevTotal           = useRef(null)

  useEffect(() => {
    if (!conversationId) return
    let cancelled = false

    const load = () =>
      api.getCost(conversationId)
        .then(d => {
          if (cancelled) return
          if (prevTotal.current !== null && d.total_usd > prevTotal.current) {
            setPulse(true)
            setTimeout(() => setPulse(false), 1200)
          }
          prevTotal.current = d.total_usd
          setData(d)
        })
        .catch(() => {})

    load()
    const id = setInterval(load, 20_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [conversationId, refreshKey])

  if (!data) return null

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {/* Breakdown panel */}
      {open && (
        <div className="mb-2 bg-white border border-gray-200 rounded-xl shadow-xl p-3 min-w-[220px]">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Chi phí AI — hội thoại này
          </p>
          {data.breakdown?.length ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[10px] text-gray-400">
                  <th className="text-left pb-1 font-normal">Model</th>
                  <th className="text-right pb-1 font-normal">Token in</th>
                  <th className="text-right pb-1 font-normal">Token out</th>
                  <th className="text-right pb-1 font-normal">USD</th>
                </tr>
              </thead>
              <tbody>
                {data.breakdown.map(r => (
                  <tr key={r.model} className="border-t border-gray-50">
                    <td className="py-1 pr-2 text-gray-700 font-medium">{shortModel(r.model)}</td>
                    <td className="py-1 text-right text-gray-500 tabular-nums">{r.input_tokens.toLocaleString()}</td>
                    <td className="py-1 text-right text-gray-500 tabular-nums px-2">{r.output_tokens.toLocaleString()}</td>
                    <td className="py-1 text-right text-gray-800 font-mono tabular-nums">{fmt(r.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-200">
                  <td colSpan={3} className="pt-1.5 text-gray-500 text-[11px]">Tổng</td>
                  <td className="pt-1.5 text-right font-mono font-semibold text-gray-900">{fmt(data.total_usd)}</td>
                </tr>
              </tfoot>
            </table>
          ) : (
            <p className="text-xs text-gray-400">Chưa có dữ liệu</p>
          )}
          <p className="text-[9px] text-gray-300 mt-2">* Chỉ tính chat, chưa tính phân tích ảnh</p>
        </div>
      )}

      {/* Badge button */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-2 px-3 py-2 rounded-full shadow-lg border bg-white
          border-gray-200 text-gray-700 transition-all duration-300 hover:shadow-xl
          ${pulse ? 'ring-2 ring-green-400 ring-offset-1' : ''}
          ${open ? 'border-blue-300 text-blue-700' : ''}`}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v2m0 8v2M9.5 9.5h3a1.5 1.5 0 0 1 0 3h-3m0 0h3.5a1.5 1.5 0 0 1 0 3H9.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-[11px] font-mono font-medium tracking-tight">{fmt(data.total_usd)}</span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}>
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  )
}
