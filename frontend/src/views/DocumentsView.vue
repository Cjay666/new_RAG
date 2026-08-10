<template>
  <div>
    <div class="flex justify-between items-center mb-16">
      <h2 style="font-size:18px;font-weight:600;">文档管理</h2>
      <div class="flex gap-8">
        <button class="btn btn-primary btn-sm" @click="showKBCreate = true" v-if="!store.activeKB">
          新建知识库
        </button>
        <label class="btn btn-primary btn-sm" style="cursor:pointer;" v-if="store.activeKB">
          上传文档
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

    <!-- Uploading / Processing indicators -->
    <div v-if="activeItems.length" class="mb-16">
      <div v-for="item in activeItems" :key="item.key" class="upload-item">
        <div class="flex items-center justify-between mb-6">
          <span style="font-weight:500;font-size:13px;">{{ item.filename }}</span>
          <span class="text-sm text-muted">{{ item.statusLabel }}</span>
        </div>
        <div class="bar-track">
          <div
            :class="['bar-fill', item.barClass]"
            :style="{width: item.progress + '%'}"
          ></div>
        </div>
        <div class="flex justify-between mt-4">
          <span class="text-xs text-muted">{{ item.progress }}%</span>
          <span v-if="item.error" class="text-xs" style="color:var(--c-danger);">{{ item.error }}</span>
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

    <div v-else-if="store.activeKB && !activeItems.length" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:36px;margin-bottom:12px;font-weight:300;">文档</div>
      <div>暂无文档，点击「上传文档」开始</div>
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

// Track items: uploading (before server returns) + processing (server-side progress)
const uploadItems = ref({})   // key -> { filename, progress, stage, error }
const processItems = ref({})  // doc_id -> { progress, stage, error }

let pollTimer = null

// Merge upload + processing items for display
const activeItems = computed(() => {
  const items = []
  for (const [key, v] of Object.entries(uploadItems.value)) {
    items.push({
      key,
      filename: v.filename,
      progress: v.progress,
      stage: v.stage,
      error: v.error,
      statusLabel: '上传中...',
      barClass: 'uploading',
    })
  }
  for (const [docId, v] of Object.entries(processItems.value)) {
    const doc = store.documents.find(d => d.doc_id === docId)
    items.push({
      key: docId,
      filename: doc?.filename || docId,
      progress: v.progress,
      stage: v.stage,
      error: v.error,
      statusLabel: stageLabel(v.stage),
      barClass: v.stage === 'error' ? 'error' : 'processing',
    })
  }
  return items
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
    for (const d of store.documents) {
      if (d.status === 'indexed' || d.status === 'failed') continue
      try {
        const { data } = await docAPI.status(d.doc_id)
        processItems.value[d.doc_id] = {
          progress: data.progress,
          stage: data.stage,
          error: data.error,
        }
        if (data.status === 'indexed' || data.status === 'failed') {
          d.status = data.status
          d.chunk_count = data.chunk_count
          // Remove from processItems after a short delay (let user see 100%)
          setTimeout(() => {
            delete processItems.value[d.doc_id]
          }, 2000)
        }
      } catch (e) { /* ignore */ }
    }
  }, 1500)
}

function stageLabel(stage) {
  const m = {
    uploaded: '等待处理', parsing: '解析中...', chunking: '分块中...',
    embedding: '向量化中...', indexing: '入库中...', done: '完成', error: '失败'
  }
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
  e.target.value = ''

  const uploadKey = 'up_' + Date.now()

  // Phase 1: show upload progress during file transfer
  uploadItems.value[uploadKey] = {
    filename: file.name,
    progress: 0,
    stage: 'uploading',
    error: null,
  }

  const onProgress = (evt) => {
    if (evt.total) {
      const pct = Math.round((evt.loaded / evt.total) * 100)
      uploadItems.value[uploadKey].progress = pct
    }
  }

  try {
    const result = await store.uploadDocument(file, onProgress)
    // Phase 1 complete — remove upload item
    delete uploadItems.value[uploadKey]
    // Phase 2: processing progress (polled)
    if (result?.doc_id) {
      processItems.value[result.doc_id] = { progress: 0, stage: 'uploaded', error: null }
    }
  } catch (err) {
    uploadItems.value[uploadKey].error = '上传失败: ' + (err.response?.data?.detail || err.message)
    uploadItems.value[uploadKey].stage = 'error'
    setTimeout(() => { delete uploadItems.value[uploadKey] }, 5000)
  }
}

async function removeDoc(docId) {
  if (confirm('确定删除？所有向量数据也将被删除。')) {
    await store.deleteDocument(docId)
    delete processItems.value[docId]
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
  const m = { uploaded: '已上传', parsing: '解析中', chunking: '分块中', embedding: '向量化中', indexed: '已入库', failed: '失败' }
  return m[s] || s
}
</script>
