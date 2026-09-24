# SalesBench 计划与阶段状态

## 当前：SB-CONSOLIDATE-001

2026-09-24，5070，沿用 `feat/sb-core-skeleton`。开工 HEAD / origin 为 `d489479c82240d120d265ac85ce7fb8fbbc6fadb`，fetch 后一致；main 保持 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。保留 `.idea/`，不合并 main，不改变 Market Round → Tick → Wave 协议。

收口范围：核对当前完整框架；修正当前/历史文档混杂；统一宿主 inspect 与恢复校验；整理回归入口及证据输出；完整真实系统回归。没有新依赖、数据库 migration 或 Engine/Runner 源码变更。架构和能力边界以 [ARCHITECTURE.md](ARCHITECTURE.md) 为统一入口；本次验证和接手信息以 [handoff](handoffs/SB-CONSOLIDATE-001.md) 为准。

## 已完成阶段

| 阶段 | 当前成果 | 历史依据 |
| --- | --- | --- |
| SB-002B | 总工程、Vue Buyer 五页、最小 health、演示接口；用户完成当时视觉验收 | [交接](handoffs/SB-002B.md) |
| SB-CORE-001 | 独立零依赖 Engine、领域分离、采购/库存/交易、权限、step、确定性测试 | [交接](handoffs/SB-CORE-001.md) |
| SB-RUNNER-001 | Round/Tick/Wave、冻结观察、有限批次、seeded resolution、journal/replay、Driver 接口 | [交接](handoffs/SB-RUNNER-001.md) |
| SB-PLATFORM-001 | FastAPI application boundary、PG/SQLAlchemy/Alembic、持久幂等/fencing/事务发布、重启恢复 | [交接](handoffs/SB-PLATFORM-001.md) |
| SB-E2E-001 | 真实网络 Buyer、工程 Seller、四角色手工入口、Wave/receipt 展示、浏览器 E2E | [交接](handoffs/SB-E2E-001.md) |
| SB-CONSOLIDATE-001 | 当前架构/命令/边界收口和完整系统回归 | [交接](handoffs/SB-CONSOLIDATE-001.md) |

历史 handoff 中“本轮不建数据库”“Vue 尚未连接”等指当时的任务范围，不能当作当前能力。SB-002B 的 `main` 是保留的早期验收点，当前完整框架仍在任务分支，主分支合并需单独授权。

## 下一步建议（等待新任务授权）

1. **最小研究 profile 与评价契约**：明确 Consumer/Seller 假设、比较指标、固定场景与失败传播结论；不把 TEST 规则当研究定案。
2. **受控真实 LLM adapter 小试**：复用同一 application boundary / Runner，验证预算、结构化意图、故障与模型记录；不改库存、资金或购买排序。
3. **可复现实验与数据交付**：固定 profile/seed/模型与代码版本，批量重复运行、指标导出及审计；由实测规模决定性能工作。

工程缺口、研究组件、未定机制和 HumanDriver 分别列于 ARCHITECTURE。正式真人实验独立立项，不能将手工 E2E 等同于 HumanDriver。收口后停止，不自动实施上述阶段。
