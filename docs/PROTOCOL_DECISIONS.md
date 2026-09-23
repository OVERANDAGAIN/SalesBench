# SB-PROTOCOL-001 一页式决策摘要

2026-09-23 · **推荐 v0.1，可交实现；未做正式实验验证。** 正文：[Round Protocol](ROUND_PROTOCOL.md) · [Human Scheduler](HUMAN_SCHEDULER.md) · [Runner](RUNNER_DESIGN.md) · [平台衔接](PLATFORM_IMPLICATIONS.md) · [一手证据](RESEARCH_SCHEDULING.md)。

## 建议固定的 v0.1 baseline

1. 宏观单位 Market Round，轮内多 Phase、多 Cycle；动作不推进 round，也不默认 round=day。
2. Seller 先同快照提交采购，统一裁决后再同 epoch 提交 Listing/价格/描述；新报价统一发布，互动期间冻结条款。
3. 每 cycle：**Buyer 问询 Q → Seller 汇总回复 R → Buyer 决策 D → 统一购买裁决**。问和买可发生在同一 cycle 的不同窗口；最后一次问询也有回复后购买机会。
4. 同窗口完整收件后才执行；模型先算完无优先权。全市场 seeded serial priority，Engine 验库存/余额/价格；不以 HTTP 时间排序，不拆单。
5. 公私聊合计限额；Seller 汇总 inbox、批量回复，R 结束明确未回复状态，不无限 pending；各方不见别人未 commit 的动作。
6. Human Ready 可选、可撤销、绑定窗口/信息版本；新窗口 active。Ready 只缩短当前收集，不跳过 R/D；timeout 不发送草稿，不替人买。
7. Round t 看 L[t-1]；Close 后生成 L[t]、统一发布，记录 previous/current rank。轮内订单/库存可更新，官方榜单不更新。
8. Runner 唯一调度和写入入口；每 Round Close 恰好 `advance(1)`。Engine 原有单动作规则保留；模型/API 故障与经济拒绝分开。

## Development Default（不是论文参数）

| 项目 | 开发值 |
| --- | --- |
| episode / seed | 3 rounds，K=3，seed=7 |
| Buyer 每 cycle | 公私聊合计 2 条、1 个购买意图，开发每单最多 1 件 |
| Seller | 每 round 采购 2 项、Listing 修改 4 项；每 cycle 回复 8 条 |
| 排名 / 环境 | TEST 成交额排名；有限固定供给、当前即时结算，无动态补货 |
| scripted | 无真实 sleep，fake clock 验 timer；正式模型不在 Skeleton |
| Human 工程试跑 | Q 45s / R 20s / D 30s；Seller 两窗口各 15s，最短开放 5s；round watchdog 360s |

## 仍需 pilot / 研究确认

K、round horizon、角色规模、问询与回复额度、数量上限、阅读/操作窗口时长、是否支持更自然的流水式对话、固定价格的行为影响、缺席处理与样本排除。比较 K 和 timer 时记录末轮未满足咨询、截断/timeout、每 cycle 成交增量、疲劳与行为变化；先定比较方法，再定正式参数。

当前随机优先的全量订单规则不保证多件分配的比例公平；Ready/timer 也不会消除全部现实时间压力。Human mixed 中必需 Agent 漏 deadline 为技术中止，不能被记为自然不回复并继续正常计分。

## 明确没有决定的研究机制

正式 Consumer Model、Seller Agent、效用/奖励/评分函数、排行榜指标与并列经济含义、推荐算法、采购拍卖、供给补货、物流/履约/退款/税费/托管、私人议价成交、真实 day 映射、实时榜单 variant。当前 TEST 规则不得改名为正式 benchmark 定案。

## 下一步及停止边界

**A：Runner Skeleton → B：持久化与网络入口 → C：H5 多人完整骨架。** A 先使协议可测，再解决 DB 恢复与 H5 协调。直接使用 [SB-RUNNER-001 实施 Prompt](prompts/SB-RUNNER-001.md)。本轮只交付调研和文档，不实施 A，也不开始 PostgreSQL/FastAPI 业务平台。
