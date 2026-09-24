# SB-CONSOLIDATE-001 收口交接

2026-09-24，5070，`D:\SalesBench`。本轮整理完整框架和开发入口，未进入真实模型、研究组件或正式真人实验阶段。当前总入口：[README](../../README.md)、[架构总览](../ARCHITECTURE.md)、[环境](../ENVIRONMENT.md)、[手工市场](../MANUAL_MARKET.md)。

## 开工与范围

分支 `feat/sb-core-skeleton`，开工 HEAD / origin **d489479c82240d120d265ac85ce7fb8fbbc6fadb**，fetch 后 ahead/behind 0/0，唯一 worktree 为 D:/SalesBench。main / origin/main 保持 **2ab44d79e5d28d5c0c17b17e3cdb2a5768579408**。原有未跟踪 `.idea/` 六文件保留，收尾核对 SHA-256，不暂存；没有陌生已跟踪修改。

逐层核对 Vue NetworkApp / MarketClient / Buyer facade / Seller UI、FastAPI 路由、MarketService、存储/恢复、Runner/Engine、各阶段 handoff 与运行脚本。确认所有真实参与者意图经 sb-platform-v1 提交，Runner 收齐 Wave 后统一裁决；SQL 和 Vue 没有第二套 purchase。历史 demo 只用于显式开发/回归，默认与生产入口不回退。

Engine/Runner 源码、protocol、锁文件、依赖、迁移和 UI 行为均未改变；没有安装新组件、搬迁主模块或改 main。当前回归新增的 session 不覆盖旧场次，历史验收截图/handoff/references 保留。

## 实际整理与修复

1. `docs/ARCHITECTURE.md` 成为项目总览：明确职责、提交/恢复链、时间与三种版本、当前/历史入口、已完成/未完成、Known Issues 与三个下一里程碑。
2. README/PLAN/ENVIRONMENT/INTERFACES 改为当前状态和可执行接手路径；旧 Vue v0.1 单动作契约移入 `docs/history/INTERFACES-v0.1.md`。修正 Engine/Runner/Platform 中已经过时的“未来平台”“Vue 未接入”描述，历史 handoff 保留原文。
3. `scripts/run.ps1 check` 顺序执行完整系统回归，任何失败即退出；不自动安装工具、不跳过 PG、不自动修改配置。启动继续保留 PG + 两个前台终端，便于明确归属与 Ctrl+C 停止，没有引入后台进程管理器。
4. 浏览器 `evidence.mjs` 统一输出目录：默认每次写 `.local/verification/<kind>/<timestamp>/`，不覆盖已验收材料。显式 `-EvidenceDir` 才保存本任务证据；完整 inspect/失败诊断仍在忽略目录。preview/demo 配置读取兼容 Windows UTF-8 BOM。旧 Agent/NOT_CONNECTED fixture 注释明确为历史测试入口。
5. `inspect_market` 原先会重放 journal，但未像 recover 一样核对 session 行的 source/state 摘要；现在检查同一 committed metadata，并复用 `MarketService._restore_verified` 的版本/经济摘要验证。新增真实 PG 两个损坏元数据用例，确保两种宿主入口都 fail closed；无研究或事务语义变化。

## 本次完整实测

实际执行：`pwsh -NoProfile -File scripts/run.ps1 check -EvidenceDir docs/verification/SB-CONSOLIDATE-001`，退出码 0。原始终端日志留 `.local/SB-CONSOLIDATE-001/check.txt`；不把历史结果当本次验证。

| 项目 | 结果 |
| --- | --- |
| Engine / Runner | **64 unittest 通过**，包括确定性排序、库存竞争、失败原子性、权限、时间/replay/recovery |
| PostgreSQL / Backend | **31 pytest 通过**（原 29 + inspect/recover 元数据损坏 2）；各测试从空随机 schema 迁移，无跳过或 SQLite 替代 |
| Vue | **26 单元测试、typecheck、production build 通过** |
| 生产预览 | 真实绑定入口、密码框、资源、无 demo/test 全局控制器，通过 |
| 四角色真实 E2E | **9 段通过**，生产 Vue + 四个隔离 Edge context + 真实 API/PG，无 mock |
| 历史五页回归 | **9 段通过**，显式 demo，产物独立留本地 |
| 兼容历史场次 | 上轮 completed session 恢复摘要一致；原手工准备场次仍 publication 0、0 receipt、0 order |

Backend 仍有两条上游 Starlette/httpx、AnyIO deprecation warning，无失败。当前工具：Git 2.51.0.windows.1、Python 3.12.14、uv 0.8.22、Node 24.19.0、pnpm 11.19.0、PostgreSQL 17.11、Edge 153.0.4234.48。没有待用户处理的登录/权限/环境阻塞。

## 新的实际 E2E 轨迹

Session **manual-20e03ef556e74ccf922ee5f832bb5857**：Seller 采购 → 两 Seller 上架 → Buyer 公共/私聊/购买入批次 → pending 时未扣钱 → 最后一件库存只一人成交，另一人 OUT_OF_STOCK → 下一 Tick Seller 看本人销售与私聊并调价/回复 → 同 Tick Buyer 见新报价 → Wait/上下架 → publication 8 实际停 API/PG，再启动并验证摘要不变 → 原 session 继续第二 Round → completed。

最终 **Engine step 2 / publication 16 / 4 订单**。PG 计数：4 bindings、28 batch receipts、33 action receipts、17 publications、263 journal entries。经济摘要 **588c21705cf500bf4d44d2bc82ffd120b0d1206feca8688e303bea6034604237**，与相同 setup/action trace 的上一轮一致。模型速度、HTTP 顺序和墙钟不进入经济结果。

确认请求真实命中 `/api/v1`，POST actions 28 次；停服期间代理 500 为预期故障注入，恢复后继续读取/成交，无 local demo 回退。公共消息可见、私聊隔离、刷新恢复已通过。新截图只使用固定验收数据，见 [12 张截图及报告](../verification/SB-CONSOLIDATE-001/README.md)。截图/自动测试不替代用户亲自验收。

## 手工接手与停止

从零配置和冻结安装见 ENVIRONMENT；已有 5070 从根目录 pg-start 后，两个终端分别 `scripts/platform.ps1 serve` 与 `scripts/run.ps1 frontend`。四个窗口访问 127.0.0.1:5173；新场次用 `scripts/platform.ps1 create-manual`，分别导入输出的 seller-a/seller-b/buyer-1/buyer-2.json。逐 Wave 操作、金额和预期结果见 MANUAL_MARKET。

上轮为用户保留的未运行场次仍可直接使用：**manual-89b7e54ba14b4b808f7647e7906e1123**，凭据仅在本机 `.local/manual/<sid>/`，本次只读检查，未替用户提交任何动作。API 文档为 127.0.0.1:8000/docs；宿主 `inspect -SessionId <sid>` / `recover -SessionId <sid>` 不公开私有数据或 token。

结束时停止本任务服务（8000/4173/5173/55432），保留数据与角色文件。前后端 Ctrl+C，最后 `scripts/platform.ps1 pg-stop`。不通过 Git 同步这些本机数据。

## Known Issues 与下一步

- **失败传播语义后续需正式确认**：保留成功前缀、后续 skipped；本次没有重新定义。
- TEST 有限供应、即时采购/全额结算、共享库存；没有正式消费者/卖方策略、排行榜/奖励、真实时间或完整履约机制。
- 缺席 actor 持续等待；手工 UI 不是正式 HumanDriver。LLMDriver 仅接口与 fake adapter，没有真实 provider。
- 单 worker、完整重放/日志，未验证大规模；无 checkpoint/HA/备份恢复承诺。代码不匹配拒绝历史场次恢复，不能绕过摘要检查。
- 轻量本机 bearer/sessionStorage，不是正式登录/公网凭据治理；inspect/journal 仅可信宿主可看。当前 PG 包装脚本按 5070 无空格路径验证。

推荐顺序：**最小研究 profile/评价契约 → 受控真实 LLM adapter 小试 → 可复现实验运行与审计/指标交付**。理由及研究/工程缺口分层见 ARCHITECTURE。正式 HumanDriver 单独立项。这里只给建议，不自动执行。

本记录所在的收口提交为最新接手点；完整 commit/push 结果在交付回复，避免自引用哈希。换机核对 `git rev-parse HEAD origin/feat/sb-core-skeleton`。本轮完成后停止。
