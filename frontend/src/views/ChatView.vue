<template>
  <div style="display:flex;gap:20px;height:calc(100vh - 96px);">
    <!-- Session sidebar -->
    <div style="width:220px;flex-shrink:0;display:flex;flex-direction:column;gap:8px;">
      <button class="btn btn-primary btn-sm" @click="newSession" :disabled="!store.activeKB">
        ＋ 新建会话
      </button>
      <div style="flex:1;overflow-y:auto;">
        <div
          v-for="s in store.sessions" :key="s.session_id"
          @click="selectSession(s.session_id)"
          :class="['card', { 'active-session': store.activeSession === s.session_id }]"
          style="padding:10px 12px;cursor:pointer;margin-bottom:4px;font-size:13px;"
        >
          <div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ s.title }}</div>
          <div class="text-xs text-muted">{{ formatDate(s.updated_at || s.created_at) }}</div>
        </div>
        <div v-if="!store.sessions.length" class="text-muted text-sm" style="text-align:center;padding:20px;">
          暂无会话
        </div>
      </div>
    </div>

    <!-- Chat area -->
    <div style="flex:1;display:flex;flex-direction:column;">
      <!-- Messages -->
      <div style="flex:1;overflow-y:auto;padding-right:8px;" ref="chatContainer">
        <div v-if="!store.activeKB" style="text-align:center;padding:60px 20px;color:var(--c-text-muted);">
          <div style="font-size:48px;margin-bottom:16px;">📚</div>
          <div style="font-size:16px;">请先在左侧选择或创建一个知识库</div>
        </div>
        <div v-else-if="!store.messages.length" style="text-align:center;padding:60px 20px;color:var(--c-text-muted);">
          <div style="font-size:48px;margin-bottom:16px;">💬</div>
          <div style="font-size:16px;">开始提问，从知识库中检索答案</div>
        </div>

        <div v-for="(msg, i) in store.messages" :key="i" :class="['chat-message', msg.role]">
          <div class="role">{{ msg.role === 'user' ? '👤 你' : '🤖 助手' }}</div>
          <div class="content" v-html="renderContent(msg.content)"></div>
          <div v-if="msg.sources?.length" style="margin-top:6px;">
            <span
              v-for="src in msg.sources" :key="src.chunk_id"
              class="source-badge"
              :title="src.content"
            >
              {{ src.doc_name }}{{ src.header_path ? ' > ' + src.header_path : '' }}
            </span>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="chat-message assistant">
          <div class="role">🤖 助手</div>
          <div class="content">检索中...</div>
        </div>
      </div>

      <!-- Input -->
      <div style="margin-top:12px;display:flex;gap:8px;" v-if="store.activeKB">
        <textarea
          v-model="question"
          class="input"
          rows="2"
          placeholder="输入你的问题..."
          @keydown.enter.exact.prevent="send"
          style="resize:none;"
        ></textarea>
        <button class="btn btn-primary" @click="send" :disabled="!question.trim() || loading" style="align-self:flex-end;">
          发送
        </button>
      </div>
    </div>

    <!-- Source panel -->
    <div v-if="lastSources.length" style="width:240px;flex-shrink:0;overflow-y:auto;">
      <div class="card-title">📎 检索来源</div>
      <div v-for="src in lastSources" :key="src.chunk_id" class="card" style="padding:10px;margin-bottom:6px;font-size:12px;">
        <div style="font-weight:600;margin-bottom:2px;">{{ src.doc_name }}</div>
        <div class="text-xs text-muted">{{ src.header_path }}</div>
        <div style="margin-top:4px;color:var(--c-accent);font-weight:600;">相关性: {{ (src.relevance_score * 100).toFixed(0) }}%</div>
        <div style="margin-top:4px;line-height:1.5;max-height:80px;overflow:hidden;">{{ src.content?.slice(0, 150) }}...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { chatAPI } from '../api/index.js'

const store = useAppStore()
const question = ref('')
const loading = ref(false)
const lastSources = ref([])
const chatContainer = ref(null)

onMounted(() => {
  if (store.activeKB) store.loadSessions(store.activeKB)
})

async function newSession() {
  await store.createSession()
  store.messages = []
  lastSources.value = []
}

async function selectSession(sid) {
  store.activeSession = sid
  await store.loadHistory(sid)
}

async function send() {
  const q = question.value.trim()
  if (!q || !store.activeKB || loading.value) return

  if (!store.activeSession) {
    await store.createSession()
  }

  question.value = ''
  loading.value = true

  // Add user message locally
  store.messages.push({ role: 'user', content: q, sources: null })

  try {
    const { data } = await chatAPI.query({
      session_id: store.activeSession,
      kb_id: store.activeKB,
      question: q,
      top_k: 5,
    })
    store.messages.push({
      role: 'assistant',
      content: data.answer,
      sources: data.sources,
    })
    lastSources.value = data.sources || []
  } catch (e) {
    store.messages.push({ role: 'assistant', content: '出错了: ' + e.message, sources: [] })
  }

  loading.value = false
  await nextTick()
  scrollBottom()
}

function scrollBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function renderContent(text) {
  if (!text) return ''
  // Simple markdown-ish rendering
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/\[来源: (.+?)\]/g, '<span class="source-badge">$1</span>')
}

// Watch for KB changes
watch(() => store.activeKB, (kbId) => {
  if (kbId) store.loadSessions(kbId)
})
</script>

<style scoped>
.active-session {
  border-left: 3px solid var(--c-accent);
  background: #e8effe;
}
</style>
