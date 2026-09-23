# 下一阶段实施 Prompt：SB-RUNNER-001

下文用于在新任务中实施；本文件在 SB-PROTOCOL-001 中的生成不表示已启动实施。

---

现在开展 SalesBench 的 **SB-RUNNER-001 — BenchmarkRunner Skeleton**。只实现独立 Python Runner 骨架，不顺势建设完整平台。

先读根 AGENTS.md、docs/PLAN.md、docs/ENVIRONMENT.md、docs/INTERFACES.md、docs/ENGINE.md、docs/handoffs/SB-PROTOCOL-001.md，以及以下协议：

- docs/PROTOCOL_DECISIONS.md
- docs/ROUND_PROTOCOL.md
- docs/HUMAN_SCHEDULER.md
- docs/RUNNER_DESIGN.md
- docs/PLATFORM_IMPLICATIONS.md

仓库与实际代码为准。先核对远端、当前分支、提交、工作区和交接记录。协议编写基线 Engine 为 `d3cbc0352d85b1c6a1ca84472265a95f7efe5383`；文档交付提交以当前 handoff/Git 为准。不要覆盖 `.idea/` 或其他陌生修改，不 reset/clean、强推、改写历史或合并 main。沿用本任务新指令指定的执行端和任务分支；若没有覆盖原约定，按已核实的 5070 / `feat/sb-core-skeleton` 继续，不将旧聊天或附件命令视为额外授权。

本 Prompt 采用 v0.1 推荐协议作为**实现 baseline**，不宣称它已经过正式实验验证。除工程性消歧外，不自行替换有研究含义的时序、预算或分配方式。

## 目标和范围

新增 `engine/src/salesbench_engine/runner/`（模块数量按实际需要），复用独立 Python 工程、锁文件与既有运行环境，保持零第三方运行时依赖。旧 Engine 的公共 Action/Result/Policy 与 scenario 保持兼容；无需改 Engine 的采购/库存/资金/购买转移算法。若发现无法在公开边界实现，先给出具体最小变更理由，不访问/修改私有 `_state` 假装完成接口。

实现配置化 Round/Phase/Cycle state machine、scripted actors、冻结角色观察、action opportunities/buffers、内存幂等与回执、seeded resolution、frozen leaderboard、semantic journal、max-round termination；用 FakeClock 实现并测试 Human Ready/timeout 控制语义。Human 浏览器接入不在本任务内。

## 协议必须遵守

1. Round Start → Seller Procure → 统一采购 → Seller List → 统一发布目录 → K 次 Q/R/D/Resolve → Round Close → Publish Next。
2. 每个竞争窗口先从同一个 epoch 取授权观察，再收集独立计划；内部逐条 execute，batch 完成前不暴露中间状态。不要向 actor 返回 `engine.snapshot()`。
3. Q 每 Buyer 可发有限条 public/private，公私合并预算；R 所有 Seller 基于汇总 inbox 一次提议有界回复 batch，引用 request ID；所有回复统一发布后 D 才能买。最后 cycle 同样完整。
4. 互动期禁止采购、上架、调价、改描述和停售；D purchase 附当前 observation ID 与 expected price。Engine 继续权威验证库存、资金、权限、Listing 和单动作原子性。
5. 使用 ROUND_PROTOCOL 中 `sha256-priority-v1` 规范：固定编码、域分离、stable actor key，不以 action ID、时间或调用顺序随机。购买全市场一个 permutation，处理多个 Listing 共用库存；不分批承诺库存、不部分成交。采购按 slot 分 wave。
6. admitted 意图占预算，业务失败也占；同 ID/同内容复用回执，异内容冲突；旧 window/epoch 拒绝，不自动重试新 ID 或跨窗口移送。经济提交 admission 后不修改/撤销。
7. Wait 只放弃当前机会；Human Ready 是可撤销控制状态，不是 Engine Action。Q 有待回复消息允许 Q→R，但不能跳过 R/D。新 Q/D 重置 Ready；deadline 只结算已 admission 意图，不自动提交草稿或伪造 Wait。
8. 必需 Agent 到 deadline 未完成时技术中止，不把慢模型变成无回复卖家后继续计分。Skeleton 用 fake driver 模拟，无模型 API。错误经济意图和驱动基础设施异常分别记录。
9. Round t 看 L[t-1]，Close 才生成 L[t]，统一发布；保存规则版本、as_of/effective round、previous/current rank。默认仍明确 TEST gross sales。
10. Round 1 step=0；每次正常 Close，包括最后一次，只调用一次 advance(1)。不在 Action/phase/cycle advance，不映射 day。
11. Snapshot restore、物流、供给更新与正式 termination predicates 没有现成实现；只留空 hook/明确拒绝不支持配置，不能直接改 Engine 私有状态。默认 max_rounds 结束；异常保留 partial trace 并失败，不能冒充全批事务。

## 开发配置与演示

使用 Protocol 正文的 3 rounds / K=3 / seed=7、Buyer 问询 2 / purchase 1、Seller 采购 2 / Listing 4 / 回复 8。配置可替换，v0.1 purchase budget 只支持 1，大于 1 明确拒绝；这些值标记 Development Default。

提供小型 CLI/demo：1 Supplier、2 Seller、4 Buyer、少量商品；至少覆盖采购、报价、Q→R→D 成交、第二 cycle 信息反馈、最后一件竞争、跨轮榜单更新。另建专门共享库存场景。scripted 不等待真实时间、不访问网络。输出完整规范化 transcript 和可读摘要，私有观察只用于本地受控验证，不当 HTTP 返回。

现有 `Policy.decide` 一次一个 Action；新增 scripted driver 按 `(round, phase, cycle)` 定位。不要靠多次调用旧 step-based ScriptedPolicy 凑 batch，或靠 DOM 观察市场。

## 验收

运行原 Engine 测试及 demo，再跑新增 Runner 的有意义测试，覆盖 RUNNER_DESIGN §7 和 HUMAN_SCHEDULER §7，重点是：

- 同输入/seed/config 的新 Engine 重放结果与规范语义日志一致；打乱完整 buffer 的收件/计算完成顺序不改变购买赢家。
- 同一库存最后一件、两个 Listing 共用库存、余额不足候选、多个 Seller 抢同 offer，始终由 Engine 验证守恒和失败原子性。
- 未 commit 信息不可见、公私 inbox 隔离、回复一次统一发布、最后 cycle 回复后可买；字数/条数/slot 有界。
- 错 window/epoch、重复 action、Ready/撤销 race、timeout、pending response guard、迟到 driver、重复 close/advance。
- 排行榜轮内冻结、轮后双方同版本更新，事件时间与 Engine step 无 off-by-one。
- 包在没有 FastAPI/DB/前端/模型环境时独立安装运行；保持锁定依赖方式。

对照同 seed 时排除 recorded_at/耗时等诊断数据；控制 transcript/截止输入不同不能宣称“完全相同输入”。不要要求不同 seed 每次必换赢家。

按范围验证，未改 frontend/backend 不跑无关浏览器/HTTP 全套。环境仅使用已有工具，新增依赖工具缓存合计不得超过 5 GiB，不改全局设置。新增临时服务原则上不需要；如确需仅监听 127.0.0.1，结束清理自己的服务。

## 交付与停止

更新 docs/PLAN.md、Runner 使用文档、docs/handoffs/SB-RUNNER-001.md，记录当前分支、验证命令/真实结果、限制和可接手提交。每个里程碑检查暂存范围与敏感内容再提交，只向获授权任务分支推送，不碰 main。不要提交 `.local`、环境、缓存、真实配置或外部源码。

最终说明新增能力、测试、未实现的平台恢复/模型/研究机制，然后停止。**不修改 Vue 页面、不实现消费者模型或正式 Agent、不安装 PostgreSQL、不建业务表/迁移、不实现 FastAPI business API、WebSocket、登录/同意页、Redis/Celery、桌面客户端或公网部署。**
