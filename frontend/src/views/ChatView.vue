<template>
  <div style="display:flex;gap:16px;height:calc(100vh - 88px);">
    <!-- Session sidebar -->
    <div style="width:200px;flex-shrink:0;display:flex;flex-direction:column;gap:8px;">
      <button class="btn btn-primary btn-sm" @click="newSession" :disabled="!store.activeKB">
        新建会话
      </button>
      <div style="flex:1;overflow-y:auto;">
        <div
          v-for="s in store.sessions" :key="s.session_id"
          @click="selectSession(s.session_id)"
          :class="['card', { 'active-session': store.activeSession === s.session_id }]"
          style="padding:8px 12px;cursor:pointer;margin-bottom:4px;font-size:13px;"
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
      <div style="flex:1;overflow-y:auto;padding-right:8px;" ref="chatContainer">
        <div v-if="!store.activeKB" style="text-align:center;padding:60px 20px;color:var(--c-text-muted);">
          <div style="font-size:36px;margin-bottom:12px;font-weight:300;">RAG</div>
          <div>请先在左侧选择或创建一个知识库</div>
        </div>
        <div v-else-if="!store.messages.length" style="text-align:center;padding:60px 20px;color:var(--c-text-muted);">
          <div style="font-size:36px;margin-bottom:12px;font-weight:300;">RAG</div>
          <div>输入问题，从知识库中检索答案</div>
        </div>

        <div v-for="(msg, i) in store.messages" :key="i" :class="['chat-message', msg.role]">
          <div class="role">{{ msg.role === 'user' ? '提问' : '回答' }}</div>
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

          <!-- Trace toggle button -->
          <div v-if="msg.role === 'assistant' && msg.trace" style="margin-top:10px;">
            <button class="btn btn-sm" @click="toggleTrace(i)" style="font-size:12px;">
              {{ expandedTraces[i] ? '收起检索流程' : '查看检索流程' }}
            </button>
            <div v-if="expandedTraces[i]" class="trace-panel">
              <TraceView :trace="msg.trace" />
            </div>
          </div>
        </div>

        <div v-if="loading" class="chat-message assistant">
          <div class="role">回答</div>
          <div class="content" style="color:var(--c-text-muted);">检索中...</div>
        </div>
      </div>

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
    <div v-if="lastSources.length" style="width:220px;flex-shrink:0;overflow-y:auto;">
      <div class="card-title">检索来源</div>
      <div v-for="src in lastSources" :key="src.chunk_id" class="card" style="padding:10px;margin-bottom:6px;font-size:12px;">
        <div style="font-weight:600;margin-bottom:2px;">{{ src.doc_name }}</div>
        <div class="text-xs text-muted">{{ src.header_path }}</div>
        <div style="margin-top:4px;color:var(--c-accent);font-weight:500;">相关性 {{ (src.relevance_score * 100).toFixed(0) }}%</div>
        <div style="margin-top:4px;line-height:1.5;max-height:80px;overflow:hidden;color:var(--c-text-secondary);">{{ src.content?.slice(0, 150) }}...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app.js'
import { chatAPI } from '../api/index.js'
import TraceView from '../components/TraceView.vue'

const store = useAppStore()
const question = ref('')
const loading = ref(false)
const lastSources = ref([])
const chatContainer = ref(null)
const expandedTraces = reactive({})

onMounted(() => {
  if (store.activeKB) {
    store.loadSessions(store.activeKB)
    if (store.activeSession) {
      store.loadHistory(store.activeSession)
    }
  }
})

async function newSession() {
  await store.createSession()
  store.messages = []
  lastSources.value = []
}

async function selectSession(sid) {
  store.setSession(sid)
  await store.loadHistory(sid)
}

function toggleTrace(i) {
  expandedTraces[i] = !expandedTraces[i]
}

async function send() {
  const q = question.value.trim()
  if (!q || !store.activeKB || loading.value) return

  if (!store.activeSession) {
    await store.createSession()
  }

  question.value = ''
  loading.value = true

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
      trace: data.trace || null,
    })
    lastSources.value = data.sources || []
  } catch (e) {
    store.messages.push({
      role: 'assistant',
      content: '出错了: ' + (e.response?.data?.detail || e.message),
      sources: [],
      trace: null,
    })
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
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
    .replace(/\[来源: (.+?)\]/g, '<span class="source-badge">$1</span>')
}

watch(() => store.activeKB, (kbId) => {
  if (kbId) store.loadSessions(kbId)
})
</script>

<style scoped>
.active-session {
  border-left: 3px solid var(--c-accent);
  background: #e6f7ff;
}
.trace-panel {
  margin-top: 10px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: #fafafa;
  padding: 14px 16px;
  font-size: 12px;
  line-height: 1.7;
  max-height: 480px;
  overflow-y: auto;
}
</style>
