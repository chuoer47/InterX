# InterX Data

产品手册数据与构建产物的唯一权威来源。各包通过 symlink 或解压引用此处的数据。

## 内容

| 文件 / 目录 | 说明 | 大小 | 交付方式 |
|-------------|------|------|---------|
| `ch-manual/*.md` | 中文产品手册（21 份） | 460 KB | git |
| `ch-manual/手册内容总览.md` | 中文手册路由索引 | 5 KB | git |
| `ch-manual/插图.zip` | 中文手册配图（2,629 张） | 136 MB | git |
| `en-manual/*.md` | 英文产品手册（21 份） | 1.2 MB | git |
| `en-manual/插图.zip` | 英文手册配图（2,632 张） | 136 MB | git |
| `build-artifacts.tar.gz` | 构建产物（见下方说明） | 67 MB | git |

## build-artifacts.tar.gz 说明

包含 `process` 和 `retrieval` 包运行所需的预构建数据，解压后放置于 `InterX/process/artifacts/`。

```
build-artifacts.tar.gz
└── manuals/                    # 40 份手册的 chunk 产物
    └── <manual_id>/
        ├── big_chunks.jsonl    # 大块（目标 900 tokens）
        ├── mid_chunks.jsonl    # 中块（目标 520 tokens）
        ├── small_chunks.jsonl  # 小块（目标 220 tokens，主要检索单元）
        ├── embeddings.jsonl    # 1024 维向量嵌入（DashScope qwen3-vl-embedding）
        └── manifest.json       # 手册级清单
```

| 组件 | 说明 | 复现依赖 |
|------|------|---------|
| `manuals/` | chunk 元数据 + 预计算向量 | 无（直接使用） |

解压后需运行 `build_db.py` 构建 Milvus 向量库（无需 API，纯本地操作）。

## 使用方式

### 1. 解压构建产物

```bash
cd InterX
tar -xzf data/build-artifacts.tar.gz -C process/artifacts/
```

### 2. 构建 Milvus 向量库

```bash
cd InterX/process
python scripts/build_db.py
```

无需外部 API，从解压的 `embeddings.jsonl` + `small_chunks.jsonl` 构建向量索引。

验证：
```bash
ls process/artifacts/manual_chunks.db/collections/    # 应包含 manual_chunks
```

### 3. 解压手册配图（可选，用于 answer 包的多模态功能）

```bash
cd InterX/data
unzip ch-manual/插图.zip -d ch-manual/
unzip en-manual/插图.zip -d en-manual/
```

### 3. 重建知识图谱（可选，用于 answer 包的 KG 扩展）

```bash
cd InterX/kg

# 从证据数据构建图结构
python .agents/skills/kg-cold-start/scripts/write_graph.py build \
  --evidence state/evidence_mapped.json \
  --graph-dir state/graph.db \
  --process-dir ../process/artifacts/manuals

# 追加 LLM 语义边（预计算结果，无需 API）
python .agents/skills/kg-cold-start/scripts/write_graph.py enrich \
  --graph-dir state/graph.db \
  --semantic state/semantic_edges.json
```

中间产物（已提交到 git，共 2.4 MB）：

| 文件 | 说明 |
|------|------|
| `kg/state/evidence_resolved.json` | 解析后的证据引用 |
| `kg/state/evidence_mapped.json` | 映射到 chunk 的证据数据 |
| `kg/state/semantic_edges.json` | LLM 预计算的语义关系边 |

### symlink 引用

```
InterX/agentic-rag/ch-manual → ../data/ch-manual
InterX/agentic-rag/en-manual → ../data/en-manual
```

## 数据来源

- 中文手册：原根目录 `data/ch-manual/`
- 英文手册：原 `InterX/agentic-rag/en-manual/`（文件数最全）
- 构建产物：由 `process` 包的 `build_chunks.py` + `embed_chunks.py` + `build_db.py` 生成
- 图谱中间产物：由 `kg` 包的冷启动流程生成（`write_graph.py` + DashScope LLM）
