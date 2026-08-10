<template>
  <div>
    <div class="flex justify-between items-center mb-16">
      <h2 style="font-size:20px;font-weight:700;">🔬 实验对比</h2>
      <button class="btn btn-primary btn-sm" @click="showCreate = true" :disabled="!store.activeKB">
        ＋ 新建实验
      </button>
    </div>

    <!-- Create Experiment -->
    <div v-if="showCreate" class="card" style="max-width:600px;">
      <div class="card-title">新建对比实验</div>
      <div class="flex-col gap-8">
        <input v-model="expName" class="input" placeholder="实验名称" />

        <div v-for="(cfg, idx) in configs" :key="idx" class="card" style="padding:12px;background:#f8f9fb;">
          <div style="font-weight:600;margin-bottom:8px;">配置 {{ idx + 1 }}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div>
              <label class="text-xs text-muted">chunk_size</label>
              <input v-model.number="cfg.chunk_size" type="number" class="input" />
            </div>
            <div>
              <label class="text-xs text-muted">chunk_overlap</label>
              <input v-model.number="cfg.chunk_overlap" type="number" class="input" />
            </div>
            <div>
              <label class="text-xs text-muted">top_k</label>
              <input v-model.number="cfg.top_k" type="number" class="input" />
            </div>
            <div style="display:flex;flex-direction:column;gap:4px;">
              <label class="flex items-center gap-4 text-sm">
                <input type="checkbox" v-model="cfg.use_hyde" /> HyDE
              </label>
              <label class="flex items-center gap-4 text-sm">
                <input type="checkbox" v-model="cfg.use_step_back" /> Step Back
              </label>
              <label class="flex items-center gap-4 text-sm">
                <input type="checkbox" v-model="cfg.use_dehydrate" /> 脱水消歧
              </label>
              <label class="flex items-center gap-4 text-sm">
                <input type="checkbox" v-model="cfg.use_reranker" /> Reranker
              </label>
            </div>
          </div>
        </div>

        <div class="flex gap-8">
          <button class="btn btn-sm" @click="addConfig">＋ 添加配置</button>
          <button class="btn btn-primary btn-sm" @click="runExperiment" :disabled="!expName">运行实验</button>
          <button class="btn btn-sm" @click="showCreate = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Experiment results -->
    <div v-if="store.experiments.length">
      <div v-for="exp in store.experiments" :key="exp.experiment_id" class="card mb-16">
        <div class="card-title">{{ exp.name }}</div>
        <div class="text-xs text-muted mb-16">{{ formatDate(exp.created_at) }}</div>

        <div v-for="(r, i) in exp.results" :key="i" style="margin-bottom:16px;">
          <div style="font-weight:600;margin-bottom:8px;">
            配置 {{ i + 1 }}:
            chunk_size={{ r.config.chunk_size }},
            top_k={{ r.config.top_k }},
            HyDE={{ r.config.use_hyde }},
            StepBack={{ r.config.use_step_back }},
            Reranker={{ r.config.use_reranker }}
          </div>
          <div class="metrics-grid" style="grid-template-columns:repeat(4,1fr);">
            <div class="metric-card" style="padding:12px;">
              <div class="metric-value" style="font-size:20px;color:var(--c-accent);">{{ (r.metrics.context_precision * 100).toFixed(1) }}%</div>
              <div class="metric-label">上下文精度</div>
            </div>
            <div class="metric-card" style="padding:12px;">
              <div class="metric-value" style="font-size:20px;color:var(--c-success);">{{ (r.metrics.context_recall * 100).toFixed(1) }}%</div>
              <div class="metric-label">上下文召回</div>
            </div>
            <div class="metric-card" style="padding:12px;">
              <div class="metric-value" style="font-size:20px;color:var(--c-purple);">{{ (r.metrics.faithfulness * 100).toFixed(1) }}%</div>
              <div class="metric-label">忠实度</div>
            </div>
            <div class="metric-card" style="padding:12px;">
              <div class="metric-value" style="font-size:20px;color:var(--c-warning);">{{ (r.metrics.answer_relevancy * 100).toFixed(1) }}%</div>
              <div class="metric-label">答案相关性</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-if="!store.experiments.length && !showCreate" class="card" style="text-align:center;padding:40px;">
      <div style="font-size:48px;margin-bottom:12px;">🔬</div>
      <div>暂无实验数据</div>
      <div class="text-sm text-muted mt-8">创建对比实验，比较不同配置下的 RAG 系统表现</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '../stores/app.js'
import { evalAPI } from '../api/index.js'

const store = useAppStore()
const showCreate = ref(false)
const expName = ref('')
const configs = ref([
  { chunk_size: 600, chunk_overlap: 120, top_k: 5, use_hyde: true, use_step_back: true, use_dehydrate: true, use_reranker: true },
  { chunk_size: 600, chunk_overlap: 120, top_k: 5, use_hyde: false, use_step_back: false, use_dehydrate: false, use_reranker: false },
])

onMounted(() => {
  if (store.activeKB) store.loadExperiments()
})

watch(() => store.activeKB, (kbId) => {
  if (kbId) store.loadExperiments()
})

function addConfig() {
  if (configs.value.length >= 5) return
  configs.value.push({ chunk_size: 600, chunk_overlap: 120, top_k: 5, use_hyde: true, use_step_back: false, use_dehydrate: true, use_reranker: true })
}

async function runExperiment() {
  await evalAPI.createExperiment({
    kb_id: store.activeKB,
    name: expName.value,
    configs: configs.value,
  })
  await store.loadExperiments()
  showCreate.value = false
  expName.value = ''
  configs.value = [
    { chunk_size: 600, chunk_overlap: 120, top_k: 5, use_hyde: true, use_step_back: true, use_dehydrate: true, use_reranker: true },
    { chunk_size: 600, chunk_overlap: 120, top_k: 5, use_hyde: false, use_step_back: false, use_dehydrate: false, use_reranker: false },
  ]
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN')
}
</script>
