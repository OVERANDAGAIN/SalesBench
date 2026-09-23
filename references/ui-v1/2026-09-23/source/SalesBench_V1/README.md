# SalesBench 买方端 V1

一个独立、零第三方运行依赖、可离线打开的中文买方网页原型。未修改或接入实验核心代码，未部署，无模型调用、真实支付、Seller 后台或 Agent 管理界面。

## 打开与开发

- **直接体验**：用 Chrome / Edge 打开 `dist/SalesBench.html`。所有样式、脚本和商品图片均已嵌入，可断网使用。
- **查看源码页面**：直接打开根目录 `index.html`，或在本目录运行 `npm run dev`，然后访问 `http://localhost:4173`。若只在本机使用，可将 `scripts/serve.mjs` 的监听地址改为 `127.0.0.1`。
- **运行测试**：Node.js 18 或以上，执行 `npm test`，无需 `npm install`。
- **复跑 Agent 示例**：`node scripts/agent-demo.cjs docs/agent-trace.json`。
- **重新生成单文件原型**：`npm run build`。

固定导航：**排行榜 → 商品推荐 → 公共交流 → 私聊 → 我的**。商品详情、确认购买、购买完成和演示说明均为弹窗。

## 已实现的流程

1. 排行榜查看 3 个模拟商家 → 进入对应商家的商品、讨论区或私聊。
2. 商品推荐展示 6 件商品 → 查看详情、公开提问、私聊或直接购买。
3. 每个商家独立讨论区：上方销售描述与关联商品，下方预设多人发言、买家新消息和商家公开回复。
4. 私聊列表与 3 个商家的独立会话，仅观察当前买家的消息。
5. 确认购买时检查数量、价格、库存和余额；成功后一次性扣余额、减库存、增加成交额／件数和本人购买历史。
6. 支持继续浏览、关闭详情和明确选择「暂不购买」。不购买不扣款，不产生订单。
7. 相同动作编号与相同内容重试返回原回执，不会重复扣款；同编号不同内容拒绝。

所有页面、真人交互、`window.salesbench` 和可用时注册的 WebMCP 工具，共用 **同一个 `createSalesBench()` 实例和 `execute()` 动作处理器**。不存在五套独立写死的业务状态。UI 商品与购买记录始终带商家归属。

## 集中说明：当前演示配置

| 项目 | V1 暂定方案 | 后续可修改位置 |
|---|---|---|
| 排名指标 | 模拟累计成交额降序；含预置交易金额；同额按商家编号 | `src/core.js` 的 `rank()`、商家种子数据 |
| 排名公开字段 | 排名、商家名、模拟成交额、成交件数 | `rank()`、`merchantView()` |
| 商品推荐 | 固定数组顺序；可按商家浏览；无个性化 | 商品数组、`observe()` |
| 商品公开字段 | 标价、库存、规格、归属与销售描述 | `productView()` |
| 预算与价格 | 初始 ¥500；整数分储存；商品 ¥49–199；均为模拟人民币 | 买家和商品种子数据 |
| 商家回复 | 基于少量关键词的预设文本；立即回复 | `execute()` 的发送消息分支 |
| 多人交流 | 预置多人公开发言 + 当前体验买家发言；不是实时多人服务 | 公开消息数据及发送动作 |
| 图像 | 3 张 AI 生成商品示意图，同系列款共用图；页面已注明 | `assets/` |
| 购买 | 确认即完成模拟交易，无物流、售后或真实支付 | `purchase` 分支 |
| 时间 | 消息和订单使用操作时刻；不模拟实验天数或轮次 | `clock` 注入参数 |
| 状态生命周期 | 当前打开页面的内存状态；五页共享，刷新后重置；不同标签页互不共享 | `src/app.js` 初始化 |

这些配置用于验证页面流程，**不是已经确定的正式实验算法，也不意味着定义了奖励函数、消费者心理机制或竞争规则**。前台「演示说明」弹窗可查看主要配置。

## Agent Buyer JSON

浏览器只暴露绑定到 `buyer_001` 的两个方法：

```js
window.salesbench.observe({ view: 'product', productId: 'p1' });
window.salesbench.execute({
  id: 'agent-purchase-001',
  type: 'purchase',
  payload: { productId: 'p1', quantity: 1, expectedUnitPriceCents: 8900 }
});
```

观察、动作与回执均可 JSON 序列化。JSON 不能提供 `actorId` / `buyerId` 来切换身份。`bindBuyer()` 只属于内核宿主，未挂到浏览器 Agent API 上。回执包含 `ok`、`actionId`、`actorId`、`type`、`revision`、结果或明确错误码。已运行示例见 `docs/agent-trace.json`。

| 动作 | payload | 效果 |
|---|---|---|
| `browse` | `page`, 可选 `merchantId` | 切换五页之一，或浏览特定商家 |
| `view_product` | `productId` | 查看指定商品，浏览器中打开详情 |
| `close_detail` | `{}` | 关闭商品详情 |
| `send_public` | `merchantId`, `text` | 发送公开消息并生成预设公开回复 |
| `send_private` | `merchantId`, `text` | 发送当前买家私聊并生成预设私聊回复 |
| `purchase` | `productId`, `quantity`, `expectedUnitPriceCents` | **立即完成模拟购买**，不是仅打开确认框 |
| `decline_purchase` | `productId` | 记录暂不购买，余额和订单不变 |

观察 view 为 `leaderboard / products / public / private / me / product`。共同信息包含当前买家身份／余额、导航、公开商家字段、演示配置和观察权限。不同 view 只增加对应页面内容；只有 `me` 返回本人订单，只有 `private` 返回本人选定商家会话。未提供 `getState()` 或内部数据导出。

权限验证含独立的 `buyer_002` 测试身份：公开消息共享；私聊、余额和订单不串号；商家内部成本不进入观察。**这只是本地原型的接口可见性边界，不是生产级认证或浏览器安全隔离**。源码和种子数据可被本机使用者查看或修改；正式实验需把内核放到受控服务端并由认证上下文绑定身份。

## 验证与交付边界

- `tests/core.test.cjs`：11 项有实际断言的内核测试。
- `scripts/agent-demo.cjs`：实际执行 JSON 购买并读取真人同一状态；余额从 50000 分变成 41100 分、订单变成 1 笔。
- `docs/agent-trace.json`：该次执行的观察、动作、回执和购买后观察。
- 已完成真实浏览器点击流程与五页截图。详见 `docs/verification.md`。

未实现：服务端认证、跨浏览器／多人同步、持久化数据库、多商家自主行动、异步消息队列与调度、模型调用、正式 user simulator、推荐或排名实验算法、真实交易、物流售后、Seller 后台、Agent 管理界面、实验核心集成。

## 环境与空间

未安装依赖，新增依赖占用 **0 B**，没有创建 `node_modules`。复用现有 Node.js、Python 和浏览器检查环境。项目源文件在独立目录内，生成过程不触碰用户本机 C 盘。交付包包含源码、图片、单文件 HTML、测试与说明；可直接删除整个解压目录清理。

商品照片已压缩为 WebP，单文件 HTML 约 0.17 MiB。最终包和截图的精确大小见 `docs/verification.md`。
