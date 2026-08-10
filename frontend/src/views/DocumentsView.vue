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

    <!-- KB Create dialog -->
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

    <!-- Document list -->
    <div v-if="store.activeKB && store.documents.length" class="card">
      <div class="card-title">文档列表 ({{ store.documents.length }})</div>
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
          <tr v-for="doc in store.documents" :key="doc.doc_id">
            <td>{{ doc.filename }}</td>
            <td>{{ formatSize(doc.file_size) }}</td>
            <td>{{ doc.chunk_count }}</td>
            <td>
              <span :class="statusClass(doc.status)">{{ statusText(doc.status) }}</span>
            </td>
            <td class="text-sm text-muted">{{ formatDate(doc.created_at) }}</td>
            <td>
              <button class="btn btn-danger btn-sm" @click="removeDoc(doc.doc_id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="store.activeKB" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:48px;margin-bottom:12px;">📁</div>
      <div>暂无文档，点击"上传文档"开始</div>
      <div class="text-sm text-muted mt-8">支持 PDF、Word、PPT、Excel、TXT、Markdown、CSV、图片</div>
    </div>

    <div v-else style="text-align:center;padding:60px 20px;color:var(--c-text-muted);">
      <div style="font-size:48px;margin-bottom:16px;">📚</div>
      <div style="font-size:16px;">请先选择或创建一个知识库</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/app.js'

const store = useAppStore()
const showKBCreate = ref(false)
const newKB = ref({ name: '', desc: '' })
const acceptFormats = '.pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.txt,.md,.csv,.png,.jpg,.jpeg,.bmp,.tiff'

async function createKB() {
  if (!newKB.value.name) return
  await store.createKB(newKB.value.name, newKB.value.desc)
  showKBCreate.value = false
  newKB.value = { name: '', desc: '' }
  store.loadDocuments(store.activeKB)
}

async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  await store.uploadDocument(file)
  e.target.value = ''
}

async function removeDoc(docId) {
  if (confirm('确定删除该文档吗？所有关联的向量数据也将被删除。')) {
    await store.deleteDocument(docId)
  }
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}

function statusClass(s) {
  if (s === 'indexed') return 'tag tag-success'
  if (s === 'failed') return 'tag' + ' tag-warning'
  return 'tag tag-info'
}

function statusText(s) {
  const map = {
    uploaded: '已上传', parsing: '解析中', chunking: '分块中',
    embedding: '向量化中', indexed: '✅ 已入库', failed: '❌ 失败',
  }
  return map[s] || s
}
</script>
