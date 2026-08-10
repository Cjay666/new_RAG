<template>
  <div>
    <!-- Step 1: Router -->
    <div class="trace-step active">
      <div class="trace-step-title">1. 查询路由 (Query Router)</div>
      <div class="trace-step-body">
        判定策略:
        <span v-for="d in trace.router.decision" :key="d" class="trace-tag">{{ d }}</span>
        <span v-if="!trace.router.decision?.length" class="trace-tag">direct</span>
        <div class="text-xs text-muted mt-4">{{ trace.router.note }}</div>
      </div>
    </div>

    <!-- Step 2: Rewriting -->
    <div class="trace-step" :class="{ active: trace.rewrites?.length > 1 }">
      <div class="trace-step-title">
        2. 查询改写
        <span class="text-xs text-muted">(共 {{ trace.rewrites?.length || 0 }} 条)</span>
      </div>
      <div class="trace-step-body">
        <div v-for="(rw, i) in trace.rewrites" :key="i" class="mb-4">
          <span style="font-weight:500;">{{ rw.strategy }}:</span>
          <span class="trace-tag" style="max-width:100%;word-break:break-all;white-space:normal;">
            {{ rw.query?.length > 120 ? rw.query.slice(0, 120) + '...' : rw.query }}
          </span>
        </div>
      </div>
    </div>

    <!-- Step 3: Retrieval -->
    <div class="trace-step active">
      <div class="trace-step-title">3. 双路检索 (Dense + Sparse)</div>
      <div class="trace-step-body">
        <div>查询数量: <strong>{{ trace.retrieval.query_count || 1 }}</strong></div>
        <div>Dense 语义检索: <strong>{{ trace.retrieval.dense_total || 0 }}</strong> 条</div>
        <div>Sparse BM25 检索: <strong>{{ trace.retrieval.sparse_total || 0 }}</strong> 条</div>
        <div>去重后候选: <strong>{{ trace.retrieval.unique_after_merge || 0 }}</strong> 条</div>
        <div class="text-xs text-muted mt-4">{{ trace.retrieval.note }}</div>
      </div>
    </div>

    <!-- Step 4: RRF -->
    <div class="trace-step active">
      <div class="trace-step-title">4. RRF 融合排序</div>
      <div class="trace-step-body">
        <div>
          {{ trace.rrf.input_count || 0 }} 条候选
          → 截断至 <strong>{{ trace.rrf.output_count || 0 }}</strong> 条
        </div>
        <div class="text-xs text-muted mt-4">{{ trace.rrf.note }}</div>
      </div>
    </div>

    <!-- Step 5: Final Top-K -->
    <div class="trace-step active">
      <div class="trace-step-title">5. 最终送入 LLM 的 Top-{{ trace.final.count || 0 }} 分块</div>
      <div class="trace-step-body">
        <div v-if="!trace.final.chunks?.length" style="color:var(--c-text-muted);">
          无召回结果（可能知识库为空或查询无匹配文档）
        </div>
        <div v-for="(c, i) in trace.final.chunks" :key="i" class="trace-chunk">
          <div style="font-weight:500;">#{{ i + 1 }} {{ c.doc_name }}</div>
          <div v-if="c.header_path" class="text-xs text-muted">{{ c.header_path }}</div>
          <div class="text-xs text-muted mt-2">RRF 分数: {{ c.score }}</div>
          <div class="mt-4" style="color:var(--c-text-secondary);line-height:1.5;">{{ c.preview }}...</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ trace: { type: Object, default: () => ({}) } })
</script>

<style scoped>
.trace-step {
  margin-bottom: 12px;
  padding-left: 14px;
  border-left: 2px solid #d9d9d9;
}
.trace-step.active {
  border-left-color: var(--c-accent, #1890ff);
}
.trace-step-title {
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 6px;
  font-size: 13px;
}
.trace-step-body {
  color: var(--c-text-secondary);
  font-size: 12px;
  line-height: 1.8;
}
.trace-tag {
  display: inline-block;
  padding: 1px 8px;
  margin: 2px 4px;
  background: #e6f7ff;
  border-radius: 3px;
  font-size: 11px;
  color: #096dd9;
}
.trace-chunk {
  padding: 6px 10px;
  margin: 4px 0;
  background: #fff;
  border: 1px solid #eee;
  border-radius: 4px;
  font-size: 12px;
}
.text-xs { font-size: 11px; }
.text-muted { color: var(--c-text-muted); }
.mt-4 { margin-top: 4px; }
.mt-2 { margin-top: 2px; }
.mb-4 { margin-bottom: 4px; }
</style>
