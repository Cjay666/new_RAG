import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

// ── Knowledge Base ─────────────────────────────────
export const kbAPI = {
  list: () => api.get('/kb/'),
  create: (data) => api.post('/kb/', data),
  delete: (kbId) => api.delete(`/kb/${kbId}`),
}

// ── Documents ──────────────────────────────────────
export const docAPI = {
  upload: (kbId, file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/documents/upload?kb_id=${kbId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    })
  },
  list: (kbId) => api.get(`/documents/list/${kbId}`),
  status: (docId) => api.get(`/documents/status/${docId}`),
  delete: (docId, kbId) => api.delete(`/documents/${docId}?kb_id=${kbId}`),
}

// ── Chat ───────────────────────────────────────────
export const chatAPI = {
  createSession: (data) => api.post('/chat/session', data),
  listSessions: (kbId) => api.get(`/chat/sessions/${kbId}`),
  deleteSession: (sid) => api.delete(`/chat/session/${sid}`),
  getHistory: (sid) => api.get(`/chat/history/${sid}`),
  query: (data) => api.post('/chat/query', data),
}

// ── Evaluation ─────────────────────────────────────
export const evalAPI = {
  run: (data) => api.post('/eval/run', data),
  history: (kbId) => api.get(`/eval/history/${kbId}`),
  detail: (evalId) => api.get(`/eval/detail/${evalId}`),
  createExperiment: (data) => api.post('/eval/experiment', data),
  listExperiments: (kbId) => api.get(`/eval/experiments/${kbId}`),
}

export default api
