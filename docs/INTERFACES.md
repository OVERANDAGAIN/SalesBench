# 接口与职责 v0.1 草案

状态：**DRAFT / 尚未与 Python 主体确认**。Python 实验主体、Buyer/Seller 策略、消费者模型未提供。
本文只约束本轮 Vue 和可替换的异步演示服务；不是已定案的正式 HTTP API。
命名统一由 `frontend/src/domain/types.ts` 实现。所有金额是整数分；时间使用 ISO 8601 UTC；展示层转本地时间。

## 1. 职责与状态归属

| 层 | 本轮职责 | 正式接入后的边界（待主体确认） |
|---|---|---|
| Vue 页面与组件 | 导航、商家筛选、弹窗、输入草稿、数量、加载和错误展示 | 保持展示职责，不裁决购买与研究规则 |
| BuyerService 数据访问边界 | `observe` / `execute` / `getReceipt` / `subscribe` | 由网络适配器替换；调用方不依赖传输协议 |
| 本地演示服务 | 本场模拟商品、商家、余额、订单和消息的唯一来源；延迟和失败可注入 | 只保留为演示/测试，不成为正式研究内核 |
| FastAPI 平台层 | 仅 `/health` | 认证、场次/参与者绑定、授权、动作协调、幂等持久化、事务及通知协调 |
| 独立 Python 实验内核 | 本轮不存在 | 裁决研究规则、调度、状态转移与实验事件；持久化提交边界需共同确认 |
| Buyer/Seller 策略与消费者模型 | 本轮不存在 | 获取被授权观察、输出结构化动作，不直接写库存或数据库 |

页面状态不是市场状态。切页、筛选、详情展开、关闭、继续浏览和暂不购买只改变界面状态，本轮不机械地发服务器动作；也不把它们伪称为已持久化的实验记录。
“暂不购买”保留可见反馈且不扣款。若研究需要采集浏览/拒购事件，另定事件规范和同意边界。
网页账户/实验参与者是平台身份；消费者模拟器是独立研究组件，不是账户页面或身份表的别名。

## 2. 身份、范围与观察

宿主绑定 `actorId` 和 `sessionId`，不接受模型在 query/payload 中切换身份。本地演示默认 `buyer_001` / `demo-session-01`。
本地闭包约束只用于演示与测试，不构成生产认证。正式身份从服务端认证上下文取得。

所有成功观察包含 `ok`、`schemaVersion: "0.1-draft"`、`mode: "local-demo"`、`sessionId`、`revision`、`view`、当前 `actor` 和公开 `merchants`。
`revision` 为当前买家可见变更序号，不是正式实验轮次。返回独立快照，调用方修改不影响服务。

| view | query 附加字段 | 返回数据 |
|---|---|---|
| `leaderboard` | 无 | `leaderboard`：公开商家 + 演示收入、成交件数、rank |
| `products` | 可选 `merchantId` | `products`：按演示顺序和筛选的公开商品 |
| `product` | 必需 `productId` | `product`：规格、描述、价格、库存、商家、图片 URL |
| `public` | 必需 `merchantId` | 本商家 `products`、公开 `messages` |
| `private` | 必需 `merchantId` | 本商家 `products`、本人 `messages`、本人会话 `conversations` 摘要 |
| `me` | 无 | 本人 `account` 与 `orders` |

商品统一 `priceCents`、`stock`、`imageUrl`；订单统一 `unitPriceCents`、`totalCents`、`createdAt`。
消息统一 `channel`、`merchantId`、`author`、`text`、`createdAt`、`isPreset`。author 内含 `id/name/role`。
私聊、订单、余额只属于当前绑定买家；不暴露其他买家状态、内部成本、策略参数或全部市场对象。
图片作为网页资源 URL；不嵌入 Base64，不把图片字节塞入模型文本观察。

```json
{"view":"product","productId":"p1"}
```

非法观察返回 `{"ok":false,"error":{"code":"INVALID_QUERY","message":"...","retryable":false}}`。
查询失败不回退到其他用户或默认全量市场。

## 3. 动作与回执

`execute(action): Promise<Receipt>`，调用前界面显示等待，成功以前不预扣余额、不显示购买完成。

| type | payload | 本地演示效果 |
|---|---|---|
| `purchase` | `productId`, `quantity`, `expectedUnitPriceCents` | 校验后一次更新余额、库存、订单、演示榜单 |
| `send_public` | `merchantId`, `text` | 写入本人公开消息，稍后另行追加预设回复 |
| `send_private` | `merchantId`, `text` | 写入本人私聊，稍后另行追加预设回复 |

不接受顶层/载荷多余字段。`quantity` 是 1–99 的整数，消息去空白后 1–500 字。
前端预校验只帮助用户；权威演示校验在服务内部，所有必要验证通过后才写入状态。

```json
{"id":"purchase-example-001","type":"purchase","payload":{"productId":"p1","quantity":1,"expectedUnitPriceCents":8900}}
```

回执共用 `schemaVersion`、`actionId`、`actorId`、`sessionId`、`revision`、`replayed`。
`status` 为 `pending/succeeded/failed`；只有 `succeeded` 的 `ok` 为 true。

```json
{"ok":false,"schemaVersion":"0.1-draft","status":"pending","actionId":"purchase-example-001","actorId":"buyer_001","sessionId":"demo-session-01","revision":0,"replayed":false}
```

```json
{"ok":true,"schemaVersion":"0.1-draft","status":"succeeded","actionId":"purchase-example-001","actorId":"buyer_001","sessionId":"demo-session-01","revision":1,"replayed":false,"result":{"type":"purchase","order":{"id":"SB-00011","productId":"p1","productName":"陶瓷随行杯","variant":"奶油白 · 380mL","merchantId":"s1","merchantName":"松间生活","unitPriceCents":8900,"quantity":1,"totalCents":8900,"createdAt":"2026-09-23T06:00:00.000Z","status":"simulated_completed"},"balanceCents":41100,"remainingStock":7}}
```

```json
{"ok":false,"schemaVersion":"0.1-draft","status":"failed","actionId":"purchase-example-002","actorId":"buyer_001","sessionId":"demo-session-01","revision":1,"replayed":false,"error":{"code":"OUT_OF_STOCK","message":"剩余库存不足，请调整数量。","retryable":false}}
```

成功发消息的 `result` 使用 `type: "message"`、`messageId`、`merchantId`、`channel`、`replyStatus: "scheduled"`。成功只表示本人消息写入，不代表预设回复已经出现。

## 4. 等待、失败与重复请求

- 动作 ID 由调用方生成，作用域是绑定的场次与买家；同 ID + 同语义载荷的重复请求复用结果，`replayed: true`，不得重复扣款或重复调度回复。
- 同 ID + 不同载荷返回 `ACTION_ID_CONFLICT`。JSON 字段顺序不影响语义指纹。
- 演示 `execute` 等待终态；等待期间 `getReceipt(actionId)` 可返回 `pending`。未知 ID 返回 null，不表示成功。
- 已完成的成功和业务失败均缓存。本地缓存随刷新丢失，不宣称跨进程或数据库幂等。
- 业务失败代码包括 `INVALID_ACTION/INVALID_PAYLOAD/INVALID_QUANTITY/PRODUCT_NOT_FOUND/MERCHANT_NOT_FOUND/PRICE_CHANGED/OUT_OF_STOCK/INSUFFICIENT_BALANCE/INVALID_MESSAGE`。失败不修改库存、余额、订单、榜单或消息。
- 演示可注入提交前暂时故障，作为可重试传输异常，保证该故障未提交状态。正式网络超时可能结果未知，必须使用相同动作 ID 重查/重试，不能自动换 ID 再扣一次。
- 真实网络适配器尚未实现，选择真实模式必须显式报 `NOT_CONNECTED`。禁止 HTTP 失败后悄悄返回模拟成功。

## 5. 变化通知

`subscribe(listener)` 返回取消订阅函数；通知用于失效当前观察、重新读取，不把整份内部状态广播给页面。
topics 为 `products/leaderboard/account/orders/messages`；消息事件附加 `merchantId/channel`。私聊通知只投递给本人；公开消息和公开库存变化可投递给本场其他买家。

```json
{"sessionId":"demo-session-01","revision":2,"topics":["messages"],"merchantId":"s1","channel":"private"}
```

本轮通过内存监听器和延迟队列实现；不是 WebSocket、真实多用户或数据库提交事件。未来 SSE/WebSocket/轮询待后端阶段选择；重连后先重新读取观察，不能假设通知从未丢失。
预设回复延迟独立于发送回执。测试驱动可注入外部商品/消息变更；控制入口只存在演示测试宿主，不向参与者页面或 Agent 暴露。

## 6. Agent 接入位置

Agent 直接调用绑定后的 BuyerService 结构化边界，可在无 DOM 的单元测试中使用；不要求打开网页，不操作弹窗。
未来 Python Agent 在服务端绑定身份/场次后调用同一业务语义，具体 Python 适配包及 HTTP 传输留待主体交付确认。
本轮可选浏览器演示入口只是适配器，不作为 Python Agent 的必需依赖。不暴露 `bindBuyer`、测试控制器或全量市场状态。

## 7. 未决项及迁移判断

排名指标、推荐机制、时间推进、实验轮次、奖励、消费者心理、正式购买/履约语义、状态所有权与持久化提交边界均未定案。
本轮配置明确固定：种子三商家六商品、固定商品顺序、模拟成交额排序、关键词预设回复、模拟购买完成；刷新重置。
数据库事务、持久幂等、认证授权、事件重放和真实通知全部未实现。

结论：没有必须先接入 Python 主体才能迁移的界面依赖。用可替换服务和演示命名隔离未决项，可以进入 C；不实现无法隔离的研究语义。
