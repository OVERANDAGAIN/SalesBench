# 环境与运行

基线：Windows 11 x64 / PowerShell 7.6.5 / Git 2.55.0.windows.5。
已实测 Node 24.19.0、pnpm 11.19.0、Python 3.12.14 可执行。Node 24 为 LTS，符合 Vite 的 Node 要求。
当前普通 Python 命令可能命中 WindowsApps 别名，使用明确的真实解释器路径。
本机工具位置将写入忽略的 `.local/runtime.json`，不写入公共启动配置。

依赖位置：`frontend/node_modules`、`backend/.venv`。
缓存位置：`D:\DevCache\SalesBench`；固定版本 uv 安装到 `D:\DevTools\uv`。
初始两处均不存在；本轮新增总上限 5 GiB。空间记录在任务交接中维护。

Syncthing 默认配置仅覆盖 `D:\Syncthing`，未覆盖工程目录；未全面排除其他同步规则。
不要把 Git 工作副本放入文件自动同步目录，也不要同步环境、缓存和数据库。

## 数据库方案（未实施）

阶段 2B 只确认方案。无现成实例时，后续优先使用 Windows 原生 PostgreSQL 17 受支持补丁版本。
有可复用实例时先核对接入和版本。数据目录在仓库及同步目录外。
本轮不安装/启动 PostgreSQL、Docker、WSL；不创建数据库、业务表、SQLAlchemy 模型或 Alembic 迁移。

## 官方依据

- https://vite.dev/guide/
- https://nodejs.org/en/about/previous-releases
- https://docs.astral.sh/uv/getting-started/installation/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://pnpm.io/cli/install
- https://www.postgresql.org/support/versioning/

## 本机启动与检查

在总目录打开 PowerShell。`.local/runtime.json` 已配置本机真实工具位置，未进入 Git；换机器参照 `scripts/runtime.example.json` 自行填写或让工具在该机器 PATH 中可用。
脚本只为子进程补充 Node 搜索路径，不修改全局 PATH。uv 固定为 0.8.22，官方 ZIP SHA-256 为 `5049375aa2a5162f132b2c1cb992e25d42d47d934cab8c174dbe6f60973dcc12`。

```powershell
Set-Location D:\SalesBench
pwsh -File .\scripts\run.ps1 install-frontend
pwsh -File .\scripts\run.ps1 install-backend
pwsh -File .\scripts\run.ps1 typecheck
pwsh -File .\scripts\run.ps1 build
pwsh -File .\scripts\run.ps1 test-backend
pwsh -File .\scripts\verify-health.ps1
```

两个终端分别启动，按各自终端的 Ctrl+C 停止：

```powershell
pwsh -File .\scripts\run.ps1 frontend
pwsh -File .\scripts\run.ps1 backend
```

前端 `http://127.0.0.1:5173`；后端 `http://127.0.0.1:8000/health`。
开发代理仅 `/api/health` → `/health`，无宽泛 CORS。健康结果为 `{"status":"ok","scope":"api_process"}`。
构建预览：`pwsh -File .\scripts\run.ps1 preview`，地址 `http://127.0.0.1:4173`。
健康验证脚本会检查端口空闲，启动、重启并停止自己的进程；已有端口占用则退出，不终止其他程序。

## 依赖锁定与版本

- Vue 3.5.43、TypeScript 5.9.3、Vite 7.3.6、Vue 插件 6.0.9、vue-tsc 3.3.11、Vitest 3.2.7；使用 pnpm 11.19.0。
- Python 3.12；FastAPI 0.141.1、Uvicorn 0.53.0；开发测试 pytest 9.1.1、httpx 0.28.1。
- 首次解析保存 `frontend/pnpm-lock.yaml` 和 `backend/uv.lock`。以后安装默认 `--frozen-lockfile` / `--locked`，uv 禁止自动下载其他 Python。
- 没有 SQLAlchemy、Alembic、数据库驱动、训练依赖或模型权重。
- pnpm 11 当前实际 store 位于配置的 `PNPM_HOME/store/v11`，即本机 `D:\DevCache\SalesBench\pnpm-home\store\v11`。uv cache 位于该缓存根下的 `uv`。
- 官方 uv ZIP 保留在缓存根下 `downloads`，安装位置 `D:\DevTools\uv\0.8.22`；未修改全局安装或系统配置。
