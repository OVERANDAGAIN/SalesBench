# Human Scheduler Profile v0.1

SB-PROTOCOL-001 / 2026-09-23。**设计建议，待可用性 pilot；本轮不改 H5、不实施被试管理。** 经济时序继承 [ROUND_PROTOCOL](ROUND_PROTOCOL.md)，Human 与 Agent 共用同一信息屏障和购买裁决。这里仅定义现实时间、操作完成、断线与提示。

## 1. 真人看到的市场活动

保留现有五页与顺序：排行榜、商品推荐、公共交流、私聊、我的；保留购买/暂不购买路径。顶部增加“当前市场阶段 · 剩余时间”，适用阶段放弱化按钮“本阶段操作完成”。不以 Round/Cycle 编号、End Round 按钮或新 Seller/Agent 后台作为体验主体。

| 协议状态 | H5 建议表达 | 可做的事 |
| --- | --- | --- |
| Seller Phase | “商家正在准备商品” | 查看已发布内容、编辑本地草稿 |
| BUYER_QUERY | “浏览与咨询 · 还剩 00:45” | 浏览、切换五页、有限问询；购买入口说明“回复整理后开放购买” |
| SELLER_REPLY | “商家正在整理回复 · 最多 00:20” | 浏览历史、编辑草稿；显示自己的问询状态 |
| BUYER_DECIDE | “查看回复与选购 · 还剩 00:30” | 查看统一发布的新消息、提交一次购买或暂不购买 |
| CYCLE_RESOLVE / Close | “正在确认本阶段结果” | 查看旧快照和本人 pending receipt，经济提交暂不可用 |
| Episode ended | “本次市场活动已结束” | 查看已授权结果，保留草稿但不自动发送 |

这是分段的自然市场活动，不宣称无限实时聊天。参加者需要知道“咨询后查看回复，再选购”和购买统一确认，不能为了弱化术语而隐瞒延迟执行。等待是否过长是 pilot 的主要检验点。

H5 五页共享一个服务器 deadline，切页不重新计时。可显示剩余问询额度的小提示，不增加复杂研究面板。网络错误明确报错，不回退本地模拟。购买 receipt 为 buffered 时显示“已提交，阶段结束后确认”；不预扣款、不保证库存、不显示购买成功。

## 2. Ready 的作用域和替代方案

Human **不必**点击 Ready。未点击者到 deadline 仍封口，已收件动作正常进入 batch，剩余额度自然闲置。Ready 是 `window_id + actor_id + visible_epoch` 上的状态，不是全 Round 的“我退出了”，也不产生 Engine Action。

| 方案 | 新信息后的行为 | 取舍 |
| --- | --- | --- |
| Ready 后硬锁 | 禁止回来，回复到达也不恢复 | 容易因误触或新回复剥夺机会，不推荐 |
| 只提醒、保持 Ready | 提示“有新信息”，用户手动撤销 | 可能在用户阅读前被全部 Ready 条件关闭 |
| **可撤销，相关新信息使旧 Ready 失效** | 恢复 active，并提示“有新信息，可以继续操作” | 推荐；需要把状态绑定信息版本，避免重复推送反复失效 |

baseline 中新研究信息只在窗口边界发布：Q 的 Ready 不继承到 D；每个新 Q/D 都 active，即使本人没收到私聊也有新的机会。R→D 回复发布后所有需要决策的 Buyer 重开完整 D 时间。公开回复对本场 Buyer 均为相关信息；私聊只影响当事人，不能通过别人的 Ready 变化泄漏私聊存在。

同一开放窗口内不会合法追加新卖方回复；重复通知/相同 epoch、单纯倒计时和 Ready 回执不使 Ready 失效。若故障恢复导致必须发布不同的经济快照，不能一边沿用原 Ready 一边照常结算：在任何新经济提交前重新签发窗口，作废旧 Ready 并给共同阅读机会；若该窗口已有待裁决购买，按故障路径中止并审计，不能静默丢弃或换价。该恢复路径留 Milestone B/C，Skeleton 测试拒绝意外 epoch 漂移。

### 2.1 撤销和操作

- window 尚未 seal，用户可点“继续操作”撤销 Ready；收到的撤销成功回执才表示生效。
- 提交新的合法经济动作会在同一收件操作里撤销本人的 Ready；已封口后返回 WINDOW_CLOSED，不挪到下一 window。
- Ready 与撤销使用控制请求 ID 幂等，与经济动作预算分开。多标签页共享服务端状态，用控制版本避免旧 Ready 覆盖新 unready。
- 已 admission 的经济意图不可编辑/撤销，Ready 撤销只恢复剩余机会。购买额已用完可继续查看，但不能追加一单。
- “暂不购买”保持既有 UI 反馈，不自动等于 Ready。只有明确“本阶段操作完成”才放弃等待剩余额度；Agent 的 Wait 则是另一种显式研究动作。

## 3. 提前结束与待回复条件

提前结束的是一个**收集窗口**。Q/D 的推荐条件：

```text
window_open
AND minimum_open_duration_elapsed
AND every_required_human_ready_for_current_epoch
AND every_required_agent_batch_final
AND no_admission_command_in_progress
AND no_undelivered_information_required_for_this_decision_window
```

seal、检查条件和收件在单写者下串行化；最后一个 Ready 与新动作/撤销竞争的结果要给明确回执。已到服务端但尚未处理的控制命令不能被无记录地越过；关闭事件保留 cutoff。客户端时钟、HTTP 请求开始时间不决定有效性，服务端 admission 边界决定是否落窗。

**避免 pending 死锁**：Q 封口用于把本窗口问题交给 Seller；“已有问询待回复”不是阻止 Q→R 的条件。它阻止的是跳过 R 直接关闭整个互动阶段/进入 Close。只有 R 将所有请求标为 answered 或明确未回复后，才开放 D；任何人 Q 时 Ready 都不能跳过 D。R 没有 Human Buyer Ready 条件。

R 可以在所有 Seller batch final 后提早发布，但必须全 Seller 一起；空 inbox 的 Seller 没有必须调用模型的任务。若本 cycle 所有 inbox 都空，直接形成空回复批次，仍开放完整 D。Seller 主动 Wait/不回复可形成 `unanswered_no_reply`；一次模型超时不是主动 Wait。

未 Ready 者仍在截止时间封口。即使所有人 Ready，也不跳过之后的 cycle，不因已经购买过就永久排除 Buyer。是否有“需求完成即退出”须另定消费者目标。

## 4. Timer 与默认 profile

比较：仅 Round timer 无法保证最后问题有回复和购买时间；仅按个人页面计时会造成不同观察截止。推荐**服务端共同的 Q/R/D 窗口 timer，加 round watchdog**。cycle 是后台实现概念，用户看自然阶段名称，不必看编号。

Development Human Mixed 示例（只用于工程试跑）：

```yaml
profile: human-mixed
human_timeout:
  query_seconds: 45
  decide_seconds: 30
  minimum_open_seconds: 5
scheduler_timeout:
  seller_procure_seconds: 15
  seller_list_seconds: 15
  seller_reply_seconds: 20
round_timeout: 360                # 运维 watchdog，非正常经济截止
agent_timeout_policy: truncate_session
human_timeout_policy: seal_submitted_only
ready_required: false
```

K=3 时正常窗口上限合计 `15+15+3×(45+20+30)=315 秒`，watchdog 留出发布与控制开销。不是正式实验时长；真实模型和阅读速度必须通过 pilot 调整。scripted profile 不等待这些现实秒数；Skeleton 的 Human 路径用 fake clock 验证。

服务端用 monotonic clock 判定进程内期限，持久化 UTC deadline 供重连/恢复与展示。客户端只显示近似倒计时，重新连上校准，不延长服务器期限。平台 B/C 需要专门恢复策略，不能进程重启后直接再送一整段时间。

### 4.1 到期时各种输入的归属

| 到期时状态 | 处理 |
| --- | --- |
| 尚未发送的消息、数量、购买表单 | 留作客户端草稿，不提交、不扣款；标“本阶段已结束，内容尚未发送” |
| 已 admission 的消息 | Q 后正常送本轮 R，Seller 即使还没开始回复也有完整 R 时间 |
| 已 admission 的 purchase | D 后统一 resolve；HTTP 客户端超时不撤销经济意图，按原 action ID 查询 |
| 请求在途、服务端尚未 admission | 截止后明确 WINDOW_CLOSED；若结果未知先查 receipt，不能换 ID 再买 |
| Seller 正在推理 | 截止前只缓冲完整合法 batch；不公开 streaming，不让部分回复抢先影响购买 |
| 迟到的模型结果 | 标 late/discarded，不移入新窗口；取消请求不保证提供者立刻停止，仍需 window token 拒收 |

Q deadline 不是 seller reply deadline。最后 cycle 的 Q 也有 R 和 D，正常情况下不会留下“已回答却没机会买”的尾巴。Seller 选择遗漏的问题在 R 终结，UI 可显示“本阶段未收到回复”，下一 Q 可用新 slot 追问；不无限保留 pending，也不自动占用下轮问询预算。

## 5. Human 与 Agent 同场

1. 相同角色获得同窗口 epoch 和相同经济动作预算。Agent 可以早结束推理，但到 batch barrier 才 commit；Human 也不会因为早点购买而预留库存。
2. Agent 只能看到其当前授权快照，不提前拿到 R 的草稿、其他人的 buffered 意图或新 cycle 的状态；D 购买决策不能在看到 Q 快照时预提交一个“将来自动买”的命令。
3. Agent final batch 提交后不能因为还有几秒就重复采样重选；跨 actor 并发只是计算优化。未来模型 token、调用数和重试预算另行冻结并记录，不能按跑得快给更多观察或经济 slot。
4. Offline agent benchmark 等齐已完成结果再 resolve；技术 watchdog 失败为 truncated，不将慢模型变成市场中的 loser。
5. Human mixed 有真实 deadline，无法声称完全没有时间压力。为避免模型 API 慢导致某一家 Seller 被当成没回复，baseline 使用保守 deadline；**任何必须的 Agent 调用到期仍未 final，整场标技术中止，不继续正常计分**。保留历史，不追溯取消已完成 cycle。可另设计全体统一暂停/延长的 profile，但不能在运行中只照顾某个 actor。
6. 模型按时返回非法经济意图是行为失败，照常记录/消耗预算；网络/API 失败、提供者不可用与脚本缺陷是基础设施/适配失败。显式记录分类，不把其中一类悄悄变成 Wait。

这种设计消除的是窗口内“快者先拿库存/先展示回复”，不是认知速度、网络漏窗、窗口长度等全部差异。报告 Human/Agent 比较时应同时报告这些截断和缺席指标。

## 6. 断线与无操作

- 连接中断不代表 Ready，不删参与者，不替他买、不自动让 Agent 接管。
- 已收件动作仍有效；未收件动作不生成。deadline 后记录 `human_timeout`、本窗口是否零动作及断线迹象，不编造主动 Wait。
- 默认固定 roster；单个长期无操作者每窗口自然 timeout，其他人最多等待既定期限，不永久卡住。其余额/库存保留，后续重连可在当前窗口剩余机会内参与。
- 重连先获取当前 phase/window/epoch、剩余预算、本人 Ready、未完成 receipt、授权消息和账户/订单；再接增量通知。过期草稿只提示，不自动重发。
- baseline 不根据浏览器心跳猜测“经济目标已经完成”，也不把临时离线直接剔除分母。永久退出和数据排除规则属于后续被试研究方案。
- 若全体 Human 在一个完整 Round 都没有有效活动，记录运维警示；v0.1 仍由 max_rounds 限制总时长。自动按缺席提前结束需显式 profile；操作者停止标 `truncated/operator_stop`，不是自然成功。

本轮不建设登录、同意页或被试名单系统。未来这些外部流程只向 Runner 提供已绑定的 participant→actor 映射。

## 7. Human Profile 必须验证的情形

Ready→撤销；Ready→新合法动作；重复 Ready 控制请求；旧 epoch Ready；所有 Ready 与一个在途 admission；Q 有 pending 消息仍能进入 R；R 未完成不能进 D；新回复后的完整 D；最后 cycle 的问答与购买；timer 到期不发送草稿；模型 late result；离线用户已提交购买的 receipt；全体缺席有界结束。

验证属于 Scheduler 状态测试及后续联调；不等于真人视觉验收或正式行为实验。oTree 机制对照与版本限制集中在 [调研文档](RESEARCH_SCHEDULING.md)，本文件规则均为 SalesBench 建议。
