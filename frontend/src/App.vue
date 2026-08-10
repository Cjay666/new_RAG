<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-logo">📚 RAG 知识库</div>
      <nav class="sidebar-nav">
        <router-link to="/">💬 对话问答</router-link>
        <router-link to="/documents">📁 文档管理</router-link>
        <router-link to="/evaluation">📊 评测面板</router-link>
        <router-link to="/experiments">🔬 实验对比</router-link>
      </nav>
      <div style="padding:12px 20px;border-top:1px solid var(--c-border);margin-top:auto;">
        <select v-model="store.activeKB" class="input" style="font-size:12px;" @change="store.setKB(store.activeKB)">
          <option value="">选择知识库</option>
          <option v-for="kb in store.kbList" :key="kb.kb_id" :value="kb.kb_id">{{ kb.name }}</option>
        </select>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAppStore } from './stores/app.js'

const store = useAppStore()

onMounted(() => {
  store.loadKBs()
})
</script>
