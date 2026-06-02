# InterX Chat

多轮对话层 — 会话管理、记忆策略与查询改写编排。

## 项目概述

`chat` 是 InterX 智能客服系统的**多轮对话编排层**。它不包含独立的问答引擎，而是负责管理会话状态、历史记忆和查询改写，将改写后的独立问题交给 `answer` 包执行实际的检索与回答生成。

核心设计理念：**chat 层只管对话流程，answer 层只管单次问答**。历史对话通过 LLM 改写为自包含的独立查询后再交给下游，answer 层无需感知对话历史。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 外部服务 | InterX Gateway（OpenAI 兼容 LLM API） |
| 兄弟包 | `answer`（必需，通过 `sys.path` 动态导入） |

## 项目结构

```
chat/
├── configs/
│   └── default.yaml              # 默认配置文件
├── scripts/
│   └── chat.py                   # CLI 入口脚本
├── sessions/                     # 会话持久化目录（JSON 文件）
│   └── {user_id}/{session_id}.json
├── src/
│   └── chat/
│       ├── prompts/              # LLM Prompt 模板
│       │   ├── rewrite.md        # 查询改写模板
│       │   └── summarize.md      # 对话摘要模板
│       ├── __init__.py           # 包入口，导出公共 API
│       ├── api.py                # FastAPI REST API 层
│       ├── config.py             # 配置 dataclass 与加载逻辑
│       ├── memory.py             # 记忆策略（滑动窗口 / 摘要 / 混合）
│       ├── models.py             # 数据模型（Turn / Session / ChatResponse）
│       ├── pipeline.py           # 核心管道编排
│       ├── query_rewrite.py      # 历史感知的查询改写
│       ├── store.py              # 会话 JSON 文件持久化
│       └── utils.py              # 工具函数
├── tests/
│   ├── test_api.py
│   └── test_chat.py
└── .gitignore
```

## 依赖清单

### 核心依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| fastapi | >=0.100 | REST API 框架 |
| uvicorn | >=0.20 | ASGI 服务器 |
| openai | >=1.0 | LLM API 客户端 |
| pydantic | >=2.0 | 数据模型验证 |
| python-dotenv | >=1.0 | `.env` 文件加载 |
| pyyaml | >=6.0 | YAML 配置解析 |

### 开发 / 测试依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| pytest | >=7.0 | 测试 |
| httpx | >=0.24 | FastAPI 测试客户端 |

## 环境搭建

### 1. 克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>/InterX/chat
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install fastapi uvicorn openai pydantic python-dotenv pyyaml
```

### 4. 配置环境变量

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

## 运行方式

### 启动 API 服务

```bash
cd InterX/chat
uvicorn src.chat.api:app --host 0.0.0.0 --port 8000
```

### 验证

```bash
curl http://127.0.0.1:8000/health
# 返回: {"status": "ok"}
```

### Python API 调用

```python
from chat import chat, ChatSettings

settings = ChatSettings.load()
result = chat("这个产品怎么用？", settings=settings)
print(result.answer)
```

### CLI 调用

```bash
python scripts/chat.py "这个产品怎么用？"
```

## 配置说明

配置文件 `configs/default.yaml` 包含以下配置段：

- `llm`：LLM 端点配置（默认模型 `qwen3-max`），用于查询改写和摘要生成
- `memory`：记忆策略配置
  - `strategy`：`sliding_window` / `summary` / `sliding_summary`（默认）
  - `window_size`：滑动窗口保留轮数（默认 5）
  - `max_summary_tokens`：摘要最大 token 数（默认 500）
  - `summary_trigger_turns`：触发摘要的轮数阈值（默认 10）
- `query_rewrite`：查询改写配置（默认启用，温度 0.1）
- `session_dir`：会话持久化目录（默认 `sessions`）

## 架构 / 数据流

```
用户请求 (question + session_id + images)
  │
  ▼
API 层 / CLI ──→ 验证 Token，解析 Base64 图片为临时文件
  │
  ▼
pipeline.chat() 核心编排
  │
  ├──→ 1. 加载/创建 Session (store)
  │
  ├──→ 2. 构建历史上下文 (memory)
  │        ┌─ sliding_window: 最近 N 轮原始对话
  │        ├─ summary: LLM 摘要 + 最近一轮
  │        └─ sliding_summary: 摘要 + 最近 N 轮（默认）
  │
  ├──→ 3. 查询改写 (query_rewrite)
  │        LLM 将带历史上下文的问题重写为自包含独立问题
  │
  ├──→ 4. 调用 answer 层
  │        传入改写后的独立问题，返回检索结果和回答
  │
  ├──→ 5. 记录 Turn，更新摘要 (memory)
  │
  └──→ 6. 持久化 Session (store)
  │
  ▼
ChatResponse (answer, session_id, rewritten_query, image_ids)
```

## 接口说明

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/chat` | POST | Bearer Token | 主聊天接口，处理多轮对话请求 |
| `/images/{image_id}` | GET | Bearer Token | 获取检索到的产品手册图片 |
| `/sessions/{user_id}` | GET | Bearer Token | 列出某用户的所有会话 ID |
| `/sessions/{user_id}/{session_id}` | GET | Bearer Token | 获取单个会话的完整数据 |
| `/sessions/{user_id}/{session_id}/reset` | POST | Bearer Token | 重置会话为空状态 |
| `/health` | GET | 无 | 健康检查端点 |

### POST `/chat` 请求体

```json
{
  "question": "这个产品怎么用？",
  "images": ["data:image/png;base64,..."],
  "session_id": "abc123",
  "user_id": "user001"
}
```

### POST `/chat` 响应体

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "answer": "产品使用方法...",
    "session_id": "abc123",
    "timestamp": 1717200000,
    "image_ids": ["img_001"]
  }
}
```

## 测试

```bash
cd InterX/chat
pytest tests/ -v
```

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| `ModuleNotFoundError: answer` | answer 包不在 Python 路径中 | 确保 `InterX/answer/src` 在 `sys.path` 中，或将 answer 包安装到虚拟环境 |
| 会话丢失 | 服务重启或 `sessions/` 目录被清理 | 会话以 JSON 文件持久化，避免删除 `sessions/` 目录 |
| 查询改写失败 | LLM API 不可用 | 检查 InterX Gateway 是否正常运行 |

## 相关包

- `answer`：单次问答引擎，chat 层的实际回答生成依赖
- `gateway`：LLM API 网关，chat 层通过其访问 LLM 服务
- `web`：前端 Web UI，调用 chat 层的 REST API
