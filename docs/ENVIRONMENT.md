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
