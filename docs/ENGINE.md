# SalesBench Experiment Engine Skeleton

SB-CORE-001 / 2026-09-23。内核骨架已实现；经济行为仍是明确命名的 TEST 规则，不是正式研究协议。

SB-RUNNER-001 / 2026-09-24：包升级至 0.2.0，新增独立 [Market Wave Runner](RUNNER.md)。以下领域边界继续适用；benchmark 调度以 RUNNER.md 为准。`Purchase` 现在必须传 `expected_offer_revision`，旧调用需要随观察一起取报价版本。本文末尾 36 项测试等为 SB-CORE-001 历史记录，本次验证见 RUNNER 交接记录。

SB-PLATFORM-001：当前包 **0.2.1**，新增 Runner `advance_boundary` / `pending_observations` / `restore_committed` 可信宿主契约；领域对象、研究调度、purchase 裁决和 TEST 经济规则不变。FastAPI 通过 [PLATFORM.md](PLATFORM.md) 的 service 调用 Runner，已实现数据库幂等、提交与恢复；本文中“未来平台”描述保留原骨架阶段背景，以下领域说明仍适用。

## 位置与职责

独立工程位于 `engine/`，Python 包为 `engine/src/salesbench_engine/`。独立 pyproject、uv.lock 和 `.venv`；零第三方运行时依赖，测试使用标准库 unittest，固定构建后端为 uv_build 0.8.22。没有搬动 frontend/backend。平台通过 backend 的锁定本地包依赖安装 Engine，Engine 不反向依赖平台。

Engine 拥有一个 Experiment 的内存状态，校验和裁决动作，生成结果/事件，推进逻辑时间。Policy 只决定意图；身份认证、HTTP、数据库事务、幂等、持久化和通知传输由未来平台 application/adapter 层负责。参与者和未来 Seller 人工界面采用 Web/H5，Engine 无 UI。

| 模块 | 职责 |
| --- | --- |
| `models.py` | 不可变领域记录、角色观察、时间、结果、事件和宿主快照 |
| `actions.py` | 不含 actor 身份的采购、上架/更新、消息、购买和等待意图 |
| `environment.py` | Engine 状态所有权、权限过滤、原子转移、守恒校验和时钟 |
| `policies.py` | Buyer/Seller/Supplier 共用 Policy 协议与按 step 等待的 ScriptedPolicy |
| `rules.py` | 可替换 RankingPolicy；默认 TestGrossSalesRanking |
| `scenario.py` | 固定小市场的 CLI 示例与自检，不是平台 API |
| `runner/` | Round/Tick/Wave、冻结观察/并发 Driver、发布、确定性裁决、进程内幂等、审计/重放 |

## Domain state

- Experiment 是一场市场的配置和作用域；Supplier、Seller、Buyer 的 ID 在该场内唯一，每个角色有且仅有一个 Account。
- Product 只有商品身份和名称。SupplierOffer 单独包含供应者、商品、进货成本、供应数量和是否有效。
- Inventory 以 `(seller_id, product_id)` 表示 Seller 已拥有数量。Listing 单独描述卖方、商品、售价、销售描述和是否在售；`offer_revision` / `content_revision` 从 1 开始。
- 多个 Listing 可以共享同一 Seller/Product 库存池，观察中的可售数量动态来自库存；没有给每个 Listing 复制一份库存。
- Procurement 与 Order 保存成交当时的数量、整数分单价、总价和 step；之后改价不会改写历史记录。
- Conversation 由 Buyer/Seller 配对，Message 区分 public/private。Account、所有成交价和成本均为整数分，拒绝 bool/float 充当金额或数量。
- 初始报价有限供给，初始 Seller 库存和 Listing 为空。标识使用明确字符串或每类单调计数 ID，不使用数组位置。生成 ID 在一场内唯一，跨场需附带 experiment_id。

`snapshot()` 是可信宿主/测试的完整不可变导出，含所有参与者和初始配置，**不得作为参与者接口返回**。它不是当前版本的持久化恢复或事件重放协议。Python 的 frozen record 是编程约束，不是对恶意同进程 Python 代码的沙箱。

## Observation / Action / Result

```python
from salesbench_engine.actions import Purchase
from salesbench_engine.models import View

observation = engine.observe(bound_buyer_id, View.PRODUCT, listing_id="cup-listing")
listing = observation.listings[0]
result = engine.execute(
    bound_buyer_id,
    Purchase(listing.listing.id, 1, listing.listing.unit_price_cents, listing.listing.offer_revision),
)
engine.advance()  # 由可信环境/宿主调用，不是 Buyer Action
```

Engine 的 actor_id 参数由可信宿主绑定，Action 内不能切换身份。Engine 校验存在性和角色权限；这个 Python 参数本身不构成 Web 认证。

| 观察 view | 数据范围 |
| --- | --- |
| market / product | 在售 Listing、关联商品、Seller 公开身份和当前可售库存；详情用 listing_id |
| suppliers | 仅 Seller：有效供应报价、供应者和商品目录 |
| self | 本人 Account；Buyer 本人订单；Seller 自己库存、全部 Listing、订单和采购；Supplier 自己报价和采购记录 |
| public | 公开消息，可按 Seller 筛选 |
| private | 仅本人参与的 Conversation/消息，可按 Seller 筛选；Supplier 无私聊权限 |
| leaderboard | 明确标记规则名的 TEST 成交额榜单，不包含 Buyer 订单明细或 Seller 成本/余额 |

每份观察只带本人 Account。事件按 audience 过滤；采购事件对 Supplier/Seller 可见，购买事件对 Buyer/Seller 可见，私聊事件只对双方可见。观察错误抛 `ObservationError(code)`，不回退到其他身份/全量状态。返回不可变 tuple/record；持有旧观察不会随着后续动作改变。

| Action | 权限与效果 |
| --- | --- |
| Procure | Seller 采购，校验报价、成本、数量、供应量和资金；立即移交库存并向 Supplier 付款 |
| CreateListing | Seller 用已有库存上架；Listing ID 不可覆盖 |
| UpdateListing | 仅所属 Seller；更新售价、描述、在售状态；多个字段作为一个动作提交 |
| SendPublic | Buyer 在指定 Seller 频道发消息；Seller 只能在自己的频道回复 |
| SendPrivate | Buyer/Seller 互发；首次消息建立双方 Conversation |
| Purchase | Buyer 购买指定 Listing；校验 actor、数量、价格/报价版本、在售状态、库存和资金 |
| Wait | 任一角色显式不行动/不购买；记录本人可见的 waited 事件，不动资金/库存/时间 |

采购和购买均先校验，成功后同时更新资金、库存、成交记录和事件。失败返回 `Result(ok=False, code=...)`，整个状态（包括事件、会话和 ID 计数器）不变。实现通过独立草稿计算、校验后整体替换保证单动作逻辑原子性；异常中断也不提交草稿。每次成功动作验证货物和资金守恒。

报价版本检查直接在 Engine 内完成：实际售价或 active 改变时 `offer_revision + 1`；实际描述改变时 `content_revision + 1`；重复赋同值不增版本，库存变化不增报价版本。合法 purchase 的报价检查顺序为 `PRICE_CHANGED` → `STALE_LISTING` → `LISTING_INACTIVE`；改价再改回也会拒绝旧版本。Order 固化成交时的 `offer_revision`。Runner 不复制这些检查。

Result 同步给出 ok/code/step/entity_id/events，没有 pending 或网络 receipt 生命周期。Event 包含 ID、kind、step、actor、entity 和 audience；它是引用式审计记录，不是足以重建完整历史的事件溯源日志。业务失败不写入 Engine 日志，未来平台可另外记录失败请求。

单 Engine 实例的锁防止并发超卖，但不协调不同进程/不同 Engine 实例。复制状态和完整事件保留适合骨架与小型实验，不宣称大规模性能或数据库事务保证。

## Policy、时间与可复现性

`Policy.decide(observation) -> Action` 为 Buyer/Seller/Supplier 共用协议，角色在观察中明确给出。Policy 不接收 Engine 或可变市场状态；宿主将返回意图交给绑定身份的 execute。替换为未来消费者/LLM Policy 不需要改动现有库存和资金逻辑。

ScriptedPolicy 每次提议一个意图；ScriptedDecision 的 at_step 未到时返回 Wait。决策在提议时消耗，即使随后被拒绝也不自动重试。Supplier 本轮只使用固定报价和 Wait，没有正式供应策略或动态补货动作。

当前 step 从 0 开始，由 `advance(n)` 显式增加；每增加一个 step 产生 time_advanced 事件，动作自身不推进时间。基础 Engine 的可选 `steps_per_demo_day` 映射从 0 开始的 demo day，默认无 day 映射；Runner 不启用该映射。Engine 无 sleep、UTC/wall-clock、自动回复线程或后台定时器。

基础 Policy 的延迟扩展位置是“宿主 advance(1) → 观察 → 调用到期 Policy → execute”。旧示例中的私人回复在 step 1 执行。`advance(n)` 不自动调用 Policy。SB-RUNNER-001 将每个正常 Round 映射为一次 `advance(1)`；Tick/Wave 不再调用 advance，Runner 禁用 demo day 映射。Tick/Wave 是 Runner 的研究调度单位，不等于 Engine step。真实分钟/小时/天仍未定。

相同配置、seed 与相同调用顺序得到相同结果。示例用独立 `Random(seed)` 选择 TEST 售价，不修改全局 RNG；可复现性不承诺并发线程抢锁次序一致。

## TEST 规则和未决研究语义

当前 TEST 规则：有限固定供应；采购立即交货和付款；购买即时结算/履约、全额计入 Seller 资金；共享库存池；非负整数分售价允许免费商品；文本上限消息 500/销售描述 2000 字符；成交额榜单按 Seller ID 打破平局；示例固定调用顺序、固定脚本和两步映射一天。

RankingPolicy 可直接替换。即时结算集中在 `_transfer` 和采购/购买转移中；未来复杂结算需先定义新的资金/订单状态契约，不宣称当前模型已经支持托管、退款或分期。

仍未确定：正式排名/推荐、消费者心理、Seller 最优策略、供给/补货机制、实际时间尺度、奖励、履约/物流、退款、佣金/税费、身份与参与者分配，以及持久化提交与跨进程恢复责任。V1 回合调度和 action trace 重放见 RUNNER.md；这不代表真实模型、数据库或研究结果。

## 与 INTERFACES v0.1 的待对齐项

| Vue 草案 | Engine 当前边界 / 平台后续工作 |
| --- | --- |
| Product 含商家售价/库存，purchase(productId) | Product/Offer/Inventory/Listing 已拆分；购买使用 listing_id，适配器需明确商品与销售 Listing 的映射 |
| ISO UTC createdAt | Engine 使用 step；平台记录请求时间与研究逻辑时间须分开 |
| actionId / pending / receipt / replayed | Engine 每次 execute 都是新意图；Runner 提供进程内动作去重，平台仍需持久幂等、回执和结果未知恢复，不能盲重试 |
| schemaVersion 0.1-draft / local-demo | Python 记录不是该 HTTP DTO；后续版本化序列化由 adapter 定义 |
| subscribe / revision | Runner 有 published version、Listing 有 offer/content revision；均不等同于 Vue 通知 revision，不能直接广播宿主快照/全体事件 |
| 预设回复自动排队 | Engine 不自动产生 Seller 回复；由宿主在逻辑 step 调用独立 Policy |
| 暂不购买只是 UI 反馈 | UI 关闭弹窗仍不产生 Engine Action；研究策略明确选择不行动时可以提交 Wait，两者不强行一一映射 |
| 排行榜/推荐 | TEST 榜单可替换；market 是稳定插入顺序的公开 Listing 集合，不是正式推荐算法 |
| 平台采购 / Seller 操作未定义 | Engine 已有对应意图；HTTP 授权和 DTO 需在下一阶段另定 |

建议调用链：Web/H5 → FastAPI 路由 → application/adapter（认证与场次绑定、DTO 转换、幂等/持久化协调）→ Engine。未来后端通过本地包依赖或构建 wheel 安装 `salesbench-engine`，不要复制源码或让 Engine 反向 import backend。

SB-PLATFORM-001 已落实提交与恢复责任：恢复的是已校验的 canonical Runner transcript，不是 snapshot；候选 Engine 执行后只有 PostgreSQL 提交成功的发布可被参与者读取。内核自身仍不提供数据库事务或身份认证。具体保证和未保证故障见 PLATFORM.md。

## 运行与验证

在工程根目录，使用本机已配置的 Python 3.12/uv：

```powershell
pwsh -File scripts/engine.ps1 install
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/engine.ps1 demo -Seed 7
pwsh -File scripts/engine.ps1 build
```

独立安装后也可直接执行 `engine\.venv\Scripts\python.exe -m salesbench_engine.scenario --seed 7`，不依赖 PowerShell 包装脚本、Vue、FastAPI、PostgreSQL 或模型 API。

36 项 Engine unittest、原 backend 2 项测试通过。测试覆盖全部要求的正常/失败转移、隐私、回滚、并发库存、时间连续性和同 seed 重现；另验证安装后在仓库外以 Python -I 运行 CLI、代码只导入标准库和自身包。wheel 在全新且只安装 Engine 的环境中从 backend 工作目录导入并跑完整场景成功；打包同时产出 sdist。

seed=7 示例有 1 Supplier、1 Seller、2 Buyer、2 Product；完成 2 次采购、2 个 Listing、调价/更新描述、2 条公开消息、2 条私聊、2 个订单和一次 advance。最终资金（分）：Supplier 800、Seller 2250、Buyer 950、另一 Buyer 1000；库存：cup 2 / bag 1；共 14 个事件。
