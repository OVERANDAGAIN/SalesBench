# SB-CORE-001 接力记录

- 唯一执行端：5070；工程 `D:\SalesBench`；任务分支 `feat/sb-core-skeleton`。
- 基线：main 与 origin/main 均为 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。开工 fetch 后一致，工作区干净，无陌生修改。
- 授权：建设独立 Engine，运行测试/示例，commit/push 本任务分支；不修改或 push main，不进入业务 API/数据库/Vue 联调。
- 目录：`engine/src/salesbench_engine`，独立 pyproject/uv.lock/虚拟环境。零运行时第三方依赖，标准库 unittest；构建使用现有 uv 内置且固定的 uv_build 0.8.22。
- A：领域、动作定义、角色观察、不可变快照、初始状态校验完成；独立锁定安装和 6 项测试通过。
- B：状态转移、策略与行为测试待完成。
- C：完整 scenario、ENGINE.md 和交付复查待完成。
- 新增长期约定：参与者与未来 Seller 人工界面仅 Web/H5，Engine 无 UI，不建设桌面原生客户端。

运行基础测试：`pwsh -File scripts/engine.ps1 test`。使用各机器 `.local/runtime.json` 中真实 Python 3.12/uv 路径，不同步依赖或缓存。
