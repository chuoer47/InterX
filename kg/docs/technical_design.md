# InterX 知识图谱技术方案（v2 — 实现版）

> 本文档反映已实现的知识图谱架构，替代旧版设计文档。

---

## 1. 定位与目标

知识图谱层（`InterX/kg/`）是 InterX 系统的独立模块，定位为**检索增强层**：

- 不替换现有 dense/BM25 首跳检索
- 不替换 small/mid/big 三粒度回答链路
- 在首跳检索之后，通过图遍历补充**跨章节的语义关联证据**

### 核心解决的问题

单手册内的多跳问题：用户问"空调制冷效果差怎么办"，首跳命中"制冷效果差的常见原因"，但解决方案在另一个章节。传统 chunk 层级无法跨越这个距离，知识图谱通过语义边把它们连起来。

### 明确不做的事

- 跨手册推理
- 替代 dense retrieval 或 BM25
- 重复 mid/big 层级扩展

---

## 2. 架构总览

```
InterX/
├── process/      # 手册解析 → chunk 生成 + embedding
├── retrieval/    # dense + BM25 + fusion + rerank → 首跳 small chunk
├── kg/           # 知识图谱构建 + 图遍历扩展
├── answer/       # 三粒度回答 + 集成
├── chat/         # 多轮对话 + query rewrite + API
└── web/          # Streamlit 前端
```

KG 在检索链路中的位置：

```
query → retrieval (首跳) → top small chunks
  → kg.expand(seed_chunks) → 扩展 chunk + 路径
  → answer (三粒度回答 + 集成)
```

---

## 3. 图数据库选型：Kùzu

### 为什么不用 Neo4j

Neo4j 需要 Docker，当前环境无法拉取镜像（网络限制）。

### 为什么选 Kùzu

- 嵌入式图数据库，无需服务器进程
- 单文件存储，每个 manual 一个 `.kuzu` 文件
- 支持 Cypher-like 查询语法
- 零基础设施依赖

### 已知限制

| 问题 | 解决方案 |
|------|---------|
| `MERGE ... SET` 只支持单个属性 | `_merge_node()` 逐属性 MERGE |
| `MATCH ... SET` 不支持 | 只用 MERGE |
| 保留字冲突（`description`, `text`, `label`, `type`） | 使用 `descr`, `txt`, `lbl`, `ptype` |
| 同时打开过多数据库导致内存泄漏 | 逐 manual 处理，处理完立即关闭连接 |

---

## 4. 图 Schema

### 节点类型

| 节点 | 关键字段 | 来源 |
|------|---------|------|
| Manual | id, name | process artifacts |
| BigChunk | id, manual_id, section_title | process big_chunks.jsonl |
| MidChunk | id, manual_id, big_chunk_id | process mid_chunks.jsonl |
| SmallChunk | id, manual_id, mid_chunk_id, txt, section_title | process small_chunks.jsonl |
| Question | id, question_text, answer_text, lang, manual_guess | agentic-rag answers |

### 边类型

| 边 | 方向 | 权重 | 含义 |
|----|------|------|------|
| HAS_BIG | Manual → BigChunk | - | 层级结构 |
| HAS_MID | BigChunk → MidChunk | - | 层级结构 |
| HAS_SMALL | MidChunk → SmallChunk | - | 层级结构 |
| ANSWERS | SmallChunk → Question | 0.5 | chunk 参与回答了某个问题 |
| CO_EVIDENCE | SmallChunk ↔ SmallChunk | 0.5 | 两个 chunk 共同回答了同一问题 |
| SEMANTIC | SmallChunk ↔ SmallChunk | 1.0 | LLM 确认的语义关系 |

### 检索权重设计

```
score(expanded_chunk) = edge_weight × hop_decay × seed_score
hop_decay = 1.0 / (1.0 + 0.3 × hops)
```

- SEMANTIC 边：1.0（LLM 确认，高质量）
- CO_EVIDENCE 边：0.5（共现关联，未经语义确认）
- 跳数衰减：每跳衰减 30%

---

## 5. 冷启动方案：基于 agentic-rag 证据

### 为什么不用 LLM 盲猜 chunk 对

原方案：C(n,2) 暴力配对所有 small chunk，送 LLM 判断关系。
问题：40 个 manual × 平均 200 chunk = 数十万次 LLM 调用，成本和时间不可接受。

### 实际方案：利用已有问答证据

agentic-rag 已有 350 个问答，每个问答的 `evidence_refs` 指向手册中的具体行号范围。这些 evidence 是实际验证过的关联，比 LLM 盲猜可靠得多。

### 四阶段构建流水线

```
Phase 1: resolve_refs.py
  agentic-rag answers (350个) → 解析 evidence_refs
  处理 string/dict 两种格式，行号格式多样
  输出: evidence_resolved.json (1699/1798 refs, 94.5%)

Phase 2: line_to_chunk.py
  行号 → chunk_id 映射（基于 source_span 区间查找）
  输出: evidence_mapped.json

Phase 3: write_graph.py build
  创建结构节点 (Manual/BigChunk/MidChunk/SmallChunk)
  创建 Question 节点 + ANSWERS 边 + CO_EVIDENCE 边
  输出: Kùzu graph.db

Phase 4: extract_semantic.py (LLM 提取 SEMANTIC 边)
  每批 5 对 chunk，串行调用 mimo-v2.5-pro
  429 限流自动退避（2-5 分钟）
  输出: semantic_edges.json → write_graph.py enrich 写入图
```

### Phase 3 LLM 提取策略

- **批量 prompt**：一次 LLM 调用处理 5 对 chunk（而非逐对调用）
- **串行执行**：避免并发打满 API 限流
- **429 退避**：遇限流等待 2-5 分钟后重试
- **跳过同 big_chunk**：同一父块内的 chunk 已通过层级关系覆盖
- **跳过已处理**：支持 resume，断点续跑
- **成功/失败分别记录**：phase3_success.log / phase3_failure.log

---

## 6. 当前图谱数据

### 节点统计

| 节点类型 | 数量 |
|---------|------|
| Manual | 39 |
| SmallChunk | 7,215 |
| MidChunk | 4,365 |
| BigChunk | 3,718 |
| Question | 350 |

### 边统计

| 边类型 | 数量 | 权重 |
|--------|------|------|
| CO_EVIDENCE | 48,508 | 0.5 |
| SEMANTIC | 3,084 | 1.0 |
| ANSWERS | 2,787 | 0.5 |
| HAS_MID | 9,514 | - |
| HAS_SMALL | 9,514 | - |

### 数据来源

| 数据 | 量 | 来源 |
|------|-----|------|
| Evidence refs | 1,699 条 (94.5%) | agentic-rag 350 问答 |
| Line → chunk 映射 | 1,699 成功 | source_span 区间查找 |
| LLM 批量提取 | 499 批次, 7.5h | mimo-v2.5-pro |

### 存储

- Kùzu graph.db: 1,220 MB（39 个 .kuzu 文件）
- 实际数据约 2.5 MB，Kùzu 固有开销约 480 倍

---

## 7. 图遍历与检索扩展

### GraphRetriever

```python
retriever = GraphRetriever(settings, store)
expansion = retriever.expand(seed_chunks, manual_id)
# 返回: expanded_chunk_ids, paths, graph_scores
```

### 遍历算法

1. 从 seed chunks 收集关联的 SemanticPoint
2. BFS 遍历 SEMANTIC_REL 边（最多 max_hops 跳）
3. 将目标 SemanticPoint 映射回 SmallChunk
4. 计算图得分（边权重 × 跳数衰减）
5. 返回扩展 chunk 列表 + 路径解释

### 权重计算

```python
rel_score = max(REL_WEIGHTS[rel_type] for rel_type in rel_chain)
hop_decay = 1.0 / (1.0 + 0.3 * (hops - 1))
graph_score = rel_score * hop_decay * graph_bonus_weight
```

---

## 8. 脚本清单

| 脚本 | 用途 |
|------|------|
| `scripts/resolve_refs.py` | Phase 1: 解析 evidence_refs |
| `scripts/line_to_chunk.py` | Phase 2: 行号 → chunk_id |
| `scripts/write_graph.py` | Phase 3/4: 写入 Kùzu (build/enrich/stats) |
| `scripts/build_remaining.py` | 增量构建: 补建缺失的 Question/CO_EVIDENCE |
| `scripts/extract_semantic.py` | Phase 4: 批量 LLM 提取 SEMANTIC 边 |
| `scripts/enrich_remaining.py` | 增量写入: 补写 SEMANTIC 边 |
| `scripts/search_graph.py` | 调试: 测试图遍历 |

---

## 9. Skill: kg-cold-start

位于 `.codex/skills/kg-cold-start/`，包含完整的冷启动工作流定义：

```
SKILL.md                      # 工作流指引
scripts/
  resolve_refs.py             # Phase 1
  line_to_chunk.py            # Phase 2
  write_graph.py              # Phase 3/4
  build_remaining.py          # 增量构建
  extract_semantic.py             # LLM 批量提取
  enrich_remaining.py         # 增量写入
references/
  graph_schema.md             # 图 schema + 权重设计
  extraction_prompt.md        # LLM 提取 prompt
agents/
  openai.yaml                 # Skill 元数据
```

---

## 10. 已知问题与后续工作

### 已知问题

1. **Kùzu 存储开销大**：1,220 MB 存储 2.5 MB 数据。后续可考虑 NetworkX 内存图替代。
2. **SEMANTIC 边去重**：enrich 时未检查已有边，可能存在重复。可通过 MERGE 替代 CREATE 解决。
3. **LLM 提取偶发失败**：499 批次中有 2 批 JSON 解析失败，重试后成功。

### 后续工作

1. **检索链路集成**：将 GraphRetriever 接入 retrieval 层，在首跳检索后自动扩展。
2. **图谱增量更新**：新手册入库时自动构建图谱。
3. **关系类型细化**：当前只有 CO_EVIDENCE 和 SEMANTIC 两种，后续可根据 SEMANTIC 边的 description 细分为 CAUSES / RESOLVED_BY 等。
4. **图谱质量评估**：抽样检查 SEMANTIC 边的准确率，优化 prompt。
