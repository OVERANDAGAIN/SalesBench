# Persistent Market Service — SB-PLATFORM-001

2026-09-24。本地单机 FastAPI + PostgreSQL application boundary，API schema `sb-platform-v1`。保留已经验收的 Round → Tick → Wave、Round-level procurement、冻结观察、seeded purchase resolution 与 V1 批次失败规则。Vue Buyer/Seller 已通过真实网络适配器接入，没有真实 LLM 或正式 HumanDriver。

SB-E2E-001 更新：Vue / Seller 工程验收页面现已接入该 boundary，见 [MANUAL_MARKET.md](MANUAL_MARKET.md)。新增本人最近 receipts 读取、create-manual 和只读 inspect CLI；无需 schema migration，Engine/Runner/事务与研究语义不变。SB-CONSOLIDATE-001 统一 inspect/recover 的源码、版本与经济摘要校验；仍无新 migration 或协议变更。

## 职责与运行路径

```text
HTTP / 未来 Agent adapter
  → MarketService（绑定、幂等、收集、事务、fencing、恢复）
  → Runner（冻结观察、批次校验、Wave 顺序与购买裁决顺序）
  → Engine（合法性、资金、库存、订单、消息、报价版本）
```

`app/api.py` 只处理 envelope、认证和响应；`app/service.py` 是双方共用的 application boundary；`app/persistence.py` / Alembic 管理存储；`app/contracts.py` 约束平台 envelope；`app/cli.py` 提供本地建库、演示与恢复审计。Engine 0.2.1 通过 backend 锁文件引用独立本地包，内核仍只依赖标准库。

收到动作请求时只保存 intent，不提前执行。`SubmissionDriver` 将已经收齐的持久批次交回原 Runner 校验/执行链；它是传输适配器，不是新增消费者策略、HumanDriver 或 LLM provider。所有 actor 可以共享同一个服务，不能直接访问 Engine。

默认一个 Uvicorn worker，进程内一个异步轮询任务调用同步 service；每 0.5 秒尝试推进 ready session，轮询时间不属于市场时间。采购、Seller/Buyer Wave 和 Round close 的顺序、机会数与排序 seed 不变；每个正常 Round 仍只 `advance(1)` 一次。只有收齐本 Wave 所有 actor 的批次才推进。未提交不是 Wait，没有自动截止、代填、改意图或新开机会。

## 数据模型与恢复权威

| 表 | 保存内容 / 边界 |
| --- | --- |
| `market_sessions` | 初始 setup、MarketConfig、源码摘要、runtime/next boundary、已提交版本、fence、trace 长度/摘要、经济状态摘要 |
| `actor_bindings` | session + actor、角色、随机 bearer token 的 SHA-256；不保存原 token |
| `actor_projections` | 当前已提交的本人 state 和下一 opportunity；与 session publication 同版本 |
| `publications` | 各版本 public snapshot、context、审计状态摘要；不直接作为任意 actor API |
| `batch_receipts` | 原始请求、指纹、pending/rejected/final receipt；session+actor+request ID 主键；每 actor/opportunity 至多一份被接收批次 |
| `action_receipts` | Runner 生成的 action ID、context、结构化动作及成功/失败/skipped outcome |
| `journal_entries` | 完整 manifest + observation/action/result/resolution/publication trace；session+连续 seq |
| `resolutions` | Runner 生成的采购/购买等裁决顺序，不重新计算经济结果 |
| `semantic_events` | Engine 产生的事件及 audience，仅供宿主审计 |
| `outbox_notices` | 与 publication 同事务保存的版本失效通知，内容不含私有状态 |

**恢复权威是初始 setup + 已提交 canonical transcript**。账户、库存、Listing 的 offer/content revision、订单、消息、事件/ID 计数器通过同版本 Runner/Engine 重放恢复；不是另写一套 SQL purchase，也不把 `snapshot()` 当反序列化契约。SQL 表保存规范 JSON/结果/投影，不独立扣款或扣库存。投影是读取加速材料，恢复会核对 trace/source/state 摘要。

Journal、semantic events、resolution、完整状态摘要和所有私有 projection 是可信宿主数据，不提供参与者全量查询接口。Actor API 只返回其绑定身份的授权投影、本人 receipt 和无内容的通知。没有跨 actor 切换参数，也不广播 SQL 表或宿主快照。

## 提交、单写者和 fencing

1. `submit` 用 session 行锁检查绑定、请求幂等、observation version 和当前机会；保存 pending 或明确 rejected receipt，独立事务提交。不会调用 Engine。
2. `claim` 用短事务锁 session，确认本 Wave 收齐、验证 trace 摘要，递增并提交 fence，捕获 base publication/trace 与批次。Round close 无 actor 输入。
3. 释放数据库锁后，`restore_committed` 重建一次性 Runner，核对记录与当前机会，再执行**一个原有边界**。此时只存在私有候选，API 仍读旧 committed projection。
4. `commit_candidate` 再锁 session，核对 fence + base publication + base trace digest。旧 writer 返回 `WRITER_FENCED`，没有写权限。当前 writer 在一个事务里追加 journal/action/result/resolution/events，结算 receipt，更新 runtime、publication、全部 actor projections 和 outbox。
5. COMMIT 成功即是 actor publication。之后不需要再替换某个内存市场才能读到新状态。API observation 的 projection + runtime 通过一次 SQL JOIN 读取，避免跨两个 READ COMMITTED statement 混入不同版本。

每场只有当前 fenced writer 能提交经济边界。多个错误启动的 worker 可能重复计算候选、互相 fence，不能重复提交；当前运维仍要求一个 worker，未承诺多 worker 的吞吐/公平性。fence 只控制提交，操作次数/HTTP 时间/线程执行顺序不参与市场排序。

## 结果未知与恢复

| 故障位置 | 已承诺的处理 |
| --- | --- |
| intent 保存前断线 | receipt 可能不存在；原 ID + 原内容可安全重试 |
| intent COMMIT 成功、响应丢失 | 查询或重试得到同一 durable pending/final receipt |
| claim 后或 Engine 执行后、经济事务尚未 COMMIT | 丢弃候选；上一 committed transcript/projection 不变；新 writer 重建再执行 |
| SQL/commit 报错，提交结果不明 | `COMMIT_UNKNOWN`；不把旧候选留作权威，不生成新 request ID；下一次从 DB 已提交记录决定实际状态 |
| COMMIT 成功、进程在响应/通知前退出 | receipt/projection/runtime/outbox 已一起落库；新进程直接读到同一结果，无“二次 publish”窗口 |
| 旧 writer 晚到 | fence/base 检查拒绝提交，不覆盖新版本 |
| Round close 提交结果不明 | 从已提交边界恢复；不会重复 `advance(1)` |
| Engine 单动作异常 | 保持 Runner V1：已执行前缀可审计，整 Wave 不发布，session failed；actor receipt 为 aborted、无未发布 outcomes；可信宿主恢复验证前缀 |
| 无法确定性记录/重放的实现异常 | 候选失败记录需先通过 restore 验证；失败则不提交该候选，保留上一边界并报错，不伪造完成或 Wait |
| trace 损坏 / source 或规则不匹配 | fail closed，需要恢复对应代码/数据；不猜测、不自动跳过或升级记录 |

服务每次推进都重建候选，因此重启没有必须序列化的常驻 Engine。已接收的部分 Wave 输入在 DB 保留；启动后轮询继续等待剩余 actor，齐备后自动推进。`recover` CLI 是只读宿主审计；后台推进使用同一恢复契约。

幂等范围是 `(session_id, actor_id, request_id)`，payload 指纹包括观察版本、opportunity 和完整有序 actions。相同 ID + 相同内容先返回旧 receipt，**在 stale observation 检查之前**；相同 ID 改内容返回 `ACTION_ID_CONFLICT`。一个新 ID 不能替换已占用机会。恢复后 Runner 从原 action ID 重建自身幂等缓存；跨进程持久保障由 DB 唯一约束、session 锁和 fence 完成。

新请求带旧 publication 明确 `STALE_OBSERVATION`；旧 price/revision 的请求可能先保存 pending，但只有原 Engine 在 Wave 执行时产生 `PRICE_CHANGED` / `STALE_LISTING`，最终 receipt 明确失败且不扣钱。平台不提前复制报价/库存经济规则。`content_revision` 和库存变化不增加 `offer_revision` 的原语义不变。

## API v1

本地 `http://127.0.0.1:8000/docs` 是 OpenAPI。管理 token 来自本机配置；所有 actor token 随创建成功响应一次返回，调用方必须妥善保留。token 绑定固定 session+actor；不得放 URL、journal 或 Git。

| 请求 | 认证 / 行为 |
| --- | --- |
| `GET /health` | 无认证；只说明 API 进程响应，不检查 DB |
| `POST /api/v1/sessions` | 管理 bearer；`session_id, setup, market_config`，创建初始版本 0 |
| `POST /api/v1/sessions/{sid}/bindings/rotate` | 管理 bearer；body `{"actor_id":"buyer-1"}`；重发新 token 并撤销旧 token |
| `GET /api/v1/sessions/{sid}/observation` | actor bearer；返回本人 state、opportunity、published_version 与 committed runtime |
| `GET /api/v1/sessions/{sid}/runtime` | actor bearer；返回 committed phase/next boundary/step/version，无他人进度或批次 |
| `POST /api/v1/sessions/{sid}/actions` | actor bearer；保存一份完整 bounded batch；202 pending、409 rejected、200 已完成的重复请求 |
| `GET /api/v1/sessions/{sid}/receipts/{request_id}` | actor bearer；只查本人 receipt；未知为 404 `RECEIPT_NOT_FOUND` |
| `GET /api/v1/sessions/{sid}/receipts` | actor bearer；本人最近 50 条回执，pending 优先；支持刷新/重新绑定后识别当前已提交机会 |
| `GET /api/v1/sessions/{sid}/notifications?after_version=2` | actor bearer；最多 100 条按版本排序的 invalidation，游标取最后版本 |
| `POST /api/v1/sessions/{sid}/run` | 管理 bearer；显式推进一个 ready 边界，通常由后台 worker 完成 |

创建 body 的 setup 使用 Engine `MarketSetup` 的规范 JSON：experiment、suppliers、sellers、buyers、products、offers、accounts；示例来自 `app.cli.demo` / `salesbench_engine.runner.demo.demo_setup`。这些是受信管理操作，不允许 actor 改初始市场。相同 session ID/相同配置的创建重试返回现有 session，`actor_tokens=null`；若初次响应丢失，由管理端 rotate 需要的 token。不同配置使用同 ID 为冲突。

动作 envelope 示例（ID/版本必须来自当前 observation）：

```json
{
  "request_id": "client-batch-001",
  "observation_version": 2,
  "opportunity_id": "<当前 observation.opportunity.opportunity_id 的 64 位摘要>",
  "actions": [
    {"type": "purchase", "listing_id": "seller-1/cup", "quantity": 1,
     "expected_unit_price_cents": 300, "expected_offer_revision": 1}
  ]
}
```

不要提交 actor_id，身份从 token 绑定。可用动作和预算在 opportunity 中明确给出，结构校验及 V1 batch failure 仍由 Runner 执行。顶层 envelope 严格校验，规范编码不超过 64 KiB；PostgreSQL JSONB 无法保存的 NUL/无效 Unicode 和非有限数明确拒绝，不静默改写。传输上限不改变 Wave action/message 预算。

Receipt 状态：`pending`（尚未裁决）、`rejected`（平台准入失败）、`succeeded`、`failed`（业务失败/invalid batch/skipped）、`aborted`（session 技术异常未发布）。结果返回 `outcomes`，包含 Runner status/code/reason；`replayed` 表示提交是否命中旧请求，不代表新成交。`COMMIT_UNKNOWN`/断线时保留原始 envelope，先查 receipt；即使查到 404，也仅以原 ID/内容重试。

通知是与提交一致的可重读持久游标，当前只有轮询。它不承诺网络 exactly-once delivery；客户端可去重、断线后补读，再重新读取 observation。failed runtime 可能在 publication 不变时更新，应同时查询 receipt/runtime；本轮没有 WebSocket/SSE 或失败状态专用订阅事件。

## 运行、迁移与验收

依赖、配置、PG 启停见 [ENVIRONMENT.md](ENVIRONMENT.md)。不在应用启动时 `create_all`，必须显式 `alembic upgrade head`；迁移 `sb_platform_001` 可在空 PostgreSQL schema 创建 10 张业务表。SQL schema 迁移不等于实验协议/trace 迁移。

`scripts/platform.ps1 test` 使用真实 PostgreSQL，每个测试建立随机隔离 schema、从空迁移、结束只删除该 schema。环境缺失时测试失败，不假称 SQLite 通过。包含两个真实 HTTP 客户端/Uvicorn 重启、跨实例重复购买、COMMIT 前后强制进程退出、unknown acknowledgement、MVCC 发布、fencing、隐私、报价、恢复摘要、失败前缀与 Round close 验证。最初平台验收见 [历史 handoff](handoffs/SB-PLATFORM-001.md)，当前完整回归见 [收口 handoff](handoffs/SB-CONSOLIDATE-001.md)。

## Known Issues / Protocol Debt

1. **失败传播语义后续需正式确认**。V1 成功前缀保留，业务失败使剩余动作 skipped，消息失败可以阻止末尾 purchase；本任务完全保留。
2. 当前经济规则仍是 TEST；没有真实 LLM、HumanDriver、正式消费者/Seller 策略、奖励、物流/退款/税费或协议变更。缺 actor 输入会持续 pending，没有新增自动超时实验规则。
3. 仅验证本机 PostgreSQL 与单 worker。fencing 保证提交排他，不宣称分布式高可用、公平调度或多 worker 的进展保证；长 replay 占用该 worker 的轮询处理时间。
4. 每次重建完整历史、保存完整观察/trace，成本随历史增长；未做 snapshot checkpoint、压缩、归档或规模测试。源码严格匹配，升级 Engine 后应使用原版本恢复旧场，不能直接绕过 guard。
5. 不覆盖磁盘损坏、数据库数据丢失、关闭 durable PG 设置、备份/灾难恢复、恶意 DB 管理员篡改、未知实现 bug 的自动修复。摘要用于一致性检查，不是数字签名或防篡改审计。
6. actor bearer + 本机管理 token 是最小绑定；没有正式用户登录、权限管理后台、TLS、公网部署、限流或生产凭据治理。5070 的数据库 owner 仅用于开发；未来部署应另做最小权限/备份方案。
7. DB 重试保留原 intent，不保证未来外部模型请求的 exactly-once 或副作用事务。未接 provider；不能将技术失败当策略 Wait。
8. Vue 当前已有真实 MarketClient / Buyer read facade / Seller 工程页，使用持久通知轮询。旧 v0.1 单动作 demo 契约只作回归；真实适配见 INTERFACES.md。手工 E2E 不等于正式 HumanDriver 实验。
