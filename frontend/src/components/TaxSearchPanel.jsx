import { useEffect, useState } from 'react'
import { api } from '../utils/api'

export default function TaxSearchPanel({ visitId }) {
  const [data, setData]       = useState(null)   // null = chưa fetch
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!visitId) return
    let cancelled = false
    setLoading(true)
    setData(null)
    api.getTaxSearch(visitId)
      .then(d => { if (!cancelled) setData(d) })
      .catch(() => { if (!cancelled) setData({ mst: null, results: [] }) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [visitId])

  // Chưa fetch hoặc không có MST
  if (!loading && (!data || !data.mst)) return null

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" strokeLinecap="round" />
        </svg>
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Kết quả tìm kiếm MST
        </span>
        {data?.mst && (
          <span className="ml-auto text-[11px] font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
            {data.mst}
          </span>
        )}
      </div>

      {loading ? (
        <div className="px-4 py-3 space-y-2">
          {[1,2,3].map(i => (
            <div key={i} className="h-3 bg-gray-100 rounded animate-pulse" style={{ width: `${70 - i*10}%` }} />
          ))}
        </div>
      ) : data?.results?.length === 0 ? (
        <p className="text-xs text-gray-400 px-4 py-3">Không tìm thấy kết quả</p>
      ) : (
        <ol className="px-4 py-3 space-y-2.5">
          {data.results.map((r, i) => (
            <li key={i} className="flex gap-2.5">
              <span className="text-[11px] text-gray-400 w-4 flex-shrink-0 pt-0.5">{i + 1}.</span>
              <div className="min-w-0">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline break-all"
                >
                  {r.url}
                </a>
                {r.snippet && (
                  <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{r.snippet}</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
