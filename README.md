# SalesBench

SalesBench 总工程：买方 Web/H5 前端、平台后端与独立 Python 实验内核按职责组织。

当前任务：SB-E2E-001，机器 5070，沿用授权分支 `feat/sb-core-skeleton`。
独立 `engine/` 已实现采购、库存、上架/调价、公开/私聊、购买、资金/订单，以及 Market Wave Runner。每 Round 先采购，再运行固定数量 Tick；V1 每 Tick 为 Seller Strategy → Buyer Action，同 Wave 冻结观察、并发收集、统一执行/发布，正常 Round 结束才推进一次 Engine step。消费者与 Seller 正式策略尚未实现，当前经济行为是 TEST 规则。

Vue 默认通过真实 `sb-platform-v1` 调用 MarketService → Runner → Engine → PostgreSQL。Buyer 保留五页，新增 Seller 工程验收页；消息、购买、采购等先加入本机会的有序草稿，明确提交后等待 Wave 裁决。刷新与服务重启不重置场次；网络失败不回退本地演示。参与者客户端只采用 Web/H5。

手工多角色验收：先启动 PostgreSQL，运行 `pwsh -File scripts/platform.ps1 create-manual`，再分别启动 `scripts/platform.ps1 serve` 与 `scripts/run.ps1 frontend`。在四个标签页/窗口打开 `http://127.0.0.1:5173`，分别导入 `.local/manual/<session>/` 下四个角色文件。详细步骤、完整轨迹与 inspect 命令见 [MANUAL_MARKET.md](docs/MANUAL_MARKET.md)。

## 持久市场服务

先按 [ENVIRONMENT.md](docs/ENVIRONMENT.md) 配好各机独立的 PostgreSQL 与忽略的 `.local/platform.json`。5070 已完成本机初始化；数据不进入 Git。

```powershell
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 install
pwsh -File scripts/platform.ps1 migrate
pwsh -File scripts/platform.ps1 test
pwsh -File scripts/platform.ps1 demo
pwsh -File scripts/platform.ps1 serve
# API 终端 Ctrl+C 后：
pwsh -File scripts/platform.ps1 pg-stop
```

API 仅监听 `127.0.0.1:8000`，PostgreSQL 仅监听 `127.0.0.1:55432`。动作提交先获得 durable pending receipt；同 Wave 收齐后才由 Runner 裁决，并与新 observation version 一起提交。提交结果未知时复用原 ID 查询/重试。数据模型、API、事务/恢复保证与限制见 [PLATFORM.md](docs/PLATFORM.md)，本次结果见 [SB-PLATFORM-001](docs/handoffs/SB-PLATFORM-001.md)。

## 独立 Engine

```powershell
pwsh -File .\scripts\engine.ps1 install
pwsh -File .\scripts\engine.ps1 test
pwsh -File .\scripts\engine.ps1 demo -Seed 7
pwsh -File .\scripts\engine.ps1 runner-demo -Seed 7 -ResolutionSeed 7 -JournalPath .local/wave-trace.json
pwsh -File .\scripts\engine.ps1 replay -JournalPath .local/wave-trace.json
```

使用本机 `.local/runtime.json` 中的 Python 3.12/uv，无需启动任何服务。Runner CLI 使用 ScriptedDriver；LLMDriver 提供可注入异步 ModelAdapter 的请求/预算/结果边界，测试使用 fake adapter，没有真实模型调用。Journal 含私有数据，仅供宿主审计。

内核见 [ENGINE.md](docs/ENGINE.md)，调度、版本、故障和重放见 [RUNNER.md](docs/RUNNER.md)。Engine 独立运行仍不需要平台或数据库。

## 本机快速开始

```powershell
Set-Location D:\SalesBench
pwsh -File .\scripts\run.ps1 frontend
```

打开 http://127.0.0.1:5173 。该终端按 Ctrl+C 停止。当前机器工具路径已保存在忽略的 `.local/runtime.json`。
其他机器先按环境文档配置各自真实工具位置并执行锁定安装。
API 单独启动：`pwsh -File .\scripts\run.ps1 backend`（存在 `.local/platform.json` 时加载数据库配置，需先启动 PG 并迁移）；`GET http://127.0.0.1:8000/health` 只说明进程响应，不是 DB readiness。
完整检查、安装、构建预览和停止方式见环境文档。

- [共同计划](docs/PLAN.md)
- [环境与命令](docs/ENVIRONMENT.md)
- [接口与职责 v0.1 草案](docs/INTERFACES.md)
- [多角色 E2E 任务接力](docs/handoffs/SB-E2E-001.md)
- [历史平台接力](docs/handoffs/SB-PLATFORM-001.md)
- [历史 Runner 接力](docs/handoffs/SB-RUNNER-001.md)
- [历史 Engine 骨架接力](docs/handoffs/SB-CORE-001.md)
- [历史 Vue 验证与截图](docs/verification/SB-002B/README.md)
- [SB-002B 历史接力](docs/handoffs/SB-002B.md)
- [开发约定](AGENTS.md)
- [原型材料](references/ui-v1/2026-09-23/HANDOFF_UI.md)

原型五页固定为：排行榜、商品推荐、公共交流、私聊、我的。
原型和后续本地模拟的排名、推荐、回复、购买均不是正式实验规则。
