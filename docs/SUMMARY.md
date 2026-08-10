# RAG 智能问答系统 — 需求设计与技术方案汇总

## 项目定位

构建一个单用户、多会话窗口的 RAG 智能问答系统，支持文档知识库管理、智能检索问答、系统质量评测。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3（4个页面：对话问答、文档管理、评测面板、实验对比） |
| 后端 | FastAPI（异步高性能 Python Web 框架） |
| 编排 | LangChain + LangGraph（最新版） |
| 向量库 | Milvus |
| 主力 LLM | DeepSeek V4 Pro（云端 API） |
| 文档解析 | MinerU 在线 API |
| Embedding | BGE-M3（Ollama 本地，~2.2GB） |
| Reranker | BGE-Reranker v2-m3（Ollama 本地，~2.2GB） |
| 本地 LLM | Qwen2.5 3B（Ollama 本地，~2GB）— Router / 改写 / RAGAS裁判 / 兜底 |
| 部署 | Docker 容器化，云服务器 2核8G+40G |
| 版本管理 | Git（github.com/Cjay666/new_RAG.git） |

---

## RAG 核心流程

### 一、文档入库（离线/在线）

```
文档上传（PDF/Word/PPT/图片/TXT/CSV）
  → MinerU API 解析 → 结构化 Markdown
  → 分块（Markdown标题切分 + 递归分隔符，500~800字，100~150重叠）
  → BGE-M3 Embedding 向量化
  → 存入 Milvus + 同时建立 BM25 倒排索引
  → Small-to-Big：子块 embedding + parent_id 指向父文档
```

分块策略按文件格式分级：
- PDF/Word/PPT/图片 → MinerU → Markdown → 标题切分 + 递归分隔符
- Markdown → 标题切分 + 递归分隔符
- TXT → 纯递归分隔符（段落→句子→字符）
- CSV → 按行转文本描述，每行一个 chunk，不硬切

### 二、查询处理（在线）

```
用户提问
  → Query Router（Qwen2.5 3B 判断问题类型）
    ├─ 清晰明确 → 跳过改写，直接检索
    └─ 模糊/复杂 → 触发 Query Rewriting（三策略并行）：
        ├─ HyDE：LLM 生成假设性答案，用答案向量检索
        ├─ Step Back：回退到原理层，拆分为原子子问题各自检索
        ├─ 脱水消歧：消解代词 + 去掉废话，产出干净检索句
        └─ 原始 Query 保底通道（防止改偏）
```

### 三、混合检索 & 分层召回

```
各路 Query × 2种检索 = N路结果集
  ├─ Dense 语义检索（向量相似度 → Milvus）
  └─ Sparse 字面检索（BM25 倒排索引）

粗召回（各路Top-100合并 ~200条）
  → 粗排 RRF（倒数排名融合，纯数学，零成本，200→30）
  → 精排 Reranker（BGE-Reranker v2-m3 Cross-Encoder，30→Top-K 5~10）
  → Small-to-Big 回填（子块 parent_id 反查完整父文档）
```

### 四、生成 & 评测

```
拼接 Prompt（System提示词 + 检索上下文 + 对话历史 + 用户问题）
  → DeepSeek V4 Pro 生成回答（含引用来源标注）
  → 返回前端展示

RAGAS 评测（Qwen2.5 3B 当裁判）：
  四个指标：Context Precision / Context Recall / Faithfulness / Answer Relevancy
  开发阶段：调参对比选最优配置
  上线后：定期跑测试集，前端可视化追踪趋势
```

---

## 前端四大页面

| 页面 | 功能 |
|------|------|
| **对话问答** | 会话列表 + 多轮对话 + 检索来源可视化（chunk排名/分数） |
| **文档管理** | 知识库CRUD + 文档上传 + 解析状态追踪 + Markdown预览 |
| **评测面板** | 四指标分数卡 + 历史趋势折线图 + 评测记录列表 |
| **实验对比** | 配置对比实验（chunk_size/Top-K/有无HyDE等）+ 结果并排对比 |

---

## 模型部署策略

| 模型 | 部署方式 | 用途 | 大小 |
|------|----------|------|------|
| DeepSeek V4 Pro | 云端 API | 主力对话生成 | — |
| BGE-M3 | Ollama 本地 | Embedding 向量化 | ~2.2G |
| BGE-Reranker v2-m3 | Ollama 本地 | 精排重打分 | ~2.2G |
| Qwen2.5 3B | Ollama 本地 | Router/改写/RAGAS裁判/兜底 | ~2G |
| MinerU | 云端 API | 文档解析 | — |

> 8GB 内存限制：Ollama 三模型**按需加载、用完即卸**，同时最多跑 2 个。

---

## 开发阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | 文档入库 → 分块 → Embedding → Milvus+BM25 → 基础检索 → LLM回答 | 🔴 最高 |
| P1 | Query Router + 三策略改写 + 混合检索 + RRF + Reranker + Small-to-Big | 🔴 最高 |
| P2 | 前端四页面（对话/文档管理/评测/实验对比） | 🟡 高 |
| P3 | RAGAS 评测集成 + 测试集管理 + 前端可视化 | 🟡 高 |
| P4 | Docker 编排 + Git + CI/CD | 🟢 中 |

---

## 关键设计决策

1. **双轨保底**：无论走哪条 Query 改写策略，原始 Query 始终保留一条检索通道，防止改偏
2. **一个 Reranker**：粗排靠 RRF 数学融合（零成本），精排才用 Reranker
3. **MinerU 在线 API**：避免本地部署 5GB+ 镜像，PDF/Word/图片统一走 Markdown 通道
4. **Small-to-Big**：小块做精准语义匹配，检索后回填完整父文档上下文
5. **模型按需加载**：2核8G 服务器跑三个 Ollama 模型，用完即卸

> ⚠️ 安全：所有 API Key 通过 Docker 环境变量注入，不硬编码。
