# InterX Gateway 技术路线（草案）

## 1. 总体原则

- 以 LiteLLM Proxy 为核心，而不是从零实现模型网关。
- 采用“配置优先 + 可插拔增强层”的方式建设 Gateway。
- 第一阶段先做可运行、可观测、可扩展的基础网关；复杂缓存与高级策略放在二阶段增强。

---

## 2. 推荐总体架构

建议目录定位为独立网关子项目：

- `InterX/gateway/`
  - `PRD.md`
  - `TECH_ROUTE.md`
  - `docker-compose.yml`（后续）
  - `litellm/`（后续放置 proxy 配置）
  - `extensions/`（后续放置缓存增强 / 中间件）
  - `monitoring/`（后续放置 Prometheus / Grafana 配置）
  - `scripts/`（后续放置运维脚本）

推荐运行形态：

1. LiteLLM Proxy 作为主网关
2. Redis 作为缓存与状态依赖
3. Prometheus + Grafana 作为指标与监控面板
4. 可选使用 LiteLLM 自带 UI / Admin 能力
5. 后续如语义缓存不足，再在 LiteLLM 前增加一个轻量增强服务

---

## 3. 分阶段技术路线

### Phase 0：方案确认（当前阶段）

输出：

- PRD
- 技术路线
- 目录结构

不做：

- 不正式编码功能实现

### Phase 1：最小可运行网关

目标：

- 跑起 LiteLLM Proxy
- 接通至少一个上游模型
- 支持 OpenAI 风格 chat/completions
- 验证 stream 能力

建议产物：

- LiteLLM 配置文件
- `docker-compose.yml`
- 基础 README
- smoke test 脚本

### Phase 2：多中转站与 latency-based routing

目标：

- 同一模型映射多个上游 endpoint
- 启用 LiteLLM 路由能力
- 验证 latency-based routing / fallback / health 检测

说明：

- 优先使用 LiteLLM 官方 routing 机制
- 若官方“latency-based routing”支持度有限，则采用“多 deployment + fallback + 健康探测 + 统计延迟”的折中实现

### Phase 3：监控与前端面板

目标：

- 打通指标采集
- 提供请求量、延迟、错误率、token、缓存命中、上游状态等看板
- 优先接入 LiteLLM 可用 UI；不足部分用 Prometheus + Grafana 弥补

建议：

- 面板采用 Grafana
- 指标来源优先 LiteLLM 暴露指标 / 日志
- 如果 LiteLLM 自带 Admin/UI 可满足基本巡检，则保留双面板

### Phase 4：缓存与语义命中增强

目标：

- 启用 LiteLLM 基础缓存
- 建立精确缓存键
- 建立候选语义缓存检索
- 用小模型做“是否可复用”二次判定

推荐策略：

1. L1：精确缓存
   - key 由模型、system、messages、tools、图像标识、关键参数组成
2. L2：近似候选检索
   - 基于 embedding / 归一化 query / SimHash 等任选其一
3. L3：小模型判定
   - 输入“当前请求 + 候选缓存请求摘要 + 上下文元信息”
   - 输出 yes/no + confidence
4. 命中后返回缓存答案；未命中则走真实上游

注意：

- stream 请求的缓存回放要单独设计
- 图片、多轮对话、工具调用请求要默认保守处理

---

## 4. 针对你 4 个核心需求的具体建议

### 4.1 关于 latency-based routing

建议路线：

- 优先查证 LiteLLM Router / Proxy 是否原生支持按延迟路由。
- 若原生支持，则直接采用官方配置。
- 若仅支持 weighted/fallback/cooldown/healthcheck 等，需要补一层：
  - 定时记录各上游最近窗口延迟
  - 动态调整路由优先级 / 权重
  - 保持配置热更新或代理前置路由

工程判断：

- 第一版最好尽量不自研复杂路由器。
- 先跑通 LiteLLM 官方机制，再补充自定义延迟策略。

### 4.2 关于“资源检测前端 / 监控前端”

建议路线：

- 第一优先：LiteLLM 原生可观测能力 / Admin UI / 日志与指标导出
- 第二优先：Prometheus + Grafana
- 第三优先：如后续需要 tracing，再接 OpenTelemetry / Langfuse / Helicone 一类平台

当前建议结论：

- 第一版直接集成 Grafana 看板最稳妥
- 如果 LiteLLM 自带 UI 可直接用，则同时保留，分别承担：
  - LiteLLM UI：代理级运维查看
  - Grafana：关键指标大盘

### 4.3 关于 stream

建议路线：

- 对外统一走 OpenAI-compatible streaming 接口
- Gateway 不做破坏 stream 的二次聚合
- 缓存命中时分两种策略：
  - 非 stream：直接返回完整缓存结果
  - stream：将缓存答案模拟为流式分块返回，或直接禁用语义缓存仅保留精确缓存

第一版建议：

- 先保证真实上游 stream 稳定透传
- 缓存命中的 stream replay 放第二阶段

### 4.4 关于混合缓存 + 小模型判定

建议路线：

- 不建议一开始就深度耦合到 LiteLLM 内核
- 建议在 Gateway 外围增加一个轻量“cache adjudicator”组件
- 执行流程：
  - 请求进入
  - 先查精确缓存
  - 若未命中，查语义候选池
  - 若候选存在，调用小模型判断是否等价
  - 命中则返回缓存，否则转发 LiteLLM

第一版风控规则建议：

- 以下请求默认禁用语义缓存：
  - 带图片输入
  - 带工具调用
  - 多轮长上下文
  - 高风险业务标记请求
- 仅对单轮纯文本 FAQ / 客服问答启用

---

## 5. 初步技术选型建议

### 必选

- 网关核心：LiteLLM Proxy
- 缓存：Redis
- 容器编排：Docker Compose
- 指标监控：Prometheus + Grafana

### 可选增强

- 语义缓存候选检索：Redis + 向量扩展 / 本地向量库 / 轻量数据库
- 小模型判定：低成本 chat model
- 链路追踪：OpenTelemetry / Langfuse（后续）

---

## 6. 风险与现实判断

### 风险 1：LiteLLM 原生“latency-based routing”能力边界

需要正式核实：

- 是不是完整原生支持
- 还是只能通过 router/fallback/weight/health 机制近似实现

### 风险 2：LiteLLM 原生缓存对“语义缓存”支持深度有限

即便 LiteLLM 有缓存机制，你要的“小模型 yes/no 判定式缓存命中”大概率仍需要自定义增强层。

### 风险 3：stream 与缓存耦合复杂

语义缓存命中后如何优雅地 replay stream，需要单独设计，不建议第一版做太重。

### 风险 4：监控“前端”不一定由 LiteLLM 单独完全覆盖

更现实做法通常是：

- LiteLLM 提供代理能力和部分观测能力
- Grafana 补足标准化监控看板

---

## 7. 我建议你审核时重点拍板的事项

请重点确认以下决策：

1. 第一版是否接受：`LiteLLM Proxy + Redis + Prometheus + Grafana`
2. 监控前端是否采用“双面板策略”：LiteLLM UI + Grafana
3. 语义缓存是否同意采用“外挂 adjudicator”而不是直接魔改 LiteLLM
4. stream replay 缓存是否放到第二阶段，而不是第一阶段强做
5. 多中转站是否默认都是 OpenAI-compatible

---

## 8. 当前结论

当前最稳妥、最容易审核通过并快速起步的路线是：

- **第一步**：把 LiteLLM Proxy 网关跑起来
- **第二步**：接入多上游和路由
- **第三步**：补全监控面板
- **第四步**：在 LiteLLM 外挂语义缓存判定层

这条路线最符合“先搭起来、再增强”的策略，也最适合多仓 InterX 的长期演进。

### Phase 2.5：上游探测与稳定性分层

目标：

- 对本地 `cc-switch` 中转站进行静态探测与持续探测
- 区分“可用但不稳定”和“稳定可作为默认节点”的上游
- 为后续 latency-based routing 提供真实候选池

当前结论：

- 探测到多个可用上游，但持续调用稳定性不一致
- 因此当前实现采用“先筛可用，再逐步放量”的务实策略

