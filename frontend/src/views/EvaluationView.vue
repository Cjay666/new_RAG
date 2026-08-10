<template>
  <div>
    <div class="flex justify-between items-center mb-16">
      <h2 style="font-size:18px;font-weight:600;">评测面板</h2>
      <button class="btn btn-primary btn-sm" @click="showRunEval = true" :disabled="!store.activeKB">
        运行评测
      </button>
    </div>

    <!-- Run Evaluation dialog -->
    <div v-if="showRunEval" class="card" style="max-width:500px;">
      <div class="card-title">运行 RAGAS 评测</div>
      <div class="flex-col gap-8">
        <textarea
          v-model="testQueries"
          class="input"
          rows="5"
          placeholder="输入测试问题，每行一个&#10;例如：&#10;什么是RAG？&#10;向量数据库的作用是什么？"
        ></textarea>
        <div class="flex gap-8">
          <button class="btn btn-primary btn-sm" @click="runEval" :disabled="!testQueries.trim()">开始评测</button>
          <button class="btn btn-sm" @click="showRunEval = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Latest metrics -->
    <div v-if="store.evalHistory.length" class="mb-16">
      <div class="card-title mb-16">最新评测结果</div>
      <div class="metrics-grid">
        <div class="metric-card" style="border-top:3px solid var(--c-accent);">
          <div class="metric-value" style="color:var(--c-accent);">{{ (latest.context_precision * 100).toFixed(1) }}%</div>
          <div class="metric-label">Context Precision<br><span class="text-xs">检索上下文精度</span></div>
        </div>
        <div class="metric-card" style="border-top:3px solid var(--c-success);">
          <div class="metric-value" style="color:var(--c-success);">{{ (latest.context_recall * 100).toFixed(1) }}%</div>
          <div class="metric-label">Context Recall<br><span class="text-xs">检索上下文召回率</span></div>
        </div>
        <div class="metric-card" style="border-top:3px solid #722ed1;">
          <div class="metric-value" style="color:#722ed1;">{{ (latest.faithfulness * 100).toFixed(1) }}%</div>
          <div class="metric-label">Faithfulness<br><span class="text-xs">回答忠实度</span></div>
        </div>
        <div class="metric-card" style="border-top:3px solid var(--c-warning);">
          <div class="metric-value" style="color:var(--c-warning);">{{ (latest.answer_relevancy * 100).toFixed(1) }}%</div>
          <div class="metric-label">Answer Relevancy<br><span class="text-xs">答案相关性</span></div>
        </div>
      </div>
    </div>

    <!-- History -->
    <div v-if="store.evalHistory.length > 1" class="card">
      <div class="card-title">评测历史</div>
      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>测试数量</th>
            <th>上下文精度</th>
            <th>上下文召回</th>
            <th>忠实度</th>
            <th>答案相关性</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in store.evalHistory" :key="e.eval_id">
            <td class="text-sm">{{ formatDate(e.created_at) }}</td>
            <td>{{ e.query_count }}</td>
            <td>{{ (e.metrics.context_precision * 100).toFixed(1) }}%</td>
            <td>{{ (e.metrics.context_recall * 100).toFixed(1) }}%</td>
            <td>{{ (e.metrics.faithfulness * 100).toFixed(1) }}%</td>
            <td>{{ (e.metrics.answer_relevancy * 100).toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty -->
    <div v-if="!store.evalHistory.length && !showRunEval" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:36px;margin-bottom:12px;font-weight:300;">评测</div>
      <div>暂无评测数据</div>
      <div class="text-sm text-muted mt-8">点击「运行评测」，使用测试问题集评估 RAG 系统质量</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAppStore } from '../stores/app.js'
import { evalAPI } from '../api/index.js'

const store = useAppStore()
const showRunEval = ref(false)
const testQueries = ref('')

const latest = computed(() => {
  if (!store.evalHistory.length) return {}
  return store.evalHistory[0].metrics
})

onMounted(() => {
  if (store.activeKB) store.loadEvalHistory()
})

watch(() => store.activeKB, (kbId) => {
  if (kbId) store.loadEvalHistory()
})

async function runEval() {
  const queries = testQueries.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!queries.length) return

  await evalAPI.run({ kb_id: store.activeKB, test_queries: queries })
  await store.loadEvalHistory()
  showRunEval.value = false
  testQueries.value = ''
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}
</script>
