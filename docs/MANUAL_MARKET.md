# 手工多角色市场验收 — SB-E2E-001

参与者入口默认是真实 Vue/H5 → `sb-platform-v1` → MarketService → Runner → Engine → PostgreSQL。这里的人工操作是工程验收输入，不是正式 HumanDriver 实验 profile。没有接模型，没有新排行榜、奖励或调度规则。

## 启动与创建场次

5070 的 PostgreSQL/锁定依赖和 `.local/runtime.json` / `.local/platform.json` 已配置。新电脑先按 ENVIRONMENT.md 重建自己的环境，不复制数据库或凭据。在 `D:\SalesBench` 打开 PowerShell：

```powershell
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 install
pwsh -File scripts/platform.ps1 migrate
pwsh -File scripts/run.ps1 install-frontend
pwsh -File scripts/platform.ps1 create-manual
```

`create-manual` 每次创建一个**新的、未执行任何参与者动作**的持久 session：Seller A、Seller B、Buyer 1、Buyer 2、两个商品、一个供应商、2 Round × 3 Tick。初始 Seller 资金各 5000 分、Buyer 各 2000 分，cup 成本 100 分、bag 成本 200 分。它通过 MarketService 创建，不直接执行 Engine。

输出 session ID 与 `D:\SalesBench\.local\manual\<session_id>` 目录，内有 `seller-a.json`、`seller-b.json`、`buyer-1.json`、`buyer-2.json`。文件含角色 bearer，是本机私密材料；不要上传、贴日志、放 URL 或发进 Git。CLI 不打印 token。

两个终端分别运行：

```powershell
pwsh -File scripts/platform.ps1 serve
```

```powershell
pwsh -File scripts/run.ps1 frontend
```

参与者地址 `http://127.0.0.1:5173`；API/OpenAPI `http://127.0.0.1:8000/docs`；PG `127.0.0.1:55432`。所有服务只监听 localhost。也可 build 后用 `scripts/run.ps1 preview` 在 4173 使用生产构建，同样代理真实 `/api/v1`。

## 四个角色如何进入

1. 打开四个独立标签页/窗口；也可以使用四个浏览器 profile。都访问同一参与者地址。
2. 点击“导入本地角色文件”，分别选四份 JSON。页面根据服务器绑定自动打开 Seller 操作台或 Buyer 五页，不根据前端角色下拉框冒充身份。
3. 也可手动输入 session ID 和 actor token（密码框）。仅保存到当前标签页 `sessionStorage`；不使用共享 localStorage，不需要管理 token。
4. 刷新页面自动重新读取服务器 observation 和本人 receipts。复制已有标签页时浏览器可能复制 sessionStorage；用“切换绑定”清除旧绑定，再导入另一角色。

绑定不是正式注册登录。关闭标签页可能丢失其本地凭据，但数据库 session 不丢失；重新导入对应 JSON 即可。若角色 token 被管理员 rotate，旧文件失效，需要保存新凭据。切换绑定清除本地草稿/请求；有 unknown 请求时应先查询回执再切换。

## 每轮怎么操作

顶部状态区显示 Round / Tick / Wave、publication、Engine step、连接状态、当前机会/预算、本人是否提交、最近回执。本人没有机会时可以浏览；不得把没提交视作 Wait。

Buyer 保留排行榜、商品推荐、公共交流、私聊、我的五页。公开或私聊的“加入本轮消息”，以及确认购买里的“加入本轮批次”，只构造本地可见草稿。消息最多两条，purchase 至多一笔且在末尾；在购买之后加入消息会放到 purchase 前面。页面不提前改钱、库存、订单或消息记录。

Seller 操作台提供采购、建立 Listing、改价、改销售描述、上下架、公开/私聊；表单点击“加入有序批次”，可按预算组合并调整先后。价格/成本字段使用**整数分**；Listing 简写 `cup` 自动补为本人 `seller-a/cup` 或 `seller-b/cup`。供应商报价仅在 Round procurement 的授权观察里显示。

所有角色都要明确点击“提交本轮批次”。单独不行动可点击“明确 Wait / 不行动”，再提交；Buyer 的“暂不购买”会移除草稿 purchase，保留消息，空批次才加入 Wait，仍需提交。清除草稿和关闭弹窗不是服务端动作。

`pending` 表示请求已保存、等其他 actor；不是成交。只有全部 actor 收齐后，Runner 校验并执行，DB 提交后发布新版本。通过通知轮询/观察刷新自动更新，手动“刷新服务器观察”也可用。正常的 pending 不提供替换本机会意图功能。

回执显示 `pending / rejected / succeeded / failed / aborted`，以及每个动作的 status、code、skipped 原因。新 publication 不会悄悄替换旧草稿的报价；旧草稿标为过期，需要操作者检查后清除并重新决定。Engine 的 PRICE_CHANGED / STALE_LISTING / OUT_OF_STOCK 等保持原裁决。

断线/COMMIT_UNKNOWN 时保留原 request ID、原版本和完整 envelope，锁定草稿，点击“查询 / 重试原请求”。查到 receipt 就使用该结果；404 才以原 ID/内容重发。页面不生成第二笔购买来猜测第一笔是否成功，也不静默进入 local demo。停 API 时 Vite 代理可能返回 500；页面明确离线，恢复后重读 DB。

## 一条完整手工轨迹

以下用新 create-manual 场次。输入每批动作后按“提交本轮批次”，需在两个相同角色的窗口都提交才能继续。价格输入单位为分。

| 当前发布 / 机会 | Seller A / Buyer 1 | Seller B / Buyer 2 | 下一发布 |
| --- | --- | --- | --- |
| 0，R1 采购 | A 采购 cups × 1 | B 采购 cups × 3 | 1 |
| 1，R1/T1 Seller | 建立 cup，Product cup，售价 300，销售描述 | 建立 cup，Product cup，售价 500，销售描述 | 2 |
| 2，R1/T1 Buyer | Buyer 1 在 A 公共区发言、私聊 A、买 A/cup 1 件，三动作一批 | Buyer 2 买 A/cup 1 件 | 3 |
| 3，R1/T2 Seller | A 改价 400、更新描述、公开回复，三动作一批 | B 私聊 buyer-2 | 4 |
| 4，R1/T2 Buyer | Buyer 1 买 B/cup 1 件 | Buyer 2 点击暂不购买 / Wait 并提交 | 5 |
| 5，R1/T3 Seller | A 下架后再上架，两个动作一批 | B Wait | 6 |
| 6，R1/T3 Buyer | Buyer 1 Wait | Buyer 2 Wait | 8（包含 Round close） |
| 8，R2 采购 | A 采购 cups × 2 | B Wait | 9 |
| 9，R2/T1 Seller | A 改价 450 | B Wait | 10 |
| 10，R2/T1 Buyer | Buyer 1 买 A/cup 1 件 | Buyer 2 买 A/cup 1 件 | 11 |
| 11–13，R2/T2 | 两 Seller 分别 Wait，再两 Buyer 分别 Wait | 所有人都明确提交 | 13 |
| 13–16，R2/T3 | 两 Seller 分别 Wait，再两 Buyer 分别 Wait | 最后自动 Round close | 16 / completed |

第一场竞争时先提交 Buyer 1，再停下来观察 pending：此时库存/订单/余额尚未改变。Buyer 2 提交后由原 seeded resolver 排序；本固定配置下 Buyer 1 成交，Buyer 2 的最终 receipt 为 OUT_OF_STOCK。HTTP 先后不决定胜负。下一 Tick，A 可见自己的销售订单、公共问题和私聊；B 能看公共问题，看不到 A 的私聊。

A 在 T2 改价/描述后，同 Tick Buyer 看见 400 分、offer revision 2 / content revision 2。上下架再复售后 offer revision 4，R2 改价后为 5；库存变化不增加 offer revision。最后四笔订单为 300、500、450、450 分；Buyer 1 余额 750 分、Buyer 2 1550 分，A 5900 分、B 5200 分、Supplier 600 分。没有把资金守恒或裁决逻辑写进 Vue；这些是当前固定场景的服务端结果。

推荐在 publication 8、R2 尚未采购时测试恢复：先 Ctrl+C 停 API，`pg-stop`，观察页面离线；再 `pg-start` 与 `serve`。不重新 create、不 rotate token，刷新原标签页，读取同一 session 后继续 R2。完成后的场次也可重启后查询。

## API、inspect 和 PostgreSQL

`/docs` 保留 OpenAPI。参与者使用 actor bearer；创建/rotate/run 的管理 bearer 仅由可信宿主掌握，不传给 Vue。端点与语义见 PLATFORM.md，新增本人列表为 `GET /api/v1/sessions/{sid}/receipts`。UI 不传 actor_id 切换权限，不能查询全量 journal。

```powershell
pwsh -File scripts/platform.ps1 inspect -SessionId '<session_id>'
pwsh -File scripts/platform.ps1 recover -SessionId '<session_id>'
```

`inspect` 是本机只读开发工具，读取一个 committed boundary 并验证恢复；输出 runtime/current publication、actor ID/role、pending/final receipts、Listings、订单、账户/库存、resolution 和 journal 计数/摘要、表行数。**不输出 token、token hash、私聊正文或原始 journal**。余额/订单等仍是宿主私有数据，不要把输出作为参与者 API 或普通用户下载。它不修改状态或推进 Wave。

| PostgreSQL 表 | 可核对的材料 |
| --- | --- |
| `market_sessions` | 已提交 runtime、publication version、fence、trace/state digest |
| `actor_bindings` | actor ID/role；不要导出 token_digest |
| `batch_receipts` | 原请求 ID、pending/final 状态、提交版本；完整 request 可能含私聊 |
| `action_receipts` | 真实 Runner 动作、action ID 和 outcome；也可能含私聊 |
| `publications` | 每个已提交 public snapshot |
| `actor_projections` | 授权观察，包括本人账户/库存/订单；全表只能宿主看 |
| `resolutions` | 原 Runner 裁决顺序 |
| `journal_entries` | canonical transcript，含恢复所需 Listing/订单/资金/消息记录，不公开 |
| `semantic_events` / `outbox_notices` | 事件与 audience / 无私密 payload 的发布失效通知 |

本架构没有第二套 SQL `orders` 经济表；订单保存在 Engine trace/本人投影，并由同版本 Engine 恢复核对。不要在 SQL 再写 purchase 或手动修余额。需要用 DB 客户端查看时只连本机配置库，在 `BEGIN READ ONLY` 中按 `session_id` 筛选必要列，禁止全表 dump/复制凭据；日常验收优先 inspect。

## 测试与边界

```powershell
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/platform.ps1 test
pwsh -File scripts/run.ps1 typecheck
pwsh -File scripts/run.ps1 test-frontend
pwsh -File scripts/run.ps1 build
pwsh -File scripts/run.ps1 test-market
```

`test-market` 要求配置 PG 已启动，8000/4173 空闲；会创建自己的持久场次，用本机 Edge 四个隔离 context 点击真实 UI，并重启配置的本机 PG。不要和其他工作同时使用该 PG；结束清理自有 API/preview/browser，最后自行 pg-stop。截图和无凭据结果见 [验收证据](verification/SB-E2E-001/README.md)。历史 demo 自动化是单独回归，不作为真实 E2E 证据。

当前仍是 TEST 规则：有限供应、即时采购/结算、共享库存、整数分报价、seeded resolver、既有批次预算和失败传播。**失败传播语义后续需正式确认**。本轮没有正式排行榜/推荐/奖励（排行榜入口只展示公开商家，统计为未发布）、消费者模型、物流/退款/税费、真实模型、人类实验协议、WebSocket/SSE 或正式身份系统。

网络适配器的五页 DTO 只做授权数据展示：`Product.id` 在 UI 中映射 Listing ID；不推断库存/钱/报价合法性。消息和订单显示 Engine Step；库存、价格和余额以已提交观察为准；封面为明确标注的中性示意，不用演示商品数据补齐真实市场。

结束时先 Ctrl+C 停前后端，再 `pwsh -File scripts/platform.ps1 pg-stop`。保留数据库与角色文件；不要删 session 来重试结果未知的购买。下一轮要新市场时再 create-manual，已有场次仍可查询。
