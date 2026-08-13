const API_BASE = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Conversations
  listConversations:  ()              => request('/conversations'),
  getConversation:    (convId)        => request(`/conversations/${convId}`),
  createConversation: (title, visitType) => request('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title: title || '', visit_type: visitType || 'standard' }),
  }),
  listMessages: (convId) => request(`/conversations/${convId}/messages`),
  getCost:      (convId) => request(`/conversations/${convId}/cost`),

  // Visit / Checklist / Photos (dùng visitId từ conversation)
  getVisit:      (visitId) => request(`/visits/${visitId}`),
  getChecklist:  (visitId) => request(`/visits/${visitId}/checklist`),
  listPhotos:    (visitId) => request(`/visits/${visitId}/photos`),
  getPhotoDetail:(photoId) => request(`/photos/${photoId}`),
  getTaxSearch:  (visitId) => request(`/visits/${visitId}/tax-search`),

  uploadPhotos: (visitId, files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request(`/visits/${visitId}/photos`, { method: 'POST', body: formData })
  },
}
