# Protocol 对 H5 / FastAPI / PostgreSQL 的后续影响

SB-PROTOCOL-001 / 2026-09-23。**接口与持久化设计草案；本轮不创建业务 API、表、SQLAlchemy model 或 migration。** 本文只承接 [ROUND_PROTOCOL](ROUND_PROTOCOL.md) 与 [RUNNER_DESIGN](RUNNER_DESIGN.md)，不重新定义调度规则。

## 1. 三类状态

| 类别 | 内容 | 权威来源 / 生命周期 |
| --- | --- | --- |
| 研究状态 | Engine 的账户、库存、订单、消息；Runner 的 round/phase/cycle、窗口、buffers、排名快照、episode status | Engine + Runner 语义；后续需通过平台持久化，不以 Vue 为准 |
| 平台持久化状态 | session/participant 映射、配置版本、receipt、幂等键、Ready 控制版本、deadline、单写者 fencing、语义事件及 outbox | PostgreSQL 提交结果；服务进程重启后仍可查询 |
| UI 临时状态 | 当前五页、展开详情、未发送文本/数量、滚动位置、加载状态、近似倒计时 | Vue；不因 timeout 自动升级成经济动作 |

三类不是三套市场账本；研究语义决定如何改变状态，数据库保存已提交的状态和证据。网页 participant 和研究 actor（Buyer/Seller/Supplier）分别建模；消费者模拟器是 actor driver，不能被当作登录用户。

## 2. 最少需要增加的传输概念

| 字段/概念 | 必要性与范围 |
| --- | --- |
| session_id、bound participant/actor | 场次与权限；从认证上下文绑定，不能靠 payload 自选身份 |
| protocol_version、config_hash | 识别运行规则；完整 config 只按权限提供，不泄漏隐藏参数 |
| round_index、phase、interaction_cycle | 服务端运行位置；cycle 可不进入主界面文案 |
| window_id、observation_id、visible_epoch | 防止旧页面在新阶段提交；冻结观察和发布版本，不混用旧 revision |
| phase_deadline、server_time | 全五页共同倒计时与重连校准；研究时间另存 |
| participant_ready、ready_control_version | 仅本人的当前窗口状态，控制并发页面；不需要广播别人 Ready |
| remaining_budget、allowed_actions | UI 显示可用操作；服务端仍权威检查 |
| action_id、action_status、code、result | buffered 与最终经济结果分离；原 ID 查询未知结果 |
| leaderboard_snapshot_id、as_of_round | 保证官方榜单冻结；previous/current rank 随 snapshot |
| event_seq / delivery_cursor | event_seq 为内部语义审计；面向参与者用授权后的 opaque cursor，不暴露全局私聊事件间隙 |

不是所有字段都塞进每个事件。运行状态响应提供 window 和 deadline；购买 receipt 引用 action/window/result；消息和订单记录自己的语义时间与必要实体 ID。公开 UI 不展示研究 seed、其他人 buffers、Seller 成本或内部审计对象。

## 3. BuyerService 的兼容路径

当前 [types.ts](../frontend/src/domain/types.ts) 是 `0.1-draft/local-demo`，含 productId、revision、同步等待终态的演示 execute 和 scheduled reply；[notConnected.ts](../frontend/src/services/notConnected.ts) 尚无网络实现。

未来 NetworkBuyerService 保留 observe/execute/getReceipt/subscribe 思路，另加最小 runtime/ready 控制边界；用新 schemaVersion 和明确 network mode，不冒充本地演示返回类型原封不动可用。

- `productId → listing_id`：一个商品可有多个报价，网络 DTO 明确展示 Listing 与 Product，不能用商品 ID 直接选卖家。
- `execute → buffered receipt`：发出购买后阶段结束才成功/失败；pending 期间显示明确状态，刷新后按 action ID 查询。
- `replyStatus`：从演示 scheduled 改为 queued_for_reply / answered / unanswered 等 Runner 状态，不能保证所有 Seller 必回复。
- 时间：消息/订单同时关联 round/cycle 与 UTC recorded_at，保留 Engine step 供内部分析，不能把 UTC 当模拟日期。
- `revision`：区分 publication epoch 与授权通知游标；旧演示 revision 不作为全场 event_seq。
- 订阅：消息只失效授权视图或带必要投影；浏览/筛选不触发新的市场信息机会，也不扣经济预算。

H5 增加顶部阶段/时间、Ready/继续操作、buffered 提示与过期草稿提示。保留五页、中文布局、购买和暂不购买；不在此建设实验运营后台或 Seller UI。具体视觉修改留 C 验收。

## 4. API 语义草案（路径可在 B 调整）

| 操作 | 含义 |
| --- | --- |
| 读取 session runtime + authorized observation | 一致地获取当前可见 epoch、窗口与授权视图；不能绕过 Broker 读实时 Engine |
| 提交 action envelope | 验身份/场次/window/epoch/slot 并持久收件；返回 buffered 或明确拒绝，不直接 route→engine.execute |
| 查询本人的 action receipt | 按 action ID 找同一请求的状态；与网络超时重试配套 |
| 设置/撤销本人的 Ready | 携带 window、epoch、control_version 和 request ID；不调用 Engine |
| WebSocket subscribe/resume | 通知运行阶段、授权结果/消息、排名版本；不是裁决器 |

同 ID + 同语义载荷返回已有回执；异载荷冲突。JSON fingerprint 要规范化，不能按原始字段顺序比较。客户端不能提交 server actor ID 替他人操作。未来 Agent 走同一结构化 application 语义，可为进程内调用，不需要 DOM 或模拟点击。

## 5. Schema implications（概念记录，不是建表授权）

| 记录组 | 建议保存 | 必要约束 / 能回答的问题 |
| --- | --- | --- |
| Session | setup/config/version/hash、seed、status、round/phase/cycle/window、publication epoch、writer revision/fence | 当前运行到哪里；每场只有一个有效写者 |
| Participant binding | participant key、actor key、role、driver kind、status | 谁可读/写哪个角色；稳定 roster 可重放 |
| Window / opportunity | start/deadline、snapshot ref、required actors、budget、sealed/cutoff、close token | 哪些人还可行动；旧窗口不能重开；Round Close 不重复 |
| Ready controls | actor/window、ready、epoch、control_version、request ID | 当前谁 Ready；撤销和多标签页顺序可解释 |
| Action / receipt | bound actor、ID、payload/fingerprint、slot、window/snapshot、status、result、recorded_at | 哪些已提交/已 resolve；重复是否已扣款；唯一 session+actor+action ID，slot admission 唯一 |
| Resolution batch | batch ID、frozen candidate IDs、algorithm/version、permutation、input/output hash、committed revision | 为什么此买家赢；故障后是否执行过 |
| Semantic event | event_seq、round/phase/cycle、kind、actor/action/entity refs、audience、Engine refs、payload | event 属于哪次机会；失败与 timeout 也保留 |
| Snapshot / committed state | 版本化状态或 setup+完整 transcript、可恢复内容、hash | 断电后重建同一 Engine/Runner；不能仅存目前 snapshot() 然后假称可 restore |
| Leaderboard snapshot | as_of/effective round、rule/version、rows、previous/current rank、final | 某时刻参与者实际看到哪个榜单 |
| Message relation / delivery | request/reply 映射、terminal reply status、outbox、授权 cursor | pending 是否仍存在；重连补发可去重 |

库存/账务的规范化表或状态文档存储方案在 B 决定；不要同时让 ORM 和 Engine 各自计算 purchase。必需唯一键、外键/作用域检查和 writer fencing 属于持久化设计，不等于已经有迁移。

## 6. 数据库提交与 Engine 发布

当前 Engine execute 立即改变内存，不能在 DB 失败时自动撤销；直接“先改 Engine，再写 DB”不能满足恢复要求。

两条可行路径：

1. **小系统推荐起点：候选 Engine + transcript 重建。** 从已提交 setup 和 canonical transcript 构建独立 Engine/Runner 候选，在候选中运行固定 batch；获得状态/结果。DB 事务记录动作终态、batch、phase、语义事件、排名、outbox 与可恢复输入；commit 成功后才交换 live 指针/发布 epoch。代价是重放成本较高，但不用猜测私有 restore。
2. **后续优化：正式 versioned checkpoint/restore 或 Engine prepare/commit。** 需另行设计完整 counters、时钟、状态版本和一致性测试，再获准修改 Engine；不能拿 deepcopy 私有属性代替公共持久化契约。

一个 Session 写者以数据库 revision/fence 验证提交权限，持锁范围与候选计算耗时在 B 权衡；另一个进程不得并行提交同一 revision。初期可单 worker、单 session queue，但仅依赖进程内锁仍不足以声称多进程安全。

| 故障点 | 必须行为 |
| --- | --- |
| 收件已持久但尚未 resolve | 新写者恢复同 batch/candidate，不丢动作、不另抽签 |
| 候选已算完，DB rollback | 丢弃候选；已公开的 live 状态保持旧 epoch；待收件可重做同 batch |
| DB commit 成功，live 指针尚未换/进程崩溃 | 以 DB committed revision 重建；不得再次扣款/advance |
| commit 结果未知 | 冻结后续写入，查 batch ID / revision 确认，不盲重试新 batch |
| DB 成功，WebSocket 发送失败 | 用事务内 outbox 重发；UI 按事件/receipt 去重，不能因此回滚成交 |

outbox 可由同应用异步循环投递，不引入 Redis/Celery。该可靠路径属于 B/C，A 只做内存单进程，不宣称跨重启 exactly-once。

## 7. 重连和恢复顺序

客户端重新绑定身份 → 读取 current runtime/epoch 和本人的 unknown/pending receipt → 获取完整授权快照与同版本 cursor → 从 cursor 订阅增量。先 subscribe 或先 snapshot 均需握手保证不丢中间发布；推荐 snapshot response 带服务端可恢复 cursor，之后补游标后的消息。

同一 action ID 在重连后继续查询；过期 window 的草稿不可自动重发。私聊历史只给参与者双方，公共状态可给本场；不要广播完整宿主 snapshot。全量全场 event_seq 不作为浏览器“缺几条消息”的依据。

平台重启时 deadline 如何恢复必须显式选择：推荐在可确定已提交边界恢复时保留原 UTC deadline，已过期的 Human 窗口按缺席策略封口；若影响必需 Agent 或快照一致性，则技术中止/统一恢复 profile，不暗中重开一个人的经济机会。B/C 应覆盖停机跨 deadline 和 commit-unknown 两类测试。

本轮到此为止；没有安装 PostgreSQL、启动服务、实现 WebSocket 或修改 Vue 源码。
