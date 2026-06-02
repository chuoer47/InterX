# InterX KG Layer

知识图谱层 — 单手册内多跳语义检索增强。

## 架构

```
query → retrieval (首跳) → top small chunks
  → kg.expand(seed_chunks) → 扩展 chunk + 路径
  → answer (三粒度回答 + 集成)
```

## 图数据库

Kùzu (嵌入式，每个 manual 一个 `.kuzu` 文件)。

## 图谱数据

| 节点 | 数量 |
|------|------|
| Manual | 39 |
| SmallChunk | 7,215 |
| MidChunk | 4,365 |
| BigChunk | 3,718 |
| Question | 350 |

| 边 | 数量 | 权重 |
|----|------|------|
| CO_EVIDENCE | 48,508 | 0.5 |
| SEMANTIC | 3,084 | 1.0 |
| ANSWERS | 2,787 | 0.5 |

## 脚本

- `scripts/write_graph.py` — 构建/丰富/统计
- `scripts/phase3_batch.py` — LLM 批量提取 SEMANTIC 边
- `scripts/search_graph.py` — 调试图遍历

## 文档

- `docs/technical_design.md` — 完整技术方案
