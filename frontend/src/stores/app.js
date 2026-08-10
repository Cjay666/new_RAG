import { defineStore } from 'pinia'
import { kbAPI, docAPI, chatAPI, evalAPI } from '../api/index.js'

const LS_KEY_KB = 'rag_activeKB'
const LS_KEY_SESSION = 'rag_activeSession'

export const useAppStore = defineStore('app', {
  state: () => ({
    kbList: [],
    activeKB: localStorage.getItem(LS_KEY_KB) || '',
    activeSession: localStorage.getItem(LS_KEY_SESSION) || '',
    sessions: [],
    documents: [],
    messages: [],
    evalHistory: [],
    experiments: [],
  }),

  actions: {
    // ── KB ────────────────────────────────────
    async loadKBs() {
      try {
        const { data } = await kbAPI.list()
        this.kbList = data
      } catch (e) { console.error(e) }
    },

    async createKB(name, desc = '') {
      const { data } = await kbAPI.create({ name, description: desc })
      this.kbList.push(data)
      this.activeKB = data.kb_id
      localStorage.setItem(LS_KEY_KB, data.kb_id)
      return data
    },

    setKB(kbId) {
      this.activeKB = kbId
      localStorage.setItem(LS_KEY_KB, kbId)
      if (kbId) {
        this.loadSessions(kbId)
        this.loadDocuments(kbId)
      }
    },

    // ── Sessions ──────────────────────────────
    async loadSessions(kbId) {
      try {
        const { data } = await chatAPI.listSessions(kbId)
        this.sessions = data
      } catch (e) { console.error(e) }
    },

    async createSession(title = '新会话') {
      if (!this.activeKB) return null
      const { data } = await chatAPI.createSession({ kb_id: this.activeKB, title })
      this.sessions.unshift(data)
      this.activeSession = data.session_id
      localStorage.setItem(LS_KEY_SESSION, data.session_id)
      return data
    },

    setSession(sid) {
      this.activeSession = sid
      localStorage.setItem(LS_KEY_SESSION, sid)
    },

    async loadHistory(sessionId) {
      try {
        const { data } = await chatAPI.getHistory(sessionId)
        this.messages = data
      } catch (e) { console.error(e) }
    },

    // ── Documents ─────────────────────────────
    async loadDocuments(kbId) {
      try {
        const { data } = await docAPI.list(kbId)
        this.documents = data
      } catch (e) { console.error(e) }
    },

    async uploadDocument(file, onProgress) {
      if (!this.activeKB) return
      const { data } = await docAPI.upload(this.activeKB, file, onProgress)
      await this.loadDocuments(this.activeKB)
      return data
    },

    async deleteDocument(docId) {
      await docAPI.delete(docId, this.activeKB)
      await this.loadDocuments(this.activeKB)
    },

    // ── Eval ──────────────────────────────────
    async loadEvalHistory() {
      if (!this.activeKB) return
      try {
        const { data } = await evalAPI.history(this.activeKB)
        this.evalHistory = data
      } catch (e) { console.error(e) }
    },

    async loadExperiments() {
      if (!this.activeKB) return
      try {
        const { data } = await evalAPI.listExperiments(this.activeKB)
        this.experiments = data
      } catch (e) { console.error(e) }
    },
  },
})
