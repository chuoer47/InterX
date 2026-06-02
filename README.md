# InterX

基于产品手册的智能客服系统 — 多通道检索、知识图谱增强、多粒度集成问答。

## 项目概述

InterX 是一个端到端的产品手册问答系统，接收用户的自然语言问题（支持中英文），从 40 份产品手册中检索证据，由 LLM 生成带图片引用的回答，并支持多轮对话。

系统采用分层架构：数据预处理 → 多通道检索 → 知识图谱扩展 → 多粒度回答生成 → 集成融合 → 多轮对话编排 → Web UI。

## 系统架构

```
用户 ──→ web (Streamlit UI)
           │
           ▼
        chat (多轮对话编排)
           │── 查询改写（历史感知）
           ▼
        answer (多粒度集成问答)
           │── retrieval (Dense + BM25 + Rerank)
           │── kg (知识图谱扩展，可选)
           │── LLM 三层并行生成 + ensemble 融合
           ▼
        gateway (LiteLLM 统一 LLM 网关)
           │── 多上游路由（MiMo / DashScope / GPT-5.5）
           │── 语义缓存（精确匹配 + LLM 等价判断）
           ▼
        上游 LLM API
```

## 包说明

| 包 | 说明 | 文档 |
|---|---|---|
| `process` | 数据预处理：Markdown 解析 → 三级 chunk → 向量嵌入 → Milvus 入库 | [README](process/README.md) |
| `retrieval` | 多通道检索：Dense + BM25 融合 + Rerank 重排，三级层次聚合 | [README](retrieval/README.md) |
| `kg` | 知识图谱：Kùzu 图数据库，LLM 语义关系提取，多跳图遍历扩展 | [README](kg/README.md) |
| `answer` | 问答引擎：路由判断 + 查询改写 + 三层并行 LLM 回答 + ensemble 融合 | [README](answer/README.md) |
| `chat` | 对话层：会话管理、记忆策略（滑动窗口/摘要）、查询改写 | [README](chat/README.md) |
| `gateway` | LLM 网关：LiteLLM 代理、多上游路由、语义缓存、Prometheus 监控 | [README](gateway/README.md) |
| `web` | 前端 UI：Streamlit 聊天界面，支持图片上传和会话管理 | [README](web/README.md) |
| `agentic-rag` | 评估数据集：351 道中英文问答题 + 证据笔记 + 答案 | [README](agentic-rag/README.md) |
| `data` | 数据仓库：产品手册、配图、构建产物 | [README](data/README.md) |

## 项目复现

### 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 系统包 | `build-essential`（编译 tiktoken） |
| Redis（可选） | 用于 gateway 语义缓存，不安装时缓存功能不可用但不影响核心功能 |
| 磁盘空间 | 约 2 GB（含数据和依赖） |

### 第一步：克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>
```

> `<REPO_URL>` 请替换为实际的 GitHub 仓库地址。

### 第二步：安装依赖

```bash
cd InterX

for pkg in process retrieval kg answer chat gateway web; do
  cd $pkg
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
  cd ..
done
```

> 如需使用 gateway 的语义缓存，还需安装：`cd gateway && source .venv/bin/activate && pip install -r extensions/semantic_cache/requirements.txt`

### 第三步：配置环境变量

每个包需要 `.env` 文件。各包均提供了 `.env.example` 模板：

```bash
for pkg in process retrieval kg answer chat gateway web; do
  cp $pkg/.env.example $pkg/.env
done
```

然后编辑各 `.env` 文件填入实际的 API 密钥。核心变量说明：

| 变量 | 用于 | 说明 |
|------|------|------|
| `INTERX_GATEWAY_API_KEY` | answer, chat, kg | Gateway 的 API 鉴权密钥 |
| `INTERX_GATEWAY_BASE_URL` | answer, chat, kg | Gateway 地址（默认 `http://127.0.0.1:4000`） |
| `LITELLM_MASTER_KEY` | gateway | Gateway 自身的主密钥 |
| `DASHSCOPE_API_KEY` | gateway | 阿里 DashScope API 密钥 |
| `UPSTREAM_1_BASE_URL` | gateway | 第一上游 LLM 地址 |
| `UPSTREAM_1_API_KEY` | gateway | 第一上游 LLM 密钥 |
| `UPSTREAM_1_MODEL` | gateway | 第一上游模型名 |
| `KAFU_LLM_API_KEY` | process, retrieval | DashScope API 密钥（嵌入/重排序） |
| `KAFU_LLM_BASE_URL` | process, retrieval | DashScope API 地址 |
| `INTERX_CHAT_API_BASE` | web | Chat API 地址（默认 `http://127.0.0.1:8000`） |
| `INTERX_CHAT_API_TOKEN` | web | Chat API Token（默认 `sk_local_dev`） |

### 第四步：解压构建产物

```bash
tar -xzf data/build-artifacts.tar.gz -C process/artifacts/
```

该文件（67 MB）包含 40 份手册的 chunk 产物（含预计算向量），已提交到 git，**无需额外下载，无需调用任何外部 API**。

### 第五步：构建 Milvus 向量库

```bash
cd process && python scripts/build_db.py && cd ..
```

验证：
```bash
ls process/artifacts/manuals/ | wc -l                    # 应输出 40
ls process/artifacts/manual_chunks.db/collections/       # 应包含 manual_chunks
```

### 第六步：重建知识图谱（可选）

answer 包的 KG 扩展功能需要图数据库。中间产物已包含在仓库中（2.4 MB），无需 LLM API：

```bash
cd kg

python .agents/skills/kg-cold-start/scripts/write_graph.py build \
  --evidence state/evidence_mapped.json \
  --graph-dir state/graph.db \
  --process-dir ../process/artifacts/manuals

python .agents/skills/kg-cold-start/scripts/write_graph.py enrich \
  --graph-dir state/graph.db \
  --semantic state/semantic_edges.json

cd ..
```

验证：
```bash
ls kg/state/graph.db/*.kuzu | wc -l                      # 应输出 39
```

### 第七步：解压手册配图（可选）

answer 包的多模态功能需要图片文件：

```bash
cd data
unzip ch-manual/插图.zip -d ch-manual/
unzip en-manual/插图.zip -d en-manual/
cd ..
```

### 第八步：创建 agentic-rag 软链接（可选）

`agentic-rag` 包的手册和图片通过软链接引用 `data/` 目录：

```bash
cd agentic-rag
ln -s ../data/ch-manual ch-manual
ln -s ../data/en-manual en-manual
cd ..
```

### 第九步：启动服务

```bash
# 1. 启动 LLM 网关
cd gateway && bash scripts/start_local.sh && cd ..

# 2. 启动对话 API
cd chat && uvicorn src.chat.api:app --host 0.0.0.0 --port 8000 &

# 3. 启动 Web UI
cd web && streamlit run app.py --server.port 8501
```

浏览器打开 `http://127.0.0.1:8501` 即可使用。

### 复现检查清单

| 检查项 | 验证命令 | 预期结果 |
|--------|---------|---------|
| 依赖已安装 | `cd process && python -c "import pymilvus; print('ok')"` | `ok` |
| 构建产物已解压 | `ls process/artifacts/manuals/ \| wc -l` | `40` |
| 向量库已构建 | `ls process/artifacts/manual_chunks.db/collections/` | `manual_chunks` |
| 图谱已重建（可选） | `ls kg/state/graph.db/*.kuzu \| wc -l` | `39` |
| 网关运行中 | `curl http://127.0.0.1:4000/health` | 正常响应 |
| 对话 API 运行中 | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| Web UI 可访问 | 浏览器打开 `http://127.0.0.1:8501` | 聊天界面 |

## 数据集

`agentic-rag/` 包含 351 道中英文问答评估题（163 中文 + 188 英文），覆盖 42 份产品手册。每题附带证据笔记和结构化答案，可用于评估系统回答质量。详见 [agentic-rag/README.md](agentic-rag/README.md)。

## 相关链接

- 各包详细文档：见上表中的 README 链接
- 技术设计：[kg/docs/technical_design.md](kg/docs/technical_design.md)
- 项目规划：[gateway/PRD.md](gateway/PRD.md)、[gateway/TECH_ROUTE.md](gateway/TECH_ROUTE.md)
