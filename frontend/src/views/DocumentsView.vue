<template>
  <div>
    <div class="flex justify-between items-center mb-16">
      <h2 style="font-size:20px;font-weight:700;">📁 文档 / 知识库管理</h2>
      <div class="flex gap-8">
        <button class="btn btn-primary btn-sm" @click="showKBCreate = true" v-if="!store.activeKB">
          ＋ 新建知识库
        </button>
        <label class="btn btn-primary btn-sm" style="cursor:pointer;" v-if="store.activeKB">
          ＋ 上传文档
          <input type="file" hidden @change="handleUpload" :accept="acceptFormats" />
        </label>
      </div>
    </div>

    <!-- KB Create -->
    <div v-if="showKBCreate" class="card" style="max-width:400px;">
      <div class="card-title">新建知识库</div>
      <div class="flex-col gap-8">
        <input v-model="newKB.name" class="input" placeholder="知识库名称" />
        <input v-model="newKB.desc" class="input" placeholder="描述（可选）" />
        <div class="flex gap-8">
          <button class="btn btn-primary btn-sm" @click="createKB">创建</button>
          <button class="btn btn-sm" @click="showKBCreate = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Processing indicators -->
    <div v-if="processingDocs.length" class="mb-16">
      <div v-for="doc in processingDocs" :key="doc.doc_id" class="card" style="padding:14px 16px;">
        <div class="flex items-center justify-between mb-6">
          <span style="font-weight:600;font-size:13px;">{{ doc.filename }}</span>
          <span class="text-sm text-muted">{{ stageLabel(doc.stage) }}</span>
        </div>
        <div style="background:#e5e7eb;border-radius:4px;height:6px;overflow:hidden;">
          <div :style="{width: (doc.progress || 0) + '%', background: doc.stage === 'error' ? 'var(--c-danger)' : 'var(--c-accent)', height:'100%', transition:'width 0.5s', borderRadius:'4px'}"></div>
        </div>
        <div class="flex justify-between mt-4">
          <span class="text-xs text-muted">{{ doc.progress || 0 }}%</span>
          <span v-if="doc.error" class="text-xs" style="color:var(--c-danger);">{{ doc.error }}</span>
        </div>
      </div>
    </div>

    <!-- Document list -->
    <div v-if="store.activeKB && doneDocs.length" class="card">
      <div class="card-title">已入库文档 ({{ doneDocs.length }})</div>
      <table class="table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>大小</th>
            <th>分块数</th>
            <th>状态</th>
            <th>上传时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in doneDocs" :key="doc.doc_id">
            <td>{{ doc.filename }}</td>
            <td>{{ formatSize(doc.file_size) }}</td>
            <td>{{ doc.chunk_count }}</td>
            <td><span :class="statusClass(doc.status)">{{ statusText(doc.status) }}</span></td>
            <td class="text-sm text-muted">{{ formatDate(doc.created_at) }}</td>
            <td>
              <button class="btn btn-danger btn-sm" @click="removeDoc(doc.doc_id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="store.activeKB && !processingDocs.length" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:48px;margin-bottom:12px;">📁</div>
      <div>暂无文档，点击"上传文档"开始</div>
      <div class="text-sm text-muted mt-8">支持 PDF、Word、PPT、Excel、TXT、Markdown、CSV、图片</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAppStore } from '../stores/app.js'
import { docAPI } from '../api/index.js'

const store = useAppStore()
const showKBCreate = ref(false)
const newKB = ref({ name: '', desc: '' })
const acceptFormats = '.pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.txt,.md,.csv,.png,.jpg,.jpeg,.bmp,.tiff'
const uploadProgress = ref({}) // doc_id → { progress, stage, error }

// Poll progress for processing docs
let pollTimer = null

const processingDocs = computed(() => {
  return store.documents.filter(d =>
    d.status !== 'indexed' && d.status !== 'failed'
  ).map(d => ({
    ...d,
    progress: uploadProgress.value[d.doc_id]?.progress || d.progress || 0,
    stage: uploadProgress.value[d.doc_id]?.stage || d.stage || 'uploaded',
    error: uploadProgress.value[d.doc_id]?.error || '',
  }))
})

const doneDocs = computed(() => {
  return store.documents.filter(d => d.status === 'indexed')
})

onMounted(() => {
  if (store.activeKB) store.loadDocuments(store.activeKB)
  startPolling()
})

watch(() => store.activeKB, (kbId) => {
  if (kbId) store.loadDocuments(kbId)
})

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    // Poll status for non-indexed docs
    for (const d of store.documents) {
      if (d.status === 'indexed' || d.status === 'failed') continue
      try {
        const { data } = await docAPI.status(d.doc_id, store.activeKB)
        uploadProgress.value[d.doc_id] = {
          progress: data.progress,
          stage: data.stage,
          error: data.error,
        }
        // Update store doc when done
        if (data.status === 'indexed' || data.status === 'failed') {
          d.status = data.status
          d.chunk_count = data.chunk_count
        }
      } catch (e) { /* ignore */ }
    }
  }, 1500)
}

function stageLabel(stage) {
  const m = { uploaded: '已上传', parsing: '解析中...', chunking: '分块中...', embedding: '向量化中...', indexing: '入库中...', done: '✅ 完成', error: '❌ 失败' }
  return m[stage] || stage
}

async function createKB() {
  if (!newKB.value.name) return
  await store.createKB(newKB.value.name, newKB.value.desc)
  showKBCreate.value = false
  newKB.value = { name: '', desc: '' }
}

async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const result = await store.uploadDocument(file)
  if (result?.doc_id) {
    uploadProgress.value[result.doc_id] = { progress: 0, stage: 'uploaded', error: null }
  }
  e.target.value = ''
}

async function removeDoc(docId) {
  if (confirm('确定删除？所有向量数据也将被删除。')) {
    await store.deleteDocument(docId)
    delete uploadProgress.value[docId]
  }
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
function formatDate(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '' }
function statusClass(s) {
  if (s === 'indexed') return 'tag tag-success'
  if (s === 'failed') return 'tag tag-warning'
  return 'tag tag-info'
}
function statusText(s) {
  return { uploaded: '已上传', parsing: '解析中', chunking: '分块中', embedding: '向量化中', indexed: '✅ 已入库', failed: '❌ 失败' }[s] || s
}
</script>
