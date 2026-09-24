# SB-METRICS-001 — Profit Leaderboard & Research Metrics

2026-09-24，执行端 5070，目录 `D:\SalesBench`。授权分支 `feat/sb-core-skeleton`；开工 HEAD 与 origin 一致：`7807df8d20a8c0f77e680bd099af262ba02c217e`。main/origin/main 保留 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。本 handoff 随任务代码提交，准确提交可用 `git log -1 --format=%H -- docs/handoffs/SB-METRICS-001.md` 获取；跨机接手必须 fetch 核对 origin。

## 交付

- `backend/app/metrics.py` 唯一事实统计：开发利润、现金差不变量、稳定排名/previous_rank、Seller/Buyer/session 指标、价格/利润/排名/Tick 轨迹。
- `metric_store.py` 从 committed transcript 校验恢复后物化，持久映射 publication→榜单；经济提交后退出或指标 commit-unknown 可补齐，有限重读关闭观察竞态。
- `sb_metrics_001` 显式迁移：market_sessions.metrics_policy、leaderboard_snapshots、metric_snapshots；无经济表副本/trigger。已升级本机现有库，保留旧 session；空 schema 迁移测试通过。
- `dev_cash_profit_v1` / policy_version 1 / `sb-metrics-v1`；默认 tick_close，可明确选 round_close。初始 0；采购/Seller Wave 不公开刷新，Tick Close 出版本，completed 沿用最终榜。与实验 protocol 独立固定版本。
- 管理 bearer 两个 GET：`/api/v1/admin/sessions/{sid}/metrics` 和 `/leaderboard`，支持 publication_version 历史查询；actor bearer 403。CLI `platform.ps1 metrics` 与 JSON/CSV，白名单导出无私聊正文/token/raw journal。
- Buyer 原排行榜与 Seller 工程页共用顶层 observation.leaderboard；显示开发口径、来源 Round/Tick/publication、排名变化。推荐顺序不绑定排名，Vue 不计算利润。
- 更新 README/ARCHITECTURE/INTERFACES/PLATFORM/PLAN/ENVIRONMENT/MANUAL_MARKET/AGENTS；详细口径及恢复约定集中在 [METRICS.md](../METRICS.md)。

## 实测

完整 `scripts/run.ps1 check`：Engine/Runner **64**、Backend/真实 PG **45**、Vue **28** 均通过；类型/生产构建、真实默认预览、真实四角色 E2E、历史 UI 回归通过。真实 E2E 包含库存竞争失败、pending、权限、负利润/平局、同 snapshot、刷新、API/PG 重启、CLI/API/导出一致。原依赖两条弃用警告保留，无新依赖或锁文件改动。

本次 completed session：`manual-67b69526cc514dcc9d74fbc0fd354454`。最终 4 单、GMV 1700 分；A 收入1200/采购300/利润900，B 收入500/采购300/利润200。17 publications / 17 metric snapshots / 7 boards，完整重放所有历史一致。榜单变化与截图/样例见 [验收材料](../verification/SB-METRICS-001/README.md)。

另准备未行动的新 metrics-enabled session：`manual-f65ea2bd108b439b8310bbc3790305b4`，publication 0。四份私有角色文件在 `.local/manual/manual-f65ea2bd108b439b8310bbc3790305b4/`，按文件名导入四个窗口即可；不打印或提交 token。此前所有场次与绑定保留。

## 继续使用

```powershell
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 migrate
# 两个终端分别运行：
pwsh -File scripts/platform.ps1 serve
pwsh -File scripts/run.ps1 frontend
# 需要新场次时才创建：
pwsh -File scripts/platform.ps1 create-manual
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>'
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>' -Format json -OutDir '.local/metrics/run-01-json'
pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>' -Format csv -OutDir '.local/metrics/run-01-csv'
```

Vue 127.0.0.1:5173、API/docs 8000、PG 55432。实际四角色逐 Wave 操作与利润变化表见 MANUAL_MARKET。收尾停止本任务 API/preview/browser/PG；重新使用先 pg-start。依赖/数据库/凭据不跨机同步。

## Known Issues / Protocol Debt

1. **失败传播语义后续需正式确认**：本轮完全保留 V1 成功前缀/失败后 skipped，统计遵从 trace；技术失败前缀只属宿主审计，公开榜不更新。
2. 开发利润是收入−采购支出，未售库存不估值，非正式利润/总分/reward。正式评价、库存成本/估值、履约费用及研究公平性待确认；负利润和平局 ID 顺序不代表正式模型优劣。
3. 旧 session NULL policy 不补造榜单，使用原市场恢复能力；新公式/源码摘要不匹配 fail closed，目前没有历史指标升级器。需固定对应源码，禁止绕过 guard。
4. 经济事务与指标物化分两次提交：receipt 已成交不因指标错误回滚；读取补齐或明确 503。首次补齐锁 session 并完整 replay，面向单机小市场，未做 checkpoint/规模保证。
5. 无真实 LLM、Consumer Model、正式 SellerPolicy、RecommendationPolicy、HumanDriver、综合奖励、WS/SSE 或公网部署。未改变 Engine/Runner 源码和研究协议。
6. DB/角色文件仍为本机开发权限边界；宿主 metrics 虽无消息正文和凭据，仍含财务私有信息，不可给参与者下载。哈希不保护恶意 DB 管理员，原备份/HA/灾难恢复限制继续存在。

本任务结束，不自动进入下一研究或模型阶段。
