# InterX Answer

多粒度集成问答管道 — 基于产品手册的智能客服回答生成。

## 项目概述

`answer` 是 InterX 系统的**问答核心引擎**。它接收用户的自然语言问题，通过多粒度检索获取证据，再由 LLM 分别在小粒度、中粒度、大粒度三个尺度上生成回答，最终通过集成融合输出高质量的综合答案。

该包位于检索层 (`retrieval`) 之上，知识图谱 (`kg`) 为可选扩展辅助。自身不管理数据库或向量索引，而是调用兄弟包 `retrieval` 和 `kg` 的能力。核心设计理念是**分层生成再融合**——兼顾精确事实、完整操作步骤和背景上下文三个维度。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 外部服务 | InterX Gateway（OpenAI 兼容 LLM API） |
| 兄弟包 | `retrieval`（必需）、`kg`（可选，未安装时优雅降级） |
| 向量数据库 | Milvus Lite（由 `retrieval` 包管理） |
| 图数据库 | Kùzu（由 `kg` 包管理，可选） |

## 项目结构

```
answer/
├── configs/
│   └── default.yaml              # 默认配置文件
├── scripts/
│   └── answer.py                 # CLI 入口脚本
├── src/
│   └── answer/
│       ├── prompts/              # LLM Prompt 模板
│       │   ├── router.md         # 路由分类（产品手册 vs 通用客服）
│       │   ├── general_answer.md # 通用客服回答模板
│       │   ├── small_answer.md   # 小粒度回答模板
│       │   ├── mid_answer.md     # 中粒度回答模板
│       │   ├── big_answer.md     # 大粒度回答模板
│       │   ├── ensemble.md       # 集成融合模板
│       │   ├── query_rewrite.md  # 查询改写模板
│       │   └── judge.md          # 评判模板（预留）
│       ├── __init__.py           # 包入口，导出公共 API
│       ├── config.py             # 配置 dataclass 与加载逻辑
│       ├── router.py             # 路由层（LLM 判断产品手册 vs 通用客服）
│       ├── pipeline.py           # 核心管道编排
│       ├── context.py            # 上下文组装（带预算控制）
│       ├── models.py             # 数据模型定义
│       ├── query_rewrite.py      # 查询改写（多变体生成）
│       ├── normalizer.py         # 答案后处理 / 归一化
│       ├── images.py             # 图片证据收集与多模态组装
│       └── utils.py              # 工具函数
├── tests/
│   ├── test_foundation.py
│   └── test_images_context.py
└── .gitignore
```

## 依赖清单

### 核心依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| openai | >=1.0 | LLM API 客户端（OpenAI 兼容协议） |
| pydantic | >=2.0 | 数据模型与 JSON Schema 验证 |
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
cd <REPO_PATH>/InterX/answer
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install openai pydantic python-dotenv pyyaml
# 如需运行测试
pip install pytest
```

### 4. 配置环境变量

在 `InterX/answer/` 目录下创建 `.env` 文件：

```bash
cat > .env << 'EOF'
INTERX_GATEWAY_API_KEY=your-gateway-api-key
INTERX_GATEWAY_BASE_URL=http://127.0.0.1:4000
EOF
```

| 变量名 | 是否必填 | 说明 |
|--------|---------|------|
| `INTERX_GATEWAY_API_KEY` | 是 | InterX Gateway 的 API 密钥 |
| `INTERX_GATEWAY_BASE_URL` | 是 | InterX Gateway 的服务地址 |

### 5. 确保下游服务就绪

```bash
# 确保 retrieval 包的向量数据库已构建（参见 process 包文档）
# 确保 InterX Gateway 已启动（参见 gateway 包文档）
```

## 运行方式

### Python API 调用

```python
from answer import answer, QASettings

settings = QASettings.load()       # 加载 configs/default.yaml
result = answer("空调制冷效果差怎么办？", settings=settings)
print(result.final_answer)         # 最终融合答案
print(result.to_dict())            # 完整结果（含三层子答案）
```

### CLI 调用

```bash
# 文本输出
python scripts/answer.py "空调制冷效果差怎么办？"

# JSON 输出，指定配置和 top-k
python scripts/answer.py "如何重置设备？" --config configs/default.yaml --top-k 10 --json
```

## 配置说明

配置文件 `configs/default.yaml` 包含以下主要配置段：

- `llm`：主 LLM 端点（默认模型 `qwen3.6-plus`），用于三层回答生成和集成融合
- `rewrite_llm`：查询改写 LLM 端点（默认模型 `qwen3-max`）
- `judge_llm`：评判 LLM 端点（预留）
- `retrieval_top_k` / `mid_top_k` / `big_top_k`：三级检索的 top-k 数量
- `small_layer` / `mid_layer` / `big_layer` / `ensemble_layer`：四层 LLM 调用参数（上下文字符预算、温度、最大 token、超时等）
- `query_rewrite`：查询改写开关与参数
- `kg`：知识图谱扩展开关与参数

每个 LLM 端点配置支持 `env_file`、`api_key_env`、`base_url_env`、`model_name` 字段，通过 `.env` 文件加载凭证。

## 架构 / 数据流

```
用户问题
  │
  ▼
查询改写 (qwen3-max) ──→ 生成最多 3 个变体查询（同义、跨语言、子问题分解）
  │
  ▼
层级检索 (retrieval.search_hierarchical)
  │──→ small_hits（精确事实）
  │──→ mid_hits（操作步骤）
  │──→ big_hits（背景概述）
  │
  ▼
KG 扩展（可选，kg.expand_hits）
  │──→ 通过 CO_EVIDENCE / SEMANTIC 边扩展 small_hits
  │
  ▼
三层并行 LLM 回答（ThreadPoolExecutor, max_workers=3）
  │──→ small_answer（8000 字符上下文，聚焦精确事实）
  │──→ mid_answer  （12000 字符上下文，聚焦操作步骤）
  │──→ big_answer  （16000 字符上下文，聚焦背景概述）
  │
  ▼
归一化（修复图片标记，去重，对齐 <PIC> 占位符）
  │
  ▼
集成融合 (ensemble) ──→ 合并三层回答，矛盾时小粒度优先
  │
  ▼
QAResult（final_answer + 三层子答案 + 元数据）
```

## 测试

```bash
# 运行全部测试
cd InterX/answer
pytest tests/ -v
```

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `ValueError: Missing API key` | `.env` 文件未配置或路径错误 | 检查 `InterX/answer/.env` 是否存在且包含 `INTERX_GATEWAY_API_KEY` |
| 回答中缺少图片 | `image_dir` 路径不正确 | 确认 `configs/default.yaml` 中 `image_dir` 指向 `../process/data/插图` |
| KG 扩展未生效 | `kg.enabled: false` 或 kuzu 未安装 | 设置 `kg.enabled: true` 并 `pip install kuzu` |

## 相关包

- `retrieval`：提供多通道混合检索能力（Dense + BM25 + Rerank），answer 包的核心上游
- `kg`：提供知识图谱扩展能力，通过图遍历补充跨章节语义关联证据
- `chat`：多轮对话层，调用 answer 包执行单次问答
- `gateway`：LLM API 网关，answer 包通过其访问 LLM 服务
- `process`：数据预处理层，提供结构化的 chunk 产物
