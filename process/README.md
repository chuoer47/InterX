# InterX Process

批量 Chunk 生产管线 — 将产品手册 Markdown 解析为三级层次的文本块并构建向量索引。

## 项目概述

`process` 是 InterX 系统的**数据预处理层**。它将 `data/` 目录下的 40 份产品手册（Markdown 格式）解析并拆分为三级层次的文本块（big / mid / small），对小块执行多模态向量嵌入，最终写入 Milvus Lite 向量数据库。

该包为下游检索 (`retrieval`)、知识图谱 (`kg`)、问答 (`answer`) 提供结构化、可追溯的向量检索单元。每个 chunk 保留面包屑路径（header_path）、源文件行号（source_span）和层级 ID 链，支持 `small → mid → big` 全链路追溯。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 系统包 | `build-essential`（编译 tiktoken） |
| 外部服务 | DashScope 多模态嵌入 API（向量嵌入阶段需要） |

## 项目结构

```
process/
├── data/                              # 源 Markdown 手册（40 份）
│   ├── 插图/                          # 手册引用的图片文件
│   ├── Bosch_Microwave.md
│   ├── Canon_EOS_20D.md
│   └── ...
├── configs/
│   └── default.yaml                   # 默认配置文件
├── scripts/
│   ├── build_chunks.py                # 构建 chunks
│   ├── embed_chunks.py                # 向量嵌入
│   └── build_db.py                    # 向量库入库
├── src/
│   └── process_chunk/
│       ├── __init__.py                # 包入口
│       ├── config.py                  # 配置加载
│       ├── cli.py                     # CLI 入口
│       ├── models.py                  # Element / Section 数据模型
│       ├── tokenization.py            # Token 计数与拆分
│       ├── parser.py                  # Markdown 解析器
│       ├── builder.py                 # 三级 chunk 构建器
│       ├── pipeline.py                # 编排层
│       ├── embedding.py               # DashScope 多模态嵌入客户端
│       ├── vector_store.py            # Milvus Lite 写入
│       └── utils.py                   # 工具函数
└── artifacts/                         # 输出产物
    ├── manuals/<manual_id>/           # 每本手册的 chunk 文件
    ├── manifests/index.json           # 全局清单
    ├── reports/                       # 统计报告
    └── manual_chunks.db               # Milvus Lite 向量库
```

## 依赖清单

### 核心依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| markdown-it-py | >=3.0 | Markdown 解析（CommonMark + Table） |
| tiktoken | >=0.5 | Token 计数（cl100k_base 编码） |
| pymilvus | >=2.4 | Milvus 向量数据库客户端 |
| requests | >=2.28 | HTTP 请求（嵌入 API 调用） |
| python-dotenv | >=1.0 | `.env` 文件加载 |
| pyyaml | >=6.0 | YAML 配置解析 |

## 环境搭建

### 1. 克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>/InterX/process
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install markdown-it-py tiktoken pymilvus requests python-dotenv pyyaml
```

### 4. 配置环境变量

在 `InterX/process/` 目录下创建 `.env` 文件（向量嵌入阶段需要）：

```bash
cat > .env << 'EOF'
KAFU_LLM_API_KEY=your-dashscope-api-key
KAFU_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EOF
```

| 变量名 | 是否必填 | 说明 |
|--------|---------|------|
| `KAFU_LLM_API_KEY` | 嵌入阶段必填 | DashScope API 密钥 |
| `KAFU_LLM_BASE_URL` | 嵌入阶段必填 | DashScope API 地址 |

## 运行方式

### 第一步：构建 chunks

```bash
cd InterX/process

# 使用默认配置，清除已有产物后重新构建
python3 scripts/build_chunks.py

# 指定配置文件，保留已有产物
python3 scripts/build_chunks.py --config configs/other.yaml --no-clean
```

输出示例：
```
built 40 manuals
big=3761
mid=4416
small=7293
```

### 第二步：向量嵌入（需要 DashScope API）

```bash
python3 scripts/embed_chunks.py

# 只处理特定手册
python3 scripts/embed_chunks.py --manual "Bosch"

# 预览模式
python3 scripts/embed_chunks.py --dry-run
```

### 第三步：向量库入库

```bash
python3 scripts/build_db.py

# 追加模式（不重建）
python3 scripts/build_db.py --no-rebuild
```

### 验证

```bash
# 检查产物目录
ls artifacts/manuals/ | head -5
cat artifacts/manifests/index.json | python3 -m json.tool | head -20
```

## 配置说明

配置文件 `configs/default.yaml` 包含以下配置段：

- `paths`：数据和产物路径
  - `manual_dir`：源手册目录（默认 `data`）
  - `image_dir`：图片目录（默认 `data/插图`）
  - `artifact_dir`：产物输出目录（默认 `artifacts`）
- `manuals.exclude`：排除的非手册文件列表
- `tokenizer`：Token 计数器配置（`cl100k_base` 编码）
- `chunking.scheme`：三级分块参数（见下表）
- `api`：嵌入 API 凭证配置
- `embedding`：DashScope 多模态嵌入参数
- `vector_store`：Milvus 向量库参数

## 架构 / 数据流

```
data/*.md（40 份产品手册）
  │
  ▼  markdown-it-py 解析
AST → Section 列表（标题层级 + 内容元素）
  │
  ▼  贪心打包 + 带重叠拆分
Big Chunks（目标 900 tokens，上限 1200）
  │
  ▼  再次拆分打包
Mid Chunks（目标 520 tokens，上限 760）
  │
  ▼  再次拆分打包
Small Chunks（目标 220 tokens，上限 320，每块最多 1 张图片）
  │
  ▼  DashScope qwen3-vl-embedding
向量嵌入（1024 维，文本 + 图片融合）
  │
  ▼  pymilvus 写入
Milvus Lite（manual_chunks.db）
```

### Chunk 三级层次

| 层级 | 目标 Token | 上限 Token | 语义定位 |
|------|-----------|-----------|---------|
| Big | 900 | 1200 | 完整章节、背景上下文 |
| Mid | 520 | 760 | 操作流程、多步骤指南 |
| Small | 220 | 320 | 精确事实、定义、单步骤 |

层级关系通过 ID 链追溯：每个 small chunk 包含 `big_chunk_id` 和 `mid_chunk_id` 字段。每个 chunk 保留 `header_path`（面包屑路径）和 `source_span`（源文件行号范围），`content_hash`（MD5）支持增量重建。

## 输出产物

```
artifacts/
├── manuals/<manual_id>/
│   ├── big_chunks.jsonl        # 大块（每行一个 JSON 对象）
│   ├── mid_chunks.jsonl        # 中块
│   ├── small_chunks.jsonl      # 小块（含 embedding_payload）
│   ├── embeddings.jsonl        # 嵌入结果
│   └── manifest.json           # 手册级清单
├── manifests/
│   └── index.json              # 全局清单（40 本手册汇总）
├── reports/
│   ├── chunk_stats.json        # 统计报告（JSON）
│   └── chunk_stats.md          # 统计报告（Markdown）
├── logs/
│   └── build.log               # 构建日志
└── manual_chunks.db            # Milvus Lite 向量库
```

实际构建结果：40 本手册、3,761 个大块、4,416 个中块、7,293 个小块、2,595 个图片引用，总耗时约 2.6 秒。

## 测试

```bash
cd InterX/process
# 当前无自动化测试
# 可通过构建产物验证：检查 manifest.json 中的 chunk 数量
```

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| 构建后 `artifacts/` 为空 | 手册文件路径不正确 | 检查 `configs/default.yaml` 中 `paths.manual_dir` 指向 `data` |
| 嵌入阶段报 API 错误 | DashScope API 密钥未配置 | 检查 `.env` 文件中的 `KAFU_LLM_API_KEY` |
| 图片引用缺失 | `image_dir` 路径不对 | 确认 `data/插图/` 目录存在且包含对应图片文件 |

## 相关包

- `retrieval`：检索层，读取本包产出的 chunk 和向量库
- `kg`：知识图谱层，读取本包产出的 chunk JSONL 文件构建图谱
- `answer`：问答层，通过 retrieval 间接使用本包产物
