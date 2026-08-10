# RAG 系统 — 云服务器部署指南

## 前置条件

- 云服务器：2核 8GB 内存 40GB 磁盘（Linux）
- 已安装：Docker + Docker Compose
- 已安装：Git

```bash
# 确认版本
docker --version     # >= 24.0
docker compose version  # >= 2.0
```

---

## 第一步：克隆项目

```bash
git clone https://github.com/Cjay666/new_RAG.git
cd new_RAG
```

## 第二步：配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Key
nano .env
```

**必须修改的配置**：

```ini
# DeepSeek API（必须）
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥

# MinerU API（必须）
MINERU_API_KEY=sk-你的MinerU密钥

# 以下保持默认即可
OLLAMA_BASE_URL=http://ollama:11434
MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
```

## 第三步：拉取 Ollama 模型

```bash
# 先启动 Ollama 容器
docker compose up -d ollama

# 拉取三个模型（每个约 2GB，共 ~6.5GB）
docker exec -it rag-ollama ollama pull bge-m3
docker exec -it rag-ollama ollama pull bge-reranker-v2-m3
docker exec -it rag-ollama ollama pull qwen2.5:3b

# 验证
docker exec -it rag-ollama ollama list
```

## 第四步：启动全部服务

```bash
# 构建并启动所有容器
docker compose up -d --build

# 查看启动状态
docker compose ps

# 查看日志
docker compose logs -f backend
```

## 第五步：验证服务

```bash
# 后端健康检查
curl http://localhost:8000/api/health

# 前端访问
# 浏览器打开：http://你的服务器IP
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 (Vue + Nginx) | 80 | 浏览器访问入口 |
| 后端 (FastAPI) | 8000 | API 服务 |
| Milvus | 19530 | 向量数据库 |
| Ollama | 11434 | 本地模型服务 |

---

## 使用流程

1. 浏览器打开 `http://你的服务器IP`
2. 创建知识库
3. 上传文档（PDF/Word/TXT 等）
4. 等待文档入库完成（状态变为 ✅ 已入库）
5. 新建会话，开始提问

---

## 常用运维命令

```bash
# 查看所有服务状态
docker compose ps

# 查看后端日志
docker compose logs -f backend

# 重启某个服务
docker compose restart backend

# 停止所有服务
docker compose down

# 重新构建并启动
docker compose up -d --build

# 清理所有数据（危险操作）
docker compose down -v
```

---

## 常见问题

### Q: 8GB 内存够用吗？
A: 够用。Ollama 三个模型约 6.5GB，但不会同时加载：
- Embedding（索引时加载）
- Reranker（精排时加载）
- 本地 LLM（改写时加载）
- 同时最多 2 个模型在内存中

### Q: 文档上传后一直"解析中"？
A: 检查 MinerU API Key 是否正确，查看后端日志：
```bash
docker compose logs backend | grep -i error
```

### Q: 检索结果为空？
A: 确认文档状态为"已入库"，Milvus 和 BM25 索引都正常。

### Q: 上传的文档能支持多大？
A: 默认 50MB。大型文档建议先分割后再上传。

### Q: 怎么查看 Ollama 模型是否在运行？
A: `docker exec rag-ollama ollama ps`
