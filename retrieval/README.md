# InterX Retrieval

多通道混合检索模块 — Dense + BM25 融合检索，支持多模态查询和三级层次聚合。

## 项目概述

`retrieval` 是 InterX 项目的**检索引擎**，在已处理的产品手册 chunk 上执行端到端的语义检索。它结合稠密向量检索（Dense）和稀疏 BM25 检索，通过 RRF 融合后经 Rerank 二阶段重排，返回 small / mid / big 三级层次的命中结果。

该包支持纯文本和图文混合的多模态查询，面向客服场景优化，为下游问答 (`answer`) 和知识图谱 (`kg`) 提供高质量的检索证据。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 系统包 | `build-essential`（编译依赖） |
| 外部服务 | DashScope API（嵌入 + Rerank） |
| 数据依赖 | `process` 包的 chunk 产物和向量库 |

## 项目结构

```
retrieval/
├── configs/
│   └── default.yaml              # 默认配置文件
├── scripts/
│   └── search.py                 # CLI 搜索工具
├── src/
│   └── retrieval/
│       ├── __init__.py           # 包入口，导出公共 API
│       ├── config.py             # 配置 dataclass 与加载逻辑
│       ├── retriever.py          # 检索编排器（混合召回 + 层级聚合）
│       ├── dense.py              # 向量检索（DashScope + Milvus）
│       ├── sparse.py             # BM25 稀疏检索（纯内存）
│       ├── fusion.py             # 多通道融合（RRF 算法）
│       ├── rerank.py             # 二阶段重排序（DashScope Rerank）
│       ├── context.py            # Prompt 上下文组装
│       ├── types.py              # 数据模型定义
│       ├── tokenizer.py          # 中英混合分词器（jieba + n-gram）
│       └── utils.py              # 工具函数
└── tests/
    └── test_retrieval.py
```

## 依赖清单

### 核心依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| pymilvus | >=2.4 | Milvus 向量数据库客户端 |
| rank-bm25 | >=0.2 | BM25 稀疏检索 |
| jieba | >=0.42 | 中文分词 |
| requests | >=2.28 | HTTP 请求（嵌入 / Rerank API） |
| python-dotenv | >=1.0 | `.env` 文件加载 |
| pyyaml | >=6.0 | YAML 配置解析 |

### 开发 / 测试依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| pytest | >=7.0 | 测试 |

## 环境搭建

### 1. 克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>/InterX/retrieval
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install pymilvus rank-bm25 jieba requests python-dotenv pyyaml
```

### 4. 配置环境变量

在 `InterX/retrieval/` 目录下创建 `.env` 文件：

```bash
cat > .env << 'EOF'
KAFU_LLM_API_KEY=your-dashscope-api-key
KAFU_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EOF
```

| 变量名 | 是否必填 | 说明 |
|--------|---------|------|
| `KAFU_LLM_API_KEY` | 是 | DashScope API 密钥（嵌入 + Rerank 共用） |
| `KAFU_LLM_BASE_URL` | 是 | DashScope API 地址 |

### 5. 确保数据就绪

```bash
# 确保 process 包的 chunk 产物和向量库已构建
ls ../process/artifacts/manuals/ | head -5
ls ../process/artifacts/manual_chunks.db
```

## 运行方式

### Python API 调用

```python
from retrieval import search, search_hierarchical, assemble_context

# 小块级检索
hits = search("空调制冷效果差怎么办？")

# 三级层次检索（供 answer 包使用）
result = search_hierarchical("如何重置设备？")
print(result.small_hits)   # 小块命中
print(result.mid_hits)     # 中块聚合
print(result.big_hits)     # 大块聚合

# 组装 LLM 上下文
context = assemble_context(hits, max_tokens=4000)
```

### CLI 搜索

```bash
cd InterX/retrieval

# 基本搜索
python scripts/search.py "空调制冷效果差怎么办？"

# 指定返回层级
python scripts/search.py "如何重置？" --level all

# 禁用 Rerank
python scripts/search.py "滤网更换" --no-rerank

# JSON 输出
python scripts/search.py "温度设置" --json

# 输出 LLM 上下文
python scripts/search.py "安装说明" --context --context-tokens 3000

# 按文档过滤
python scripts/search.py "按键说明" --filter 'doc_name == "Bosch_Microwave"'
```

### 验证

```bash
# 运行测试
pytest tests/ -v
```

## 配置说明

配置文件 `configs/default.yaml` 包含以下配置段：

- `api`：DashScope API 凭证（`.env` 文件路径和环境变量名）
- `embedding`：嵌入模型配置
  - `model_name`：`qwen3-vl-embedding`（多模态）
  - `dimension`：1024 维
  - `enable_fusion`：true（文本 + 图片融合嵌入）
  - `query_prompt` / `document_prompt`：查询侧和文档侧的 prompt
- `vector_store`：Milvus 向量库配置
  - `collection_name`：`manual_chunks`
  - `metric_type`：`COSINE`
- `rerank`：重排序配置
  - `enabled`：true
  - `model_name`：`qwen3-rerank`
- `fusion`：融合配置
  - `method`：`rrf`（Reciprocal Rank Fusion）
  - `rrf_k`：60
  - `channel_weights`：`dense: 0.65, bm25: 0.35`
- `params`：检索参数
  - `bm25_top_k` / `dense_top_k`：各通道召回数（默认 20）
  - `hybrid_top_k`：融合后返回数（默认 10）
  - `rerank_candidate_k`：重排候选数（默认 20）
  - `return_mid_top_k` / `return_big_top_k`：中块 / 大块返回上限

## 架构 / 数据流

```
用户查询（文本 + 可选图片）
  │
  ▼
第一阶段：双通道召回（并行）
  │── Dense: embed_query() → Milvus ANN 搜索 → top 20
  │── BM25: jieba + n-gram 分词 → 内存索引打分 → top 20
  │
  ▼
第二阶段：通道融合
  RRF: rrf_score = Σ (weight / (k + rank))
  Dense 权重 0.65, BM25 权重 0.35, k=60
  → top 20 候选
  │
  ▼
第三阶段：二阶段重排序
  qwen3-rerank 对候选打分，按新分数重排
  （失败时静默降级到融合排序）
  │
  ▼
第四阶段：层级聚合
  small_hits → 按 mid_chunk_id 聚合 → mid_hits
  mid_hits  → 按 big_chunk_id 聚合 → big_hits
  │
  ▼
HierarchicalResult (small_hits + mid_hits + big_hits + meta)
```

## 测试

```bash
cd InterX/retrieval
pytest tests/ -v

# 查看覆盖率
pytest tests/ --cov=retrieval --cov-report=term-missing
```

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `pymilvus` 连接失败 | 向量库文件不存在 | 运行 `process` 包的 `build_db.py` 构建向量库 |
| 嵌入 API 报 401 | DashScope API 密钥未配置 | 检查 `.env` 文件中的 `KAFU_LLM_API_KEY` |
| BM25 检索无结果 | jieba 词典加载失败 | 确认 `jieba` 包已安装：`pip install jieba` |
| Dense 检索降级 | DashScope API 不可用 | 系统会自动降级为纯 BM25（需 `allow_dense_fallback: true`） |

## 相关包

- `answer`：问答层，调用 `search_hierarchical()` 获取三级检索结果
- `kg`：知识图谱层，使用本包的 seed hits 进行图扩展
- `process`：数据预处理层，提供 chunk 产物和向量库
