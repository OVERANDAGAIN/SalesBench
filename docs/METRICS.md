# Development Profit Leaderboard 与研究指标

SB-METRICS-001，2026-09-24。这是开发用事实统计，**不是最终 benchmark 评价、总分或 reward**。没有改变 Engine 经济行为、Round → Tick → Wave、购买排序或 batch failure 语义。未实现 RecommendationPolicy。

## 口径与公开刷新

所有金额为整数分。`dev_profit_cents = cumulative_sales_revenue_cents - cumulative_procurement_spend_cents`；同时核对 `current_cash_cents - initial_cash_cents`。负数合法，未售库存不计价值。当前有限供应、即时交货/全额结算仍是 TEST 规则；佣金、税费、物流、退款、托管、折旧均未定义。

不一致记录 `PROFIT_CASH_DELTA_MISMATCH` 及两种值，利润置 null，不选择其中一个；宿主可以查错误，参与者观察返回 `METRICS_INCONSISTENT`，不发布伪排名。

Session 创建时锁定 `policy_id=dev_cash_profit_v1`、`policy_version=1`、`metric_schema_version=sb-metrics-v1`、refresh 和 calculator_digest。默认 `tick_close`；管理创建请求可传 `"metrics_policy":{"refresh":"round_close"}`。只接受这两种策略；没有 wall-clock 刷新。源码摘要将 CRLF 规范化为 LF，不依赖机器路径。

| 时点 | 默认 tick_close 的公开榜单 | 宿主指标 |
| --- | --- | --- |
| 初始 publication 0 | 全 Seller 利润 0；previous_rank=null | 初始资金与零累计量 |
| Round procurement 正常提交 | 沿用上一榜单 | 采购支出、资金、库存更新 |
| Seller Wave 正常提交 | 沿用上一榜单 | Listing/实际改价/消息等更新 |
| Buyer Wave 正常提交 / Tick Close | 新持久榜单 | 新成交及完整 Tick 统计 |
| Round Close / completed | 沿用最后 Tick 榜单 | runtime/step/status 更新 |
| pending / rejected intent | 不变 | 不算经济动作事实 |
| 技术 aborted | 不公开刷新 | 标记 committed_failure_prefix，统计已提交审计前缀 |

`round_close` 只在初始和正常 Round Close 生成新榜单，不增加机会或改变 Wave。每次规定刷新都生成新版本，即便数值未变。排序为利润降序、seller_id 升序；平利润的 ID 顺序只是稳定展示。previous_rank 是上一份**正式榜单**的名次，不是上一个 publication 的重算。

公共 snapshot 白名单：`leaderboard_snapshot_id`、`session_id`、`source_publication_version`、`round_index`、`tick_index`、`policy_id`、`policy_version`、`metric_schema_version`、`refresh_policy`、`generated_from_committed_state`、`rows`。每行只有 seller_id、display_name、current_rank、previous_rank、dev_profit_cents。ID 为规范 payload 的确定性摘要。初始 round/tick 为 0，界面显示“初始榜单”。

Buyer/Seller 共用 application observation 顶层 `leaderboard`，从 DB 中同一 publication 的持久映射读取；Vue 只格式化金额/名次变化，不算利润。榜单不进入也不修改原 Runner frozen observation dataclass/journal，Engine/Runner source digest 保持不变；未来 Agent 应通过相同 application boundary 使用此扩展。商品列表继续使用原 public listings 顺序，与利润榜无关。

## 唯一计算位置与提交边界

`backend/app/metrics.py` 是唯一统计/排名实现，读取经过原恢复校验的 committed canonical transcript：初始 setup、Engine action_result 的事实表变更、admission/skipped、publication、aborted。订单/采购总额直接取 Engine 已裁决事实，不重算 purchase，不根据 pending request 或候选 Runner 统计。

`metric_store.py` 只负责版本校验、读 DB、物化和历史映射；API/CLI 不复制公式。原经济事务先 COMMIT journal/receipt/projection/runtime/outbox；随后从 DB 已提交记录派生并提交指标。两者不是一个数据库事务，但派生视图可以从 committed trace 唯一补齐。

- 经济 COMMIT 前失败：上一指标/榜单不变，候选丢弃。
- 经济 COMMIT 后、指标 COMMIT 前退出：经济回执仍有效；下次观察/推进/宿主查询补齐派生视图，不重新成交。
- 指标 COMMIT 回执未知：重连核对主键和 payload digest；已提交则复用，未提交则从原 trace 重建。
- observation 通过一次 SQL MVCC JOIN 读取 projection/runtime/精确 transcript_count 的指标及其榜单。若经济提交恰好发生在预检查之后，最多三次补齐/重读；仍未就绪返回 `METRICS_NOT_READY`，绝不把新市场与错误榜单组合。
- 通知仍是原 durable publication invalidation，无新 WS/SSE 或指标时钟。轮询观察能修复提交间隙；请求结果未知仍按原 ID 查询/重试 receipt，不把指标失败解释成购买失败。
- 物化先完整核对原 source/trace/economic digest；缓存读取校验指标 payload 与 session source trace/state 摘要。`recover` / `inspect` 原恢复校验不被跳过。

持久历史只追加，发现现存 payload 与重放不一致报错，不覆盖。正式修改公式必须新的显式版本/迁移方案；当前 calculator digest 不匹配会 `METRICS_POLICY_MISMATCH`，需对应源码读取，不能静默重算旧榜。

## PostgreSQL 与历史场次

显式迁移 `sb_metrics_001` 接在 `sb_platform_001` 后：

| 表 | 新增内容 |
| --- | --- |
| market_sessions | nullable JSONB metrics_policy：该 session 固定策略/版本/计算器摘要 |
| leaderboard_snapshots | 主键 session_id + source_publication_version，公共 payload 与 digest，引用原 publications |
| metric_snapshots | 主键 session_id + transcript_count，source publication、leaderboard_source_version、宿主 payload 与 digest |

合计 12 张应用表，另有 alembic_version。没有复制账户、库存、订单或采购经济表，也无 trigger。每个 published boundary 均存指标及榜单映射；同 publication 的技术失败前缀以不同 transcript_count 区分。

升级前的旧 session 保留 NULL policy：其 observation.leaderboard=null，宿主指标返回 `METRICS_NOT_ENABLED`，原市场仍可 recover/observe。**不会补造当时参与者并未看到的历史榜单**。新 create-manual 场次默认启用新榜；用户不需删旧库。运行 `scripts/platform.ps1 migrate` 显式升级即可。

## 宿主 schema 与计数含义

报告顶层包含版本/policy、session_id、source_publication_version、source_transcript_count/digest、source_state_digest、generated_from_committed_state、economic_visibility、consistency_errors，以及：

| 区域 | 字段 |
| --- | --- |
| sellers | seller_id/display_name；initial_cash_cents、current_cash_cents、cumulative_sales_revenue_cents、cumulative_procurement_spend_cents、dev_profit_cents、orders_count、units_sold、units_procured、current_inventory_units、active_listing_count、price_change_count、public_messages_sent、private_messages_sent、successful_actions、failed_actions、skipped_actions |
| buyers | buyer_id/display_name；initial_balance_cents、current_balance_cents、cumulative_spend_cents、orders_count、units_bought、public_messages_sent、private_messages_sent、failed_purchase_count |
| summary | session_id/status、current_round/current_tick、tick_count、publication_count、total_orders、total_units_sold、total_gmv_cents、public_message_count/private_message_count、succeeded_actions/failed_actions/skipped_actions、technical_failure_count、invalid_batch_count、metric_schema_version、ranking_policy |
| histories | leaderboard/history、publication_leaderboards、profit_trajectory、price_trajectory、tick_history |

successful/failed 只计 Engine 实际 action_result，Wait 是成功动作；skipped 只计 Runner 明确记录的跳过。平台 rejected/pending 不计，invalid batch 单列；technical_failure_count 是 committed aborted 边界数，不是 HTTP 重试次数。failed_purchase_count 只计实际执行失败的 purchase，不把 skipped purchase 当成交失败。price_change_count 只计实际价格变化，不计首次建 Listing、同值改价、描述或上下架；price_trajectory 额外含首次上架价。tick_count 为正常完成 Buyer Wave 数；publication_count 包含初始 0。

技术 aborted 时宿主指标可含已提交而未公开的成功前缀，以 `economic_visibility=committed_failure_prefix` 明示；公开榜仍是上一正常 Tick，不能把两者混用。history 查询按 publication 返回该版本最新 committed prefix，同时保留 transcript_count 便于审计。

## API 与 CLI

管理 bearer：`GET /api/v1/admin/sessions/{sid}/metrics` 与 `/leaderboard`，可加 `?publication_version=3`。OpenAPI `/docs` 标明 Trusted researcher/host；无 token 为 401，actor token 为 403。不要将管理 token 交给 Vue、写 URL 或命令历史。参与者只从原授权 observation 取得公共 leaderboard。

可信本机命令使用忽略的 `.local/platform.json`，不打印凭据：

```powershell
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>'
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>' -Format json -OutDir '.local/metrics/run-01-json'
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>' -Format csv -OutDir '.local/metrics/run-01-csv'
```

OutDir 必须不存在，避免覆盖旧导出。JSON 为 metrics.json；CSV 为 session/sellers/buyers/ticks/prices/profits/ranks.csv 与 manifest.json。空 history 对应空 CSV；字符串公式前缀做电子表格转义，负整数金额保持数值。报告无 token、私聊正文、原始请求/模型输出或完整 journal，但包含全场财务事实，仍只供可信研究者。普通导出留 `.local/`；本任务 Git 示例仅是固定测试数据。

## 验证与限制

自动用例覆盖公式/不变量、负值/平局/名次变化、tick/round 刷新、pending 隔离、故障补齐/竞态、历史重放、权限、JSON/CSV 和商品顺序。真实四角色 UI→HTTP→PG 路径见 [证据](verification/SB-METRICS-001/README.md)，手工步骤见 [MANUAL_MARKET.md](MANUAL_MARKET.md)。

仍是本机小市场：首次补齐会锁 session 并完整重放，历史报告读取完整指标历史；没有增量 checkpoint、大规模性能保证或指标升级器。摘要是完整性校验，不防恶意 DB 管理员。无正式研究评价、库存估值/奖励、Consumer Model、真实 provider、推荐或 HumanDriver。**batch 失败传播语义后续需正式确认**，本任务仅按当前 V1 事实计数。
