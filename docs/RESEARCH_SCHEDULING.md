# SB-PROTOCOL-001：调度机制证据核对

核对日期：2026-09-23。本文只提供设计依据，不报告 SalesBench 的实验结果。`P` = 论文明确陈述；`D` = 官方文档明确陈述；`C` = 阅读指定版本代码所得；`I` = 推断；`?` = 本次材料不足。没有运行外部项目，也没有将其代码复制进 SalesBench。

## 1. 来源与版本

| 标记 | 本次使用的一手来源 | 版本 / 定位 |
| --- | --- | --- |
| M | [Market-Bench 论文](https://arxiv.org/html/2604.05523v1) | v1，2026-04-07；§3、§4.1、附录 A/A.1。供应链采购与零售竞争；不是同名量化回测项目 2512.12264 |
| E | [E-Commerce Bench 论文](https://arxiv.org/html/2608.30730v1) | v1，2026-08-31；§3.2、§3.5、附录 A/D |
| EC | [E-CommerceBench 官方仓库](https://github.com/QwenLM/E-CommerceBench/tree/b84678071c424fc94713b0a9e1ae86c519bd74c7) | commit `b84678071c424fc94713b0a9e1ae86c519bd74c7`，提交时间 2026-09-13 UTC |
| B | [Business Arena 论文](https://arxiv.org/html/2608.08621v1) | v1，2026-08-09（HTML 版本页标注）；§3.1、附录 C/D/K |
| BC | [BusinessArena 官方仓库](https://github.com/Accio-org/BusinessArena/tree/6f497f598696ee2792c5ac08733e61d853400513) | commit `6f497f598696ee2792c5ac08733e61d853400513`，2026-08-11；树中只有 README、论文和展示素材，没有可检查的运行器源码 |
| G | [Magentic Marketplace 论文](https://arxiv.org/html/2510.25779v1) | v1，2025-10-27；§3、§5.4、§6 |
| GC | [Magentic Marketplace 官方仓库](https://github.com/microsoft/multi-agent-marketplace/tree/9a651c7632685e4aeb2956dfe315df0cec6e8a92) | commit `9a651c7632685e4aeb2956dfe315df0cec6e8a92`，2026-09-14 UTC |
| O1 | [oTree Wait pages](https://otree.readthedocs.io/en/latest/multiplayer/waitpages.html) | latest，检索于 2026-09-23；含 6.0 行为说明，不当成固定发布版本 |
| O2 | [oTree Timeouts](https://otree.readthedocs.io/en/latest/timeouts.html) | 同上 |
| O3 | [oTree Live pages](https://otree.readthedocs.io/en/latest/live.html) | 同上；异步 live method 的 6.0 要求 |

Market-Bench 本次没有核实到对应的官方可运行仓库，以下只依赖论文算法；不假定其实际线程、锁或随机数实现。Business Arena 的源码限制同样保留。论文版本与随后公开代码不默认完全一致。

## 2. 时间、观察、行动与对话

| 系统 | 时间 / 顺序 / 同步 | 对话与预算 |
| --- | --- | --- |
| Market-Bench [M] | **P**：每个 step 包含采购与零售；采购有多个 bidding round，LLM 并行提交，最终分配后再并行收集价格和 slogan，随后执行消费者选择。示例为 6 steps、每 step 2 次 bidding round | **P**：采购轮提供前轮结果；零售是 persona attention 加购买规则。**?**：没有本文所需的自由 Buyer–Seller 多轮聊天协议或真人超时规范 |
| E-Commerce Bench [E] | **P**：turn 是一次模型回复，可含多项工具；按给定顺序执行。工具耗模拟分钟，营业时间 08:00–18:00，跨日和主动跳日触发日处理 | **P**：供应者/SKU 可反复议价并开启新 session；示例上限 365 天、4000 turns，连续三轮无工具会停止；上下文另有预算。不是多人买家共用的同步 round |
| Business Arena [B] | **P**：一个被测店铺先经营并选择推进 day，环境再处理买家、竞争者、物流与费用；30-day horizon，节庆日历压缩对应一年 | **P**：可处理买方询价、供应者和客户服务；**?**：同日对话轮数、统一 token/action 上限、内部 buyer 遍历与冲突优先级，公开材料不足以写成可执行规则 |
| Magentic Marketplace [G, GC] | **P**：搜索、消息、proposal、payment 与异步 receive；**C**：客户本地 conversation step 与商家轮询，不是全市场统一 round | **C**：商家一次 fetch 后按客户分组并发处理；customer max_steps 可配置。不同客户的对话独立推进，未见 SalesBench 式 Q/R/P 全局屏障 |
| oTree [O1–O3] | **D**：WaitPage 等组员到齐后放行，可统一计算；Live pages 支持持续通信；两者是应用可选机制 | **D**：可配置页面或跨页 deadline、实时私发/广播；经济动作预算与回合结束由实验作者定义，不是框架的统一市场规则 |

## 3. 竞争、延迟、公共状态与结束

| 系统 | 资源竞争与现实延迟 | 人类、公开状态、终止 |
| --- | --- | --- |
| Market-Bench [M] | **P**：采购按 bid 降序、同价随机打破平局并贪心分配。零售从可见且有库存的最低价商家买。**?**：消费者之间最后库存的排序、零售同价 tie 的具体规则 | **P**：step 末记市场历史/指标，有限 horizon；**?**：参与者可见榜单更新屏障、真人机制。不能从“并行 LLM”进一步声称线程实现完全消除了 latency 影响 |
| E-Commerce Bench [EC] | **C**：环境用显式 `advance_minutes` / 跳日推进；多个 run 各建自己的环境。**I**：该入口的并行 run 不能被解读为共享库存的多模型竞争 | **C**：达到日上限或破产结束，harness 另有 turn 限制；日事件随工具结果反馈。**?**：真人 Ready、同场买家 lottery、轮内公开榜单；论文排行榜不是运行中的市场信号 |
| Business Arena [B, BC] | **P**：竞争者是脚本市场人口。**?**：竞价/库存争抢的原子顺序、同 snapshot 保证及 response latency 是否进入调度；未公开运行器，不能声称已验证 | **P**：最终 day 后处理残余资产估值。**?**：真人 Ready、timeout、会话内榜单刷新；网站评测排名不能代替这一信息 |
| Magentic Marketplace [G, GC] | **P**：研究专门比较 proposal 到达顺序并报告首 proposal 偏好。**I**：异步 fetch/处理让可用信息受到达时序影响；这不是“论文规定 HTTP 先到者获得最后库存” | **C**：launcher 等客户任务全部完成后关停服务方。**?**：没有核实通用稀缺库存 lottery、冻结榜单或实际真人 Ready 实验；支持人机协作的讨论不等于已经实施真人调度 |
| oTree [O1–O3] | **D**：live async 修改共享 group 可能发生竞争；WaitPage 可集中结算。按到达顺序组队是可选匹配功能，不能用作购买优先级 | **D**：timeout 可保存已填字段或由作者覆盖；live 消息历史需应用保存并在刷新后重发。框架不会替 SalesBench 定义无操作者的经济选择或 episode 终止 |

## 4. 关键代码定位与推断边界

- **EC/C**：[工具执行器](https://github.com/QwenLM/E-CommerceBench/blob/b84678071c424fc94713b0a9e1ae86c519bd74c7/agent/ecommerce_tool_manager.py#L264) 的 `ask_code_exec` 按列表顺序执行；配置中的 parallel tool calls 指模型可提出批量调用，不代表环境并行改变状态。
- **EC/C**：[环境时钟与结束检查](https://github.com/QwenLM/E-CommerceBench/blob/b84678071c424fc94713b0a9e1ae86c519bd74c7/tools/ecommerce_env.py#L2573) 区分日推进、事件缓冲和终止；[chatbox](https://github.com/QwenLM/E-CommerceBench/blob/b84678071c424fc94713b0a9e1ae86c519bd74c7/tools/chatbox.py#L270) 一次发送消耗模拟 30 分钟，不直接使用 API 耗时。
- **EC/C**：[run.py](https://github.com/QwenLM/E-CommerceBench/blob/b84678071c424fc94713b0a9e1ae86c519bd74c7/run.py) 与 [agent loop](https://github.com/QwenLM/E-CommerceBench/blob/b84678071c424fc94713b0a9e1ae86c519bd74c7/agent/ecommerce_agent.py#L212) 分别控制独立 runs 和模型 turns；不能把一次模型 turn 当作市场 day。
- **GC/C**：[customer.step](https://github.com/microsoft/multi-agent-marketplace/blob/9a651c7632685e4aeb2956dfe315df0cec6e8a92/packages/magentic-marketplace/src/magentic_marketplace/marketplace/agents/customer/agent.py#L90) 维护本地 step、max_steps 和轮询等待；“成交立即 shutdown”在此版本被注释掉，不能据注释声称每人一单即停止。
- **GC/C**：[business.step](https://github.com/microsoft/multi-agent-marketplace/blob/9a651c7632685e4aeb2956dfe315df0cec6e8a92/packages/magentic-marketplace/src/magentic_marketplace/marketplace/agents/business/agent.py#L150) 汇集本次 fetch，再按客户组织；[fetch_messages](https://github.com/microsoft/multi-agent-marketplace/blob/9a651c7632685e4aeb2956dfe315df0cec6e8a92/packages/magentic-marketplace/src/magentic_marketplace/marketplace/protocol/fetch_messages.py) 支持过滤、分页和索引，并没有 Market Round inbox 的概念。
- **GC/C**：[AgentLauncher](https://github.com/microsoft/multi-agent-marketplace/blob/9a651c7632685e4aeb2956dfe315df0cec6e8a92/packages/magentic-marketplace/src/magentic_marketplace/platform/launcher.py#L253) 创建客户/商家并发任务；客户结束条件仍由各 agent 决定，不由“单笔 payment”统一代表。

## 5. 对 SalesBench 的设计启发（全部为建议）

1. 借鉴 Market-Bench 的收集—裁决边界，但不引入其采购拍卖或消费者模型。SalesBench 当前 `Procure` 仍是固定报价采购。
2. 借鉴 E-Commerce Bench 对模型调用、动作与模拟时间的区分；目前不为每次查看余额收费，也不把 Round 等同营业日。
3. Business Arena 提醒我们保存跨期资产与延迟义务，但其 30 日或残值公式没有得到 SalesBench 授权。
4. Magentic 的到达顺序问题支持测试批量信息发布；它并未证明某种 SalesBench 调度一定最优。屏障只能消除窗口内速度排序，仍需检查展示顺序与跨窗口行为。
5. oTree 提供同步与超时的工程参照；SalesBench 使用现有 Vue/H5，不迁移框架。超时不自动提交草稿购买，Ready 也不能等同实验退出。

当前五类材料足以支撑核心比较；没有为凑数量加入金融连续竞价等不同任务。推荐协议、其代价与仍需 pilot 的问题分别见 [ROUND_PROTOCOL](ROUND_PROTOCOL.md)、[HUMAN_SCHEDULER](HUMAN_SCHEDULER.md)、[决策摘要](PROTOCOL_DECISIONS.md)。
