# 本地环境与运行

本文件描述当前完整框架，历史安装过程/空间报告见各 handoff。所有命令在仓库根目录的 PowerShell 7 执行；服务只监听 127.0.0.1，单 Uvicorn worker。新机器独立安装依赖、初始化自己的 PG；Git 只同步代码、锁文件和经过检查的文档。

## 工具与目录

| 工具 | 项目要求 / 当前 5070 |
| --- | --- |
| Git | 可 fetch/push 当前任务分支；不修改 main、不重写历史 |
| Node / pnpm | Node >=22.13.0，当前 24.19.0；packageManager 固定 pnpm 11.19.0 |
| Python / uv | Python >=3.12,<3.13，当前 3.12.14；uv 0.8.22 |
| PostgreSQL | 当前验证 17.11，127.0.0.1:55432，UTF8，SCRAM；不以 SQLite 代替 |
| 浏览器 | 使用已有 Edge/Chrome；playwright-core 在锁文件内，不下载浏览器 |

| 路径 | 内容 / 是否同步 |
| --- | --- |
| `.local/runtime.json` | 本机工具绝对路径和缓存根；按 `scripts/runtime.example.json` 填写，忽略 |
| `.local/platform.json` | PG 连接、管理 token、bin/data/log 路径；按 `scripts/platform.example.json` 填写，忽略 |
| `.local/manual/<sid>/` | 含 actor token 的四份角色文件，仅本机保存，忽略 |
| `.local/verification/<kind>/<timestamp>/` | 每次回归截图/结果与宿主诊断，默认忽略 |
| `frontend/node_modules`、`backend/.venv`、`engine/.venv` | 各机按锁重建，忽略 |
| `D:\DevCache\SalesBench` | 5070 pnpm / uv / 浏览器临时缓存，不同步 |
| `D:\DevTools\postgresql\17.11-4\pgsql` | 5070 PG 程序，未安装系统服务 |
| `D:\DevData\SalesBench\postgres-17` | 5070 PG 数据，在 Git/同步目录外；日志为相邻 `postgres-17.log` |

脚本只设置当前进程及子进程的 PATH/环境变量，不改全局 PATH、注册表或系统服务。不要把真实 `.env`、配置/角色 JSON、数据库 dump、完整 journal 放 Git/普通日志。管理 token 不进入浏览器。

## 从零配置新机器

1. 确认目标目录为空或是正确仓库，安全 clone/fetch 后检出最新授权任务分支（当前 `feat/sb-core-skeleton`）；保留陌生修改。当前 main 尚不是完整框架基线，不自行合并。
2. 安装或复用满足上表的工具，优先本机约定工具目录。创建 `.local/`，复制两个 example JSON 为对应的本机文件，填写实际路径。`runtime.json` 的 `browser` 指向现有浏览器可执行文件；不要同步另一台机器的配置。
3. PostgreSQL 使用自己控制的开发 cluster。若数据目录已有 `PG_VERSION`，只核对它，不重新 initdb。全新目录可在交互终端运行（示例路径按本机实际替换）：

```powershell
& 'D:\DevTools\postgresql\17.11-4\pgsql\bin\initdb.exe' `
  -D 'D:\DevData\SalesBench\postgres-17' -U salesbench_owner -W `
  --encoding=UTF8 --locale=C --auth-host=scram-sha-256 --auth-local=scram-sha-256
```

`-W` 交互输入本机密码，不把真实密码写到命令或日志。该本地 bootstrap owner 是开发身份，不是生产最小权限方案。通过可信编辑器设置该 cluster 的 `postgresql.conf`：`listen_addresses = '127.0.0.1'`、`port = 55432`；保留 `fsync` / `synchronous_commit` / `full_page_writes` 为 on。不要改其他工作正在使用的 cluster。

填写 `.local/platform.json` 的 `database_url`（postgresql+psycopg、对应本机 owner/密码/端口、库名 salesbench_platform；密码中的 URL 保留字符需编码）、随机且保密的 `admin_token`、`pg_bin`、`pg_data`、`pg_log`、`pg_port`。当前 pg_ctl 包装器按 Windows 5070 无空格目录验证；使用示例目录风格，路径含空格的支持未验证。示例文件的占位符不能作为实际密码/token。

4. 安装冻结/锁定依赖，建立新库和迁移（不改锁文件迁就工具）：

```powershell
pwsh -File scripts/engine.ps1 install
pwsh -File scripts/run.ps1 install-frontend
pwsh -File scripts/platform.ps1 install
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 init-db
pwsh -File scripts/platform.ps1 migrate
```

`init-db` 只接受 127.0.0.1 的 salesbench_platform，已存在则保留；它不创建 cluster。`migrate` 用 Alembic，应用启动不做自动 DDL。5070 已初始化/建库/迁移，无需重复 initdb。平台测试每次使用独立随机 schema，从空迁移并只清理自己的 schema，不清空手工市场。

Backend 的锁定依赖以 editable path 引用 `../engine`；不需要把 Engine 安装到全局。Engine 0.2.1 零第三方运行时依赖；Backend/前端具体依赖版本以各自 pyproject/package.json 和 uv.lock/pnpm-lock.yaml 为准。本轮无新依赖或锁文件变更。

安装依据：[PostgreSQL Windows](https://www.postgresql.org/download/windows/)、[initdb](https://www.postgresql.org/docs/17/app-initdb.html)、[uv 项目同步](https://docs.astral.sh/uv/concepts/projects/sync/)、[pnpm install](https://pnpm.io/cli/install)。5070 的具体安装与散列记录在 [Platform handoff](handoffs/SB-PLATFORM-001.md) 和历史验收材料中；本文件不要求各机器复制相同目录或凭据。

## 日常启动与停止

```powershell
pwsh -File scripts/platform.ps1 pg-status
pwsh -File scripts/platform.ps1 pg-start  # 仅在未运行时
pwsh -File scripts/platform.ps1 migrate  # SB-METRICS-001 显式升级，保留旧场次
pwsh -File scripts/platform.ps1 create-manual  # 需要新场次时；不重置已有场次
```

两个终端分别执行 `pwsh -File scripts/platform.ps1 serve` 与 `pwsh -File scripts/run.ps1 frontend`。前端 5173，API 8000，PG 55432；四角色导入和完整操作见 [MANUAL_MARKET.md](MANUAL_MARKET.md)。Vite 代理 `/api/v1` 到 localhost API；开发态另有 `/api/health` → `/health`，无宽泛 CORS。

`pwsh -File scripts/run.ps1 build` 后可用 `preview` 在 4173 查看同样真实网络的生产包。默认 network；历史 demo 仅开发时显式 `VITE_BUYER_SERVICE=demo`，不能作为断网回退或真实 E2E 证据。

按各自终端 Ctrl+C 停前后端，最后 `pwsh -File scripts/platform.ps1 pg-stop`；只停本任务拥有的服务，不按端口全局查杀。session 与角色文件保留；重启后重新导入原角色文件或刷新原标签页即可继续/查询，无需重新 create。

## 常用检查与审计

| 目的 | 根目录命令 |
| --- | --- |
| 完整回归（下述全部） | `pwsh -File scripts/run.ps1 check` |
| Engine / Runner | `pwsh -File scripts/engine.ps1 test` |
| PostgreSQL / Backend | `pwsh -File scripts/platform.ps1 test` |
| Vue 类型 / 测试 / 生产构建 | `pwsh -File scripts/run.ps1 typecheck` / `test-frontend` / `build` |
| 生产默认入口 | `pwsh -File scripts/run.ps1 test-preview` |
| 真实四角色 E2E | `pwsh -File scripts/run.ps1 test-market` |
| 历史演示五页回归 | `pwsh -File scripts/run.ps1 test-browser` |
| 只读宿主检查 | `pwsh -File scripts/platform.ps1 inspect -SessionId '<sid>'` |
| 只读重放验证 | `pwsh -File scripts/platform.ps1 recover -SessionId '<sid>'` |
| 宿主指标 / 默认 JSON | `pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>'` |
| CSV 导出（新私有目录） | `pwsh -File scripts/platform.ps1 metrics -SessionId '<sid>' -Format csv -OutDir '.local/metrics/run-01'` |

`check` 顺序执行并在第一次失败时退出；要求依赖已安装、PG 已启动/迁移、8000/4173/5173 空闲。它不安装工具、不偷偷跳过 DB 测试。`test-market` 创建自己的持久场次，用四个隔离浏览器 context 操作真实生产 Vue/API/PG，**实际重启配置的开发 PG**。不要在其他任务使用该 PG 时执行；测试清理自己的 API/preview/browser，PG 留给调用方显式停止。

浏览器各次产物默认写 `.local/verification/<kind>/<timestamp>/`；不会覆盖 `docs/verification/` 中已验收证据。需要保存任务证据时加 `-EvidenceDir docs/verification/<任务编号>`；`check` 仅把真实 market/preview 放入该目录，历史 demo 仍留 `.local`。完整 inspect 和失败截图永远留本地；提交前检查输出，不导出凭据/全量私有数据。

独立 demo：`scripts/engine.ps1 demo` / `runner-demo -JournalPath .local/wave-trace.json` / `replay -JournalPath .local/wave-trace.json`；journal 父目录须存在且含私密观察，不能上传。`platform.ps1 demo` 是自动脚本 smoke，不是给人工操作者的场次；人工场次用 create-manual。

`run.ps1 backend/install-backend/test-backend` 保留为旧命令兼容入口；完整平台推荐统一使用 platform.ps1。未配置平台时 `/health` 可正常而市场 API 返回 503；`scripts/verify-health.ps1` 仅历史进程/代理 smoke，不代替完整回归。

## 常见接手问题

- 端口占用：确认原进程归属，停止自己的旧终端或保留现场；不要自动杀别人的服务。
- 等待其他参与者：到对应 Seller/Buyer 的窗口明确提交，未提交不是 Wait。
- stale / price / revision 失败：检查新观察，清理旧草稿后重新决定；unknown 必须先查原 receipt，不用新 ID 猜测成交。
- 恢复源码不匹配：检出创建该 session 的对应 Engine 版本；禁止绕过摘要检查或把 snapshot 当恢复数据。
- 工具/依赖不匹配：核对本机配置与锁文件，不更新锁文件掩盖环境问题。
- PG/API 重启：保留同 session 和 token，先 PG 后 API；没有自动恢复已损坏数据、备份或 HA 保证。
- 旧场次榜单未启用：sb_metrics_001 不补造历史，迁移后 create-manual 建新场次即可。METRICS_POLICY_MISMATCH 必须核对创建该场次的计算器版本，不静默替换口径。宿主指标/导出含私有财务，普通材料留 `.local`，见 METRICS.md。
