# SB-E2E-001 浏览器验收证据

本目录来自当前生产构建、真实 FastAPI/PostgreSQL 和本机 Edge 的四个隔离 browser context，非 local demo。参与者采购/消息/购买/Wait 全部通过 UI 构造批次并 POST 到 `sb-platform-v1`；没有 route mock、DOM 注入市场状态或直接执行 Engine。图中都是固定工程验收输入，不含真实参与者隐私或 token。

[results.json](results.json) 记录实际 session、浏览器版本、九段验收轨迹、HTTP 路径/次数、DB 表计数和成交结果。停服期间的代理 500 为预期故障注入，页面显示离线，重启后恢复；不能把这些请求说成全程无网络错误。[preview-results.json](preview-results.json) 验证生产入口是角色绑定页、token 为密码输入、无 demo/test 控制器。

| 截图 | 验证内容 |
| --- | --- |
| [Seller 采购](seller-procurement.png) | Round 采购观察、本人资金、机会和预算 |
| [Buyer 商品](buyer-products.png) | 两位 Seller 的真实 Listings，保留 Buyer 五页视觉 |
| [Buyer pending](buyer-pending.png) | 本人提交、等待其他 Buyer，不提前成交 |
| [购买失败](buyer-failed-purchase.png) | 同抢最后库存的 OUT_OF_STOCK 回执 |
| [Seller 反馈](seller-feedback.png) | 下一 Tick 的已提交订单、库存、公开与本人私聊 |
| [公共交流](buyer-public.png) | 上一 Wave 消息与下一 Seller Wave 公开回复 |
| [私聊](buyer-private.png) | 当前 Buyer/Seller 私人会话 |
| [账户](buyer-account.png) | 已提交余额、订单与逻辑 Step |
| [排行榜入口](buyer-ranking.png) | 公开商家目录，明确未发布排名/统计 |
| [最终账户](buyer-final-account.png) | 完成两 Round 后的真实订单与余额 |
| [Seller 终态](seller-final.png) | final runtime、Listing revisions、销售结果 |
| [H5 商品](h5-buyer-products.png) | 390px 手机布局，无整页水平溢出 |

重跑命令见 [操作指南](../../MANUAL_MARKET.md)。`test-market` 会创建新 session，并更新本任务这组证据；不会修改历史 SB-002B 截图。测试只是自动工程验证，不代替用户下一次亲自操作验收。结算、供给与批次失败规则仍为当前 TEST/V1 规则。
