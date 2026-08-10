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
    <div v-if="store.evalHistory.length" class="card">
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
            <th>操作</th>
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
            <td>
              <button class="btn btn-sm" @click="showDetail(e)" style="font-size:12px;">查看详情</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Detail Modal -->
    <div v-if="detailVisible" class="modal-overlay" @click.self="detailVisible = false">
      <div class="modal-content" style="max-width:800px;max-height:85vh;overflow-y:auto;">
        <div class="flex justify-between items-center mb-16">
          <h3 style="margin:0;">RAGAS 评测详情</h3>
          <button class="btn btn-sm" @click="detailVisible = false">关闭</button>
        </div>

        <div v-if="detailData">
          <!-- Method info -->
          <div class="card" style="padding:12px;margin-bottom:16px;background:#e6f7ff;border:1px solid #91d5ff;">
            <div style="font-size:12px;">
              评测方法: <strong>{{ detailData.method === 'ragas' ? 'RAGAS (LLM-as-Judge)' : '简化启发式' }}</strong>
              <span v-if="detailData.judge_model"> | 裁判模型: {{ detailData.judge_model }}</span>
            </div>
          </div>

          <!-- Metric explanations -->
          <div class="card-title mb-8">四项指标测评原理</div>
          <div v-if="detailData.explanation" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">
            <div v-for="(exp, key) in detailData.explanation" :key="key" class="card" style="padding:12px;font-size:12px;">
              <div style="font-weight:600;margin-bottom:6px;">{{ exp.title }}</div>
              <div class="text-xs text-muted mb-4">{{ exp.process }}</div>
              <div style="color:var(--c-text-secondary);line-height:1.6;background:#fafafa;padding:6px 8px;border-radius:3px;">
                {{ exp.example }}
              </div>
            </div>
          </div>

          <!-- Per-question breakdown -->
          <div class="card-title mb-8">逐题拆解 ({{ detailData.questions?.length || 0 }} 题)</div>
          <div v-for="(q, qi) in detailData.questions" :key="qi" class="card" style="padding:14px;margin-bottom:12px;">
            <div style="font-weight:600;margin-bottom:8px;">#{{ qi + 1 }} {{ q.question }}</div>

            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px;">
              <div style="text-align:center;padding:6px;background:#fafafa;border-radius:3px;">
                <div style="font-size:14px;font-weight:600;" :style="{color: scoreColor(q.scores.faithfulness)}">
                  {{ (q.scores.faithfulness * 100).toFixed(0) }}%
                </div>
                <div class="text-xs text-muted">忠实度</div>
              </div>
              <div style="text-align:center;padding:6px;background:#fafafa;border-radius:3px;">
                <div style="font-size:14px;font-weight:600;" :style="{color: scoreColor(q.scores.answer_relevancy)}">
                  {{ (q.scores.answer_relevancy * 100).toFixed(0) }}%
                </div>
                <div class="text-xs text-muted">相关性</div>
              </div>
              <div style="text-align:center;padding:6px;background:#fafafa;border-radius:3px;">
                <div style="font-size:14px;font-weight:600;" :style="{color: scoreColor(q.scores.context_precision)}">
                  {{ (q.scores.context_precision * 100).toFixed(0) }}%
                </div>
                <div class="text-xs text-muted">精度</div>
              </div>
              <div style="text-align:center;padding:6px;background:#fafafa;border-radius:3px;">
                <div style="font-size:14px;font-weight:600;" :style="{color: scoreColor(q.scores.context_recall)}">
                  {{ (q.scores.context_recall * 100).toFixed(0) }}%
                </div>
                <div class="text-xs text-muted">召回率</div>
              </div>
            </div>

            <details style="font-size:12px;">
              <summary style="cursor:pointer;color:var(--c-accent);">查看回答 & 上下文</summary>
              <div style="margin-top:8px;padding:8px;background:#f5f5f5;border-radius:3px;">
                <div style="font-weight:500;margin-bottom:4px;">AI 回答:</div>
                <div style="color:var(--c-text-secondary);line-height:1.6;margin-bottom:10px;">{{ q.answer }}</div>
                <div style="font-weight:500;margin-bottom:4px;">召回上下文 ({{ q.contexts?.length || 0 }} 条):</div>
                <div v-for="(ctx, ci) in q.contexts" :key="ci" style="padding:3px 6px;margin:2px 0;background:#fff;border:1px solid #eee;border-radius:2px;color:var(--c-text-secondary);">
                  [{{ ci + 1 }}] {{ ctx }}...
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
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
const detailVisible = ref(false)
const detailData = ref(null)

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

async function showDetail(row) {
  detailVisible.value = true
  detailData.value = row.detail || { method: 'none', questions: [], explanation: {} }
}

function scoreColor(v) {
  if (v >= 0.8) return 'var(--c-success)'
  if (v >= 0.5) return 'var(--c-warning)'
  return 'var(--c-danger)'
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.modal-content {
  background: #fff; border-radius: 8px; padding: 24px;
  width: 90%; max-height: 85vh; overflow-y: auto;
}
</style>
