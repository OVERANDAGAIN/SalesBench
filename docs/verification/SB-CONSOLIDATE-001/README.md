# SB-CONSOLIDATE-001 当前回归证据

2026-09-24 在 5070 用当前生产构建、Edge 四个隔离 context、真实 FastAPI/Runner/Engine/PostgreSQL 重新运行。不是 SB-E2E-001 截图副本；原历史记录保持原样。

[results.json](results.json) 记录完整九段轨迹、实际 HTTP/PG 计数、session、订单与经济摘要；[preview-results.json](preview-results.json) 记录生产默认入口；[checks.json](checks.json) 汇总本次所有检查。日志和完整宿主 inspect 留 `.local`，不进入本目录。

| 截图 | 内容 |
| --- | --- |
| [Seller 采购](seller-procurement.png) | Round procurement 的真实机会和资金 |
| [Buyer 商品](buyer-products.png) | Seller 发布后的真实 Listings |
| [Buyer pending](buyer-pending.png) | 已提交但等待另一个 Buyer，无提前成交 |
| [库存竞争失败](buyer-failed-purchase.png) | Engine 返回 OUT_OF_STOCK |
| [Seller 反馈](seller-feedback.png) | 下一 Tick 本人订单、公共与私聊 |
| [Buyer 私聊](buyer-private.png) | 授权 inbox |
| [Buyer 公共](buyer-public.png) | 已发布公共消息 |
| [Buyer 中途账户](buyer-account.png) | 重启前余额/订单 |
| [排行榜入口](buyer-ranking.png) | 真实商家目录，排名未发布 |
| [Buyer 最终账户](buyer-final-account.png) | completed 后已提交余额/订单 |
| [Seller 最终状态](seller-final.png) | completed 库存/Listing/销售 |
| [H5 商品](h5-buyer-products.png) | 390px 窄屏，无整页横向溢出 |

这些截图只含固定验收市场的数据，不含 actor/admin token。OUT_OF_STOCK 和中途代理 500 是有意验证失败/断线，不是测试未通过。人工验收步骤见 [手工指南](../../MANUAL_MARKET.md)，本次收口详情见 [handoff](../../handoffs/SB-CONSOLIDATE-001.md)。
