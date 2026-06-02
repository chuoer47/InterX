# InterX Web

基于 Streamlit 的智能客服前端界面 — InterX 多轮对话系统的用户交互层。

## 项目概述

`web` 是 InterX 项目的**前端 Web UI**，基于 Streamlit 框架构建，作为智能客服系统的用户界面。它是一个纯客户端，不包含任何业务逻辑或模型推理代码，所有功能通过 HTTP API 调用后端 `chat` 包实现。

支持用户身份管理、多会话切换、历史对话回溯、图片上传与展示等完整功能。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| 外部服务 | InterX Chat API（由 `chat` 包提供） |

## 项目结构

```
web/
└── app.py              # Streamlit 应用入口（单文件）
```

## 依赖清单

### 核心依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| streamlit | >=1.30 | Web UI 框架 |
| requests | >=2.28 | HTTP 客户端 |

## 环境搭建

### 1. 克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>/InterX/web
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install streamlit requests
```

### 4. 配置环境变量

| 变量名 | 是否必填 | 默认值 | 说明 |
|--------|---------|--------|------|
| `INTERX_CHAT_API_BASE` | 否 | `http://127.0.0.1:8000` | Chat API 后端地址 |
| `INTERX_CHAT_API_TOKEN` | 否 | `sk_local_dev` | API 认证 Token |

```bash
export INTERX_CHAT_API_BASE=http://127.0.0.1:8000
export INTERX_CHAT_API_TOKEN=sk_local_dev
```

### 5. 确保后端服务就绪

```bash
# 确保 chat 包的 API 服务已启动（参见 chat 包文档）
curl http://127.0.0.1:8000/health
# 应返回: {"status": "ok"}
```

## 运行方式

### 启动

```bash
cd InterX/web
streamlit run app.py --server.port 8501
```

### 验证

在浏览器中打开 `http://127.0.0.1:8501`，应看到"InterX 智能客服"界面。

## 架构 / 数据流

```
用户浏览器
  │
  ▼  Streamlit UI
web/app.py（纯客户端）
  │
  ▼  HTTP API（Bearer Token 认证）
chat 包 REST API（端口 8000）
  │
  ▼
answer → retrieval → process artifacts
```

### 调用的后端端点

| 方法 | 端点 | 用途 | 超时 |
|------|------|------|------|
| POST | `/chat` | 发送用户问题，获取 AI 回答 | 无限制 |
| GET | `/images/{img_id}` | 获取产品手册图片 | 10 秒 |
| GET | `/sessions/{user_id}` | 获取用户历史会话列表 | 5 秒 |
| GET | `/sessions/{user_id}/{session_id}` | 获取会话详细记录 | 5 秒 |

## UI 功能

### 侧边栏

- 用户 ID 输入框（支持多用户切换）
- "新对话"按钮
- 历史会话列表（点击回溯加载完整对话）
- 当前 Session ID 显示

### 主对话区

- 标准 Chat 气泡式界面
- 图片上传（支持 PNG / JPG / JPEG / WEBP，最多 3 张，每张 5MB）
- AI 回答中的图片内嵌展示（通过 `<PIC>` 占位符机制）
- 加载状态 Spinner
- 完善的错误处理（连接失败、HTTP 错误、业务错误）

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| 页面显示"连接后端服务失败" | Chat API 未启动或地址错误 | 确认 `chat` 包 API 服务已启动；检查 `INTERX_CHAT_API_BASE` |
| 401 认证失败 | Token 不匹配 | 检查 `INTERX_CHAT_API_TOKEN` 是否与后端一致 |
| 图片加载失败 | 图片服务端点不可用 | 确认 `chat` 包的 `/images/{id}` 端点正常 |
| 历史会话为空 | 会话未持久化或用户 ID 不同 | 检查 `chat` 包的 `sessions/` 目录 |

## 相关包

- `chat`：多轮对话后端，提供 REST API
- `answer`：问答引擎（通过 chat 间接调用）
- `gateway`：LLM 网关（通过 chat 间接调用）
