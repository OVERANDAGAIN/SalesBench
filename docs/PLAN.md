# SalesBench 计划与阶段状态

## 当前：SB-METRICS-001

2026-09-24，5070，沿用 `feat/sb-core-skeleton`。开工 HEAD / origin 为 `7807df8d20a8c0f77e680bd099af262ba02c217e`，fetch 后一致；main 保持 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。保留 `.idea/`，不合并 main，不改变 Market Round → Tick → Wave 协议。

本轮完成：已提交事实的唯一 Metrics 计算；版本化 dev_cash_profit_v1 / sb-metrics-v1；默认 Tick Close 的持久利润榜；Buyer/Seller 共用公开榜单；宿主 API/CLI/JSON/CSV 和历史轨迹。新增显式 sb_metrics_001 迁移（两张派生表与 session policy），无新依赖或 Engine/Runner 源码变更。实际完成完整回归：Engine/Runner 64、后端/真实 PG 45、Vue 28、类型/构建、生产预览、真实四角色含重启及历史 UI。见 [指标说明](METRICS.md)、[handoff](handoffs/SB-METRICS-001.md) 和 [当前架构](ARCHITECTURE.md)。

## 已完成阶段

| 阶段 | 当前成果 | 历史依据 |
| --- | --- | --- |
| SB-002B | 总工程、Vue Buyer 五页、最小 health、演示接口；用户完成当时视觉验收 | [交接](handoffs/SB-002B.md) |
| SB-CORE-001 | 独立零依赖 Engine、领域分离、采购/库存/交易、权限、step、确定性测试 | [交接](handoffs/SB-CORE-001.md) |
| SB-RUNNER-001 | Round/Tick/Wave、冻结观察、有限批次、seeded resolution、journal/replay、Driver 接口 | [交接](handoffs/SB-RUNNER-001.md) |
| SB-PLATFORM-001 | FastAPI application boundary、PG/SQLAlchemy/Alembic、持久幂等/fencing/事务发布、重启恢复 | [交接](handoffs/SB-PLATFORM-001.md) |
| SB-E2E-001 | 真实网络 Buyer、工程 Seller、四角色手工入口、Wave/receipt 展示、浏览器 E2E | [交接](handoffs/SB-E2E-001.md) |
| SB-CONSOLIDATE-001 | 当前架构/命令/边界收口和完整系统回归 | [交接](handoffs/SB-CONSOLIDATE-001.md) |
| SB-METRICS-001 | Development 利润榜、宿主事实指标、持久历史与 JSON/CSV、真实 UI 验证 | [交接](handoffs/SB-METRICS-001.md) |

历史 handoff 中“本轮不建数据库”“Vue 尚未连接”等指当时的任务范围，不能当作当前能力。SB-002B 的 `main` 是保留的早期验收点，当前完整框架仍在任务分支，主分支合并需单独授权。

## 下一步建议（等待新任务授权）

1. **最小研究 profile 与评价契约**：明确 Consumer/Seller 假设、比较指标、固定场景与失败传播结论；不把 TEST 规则当研究定案。
2. **受控真实 LLM adapter 小试**：复用同一 application boundary / Runner，验证预算、结构化意图、故障与模型记录；不改库存、资金或购买排序。
3. **可复现实验与数据交付**：基于已有指标导出固定 profile/seed/模型与代码版本，增加批量重复运行与分析；由实测规模决定性能工作。

工程缺口、研究组件、未定机制和 HumanDriver 分别列于 ARCHITECTURE。正式真人实验独立立项，不能将手工 E2E 等同于 HumanDriver。收口后停止，不自动实施上述阶段。
