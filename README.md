# SalesBench

SalesBench 是一个本地可持久运行的多角色市场实验框架：Vue/H5 Buyer 与 Seller → FastAPI / MarketService → Runner → Engine，PostgreSQL 保存已提交的意图、回执、授权投影与恢复记录。尚未接真实 LLM 或正式 Consumer Model / Seller Policy，当前经济行为明确属于 TEST 规则。

当前任务 **SB-METRICS-001**，执行端 5070，分支 **`feat/sb-core-skeleton`**。已接入持久化开发利润榜与宿主研究指标；不是正式 benchmark 评分。完整框架在该任务分支；`main` 保留早期 UI 验收基线，没有自动合并。接手前先 fetch，核对分支/HEAD/工作区与 [最新 handoff](docs/handoffs/SB-METRICS-001.md)，保留陌生修改。

## 先看什么

- [项目总览与架构](docs/ARCHITECTURE.md)：模块职责、唯一经济逻辑、时间/版本、已完成/未完成、后续三个里程碑。
- [环境与从零配置](docs/ENVIRONMENT.md)：各机独立工具/依赖/PG、常用命令、停止方式。
- [四角色手工市场](docs/MANUAL_MARKET.md)：创建场次、绑定四个窗口、逐 Wave 操作及 inspect。
- [当前接口](docs/INTERFACES.md)、[Engine](docs/ENGINE.md)、[Runner](docs/RUNNER.md)、[Platform](docs/PLATFORM.md)：各层技术契约。
- [利润榜与 Metrics](docs/METRICS.md)：开发口径、Tick Close 版本、宿主 API/JSON/CSV 与历史兼容边界。
- [计划](docs/PLAN.md)、[开发约定](AGENTS.md)、[本次实测证据](docs/verification/SB-METRICS-001/README.md)。历史只需按需查 handoff，无需聊天记录。

## 本机启动

在 `D:\SalesBench` 的 PowerShell 7 中运行。5070 的工具、依赖、PG cluster 和库已配置；新机器先完成 ENVIRONMENT，不复制 `.local`、数据库、node_modules 或 `.venv`。

```powershell
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 migrate  # 升级现有库，保留旧场次
pwsh -File scripts/platform.ps1 create-manual
```

两个终端分别启动（各自 Ctrl+C 停止）：

```powershell
pwsh -File scripts/platform.ps1 serve
```

```powershell
pwsh -File scripts/run.ps1 frontend
```

四个窗口访问 http://127.0.0.1:5173 ，分别导入 create-manual 输出目录中的四份角色 JSON。每人明确提交有限批次；未提交持续等待，不能自动视作 Wait。默认与生产构建均使用真实平台；网络故障无 demo 回退。

API 文档 http://127.0.0.1:8000/docs 。`/health` 仅说明 API 进程响应，不证明数据库/场次可恢复。

```powershell
pwsh -File scripts/platform.ps1 inspect -SessionId '<session_id>'
pwsh -File scripts/platform.ps1 metrics -SessionId '<session_id>'
# 前后端终端 Ctrl+C 后，仅停止自己使用的开发 PG：
pwsh -File scripts/platform.ps1 pg-stop
```

## 回归与独立运行

依赖已按锁文件安装、PG 已启动并迁移，8000/4173/5173 空闲时，一条命令跑完整系统回归：

```powershell
pwsh -File scripts/run.ps1 check
```

包含 Engine/Runner、真实 PG 后端、Vue typecheck/tests/build、生产预览、真实四角色 E2E 和历史 UI 回归。**真实 E2E 会重启配置的开发 PostgreSQL**，不要与其他使用该 PG 的工作同时运行；结束自行 pg-stop。失败即停止，未执行项目不能算通过。浏览器使用已有 Edge/Chrome，不下载浏览器。

普通回归产物默认写 `.local/verification/<kind>/<timestamp>/`，不覆盖历史验收截图。显式保存本轮公开验收材料：`check -EvidenceDir docs/verification/<任务编号>`；宿主 inspect/失败诊断仍留在 `.local`。加入 Git 前检查凭据及私有内容。

独立 Engine/Runner 无需任何服务：

```powershell
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/engine.ps1 runner-demo -JournalPath .local/wave-trace.json
pwsh -File scripts/engine.ps1 replay -JournalPath .local/wave-trace.json
```

参与者客户端只采用 Web/H5。当前不接真实模型、不建设 HumanDriver、正式排名/奖励/履约或公网服务；批次失败传播保留为 Protocol Debt。详细边界与下一步见项目总览。
