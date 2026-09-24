# 当前接口与层间适配

当前 HTTP/application schema 是 **sb-platform-v1**；端点、envelope、状态码、故障保证见 [PLATFORM.md](PLATFORM.md)，运行时 OpenAPI 是 `/docs`。Market Wave 协议为 **sb-wave-v1**；前端不得借适配改变它。旧 Vue 单动作演示草案已移到 [历史契约](history/INTERFACES-v0.1.md)，仅供 demo/test 对照。

## 当前调用边界

| 调用方 | 入口 | 边界 |
| --- | --- | --- |
| Buyer 五页 | `NetworkBuyerService` → `MarketClient` | observe/subscribe 是展示 facade；stage/decline 构造草稿，submitBatch 才提交完整批次 |
| Seller 工程页 | 同一个 `MarketClient` | 按当前 opportunity 的角色/预算构造有序批次，不直接改市场状态 |
| HTTP / 未来 Agent | FastAPI → `MarketService` | 绑定身份、持久 intent/receipt、候选推进、事务发布；不直接 Engine.execute |
| 本机可信 CLI | 同一个 `MarketService` | 创建/恢复/只读 inspect；不作为公开参与者数据端点 |
| Platform | SubmissionDriver → Runner → Engine | 原 Wave/结构校验/裁决链；数据库没有第二套 purchase |

`MarketClient` 调用授权 observation、notifications、本人 receipts 和 actions。默认开发入口与生产构建均为 network；仅开发环境显式 `VITE_BUYER_SERVICE=demo` 启用历史演示，不存在网络错误回退。

## DTO 与语义映射

| 概念 | 当前契约 |
| --- | --- |
| session / actor | token 绑定固定身份；不接受 action payload 自报 actor_id；Vue 用每标签页 sessionStorage |
| Product / Listing | Engine Product 只有商品身份；五页展示 DTO 的 `Product.id` 实际映射 `listing_id`，不把 Offer/Inventory 混进 Engine Product |
| 金额 / 库存 | 整数分；展示已提交授权值，合法性与扣款/扣库存只归 Engine |
| 授权观察 | 公共 Seller/在售 Listing/消息 + 本人 own/inbox；采购机会额外给 Seller supplier offers |
| publication | 已提交 public/projection 版本；本 actor observation/runtime 与其一致 |
| offer / content revision | 分别对应价格/active 与销售描述；库存变化不增加 offer revision |
| 时间 | Round/Tick/Wave 为 Runner context；订单/消息显示 Engine Step，不能当 UTC 时间 |
| opportunity / batch | 本 actor 本 Wave 的稳定机会 ID + 可用动作/预算；显式提交有序 batch，purchase 至多一笔且在末尾 |
| purchase | 保存观察时的 listing_id、quantity、expected_unit_price_cents、expected_offer_revision，旧草稿不自动换报价 |
| request / action ID | Web request_id 标识完整批次、支持跨进程重试；Runner action_id 标识批次内动作。两者均不决定购买顺序 |
| receipt | pending / rejected / succeeded / failed / aborted；pending 只表示已持久接收，不表示成交。失败/skipped 原因原样展示 |
| 通知 / subscribe | 当前使用持久 notification polling 再读取授权观察；失败 runtime 可能不增版本，因此同时轮询观察/回执 |
| 排行榜 | observation 顶层 leaderboard 为公共持久快照；新场次默认 Tick Close 刷新 dev_cash_profit_v1，所有 actor 同 publication 共用。旧场次 NULL policy 保留 null，不补造历史。详情见 METRICS.md |
| 宿主 Metrics | 管理 bearer 的 `/api/v1/admin/sessions/{sid}/metrics`、`/leaderboard`；actor token 403，Vue 不读取全场私有财务 |
| 商品推荐 / 图片 | 原 public listings 顺序不随排名变化；商品使用标注的中性示意图片，不注入演示商品或推荐算法 |

同 opportunity 的 Seller 都提交后才发布，Buyer 再读取同 Tick 新价。Buyer 消息/购买也先入草稿再整批提交。切页、筛选、关弹窗不是 Engine action；明确“不购买”会从草稿移除 purchase、保留消息，空批次才变为 Wait，仍须提交。未提交持续等待。

## 重连与失败

- POST 前保存原 request ID、publication、opportunity 和完整有序 actions。响应未知时不换 ID，不编辑原请求；先查询 durable receipt，404 时也只重发原 envelope。
- 相同 ID/内容先返回旧 receipt；同 ID 不同内容为 ACTION_ID_CONFLICT。新 ID 不能替代本机会已接收批次。
- stale publication 为平台 rejected；PRICE_CHANGED / STALE_LISTING / OUT_OF_STOCK 等由 Engine 在 Wave 内裁决，最终 receipt 才判定经济结果。
- 刷新/重新绑定从 server observation 与本人最近 50 个 receipts 恢复，pending 优先；列表不包含其他 actor 意图。失败网络明确离线，旧数据显示为可能过期。
- admin token、完整 DB、journal、全场 inspect 从不提供给 Vue。actor token 不放 URL、普通日志、截图或 Git。
- 指标与经济提交之间若短暂缺派生视图，服务器有限补齐重读；仍不可用为 METRICS_NOT_READY，不返回版本不匹配的榜单。指标一致性/源码策略错误 fail closed。receipt 幂等不受影响，不能将指标错误视为购买回滚。

## 仍需独立设计的边界

正式 Agent provider/profile、Consumer Model / Seller Policy、正式用户身份与 HumanDriver、正式评价/奖励、真实时间映射和履约仍未实现；开发利润榜不代表这些研究机制已经定案。

**失败传播语义后续需正式确认**：当前 Runner 保留成功前缀，业务失败后跳过剩余动作，可能使失败消息阻止末尾 purchase。本轮不改变此规则。细节和当前保证见 [ARCHITECTURE.md](ARCHITECTURE.md)、RUNNER/PLATFORM。
