# Market Wave Runner — SB-RUNNER-001

2026-09-24，当前 `salesbench-engine` **0.2.1**。Runner 位于 `engine/src/salesbench_engine/runner/`，与 Engine 同一个独立 Python 包，零第三方运行时依赖。无需 Vue、FastAPI、数据库或真实模型服务。LLM-first 指协议直接面向模型的冻结观察和结构化批次；不表示已经接入正式模型/策略。

SB-PLATFORM-001 将包升级至 **0.2.1**，只增加下面的可信宿主步进与恢复契约。本文的研究语义、排序、批次失败传播和版本规则不变。平台持久保证见 [PLATFORM.md](PLATFORM.md)，不归独立 Runner 内存缓存承担。

## 可信宿主边界（0.2.1）

- `next_boundary` 返回下一 Wave 或 Round close；`pending_observations()` 从当前发布构造该机会的授权观察，不执行、不追加日志。只供宿主按 actor 过滤，不能把整张映射给参与者。
- `await advance_boundary()` 只执行一个原有 Wave 或 Round close。与完整 `run()` 使用同一执行路径，不增加 micro-wave；busy/terminal 对象拒绝重入。`run()` 仍是一次完整运行入口，逐边界宿主不要混用它。
- `restore_committed(records, drivers)` 从初始 setup + 记录的动作恢复全新 Runner，核对 source/protocol/rules、连续序号与全部逻辑记录；接受初始发布、正常 Wave/close、completed、可核对的已记录失败边界，拒绝未完成的日志后缀。返回对象可继续下一个边界；失败/完成对象不可续跑。
- 恢复保留原有时间戳/transport 审计前缀；只有核对完成后才绑定下一机会的 Driver。恢复不调用模型，不从 snapshot 反序列化内部状态。源码摘要不同需要对应历史代码，数据库 migration 不会自动升级实验 trace。
- `advance_boundary()` 形成的内存发布只是宿主候选。平台在 DB 事务提交 journal、回执、授权 projection/outbox 后才对外可见；提交失败丢弃候选，从 committed transcript 重新构造。

## 职责与时间

Engine 裁决资金、库存、报价、权限、订单和单动作原子性。Runner 只管理机会、观察、批次、顺序、发布与审计。Driver 只提出意图，不能得到 Engine 或宿主全量 snapshot。可信 Python Driver 不是恶意代码沙箱；提供给外部模型的是经过授权的序列化观察。

```text
Round 1 (Engine step = 0)
  ROUND_PROCUREMENT：每 Seller 一次 Procure 或 Wait → publish
  Tick 1：SELLER_STRATEGY → publish → BUYER_ACTION → publish
  Tick 2：SELLER_STRATEGY → publish → BUYER_ACTION → publish
  ...固定 K 个 Tick...
  close / 统计 → Engine.advance(1) → publish
Round 2 (Engine step = 1)
  ...
max_rounds 正常结束 (Engine step = max_rounds)
```

一个 Tick 是一组已配置的 Wave，不是一个 actor 动作，也不是现实分钟。一个 Wave 给该角色的每位 actor 一次机会；一个机会可以提交有限的有序动作批次。所有人 wait 仍运行到固定终点。Round 内的采购、所有 Tick/Wave/动作均不 advance；异常 Round 不 close、不 advance。Runner 拒绝 `steps_per_demo_day`，不引入 wall-clock 经济时间。

Round/Tick 编号从 1 开始；采购使用 tick=0。初始发布版本为 0，正常 Wave 和 Round close 各产生下一 published version。Engine Event/Order 仍记录 step；精确 round/tick/wave/action 关系由 journal 保存，不能只用 Engine step 区分同 Round 消息。

生命周期为 `created → collecting → executing → publishing`，按配置重复；Round 末进入 `closing_round`，最终 `completed` 或 `failed`。Runner 单次使用，不能重入、续跑失败对象或自动重试。`run()` 返回宿主状态；调用方必须检查 `phase`，失败细节在 journal。CLI 失败返回非零。

## 模块

| 文件 | 职责 |
| --- | --- |
| `protocol.py` | Round/Tick/Wave context、配置、不可变观察、公开投影和 outcome |
| `scheduler.py` | 数据驱动 Wave 循环、并发收集、执行/发布边界、确定性优先级 |
| `codec.py` | 严格批次解码、动作 schema 描述、规范 JSON/SHA-256、setup 重建 |
| `drivers.py` | ScriptedDriver、LLMDriver、ModelAdapter、模型请求与 token 预算 |
| `journal.py` | 宿主审计、状态变化摘要、加锁的进程内动作去重 |
| `replay.py` | 从初始 setup 重跑记录意图，核对观察、裁决、结果和状态 |
| `recovery.py` | 校验 committed prefix，恢复下一边界游标、发布、幂等及记录前缀 |
| `demo.py` | 3 Seller / 4 Buyer 的小型确定性 CLI，不是正式 API |

Wave 定义包含名称、角色、动作集合、批次/消息/purchase 预算。调度循环遍历配置，不为每一 Tick 手写两套流程；V1 校验只接受 `SELLER_STRATEGY → BUYER_ACTION` 两种已实现 Wave，预算可配置。以后增加 conversation micro-wave 要显式扩展协议、能力与验证；本版不接受未支持序列。

## 冻结观察与发布

每个 Wave 开始前，从上一个正常发布构造全部 `DecisionObservation`，在任何 Driver 调用前记录。包含 context、稳定 opportunity ID、Wave 动作预算、共享的不可变 `PublicSnapshot`、本 actor 的 self/inbox 观察、上次机会 outcome；采购阶段另加 Seller 供应商观察。

PublicSnapshot 仅含版本、Engine time、Seller 公开身份、在售 ListingView 和公开消息。它不含任何账户、内部成本、私聊、订单、采购或宿主全量事件。private 部分通过 `Engine.observe(actor, SELF/PRIVATE/SUPPLIERS)` 取得，不拼装绕过 Engine 权限。供应商报价只在采购机会提供给 Seller；不提供给 Buyer。排行榜观察关闭。

同 Seller Wave 的公共投影为同一版本、同一不可变对象；Buyer Wave 同理。各自余额、库存、订单、会话和私聊互不串用。模型请求只序列化绑定 actor 的观察，身份不由模型返回的动作控制。

全部 Driver 返回后才开始执行。执行期间，actor-facing `Runner.observe(actor)` 始终返回旧的 published state；全部正常执行/业务失败处理完成后，先构造完整投影，再整体替换。Seller 本 Tick 改价/上下架/描述和消息因此对同 Tick Buyer 生效；Buyer 本 Wave 消息对下一次相关 Wave 生效。批次内没有重新 observe，回复不会自动变成 conversation micro-wave。

`economic_state()`、journal、内部 Engine 都是可信宿主审计边界，不得给 actor。发布不是数据库事务；异常执行后真实内存可能有成功前缀，actor 仍看到上一个发布，任务停止。

## 动作批次与失败

模型输出为 `{"actions":[{"type":"wait"}]}` 形式的严格 JSON。禁止多余字段、重复 JSON key、actor 身份字段、错误标量类型；bool 不能代替整数。整个批次先做结构/角色/预算校验，再交 Engine 做业务检查。

| Wave | V1 动作与默认上限 |
| --- | --- |
| Round procurement | 1 个 Procure 或 Wait；每 Seller 每 Round 仅一次，无自动补货 |
| Seller strategy | 最多 3 个：创建 Listing、改价/描述/active、公开/私聊；消息最多 2；或单独 Wait |
| Buyer action | 最多 3 个：公开/私聊最多 2；至多 1 笔 Purchase 且必须末尾；或单独 Wait |

空批次、混用 Wait、采购进入 Tick、purchase 非末尾/多笔等都整批 invalid，消耗本次机会，其他 actor 继续。合法形状但无库存/无资金/对象不存在等由 Engine 返回 business failure。为了消除同名创建的先后优势，Runner 新 Listing ID 必须是 `actor_id/local-name`，local-name 非空且不含 `/`；Engine 单独使用时保留原有 ID 契约。

**V1 business failure：保留本 actor 已成功前缀，停止该批次，所有后续动作逐项记录 `skipped` 和 `PRIOR_BUSINESS_FAILURE:<action_id>:<code>`。其他 actor 继续。** Buyer 前置消息失败会连带跳过末尾 purchase；后续 purchase 失败不会撤销已经发送的消息。该失败传播语义后续需正式确认，见 Known Issues；本任务不重新设计。

采购/Seller 按确定性 actor 顺序执行，各 actor 内保持批次顺序。Buyer 先执行各批次的非 purchase 前缀，再汇总所有未被 skipped 的末尾 purchase，统一裁决。一次购买全量成功或全量失败，没有部分成交/替代商品。

## 购买优先级与报价版本

裁决算法 `sha256-actor-v1`：对 UTF-8 canonical JSON（排序键、无多余空格、保留 Unicode）做 SHA-256，按摘要升序，极端摘要碰撞按 actor ID 升序。输入严格为 algorithm、purpose、resolution_seed、稳定 design_id、round、tick、wave、actor_id。purpose 分为 procurement / seller_actions / buyer_messages / purchase。

购买使用整个 Buyer Wave 的一个顺序，不按 Listing 单独排序；不同 Listing 共享 Seller/Product 库存时仍由同一个顺序交给 Engine，失败候选不阻止下一位。日志保存 purpose、输入上下文、每个 actor 摘要和最终顺序。不能加入 action ID、模型参数、调用/HTTP 顺序、耗时、Python `hash()` 或临时 session UUID。稳定 actor ID/design_id 是实验配置的一部分，配对比较时必须固定。

Engine Listing 的 `offer_revision` 和 `content_revision` 初值为 1。改售价或 active 的实际值使 offer revision 加一；同动作同时改两者只加一。描述实际改变使 content revision 加一。重复赋相同值不增版本；采购/销售/其他 Listing 共享库存变化不增 offer revision。停售再上架、改价再改回也会留下新版本。

Purchase 必须提供 listing_id、quantity、expected_unit_price_cents、expected_offer_revision。Engine 在合法输入和对象存在后按价格→报价版本→active 检查，分别返回 PRICE_CHANGED / STALE_LISTING / LISTING_INACTIVE，随后检查库存/余额。成交 Order 记录实际 offer_revision。描述更新不使报价过期。这是包 0.2.0 对旧 Python Purchase 构造器的显式不兼容更新，旧 scenario/tests 已迁移；未修改 Vue 草案。

## Driver、配置与故障

市场配置和模型运行配置独立：

| 配置 | 内容 |
| --- | --- |
| MarketSetup / Experiment | 市场初始数据、market seed、固定角色 ID |
| MarketConfig | 稳定 design_id、resolution_seed、max_rounds=2、ticks_per_round=3、Wave 预算 |
| RuntimeConfig | concurrency=8、timeout_seconds=30，仅控制调用；不影响优先级 |
| 每个 LLMDriver 的 ModelSettings | 显式 provider/model、input token 上限 16000、output 上限 1024、temperature=0 |

`Driver.decide(DecisionObservation) -> await DriverReply`。ScriptedDriver 使用固定函数产生结构化意图，经过与模型相同的 JSON 校验链。LLMDriver 构造系统约束、授权 observation 和动作字段 schema，调用注入的 `ModelAdapter.count_input_tokens(request)` / `await generate(request)`，检查输入/输出预算，记录原文、可用模型版本和 token 使用。schema 是 provider-independent 字段描述，不宣称是某家 API 的 JSON Schema。

Adapter 负责 provider SDK/HTTP、准确输入 token 计数、落实输出上限、异步 I/O 和取消；凭据留在 adapter 内，不进入配置或 journal。模型 SDK/实际 provider adapter、本地/远程模型服务均未在本轮安装或接入。模型文本本身可能非确定性，**重放固定记录的动作，不重新调用模型**。更改 provider 导致动作变了当然可能改变市场；速度/并发度不影响相同意图的裁决。

调用使用 semaphore + 每次实际开始调用后的 timeout（排队时间不计入调用 timeout）。所有调用收集后才执行；没有自动重试、静默 fallback 或自动补 Wait。

| 情况 | 处理 |
| --- | --- |
| 显式 Wait | 正常策略动作，记录 Engine waited event，不推进时间 |
| 不合法模型 JSON/批次 | invalid_batch，本 actor 消耗机会，其他 actor 继续，正常发布 |
| provider exception、timeout、token budget 超限 | 技术失败，整 Wave 不执行，终止；保留此前正常 Wave |
| Engine 意外异常 | 保留已提交动作前缀，记录故障 action ID/异常类型/状态摘要，不发布当前 Wave，终止 |
| 宿主取消 run | 取消并等待未完成调用清理，标记 terminal failed；不自动继续 |

任意异常字符串可能含认证信息，因此只记录异常类型，原始模型输出照录。异步 adapter 必须合作取消且不能阻塞事件循环；当前没有子进程级强制终止不合作 Driver 的隔离器。

## 幂等、journal 与 replay

opportunity ID 由稳定 design_id/experiment_id/context/actor 的规范摘要产生，action ID 再附批次索引。这些 ID **只用于身份/幂等，不参与购买排序**。ActionExecutor 使用锁覆盖查重、Engine.execute 与结果缓存；同 ID + 相同 actor/context/action 返回缓存结果，不再执行；不同内容抛 `ACTION_ID_CONFLICT`。成功和业务失败均缓存。未执行的 skipped/invalid 由机会记录表达，单次 Runner 不重新开放机会。不是数据库/跨进程幂等。

Journal 保存初始 setup、市场/运行/模型配置、协议/规则/源码摘要；每份实际授权 observation；raw output、模型元数据、token 和诊断耗时；批次 admission 与动作 ID；resolution 顺序；每次 action attempt/result/events、改变的状态表及完整状态摘要；skipped、发布、Round 统计、结束/故障边界。时间戳只供诊断。Journal 全量包含私有数据，只供宿主，不上传 Git、不广播参与者。默认内存存储，只有显式 `--journal` 才写文件。

Replay 从 manifest 的初始 setup 创建全新 Engine，用记录的输出恢复结构化意图，重新执行观察生成、批次校验、排序、Engine 裁决、发布/advance，并核对逻辑记录与经济状态。无需模型，也不直接恢复终态 snapshot。诊断时间和 transport 元数据不参与经济对比；改变动作/裁决/状态记录会被发现。源码/协议摘要不符直接拒绝，需要检出对应代码版本。

正常运行和 collection failure trace 可重放；已记录 Engine action fault 可在故障动作之前按记录中止，核对成功前缀，**不是重新制造该实现 bug**。取消过程中缺失的 response、日志损坏、进程崩溃、非 action 阶段实现异常不保证重放，遇到不一致失败关闭；不伪造完成记录。Journal 是可核对的审计材料，不是有签名的防篡改证据，也不是 durable WAL/crash recovery。

## 运行

在项目根目录（先按 ENVIRONMENT 配好本机工具与 `.local/`）：

```powershell
pwsh -File scripts/engine.ps1 install
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/engine.ps1 runner-demo -Seed 7 -ResolutionSeed 7 -JournalPath .local/wave-trace.json
pwsh -File scripts/engine.ps1 replay -JournalPath .local/wave-trace.json
pwsh -File scripts/engine.ps1 build
```

独立已安装包：`python -m salesbench_engine.runner.demo --journal trace.json`；重放用 `--replay trace.json`。示例固定 3 Seller、4 Buyer、2 Product、2 Round、每 Round 3 Tick；每 Round 采购，首 Tick 的 4 Buyer 争购 seller-1 的最后一件 cup，下一 Tick Seller 改价/描述并回复。CLI 打印结构化 Wave/purchase/order 轨迹和 state digest；用于 smoke，不冻结研究策略。

## 当前平台边界与 Known Issues / Protocol Debt

- **失败传播语义后续需正式确认**：V1 保留前缀、业务失败跳过尾部，可能令一条失败消息阻止购买；当前明确实现此规则，不将其宣称为永久研究协议。
- TEST 经济规则仍为即时采购交货/付款、即时全额收款、有限供给、共享库存，无物流/退款/佣金/税。正式消费者、Seller 策略、排行榜/奖励、真实时间尺度、供给再生尚未定义。
- 无 HumanDriver、conversation micro-wave、真实 provider 集成；冻结观察和批次上限已经保留扩展点，未实现能力会拒绝而非猜测。
- 单进程单写者，journal/cache/发布均为内存。全量历史观察与状态表 delta 的存储成本随运行增长；LLM 输入超限终止，不静默截断。面向小型实验，未进行大规模吞吐/成本测试。
- Engine 与 Runner 两层原子性不同：单动作原子；Wave 正常完成才发布但不是整 Wave 回滚事务。异常前缀需要宿主处理，不能把旧发布状态当成当前内部经济状态。
- FastAPI 当前通过 MarketService 创建/恢复候选 Runner，绑定 actor/session，提交后输出授权 projection；路由不得直接 execute 绕开 Wave 或按 HTTP 先后裁决。
- Vue 已通过 sb-platform-v1 映射 Listing、三种版本、逻辑 step、opportunity/批次/receipt 与私有投影。历史 v0.1 演示契约仅供对照，见 INTERFACES.md。
- 独立 Runner 不承担持久幂等/数据库事务。SB-PLATFORM-001 已在 application 层实现这些能力，见 PLATFORM.md；Vue Buyer/Seller 已完成真实 E2E，真实模型仍未接入。
