<template>
  <div>
    <div class="flex justify-between items-center mb-16">
      <h2 style="font-size:18px;font-weight:600;">评测面板</h2>
      <button class="btn btn-primary btn-sm" @click="openEvalPanel" :disabled="!store.activeKB || evalRunning">
        {{ evalRunning ? '⏳ 评测中...' : '运行评测' }}
      </button>
    </div>

    <!-- 评测输入面板 -->
    <div v-if="showRunEval" class="card" style="max-width:520px;position:relative;">
      <div class="card-title">运行 RAGAS 评测</div>

      <!-- 进度条 -->
      <div v-if="evalRunning" class="mb-12" style="padding:12px;background:#f6ffed;border:1px solid #b7eb8f;border-radius:4px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <span style="font-size:14px;font-weight:500;">{{ evalProgress }}</span>
        </div>
        <div class="progress-track">
          <div class="progress-bar"></div>
        </div>
        <div class="text-xs text-muted mt-4">每道题需走完整 RAG 链路 + RAGAS 裁判打分，请耐心等待</div>
      </div>

      <div class="flex-col gap-8">
        <textarea
          v-model="testQueries"
          class="input"
          rows="5"
          :disabled="evalRunning"
          placeholder="输入测试问题，每行一个&#10;例如：&#10;路明非是谁？&#10;源稚生和源稚女什么关系？"
        ></textarea>
        <div class="flex gap-8">
          <button
            class="btn btn-primary btn-sm"
            @click="runEval"
            :disabled="evalRunning || !testQueries.trim()"
          >
            {{ evalRunning ? '评测中...' : '开始评测' }}
          </button>
          <button class="btn btn-sm" @click="showRunEval = false" :disabled="evalRunning">取消</button>
        </div>
      </div>
    </div>

    <!-- 最新结果 -->
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

    <!-- 评测历史 -->
    <div v-if="store.evalHistory.length" class="card">
      <div class="card-title">评测历史</div>
      <table class="table">
        <thead>
          <tr>
            <th>时间</th><th>题数</th><th>上下文精度</th><th>上下文召回</th>
            <th>忠实度</th><th>答案相关性</th><th>操作</th>
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

    <!-- 详情弹窗 -->
    <div v-if="detailVisible" class="modal-overlay" @click.self="detailVisible = false">
      <div class="modal-content" style="max-width:820px;max-height:85vh;overflow-y:auto;">
        <div class="flex justify-between items-center mb-16">
          <h3 style="margin:0;">RAGAS 评测详情</h3>
          <button class="btn btn-sm" @click="detailVisible = false">关闭</button>
        </div>

        <!-- 评测方式 -->
        <div class="card" style="padding:10px 14px;margin-bottom:16px;background:#e6f7ff;border:1px solid #91d5ff;">
          <div style="font-size:13px;">
            评测方法: <strong>{{ detailData.method === 'ragas' ? 'RAGAS (LLM-as-Judge)' : detailData.method === 'heuristic' ? '简化启发式（需安装 ragas 库获得精准打分）' : '未知' }}</strong>
            <span v-if="detailData.judge_model"> | 裁判模型: {{ detailData.judge_model }}</span>
          </div>
        </div>

        <!-- 四项指标原理（前端硬编码，确保永远显示） -->
        <div class="card-title mb-8">四项指标测评原理</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">
          <div v-for="exp in metricExplanations" :key="exp.key" class="card" style="padding:12px;font-size:12px;">
            <div style="font-weight:600;margin-bottom:6px;">{{ exp.title }}</div>
            <div class="text-xs text-muted mb-4">{{ exp.process }}</div>
            <div style="color:var(--c-text-secondary);line-height:1.6;background:#fafafa;padding:6px 8px;border-radius:3px;">
              💡 {{ exp.example }}
            </div>
          </div>
        </div>

        <!-- 逐题拆解 -->
        <div class="card-title mb-8">逐题拆解 ({{ detailData.questions?.length || 0 }} 题)</div>
        <div v-if="!detailData.questions?.length" style="text-align:center;padding:20px;color:var(--c-text-secondary);font-size:13px;">
          暂无逐题数据。运行一次评测后自动生成。
        </div>
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
              <div style="color:var(--c-text-secondary);line-height:1.6;margin-bottom:10px;white-space:pre-wrap;">{{ q.answer || '(无)' }}</div>
              <div style="font-weight:500;margin-bottom:4px;">召回上下文 ({{ q.contexts?.length || 0 }} 条):</div>
              <div v-for="(ctx, ci) in q.contexts" :key="ci" style="padding:3px 6px;margin:2px 0;background:#fff;border:1px solid #eee;border-radius:2px;color:var(--c-text-secondary);">
                [{{ ci + 1 }}] {{ ctx }}...
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!store.evalHistory.length && !showRunEval" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:36px;margin-bottom:12px;font-weight:300;">📊 评测</div>
      <div>暂无评测数据</div>
      <div class="text-sm text-muted mt-8">点击「运行评测」，输入测试问题评估 RAG 系统质量</div>
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
const evalRunning = ref(false)
const evalProgress = ref('')
const detailVisible = ref(false)
const detailData = ref({ method: '', questions: [] })

// 四项指标原理 — 前端硬编码，确保永远显示
const metricExplanations = [
  {
    key: 'faithfulness',
    title: '忠实度 (Faithfulness)',
    process: '1. LLM 将回答拆解为原子声明 → 2. 逐条判断该声明能否从上下文中推断 → 3. 可推断数/总声明数',
    example: '回答「路明非是卡塞尔学院学生」→ 拆分→ 上下文包含「路明非就读于卡塞尔学院」→ ✅ 可推断 → 得分+1',
  },
  {
    key: 'answer_relevancy',
    title: '答案相关性 (Answer Relevancy)',
    process: '1. LLM 根据回答反推可能的问题 → 2. 与原问题做 Embedding 余弦相似度 → 3. 多个相似度取平均',
    example: '回答「路明非在高天原执行任务」→ 反推「路明非在执行什么任务」→ 相似度 0.85 → 得分高',
  },
  {
    key: 'context_precision',
    title: '上下文精度 (Context Precision)',
    process: '1. LLM 逐条判断每个召回 chunk 是否与问题相关 → 2. 相关数/总数 → 3. 排名靠前的相关 chunk 权重更高',
    example: '召回5个chunk → 其中3个相关 → 且3个都排在前面 → 精度=100%',
  },
  {
    key: 'context_recall',
    title: '上下文召回率 (Context Recall)',
    process: '1. LLM 从回答中提取关键信息点 → 2. 判断每个信息点能否在召回上下文中找到 → 3. 找到数/总信息点数',
    example: '回答含3个关键事实 → 2个在chunk中找到 → 召回率=66.7%',
  },
]

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

function openEvalPanel() {
  showRunEval.value = true
  testQueries.value = ''
}

async function runEval() {
  const queries = testQueries.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!queries.length) return

  evalRunning.value = true
  evalProgress.value = `正在评测 ${queries.length} 道题，每道走完整 RAG 链路...`

  try {
    await evalAPI.run({ kb_id: store.activeKB, test_queries: queries })
    await store.loadEvalHistory()
    showRunEval.value = false
    testQueries.value = ''
  } catch (e) {
    alert('评测失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    evalRunning.value = false
    evalProgress.value = ''
  }
}

function showDetail(row) {
  detailVisible.value = true
  detailData.value = row.detail || { method: 'unknown', questions: [] }
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
.progress-track {
  width: 100%; height: 6px; background: #e8e8e8;
  border-radius: 3px; overflow: hidden; position: relative;
}
.progress-bar {
  position: absolute; top: 0; left: 0; height: 100%;
  width: 30%; border-radius: 3px;
  background: linear-gradient(90deg, #1677ff, #69b1ff);
  animation: progressSlide 1.8s ease-in-out infinite;
}
@keyframes progressSlide {
  0%   { left: -30%; }
  100% { left: 100%; }
}
</style>
