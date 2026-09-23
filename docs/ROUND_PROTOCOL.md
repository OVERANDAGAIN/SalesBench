# SalesBench Round Protocol v0.1

任务：SB-PROTOCOL-001；2026-09-23；状态：**建议的可实施 baseline，未经实验验证，不是正式论文协议**。本文件是时间、动作机会、裁决与公开状态的唯一规则正文；真人控制见 [HUMAN_SCHEDULER](HUMAN_SCHEDULER.md)，架构见 [RUNNER_DESIGN](RUNNER_DESIGN.md)，证据见 [RESEARCH_SCHEDULING](RESEARCH_SCHEDULING.md)。

## 1. 当前实现与本协议边界

核对基线 `d3cbc0352d85b1c6a1ca84472265a95f7efe5383`，对应 [ENGINE](ENGINE.md)、[INTERFACES](INTERFACES.md) 和实际 [environment.py](../engine/src/salesbench_engine/environment.py)、[actions.py](../engine/src/salesbench_engine/actions.py)、[models.py](../engine/src/salesbench_engine/models.py)。

当前 Engine 可独立采购、建/改 Listing、发消息、购买、Wait 和显式 advance。单动作成功原子提交，失败不写事件；多个 Listing 共用 `(seller_id, product_id)` 库存。其 `observe(LEADERBOARD)` 每次根据已有订单计算榜单；`snapshot()` 不是 restore 协议，Event 也不是完整重放日志。Policy 当前一次只返回一个 Action。以下窗口、buffer、排名快照、ready 与运行日志**均尚未实现**。

v0.1 在上层串联这些能力，不修改现有即时结算等 TEST 经济规则。Supplier 更新、物流、托管、返款、复杂谈判合约均只有扩展位置，没有虚构对应 Engine API。

## 2. 规范词与不变量

- `benchmark_round` 从 1 开始；一个 Round 是宏观市场机会，包含阶段与至多 K 个 cycle。Action、Event、模型调用和页面点击均不是 Round。
- `phase` 表示协议状态；`interaction_cycle` 在互动期为 1..K，其他阶段为 null。`window_id` 唯一标识一次收集机会，旧窗口动作不能挪到新窗口。
- **同源快照**：竞争者的公共信息取自同一个发布版本，私有信息仍按角色过滤；不要求所有人的观察字节相同。
- **先收集、后裁决、再发布**：模型可以顺序或并发计算，完成早不能提前改变经济状态或看到别人的未提交动作。
- **唯一写者**：只有 Runner 可调用该 Engine 的 execute/advance；平台不得绕过 Runner。
- **批次非事务**：单动作原子，整个 batch 不是全成全败；某个动作业务失败不回滚其他合法成交。内部逐个 execute，整批完毕前不开放中间观察。
- **现实耗时不排序**：窗口内经济优先级不使用 HTTP 时间、模型耗时、线程抢锁顺序或客户端生成的 action ID。跨窗口机会和真人 deadline 仍是协议的显式条件。

## 3. Round 生命周期

| 阶段 | 处理与可见性 | 退出条件 |
| --- | --- | --- |
| `ROUND_START` | 处理预先登记、到期于本 round start 的环境事件；确定参与角色与预算；沿用已发布榜单 L[t-1]；生成起始观察 S[t,0] | 到期事件全部完成或显式失败；不开放半完成环境 |
| `SELLER_PROCURE` | 所有 Seller 基于 S[t,0] 提交采购计划；offer/成本、公共旧价同源，资金/库存私有 | 全部封口或 profile deadline；批量裁决采购 |
| `SELLER_LIST` | 所有 Seller 基于采购统一完成后的同一 epoch，观察各自采购结果/库存，提交建 Listing、改价、描述、停售 | 封口后统一 commit；发布本轮商品目录 C[t] |
| `BUYER_QUERY(c)` | Buyer 浏览并提交 public/private 问询；公开数据来自上次完整发布，询问暂存 | 收集封口；消息合法性由 Engine 判定并进入本 cycle inbox |
| `SELLER_REPLY(c)` | Seller 获得完整、已授权的本 cycle inbox，一次形成有上限的回复 batch | 所有回复 batch 封口；统一执行并发布问询、回复和未回复状态 |
| `BUYER_DECIDE(c)` | Buyer 基于回复发布后的观察提交购买或 Wait；购买仍暂存 | 封口后进入 RESOLVE |
| `CYCLE_RESOLVE(c)` | 确定 seeded 顺序，逐项交 Engine 校验执行；发布购买结果、库存与本人状态 | 完成且 c<K 则 c+1；否则 ROUND_CLOSE |
| `ROUND_CLOSE` | 完成 close hook（当前为空）、记录本轮汇总，生成 L[t]，恰好调用一次 `engine.advance(1)` | 形成完整 close record，评估 termination |
| `PUBLISH_NEXT` | 在同一发布屏障向 Buyer/Seller 生效 L[t]；结束则发布 final，否则进入 t+1 | 所有视图指向同一新 epoch 后才开放下一机会 |

Round Start 的建议到期顺序：上一轮明确标注延迟的环境义务 → 供给更新 → 发布起始观察；同 due-time 再按配置的 event kind priority、稳定 schedule ID 排序，不能靠注册调用时序。**SB-RUNNER-001 只支持空经济 hook**：非空补货/物流配置应拒绝，不直接改 Engine 私有状态。过去未回复的聊天作为历史保留，不自动变成到期经济动作。

Seller Phase 特意分两个屏障：采购成功前无法合法为新库存上架。若将采购与 Listing 放进一次盲计划，需要依赖失败/条件动作规则；若让每个 Seller 采购后立即自由调价，后调用者又会看到先调用者的新价。两步屏障能复用现有 Engine，并保证第二屏障没有人看到本阶段别人的未 commit 新价。

每个 Seller 的计划有固定 slot 顺序，可引用已有公开 offer/product，但不能条件性窥视批内结果再加动作。采购完成后只在下一个正式窗口重新决策。Listing ID 由宿主按场次/Seller/slot 稳定命名空间生成，不能用抢占别人 ID 制造冲突。所有公开价格与描述在 SELLER_LIST 结束时一起生效。

## 4. Interaction Cycle 方案比较与选择

| 方案 | 精确顺序 | 优点 | 代价 |
| --- | --- | --- | --- |
| A：流水式 | Buyer 观察 → 同时提交消息/购买 → 购买 resolve → Seller 汇总回复 → 下一 cycle Buyer 才能利用回复 | 两次收集，允许直接买和问并行；等待少 | 询问需跨 cycle 才能转化；最后 cycle 需增加尾部购买机会，否则新回复无法被使用；K 的含义不直观 |
| **B：询问—回复—决策（推荐）** | Buyer Q → Seller R → Buyer D → purchase resolve | 每个 cycle 都有完整问答后购买机会；最后 cycle 无悬空购买问题；Human/Agent 共用窗口 | 三个窗口，真人会感到短暂等待；不能在同一瞬间既发问又完成购买；不是无限实时聊天 |

“Seller 先回上一 cycle inbox，再 Buyer 同时问/买”是 A 的另一种流水排列，同样需要首尾特殊处理。v0.1 选择 B；若 pilot 发现等待破坏自然体验，再把 A 作为完整注册的 variant 比较，不临时混用。

### 4.1 买方动作机会

Q 阶段每 Buyer 最多 `buyer_action_budget.messages_per_cycle` 条消息，public/private **共用**额度；默认 2。每条占一个固定 slot，目的 Seller 可相同或不同，字数继续受 Engine 的 500 字限制。客户端可连续发送到额度上限，但发送不产生新的观察机会，不能通过反复请求绕开 slot。Q 内其他人的消息不实时公开。

D 阶段每 Buyer 最多 `buyer_action_budget.purchases_per_cycle` 个购买意图；v0.1 支持值为 **1**。这是配置的支持范围约束，不是最终 benchmark 数字；大于 1 需要先定义共享预算与多个商品的偏好顺序，v0.1 明确拒绝。每次购买数量遵守 Engine 合法整数规则，Development 配置再限制为最多 1 件以简化最后库存测试；后续可调数量但仍全量成交或全量拒绝。

同一 cycle 可以先发消息、后购买，并可利用本 cycle 回复；不能一个原子动作既问又买。D 阶段不接收新问题，草稿留至下一 Q，最后 cycle 后留作未发送草稿。无问题者仍保留 D 的购买机会。已用完问询预算不影响购买预算。

`Wait` 表示本窗口放弃剩余动作机会，单独使用；不能与非空 batch 混装。它只封口当前窗口，下一窗口重新给机会。自动 timeout 缺席不会伪造一条本人选择的 Engine Wait。

### 4.2 Seller inbox 与回复

Q 封口后 Runner 按稳定规则调用 Engine 提交消息，给 Seller 的 inbox 包含本 cycle 新消息及必要的授权历史。public 频道可见范围按现有 Engine 保留；private 只给会话双方，不因“汇总”泄露给其他 Seller。Seller 的公共视图同 epoch，自己收到的问询另外组成 `addressed_inbox`。

每个请求由 Runner 的 `request_id` 与 Engine message ID 关联。一次提议一个 reply batch，最多 `seller_action_budget.replies_per_cycle` 条；默认 8，适用于默认 4 Buyer × 2 问询全部集中给一家。每个请求最多一条回复；回复必须引用本窗口自己的请求、频道匹配。公开请求可引用公开回复，私聊请求只能私聊回复；不自动把私聊摘录转公开。当前 Engine 不含 reply-to 字段，这种关联在 Runner envelope/日志中保存。

inbox 不按 HTTP 到达顺序排列：先按 Buyer 的 seeded priority 做 round-robin，再按各 Buyer slot。public/private 不因传输类别获得优先。Seller 可以选择不回某条；R 封口后所有请求终结为 `answered`、`unanswered_budget` 或 `unanswered_no_reply`，不留下无限 pending。预算已经耗尽的遗漏标 budget，其余遗漏标 no_reply；回复动作失败仍保留其 failure code，问题标 no_reply。缺少回复不能伪装成商家说了“拒绝”。模型调用故障与主动不回复严格区分，见 Human Profile。

R 的全部回复完成后一次发布，Buyer 在此之前只知道自己的问询已收件/进入处理。Seller 之间不见同窗口别家的部分回复再改答案；Buyer 不见 token streaming、草稿或先完成的 Seller 回复。新 public/private 信息只在发布屏障进入市场视图。

### 4.3 价格和库存

baseline 只在 Seller Phase 调整报价、描述和在售状态；互动期间拒绝 Procure/CreateListing/UpdateListing。整个 Round 内 Listing 条款冻结，库存与 Buyer 资金则在每次 cycle resolve 后更新。聊天中的价格承诺是文本，不生成折扣合同，支付仍使用 Listing 价格。

D 的 `observation_id` 固定到该 cycle 决策快照，purchase 附 `expected_unit_price_cents`。并发买家看到同样的公开可售量，但看到不代表预留。Runner 不改价凑成交，Engine 在执行时仍校验价格/库存/余额；非预期 PRICE_CHANGED 应报告协议或外部写入异常，不能自动用新价重试。

未来允许 cycle 调价时，合理 variant 是 Seller 在 R 提议价格，于 R→D 发布前一起生效并重新给所有 Buyer 完整 D 机会；另一个 variant 是只在下一 cycle 生效。两者会改变谈判和信息集，必须独立版本化。本轮均不实现，不能在 Buyer 已提交 D 购买后追溯换价。

## 5. 多人竞争与确定性裁决

| 规则 | 特征 | v0.1 判断 |
| --- | --- | --- |
| 固定公开 priority | 易复现，低 ID 长期占先；参与者可据此调整策略 | 不选为 baseline；公开轮换优先可作为 variant |
| seeded random serial priority | 每窗口随机排列参与者，按序执行不可分割订单；与耗时无关 | **Development Baseline**；记录算法与排序输入 |
| allocation lottery | 按单位或配额抽签，可能拆单/按量加权，需定义退款、部分成交和公平单位 | 单件单买家时可等价于随机优先；多件时是不同机制，本轮不实现 |
| 按出价/福利优化分配 | 会改变固定标价市场与买家报告行为 | 留作研究 variant，不擅自引入拍卖 |

### 5.1 规范排序算法

采用 `sha256-priority-v1`，不依赖 Python `hash()`、全局 RNG、线程调度或字典插入顺序。排序键：

```text
key(actor, wave) = SHA256(UTF8(canonical_json([
  "sb-round-v0.1", seed, scenario_id, round_index, phase,
  interaction_cycle_or_null, purpose, wave, stable_actor_key
])))
```

canonical_json 采用 JSON array，UTF-8、无空白、`ensure_ascii=false`、禁止浮点/NaN；数字用十进制整数。stable_actor_key 为宿主预先分配的 ASCII 稳定 roster key，不使用用户可改名称。按 32 字节摘要升序，再按 actor key 升序作极端 hash 碰撞兜底。`purpose` 分开 procurement、listing、purchase、inbox、reply；同 seed 的别处随机调用不能扰动排序。phase 取原收集窗口的枚举字符串（例如 purchase 使用 `BUYER_DECIDE`，不随当前已进入 CYCLE_RESOLVE 而改变）；wave/slot 从 0 开始。runtime session UUID、UTC、receipt ID 不进排序键。保存完整排序候选与最终 permutation；seed 可在场次结束后披露供审计，不给参与者自行挑选身份/seed。

各域对应关系固定为：procurement→SELLER_PROCURE，listing→SELLER_LIST，inbox→BUYER_QUERY，reply→SELLER_REPLY，purchase→BUYER_DECIDE。非互动阶段 cycle=null。消息/回复按 slot 分波，在每 wave 中对发送者做相应域排序；同一 Buyer 的 slot 顺序保持，跨 Seller inbox 是同一已序列化消息批次的授权子集，不重新按到达时间排序。

可供实现自检的向量：seed=7、scenario_id=`dev-small-market`、round=1、phase=`BUYER_DECIDE`、cycle=1、purpose=`purchase`、wave=0 时，buyer_001 的 SHA256 为 `9289ea3ebd50b7828064d46f395d767f265674c9b5b82fc9222b0e028c2c1783`，buyer_002 为 `651cd4d4f5ff137d0434588644c9b7113af32c7a33d4076100a11adeb69d577c`。两人争最后一件且均合法时，buyer_002 先交 Engine，另一人随后 OUT_OF_STOCK；两人的 HTTP 顺序不影响此结果。这是排序向量，不是已经实现 Runner 的运行结果。

Purchase 每 Buyer 一个 slot，**全市场共用一个 permutation** 后依次 `engine.execute`；不能按 listing_id 独立分配，因为不同 Listing 可能共享库存。赢家的成功由 Engine 决定；排前者余额不足或数量过大失败后，后者仍有机会。数量不足不部分成交、不替换商品、不跨 cycle 自动重试。候选只包含当前有效窗口内已 admission 的动作；不在排序前重写经济参数。

采购支持多个 slot：按 wave=slot index，从第 0 个 slot 起每 Seller 至多执行一项，再下一 wave；每 wave 使用各自 seeded priority。这同时处理共用 SupplierOffer 和同 Seller 跨 offer 共享资金。优先 slot 是 Seller 的显式计划，不随结果插入新意图。Listing 操作使用相同按 slot 分波的确定顺序；同一 Seller 对同一 Listing 同批只允许一项创建或更新，避免隐含的“后写覆盖”。

动作非法的经济原因交 Engine；身份、窗口、schema、额度、slot 重复由 Runner 拒绝。phase 收件通过后占 slot，后续业务失败也占预算；重发同 action ID/同内容不占新 slot，同 ID/不同内容冲突。v0.1 收件后的经济意图不可编辑/撤销，UI 必须在提交前确认，并说明统一确认时间；Ready 撤销不会撤销订单。后续若增加 cancel/replace，必须固定 slot、审计版本并保证不能刷 lottery 次数。

### 5.2 谁处理冲突

| 情况 | Runner | Engine |
| --- | --- | --- |
| 最后库存 / 多 Listing 共享池 | 冻结候选、seeded 顺序、统一发布 | 实时验证共享库存、合法数量、原子扣库存/扣款 |
| 观察后意外换价 | 拒绝错 window/snapshot，记录异常，不自动改价 | expected price 校验 |
| Listing 不存在、已停售或不属该 Seller | 检查动作所属阶段；不自行修复实体 | 存在性、权限、active 校验 |
| 多 Seller 抢同 offer | 同源观察、分波排序 | 供给、成本、资金、转移 |
| 重复 HTTP/模型提交 | envelope 幂等、quota、审计状态 | 不承担网络幂等；每次 execute 都是新动作 |
| public/private 同时消息 | inbox 聚合、稳定展示顺序、reply 关联和上限 | 消息权限、频道、文本与会话合法性 |

## 6. Wait、Ready、窗口封口和 Round 结束

| 概念 | 拥有者 | 含义 |
| --- | --- | --- |
| Wait | Agent/明确选择不行动的研究 actor | 当前 opportunity 不行动；必要时交 Engine 留下 waited 事件 |
| Ready | Human 的 Scheduler 状态 | 当前 window 目前操作完成，可在 seal 前撤销；无资金/库存效果 |
| sealed opportunity | Runner | 不能再追加此窗口动作；用于 agent batch final、截止时间或提前关闭 |
| Round Close | Runner 状态机 | K 个完整 cycle 已处理，或注册的终止条件允许在安全边界结束 |

未点击 Ready 也在截止时间封口。全部 Ready 只能提前结束**当前收集窗口**，不能跳过 Seller Reply、Buyer Decide 或剩余 cycles。Agent Wait 不等于 Human Ready，也不等于本人退出 episode。

Agent 的 batch 带显式 final 元数据，非空 batch 也可 final；空 final 表示不再补动作，不必伪造 Engine Wait。只有显式 Wait 才调用 Engine 留 waited 事件。预算为 0 或本窗口无可回复请求的角色不加入 required actors；不得等待一个根本没有行动机会的角色。Human Ready 和 Agent final 只供 Scheduler 控制，不公开为对手观察。

baseline 不因“大家这次 Wait”提前终止 Round：未来 cycle 仍可能产生问询/购买。提前结束 episode 的研究条件仅在 Round Close 检查；技术中止有单独状态。Human 细节以 [HUMAN_SCHEDULER](HUMAN_SCHEDULER.md) 为准。

## 7. 排行榜与信息发布

定义 `L[t]` 为 **Round t close 后形成**的 leaderboard snapshot，`as_of_round=t`、`effective_round=t+1`、`snapshot_id` 与计算规则版本唯一；Round 1 使用初始化 L[0]。Round t 中所有角色看到 L[t-1]，Round Start 不重新计算成另一个不同榜单。起始环境变化可以影响 offer/catalog，但不能偷偷刷新本轮排名。

close 后新榜单在 PUBLISH_NEXT 一起生效；“同时”指服务端 epoch 同时切换，不承诺网络包到达同一毫秒。开放下一窗口前缓存旧榜单失效；每个响应返回 snapshot_id 防止跨版本拼接。最后一轮结束也发布 L[T]，此时标记 `final=true`，不意味着实际存在可行动的 T+1。

snapshot 保存配置化 `metric_definitions`、`rule_version`、每 Seller 的 `current_rank` 和 `previous_rank`；L[t] 的 previous 指 L[t-1]。L[0] previous=null，初始化排序仅开发展示；相同名次/并列规则随 ranking rule 记录。缺失指标用 null/未启用，不能当 0。Engine 的 TEST gross sales/units 只作开发占位，不是正式利润或奖励。

允许配置的候选指标包括成交额、销量、已实现利润、履约或关系指标，但后几项需要相应状态/定义后才能启用；不能从当前余额差自动声称算出了长期利润。Round 内本人余额、订单、cycle 库存和屏障消息正常更新，冻结的是排行榜，不是整个市场。

H5 文案：“本阶段榜单保持不变，下一阶段更新”；切换后可显示“榜单已更新”。研究元数据不要求作为主界面术语显示。未来实时榜单 variant 会引入早期成交→曝光/跟随→后续成交的反馈、观察刷新频率差异、位次锚定及策略性等待；需要明确刷新节奏并与冻结 baseline 对照。本轮不实现该 variant，也不默认排名驱动推荐顺序。

## 8. 时间模型与 Engine step

| 时间 | 用途 | 不用于 |
| --- | --- | --- |
| benchmark_round | 宏观机会、跨期指标与 episode horizon | 现实日期、模型调用计数 |
| phase / interaction_cycle / window_id | 行动权限、信息屏障、Ready scope | 自动经济估值 |
| event_seq | Runner 已确定的语义事件顺序，场次内单调，包含拒绝/timeout/phase | 库存优先级或用户速度排名 |
| recorded_at（UTC） | 收件、运维、真实等待时间分析 | baseline 经济排序 |
| deadline / monotonic clock | 服务端收件截止与活性保障；UI 倒计时 | 模拟 day |
| engine.step | 现有内部逻辑 tick，与 Engine 记录兼容 | Human UI 主标签 |

v0.1 新 episode 从 engine.step=0 开始；Round t 内 step=t-1，Close 恰好 advance(1)，因此 close 后 step=t。最后一轮也 advance 一次；Close 的 time_advanced 事件仍归属刚关闭的 round，保存 step_before/after 避免 off-by-one。不在每条消息、phase 或 cycle advance。此一一映射是 adapter 约定，不是永久领域定律。

以后有物流/结算再定义更细 internal ticks，显式记录 round→tick range 和事件到期边界；不能默认 tick=day。Development 配置不启用 `steps_per_demo_day`。

两种日志分开：receipt 收件流水按实际顺序记录，带 ingress_seq/UTC；`event_seq` 的市场语义日志在屏障处按规范顺序写入。不能拿到达序号重排 batch。同一配置、初始状态、seed、稳定身份和**同一 admitted action/control transcript**必须重现状态与语义日志（排除 UTC/耗时）。同一 seed 不保证真人决策或 LLM 输出重复；改变 deadline 使动作漏窗也不属于“同一输入”。

## 9. 配置、Development Default 与 pilot

下面是开发夹具，不是正式 benchmark 参数；episode 启动后配置冻结、记录 hash。

```yaml
protocol_version: sb-round-v0.1
profile: scripted                 # human-mixed 见 HUMAN_SCHEDULER
scenario_id: dev-small-market
seed: 7
max_rounds: 3
max_interaction_cycles: 3
buyer_action_budget:
  messages_per_cycle: 2           # 公私聊总和
  purchases_per_cycle: 1          # v0.1 只支持 1
  max_units_per_purchase: 1       # 开发数量限制，可配置
seller_action_budget:
  procurements_per_round: 2
  listing_mutations_per_round: 4
  replies_per_cycle: 8
round_timeout: null              # scripted 不用真实时间决定经济机会
human_timeout: null
tie_break: sha256-priority-v1
ranking_rule: test_gross_sales
environment_updates: none
early_economic_termination: disabled
```

开发市场建议 1 Supplier、2 Seller、4 Buyer、少量 product，包含两个 Listing 共享库存的专门场景。scripted 直接推进屏障，不 sleep；fake clock 测试 timer。max_rounds、K、数量上限为正整数；消息/采购/Listing/回复预算为非负整数，0 表示没有该类机会，purchase budget 在 v0.1 必须为 1；seed 为整数，禁止 bool 冒充数值。金额沿用整数分；token/模型调用预算是未来 Policy adapter 的配置，不能偷换成经济 action budget。Skeleton 不调用 LLM。

K=3 可覆盖初次询问、后续澄清、最后决策，并能快速手查全部轨迹；不是文献证明的最优值。pilot 分别改变 K（例如 1/3/5）、问询额度、Seller 回复容量、窗口时长与市场拥挤程度，记录最后窗口仍有草稿/未满足问询比例、每 cycle 新信息与成交、timeout、阅读时间、疲劳和成交/利润轨迹。按 Human/Agent 分层，固定其他参数并重复种子；观察边际改善与截断率，再预注册正式参数和样本量。不能看哪一组最利于某模型就定参。

## 10. Episode 结束与指标准备

- **默认**：完成 max_rounds 后正常结束，执行最后 Close 与 final publication。
- **市场无法继续**：需证明没有可售/可补给资源、未完成义务或未来到期事件能恢复交易；一次无成交、余额低或全部 Wait 均不足以证明。v0.1 默认关闭自动检测，暴露明确配置的 termination predicate。
- **目标完成**：仅在任务预先定义主要目标且目标完成谓词获确认时开启；本轮不发明消费者效用/需求目标。
- **其他自然终止**：角色退出、所有关键参与者缺失、资源耗尽可预注册成 profile 条件；与基础设施故障/人工停止分开。
- **技术中止**：异常、模型/平台不可用、round watchdog 为 `truncated`/`failed`，保留已发生交易和未 resolve 意图，不伪装正常完成或插入自动购买。

close 记录初始/期末资金和库存、采购/订单数量与成交单价、成本来源、成功/失败/缺席、消息与 reply 关系、公开快照和观察机会、各轮资源状态、termination reason。采购与销售批次成本归属尚未定义，保留原始账务事实供以后选择成本核算；关系指标保留伪名 Buyer–Seller 连接与消息/复购序列，不在此定义“信任得分”。未来税费、退款、物流和奖励未实现时不能从缺失字段推算正式分数。
