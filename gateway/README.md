# InterX Gateway

基于 LiteLLM 的统一 LLM API 网关，支持多上游路由、语义缓存和可观测性监控。

## 项目概述

`gateway` 是 InterX 项目的**统一 LLM 入口网关**。它将系统中的 LLM 请求统一路由到多个上游提供商（小米 MiMo、阿里 DashScope、GPT-5.5 中转等），在 LiteLLM Proxy 之上叠加语义缓存扩展以降低调用成本，并提供 Prometheus + Grafana 的完整可观测性支持。

所有 InterX 包（`answer`、`chat`、`kg`）的 LLM 调用均通过此网关代理，对外暴露 OpenAI 兼容的 `/v1/chat/completions` 接口。

## 前置要求

| 依赖项 | 版本 / 说明 |
|--------|------------|
| 操作系统 | Ubuntu 22.04+ / macOS 13+ |
| Python | 3.11+ |
| Docker（可选） | 20.10+（Docker 模式部署时需要） |
| 系统包 | `redis-server`（本地模式时自动启动，端口 6380） |
| 外部服务 | 上游 LLM API（至少一个：小米 MiMo / 阿里 DashScope / 其他 OpenAI 兼容服务） |

## 项目结构

```
gateway/
├── .env.example                  # 环境变量模板
├── litellm/                      # LiteLLM 配置文件
│   ├── config.yaml               # 实际生效配置
│   ├── config.template.yaml      # 模板（os.environ 占位符）
│   ├── config.multi.yaml         # 多上游实验配置
│   └── config.stable.yaml        # 稳定版配置
├── extensions/
│   └── semantic_cache/           # 语义缓存扩展（独立 FastAPI 服务）
│       ├── app/
│       │   └── main.py           # 语义缓存核心逻辑
│       ├── Dockerfile
│       └── requirements.txt
├── monitoring/
│   ├── grafana/                  # Grafana 仪表盘与数据源配置
│   ├── local/                    # 本地模式 Prometheus 配置
│   └── prometheus/               # 容器模式 Prometheus 配置
├── scripts/                      # 运维脚本
│   ├── bootstrap_env.sh          # 环境引导
│   ├── start_gateway.sh          # Docker 模式启动
│   ├── start_local.sh            # 本地模式启动
│   ├── stop_gateway.sh           # 停止服务
│   ├── render_config.py          # 配置模板渲染
│   ├── smoke_test.py             # 冒烟测试
│   ├── cache_test.py             # 缓存测试
│   ├── stream_test.py            # 流式测试
│   ├── routing_probe.py          # 路由探测
│   ├── score_upstreams.py        # 上游评分
│   ├── gateway_status.sh         # 状态查看
│   ├── local_monitor.py          # 本地监控
│   └── start_monitoring.sh       # 启动监控栈
├── ops/
│   └── interx-gateway            # 统一运维入口
├── state/                        # 运行时状态（PID 文件等）
├── logs/                         # 日志目录
├── secrets/                      # 密钥目录
├── docs/
│   └── cc_switch_template.md     # cc-switch 集成模板
├── docker-compose.yml
└── tests/                        # 测试结果
```

## 依赖清单

### 核心依赖（LiteLLM Proxy）

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| litellm[proxy] | >=1.0 | LLM 代理核心 |
| pyyaml | >=6.0 | 配置文件解析 |

### 语义缓存依赖

| 包名 | 版本约束 | 用途 |
|------|---------|------|
| fastapi | ==0.115.0 | 缓存服务 Web 框架 |
| uvicorn[standard] | ==0.30.6 | ASGI 服务器 |
| redis | ==5.0.8 | 缓存存储 |
| httpx | ==0.27.2 | HTTP 客户端 |
| prometheus-client | ==0.20.0 | 指标暴露 |
| pydantic | ==2.9.2 | 数据验证 |

## 环境搭建

### 1. 克隆仓库

```bash
git clone <REPO_URL>
cd <REPO_PATH>/InterX/gateway
```

### 2. 初始化环境

```bash
# 引导脚本：创建虚拟环境并安装依赖
bash scripts/bootstrap_env.sh
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际值
```

| 变量名 | 是否必填 | 默认值 | 说明 |
|--------|---------|--------|------|
| `LITELLM_MASTER_KEY` | 是 | `change-me` | LiteLLM API 鉴权密钥 |
| `LITELLM_SALT_KEY` | 否 | `change-me-too` | 盐值密钥 |
| `UPSTREAM_1_BASE_URL` | 是 | — | 第一上游 API 地址 |
| `UPSTREAM_1_API_KEY` | 是 | — | 第一上游 API 密钥 |
| `UPSTREAM_1_MODEL` | 是 | — | 第一上游模型名 |
| `UPSTREAM_1_TPM` | 否 | `120000` | 每分钟 Token 上限 |
| `UPSTREAM_1_RPM` | 否 | `3000` | 每分钟请求上限 |
| `UPSTREAM_2_*` | 否 | — | 第二上游（可选，同上结构） |
| `DASHSCOPE_API_KEY` | 视情况 | — | 阿里 DashScope API 密钥 |
| `REDIS_URL` | 否 | `redis://redis:6379/0` | Redis 连接地址 |
| `SEMANTIC_CACHE_ENABLED` | 否 | `true` | 是否启用语义缓存 |
| `SEMANTIC_CACHE_MODEL` | 否 | `gpt-4o-mini` | 语义判断用的模型 |
| `SEMANTIC_CACHE_THRESHOLD` | 否 | `0.92` | 语义等价置信度阈值 |
| `SEMANTIC_CACHE_MAX_CANDIDATES` | 否 | `5` | 最大候选数 |
| `GRAFANA_ADMIN_USER` | 否 | `admin` | Grafana 管理员用户名 |
| `GRAFANA_ADMIN_PASSWORD` | 否 | `admin` | Grafana 管理员密码 |

### 4. 渲染配置

```bash
# 从模板生成 config.yaml（注入环境变量值）
python3 scripts/render_config.py
```

## 运行方式

### Docker 模式

```bash
# 稳定模式（使用 config.stable.yaml）
bash scripts/start_gateway.sh stable

# 多上游模式（使用 config.multi.yaml）
bash scripts/start_gateway.sh multi
```

### 本地模式（无 Docker）

```bash
bash scripts/start_local.sh
```

此脚本自动完成：启动 Redis（端口 6380）、启动 LiteLLM Proxy（端口 4000）、启动语义缓存服务（端口 4010）。

### 统一运维入口

```bash
ops/interx-gateway start stable   # 启动
ops/interx-gateway start multi    # 多上游模式
ops/interx-gateway status         # 查看状态
ops/interx-gateway probe          # 路由探测
ops/interx-gateway monitor        # 启动监控
```

### 停止服务

```bash
bash scripts/stop_gateway.sh
```

### 验证

```bash
# 冒烟测试
python3 scripts/smoke_test.py

# 查看运行状态
bash scripts/gateway_status.sh
```

## 配置说明

### LiteLLM 配置

- `litellm/config.template.yaml`：模板文件，使用 `os.environ/XXX` 占位符从环境变量注入
- `litellm/config.yaml`：由 `render_config.py` 生成的实际配置
- `litellm/config.stable.yaml`：稳定版配置（单上游，推荐生产使用）
- `litellm/config.multi.yaml`：多上游实验配置

关键全局设置：
- `drop_params: true`：自动丢弃不支持的参数
- `request_timeout: 600`：请求超时 600 秒
- `routing_strategy: simple-shuffle`：随机路由策略
- `allowed_fails: 3`，`cooldown_time: 30`：失败 3 次后冷却 30 秒

## 架构 / 数据流

```
InterX 各包 (answer / chat / kg)
  │
  ▼  OpenAI 兼容请求
语义缓存层 (端口 4010)
  │── 精确匹配 (SHA-256 哈希 → Redis) ──→ 命中 → 直接返回
  │── 语义匹配 (LLM 判断等价性)         ──→ 命中 → 直接返回
  │── 未命中 → 回源 ↓
  │
  ▼
LiteLLM Proxy (端口 4000)
  │── 路由策略: simple-shuffle
  │── 故障转移: 3 次失败 → 冷却 30 秒
  │
  ▼
上游 LLM 提供商
  ├── 小米 MiMo (mimo-v2.5-pro)
  ├── 阿里 DashScope (qwen3.6-plus, qwen3-max, qwen3-vl-embedding, qwen3-rerank)
  └── GPT-5.5 中转
```

## 接口说明

| 接口 | 端口 | 方法 | 说明 |
|------|------|------|------|
| `/v1/chat/completions` | 4000 | POST | LiteLLM 统一 LLM 入口（OpenAI 兼容） |
| `/v1/cache/chat/completions` | 4010 | POST | 语义缓存层入口（建议优先使用） |
| `/metrics` | 4010 | GET | 语义缓存 Prometheus 指标 |

## 常见问题与排错

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| 网关无法启动 | `.env` 文件缺失或上游配置错误 | 确认 `.env` 存在且上游 API 地址/密钥正确 |
| 请求超时 | 上游 LLM 响应慢 | 检查 `request_timeout` 设置；尝试切换上游 |
| 语义缓存未命中 | 阈值过高或候选数不足 | 降低 `SEMANTIC_CACHE_THRESHOLD` 或增加 `SEMANTIC_CACHE_MAX_CANDIDATES` |
| Redis 连接失败 | Redis 服务未启动 | 本地模式：确认端口 6380 可用；Docker 模式：检查容器状态 |

## 相关包

- `answer`：问答引擎，通过网关调用 LLM
- `chat`：对话层，通过网关调用 LLM
- `kg`：知识图谱层，通过网关调用 LLM 进行语义关系提取
