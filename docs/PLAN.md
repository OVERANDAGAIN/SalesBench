# 总计划

## 当前任务 SB-PROTOCOL-001

2026-09-23：在已有 H5 与独立 Engine 上设计 Benchmark Round Protocol / Human Scheduler；本轮只做一手调研、源码核对与 docs 文档，不实施 Runner 或业务平台。沿用已核对的 5070 工作副本与 `feat/sb-core-skeleton`；Engine 基线 `d3cbc0352d85b1c6a1ca84472265a95f7efe5383`。保留已有未跟踪 `.idea/`。

状态：调研与设计交付完成，文档静态核对通过。交付入口：[一页式决策摘要](PROTOCOL_DECISIONS.md)。规范正文为 [ROUND_PROTOCOL](ROUND_PROTOCOL.md)、[HUMAN_SCHEDULER](HUMAN_SCHEDULER.md)、[RUNNER_DESIGN](RUNNER_DESIGN.md)、[PLATFORM_IMPLICATIONS](PLATFORM_IMPLICATIONS.md)；一手来源与代码推断集中在 [RESEARCH_SCHEDULING](RESEARCH_SCHEDULING.md)。这些是未经正式实验验证的 v0.1 推荐，不把 Development Default 或既有 TEST 经济规则升级为研究定案。

下一步顺序调整为：**A / SB-RUNNER-001 独立 Runner Skeleton → B / Platform Integration V1 → C / Whole-System Skeleton V1**。A 的直接实施文本见 [Prompt](prompts/SB-RUNNER-001.md)；本轮生成 Prompt 后停止，不执行它。最终范围和验证见 [本任务交接](handoffs/SB-PROTOCOL-001.md)。以下 SB-CORE-001 与 SB-002B 保留为历史；旧文中的“下一步直接接数据库”已被本节替代。

## SB-CORE-001（已完成）

2026-09-23 用户授权先建设 Python Experiment Engine Skeleton，再考虑平台持久化接入。执行端 5070，分支 `feat/sb-core-skeleton`，从验收基线 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408` 创建；不修改或推送 main。

目标已完成：独立 `engine/` 包、明确领域/观察/动作边界、采购到销售的完整内存流程、step、可替换策略、确定性场景和测试。A / B / C 均完成；Engine 36 项测试和原后端 2 项测试通过，独立 wheel 导入与两轮场景验证通过。设计见 [ENGINE.md](ENGINE.md)，交付见 [SB-CORE-001](handoffs/SB-CORE-001.md)。

下一阶段候选（待新指令）：FastAPI + PostgreSQL 通过 application/adapter 调用 Engine。先确定持久状态恢复/版本、Engine 草稿发布与数据库提交协调、跨进程单写者及持久幂等；本任务没有实现这些能力，也没有接入正式研究模型。

本任务不建设业务 API、数据库、Vue 网络适配器、LLM 或桌面客户端。下文 SB-002B 与原后续计划保留为历史；当前授权顺序以本节为准。

## SB-002B 边界（历史）

唯一工程 `D:\SalesBench`；远端 `https://github.com/OVERANDAGAIN/SalesBench.git`。
任务 SB-002B，机器 3050，任务分支 `chore/sb-002b-bootstrap`，验收基线分支 `main`。
2026-09-23 初始确认远端为空，克隆后建立指定任务分支；各实施检查点已推送。
用户完成视觉验收后，明确授权在确认没有独立 `main` 历史、陌生修改或缺失的验收提交后，以本次收尾提交建立并推送 `main`，保留任务分支。这项授权替代本轮此前只推送任务分支的限制；不强推、不重写历史、不调整 GitHub 默认分支设置。

## SB-002B 里程碑（历史）

1. A / 阶段 2B：**完成**。材料归档、工程约定、锁文件、最小 Vue 与 FastAPI 健康检查已完成；类型、构建、后端、HTTP、重启检查通过。
2. B / 阶段 3：**v0.1 草案完成，待 Python 主体接入时确认**。接口与职责见 `docs/INTERFACES.md`；Python 主体尚未提供，未宣称双方定案，未决研究规则保持隔离。
3. C / 阶段 4A：**实现、自动检查及用户视觉验收完成**。保留原型界面的 Vue 买方端、异步演示服务和自动检查已完成。2026-09-23 用户实际启动前后端、操作五页与主要流程，确认布局、视觉和使用体感与已认可 HTML 原型一致。

当前 Vue 仍默认连接本地异步演示服务；FastAPI 仅有 `GET /health` 健康检查，尚未接入真实业务 API、PostgreSQL 或正式 Python 实验内核。健康检查只表示 API 进程可响应。

本次仅更新验收状态和接力信息；收尾重跑 typecheck、production build、前端 18 项测试、后端 2 项测试，均通过。未修改页面或演示行为，无需重复浏览器自动化。收尾完成后停止，不开始下一阶段实施。

## SB-002B 收尾时的后续计划（历史）

下一阶段：**平台后端最小共享服务：FastAPI 业务 API + PostgreSQL + SQLAlchemy/Alembic + Vue network adapter；正式 Python 实验内核仍待主体交付。**

入口：以验收基线为基础，先核对 `docs/INTERFACES.md` v0.1 草案和 `docs/ENVIRONMENT.md`，在新任务中明确最小共享服务范围、数据库运行或接入方案及验证方式，获准后实施。本轮不安装数据库或创建业务表。
正式 Python 主体到位后再确认包边界与状态裁决责任；当前演示规则不作为正式研究语义。
`backend/app/db/`、`backend/migrations/`、`research/`、`deploy/` 在实际工作发生时创建，不生成空模块。
优先兼容已有研究工程结构，不为目录示意搬迁主体。

## 材料

五份原件归档到 `references/ui-v1/2026-09-23/`，来源文件未修改。
ZIP 的 23 个文件展开到该目录下的 `source/SalesBench_V1/`，仅作为迁移参考。
五页：排行榜、商品推荐、公共交流、私聊、我的。原型规则只是演示配置。
