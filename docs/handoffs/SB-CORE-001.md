# SB-CORE-001 接力记录

- 唯一执行端：5070；工程 `D:\SalesBench`；任务分支 `feat/sb-core-skeleton`。
- 基线：main 与 origin/main 均为 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。开工 fetch 后一致，工作区干净，无陌生修改。
- 授权：建设独立 Engine，运行测试/示例，commit/push 本任务分支；不修改或 push main，不进入业务 API/数据库/Vue 联调。
- 目录：`engine/src/salesbench_engine`，独立 pyproject/uv.lock/虚拟环境。零运行时第三方依赖，标准库 unittest；构建使用现有 uv 内置且固定的 uv_build 0.8.22。
- A：领域、动作定义、角色观察、不可变快照、初始状态校验完成；独立锁定安装和 6 项测试通过。
- A 提交 `583b3df` 已推送并建立远端跟踪；首次直连推送遇到连接重置，使用机器已有代理对单次 Git 命令重试成功，没有修改全局代理配置。
- B：采购、Listing 创建/更新/停售、公开/私聊、购买、等待、step 和脚本策略完成。32 项测试通过，包含资金/货物守恒、异常注入回滚、权限隔离和最后一件库存并发购买。
- B 提交 `ff617d7` 已推送。
- C：完整两轮 scenario、ENGINE.md、接口对照、共同约定、README/PLAN/ENVIRONMENT 更新和交付复查完成。
- 新增长期约定：参与者与未来 Seller 人工界面仅 Web/H5，Engine 无 UI，不建设桌面原生客户端。

## 运行与实测

使用各机器 `.local/runtime.json` 中真实 Python 3.12/uv 路径，不同步依赖或缓存。在根目录运行：

```powershell
pwsh -File scripts/engine.ps1 install
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/engine.ps1 demo -Seed 7
pwsh -File scripts/engine.ps1 build
```

- Engine 36 项 unittest 全部通过；包括用户要求的采购、资金失败、Listing、权限、公开/私聊、购买/失败原子性、step 和同 seed 重现，并覆盖异常注入回滚、共享库存和最后一件商品并发购买。
- 原后端 pytest 2 项通过。frontend/backend 的源码、锁文件和既有启动脚本与 main 无差异，不重复 Vue 视觉验收或浏览器自动化。
- seed=7：两轮购买、2 个订单、2 次采购、2 个 Listing、公开/私聊各 2 条、14 个事件，最终 step=1。Buyer 余额 950 分，Seller 2250 分，Supplier 800 分，另一 Buyer 1000 分；库存 cup=2 / bag=1。
- CLI 在仓库外使用已安装 Engine 和 Python -I 执行成功；相同 seed 全部输出一致，没有改动全局 RNG。
- wheel/sdist 均构建成功；在 `.local/SB-CORE-001/package-check` 全新环境中只安装 wheel，从 backend 目录以 Python -I 导入 Engine 并执行完整场景成功。该环境中没有 FastAPI/SQLAlchemy，也没有修改 backend 环境。
- Engine uv.lock 仅包含本地包，零运行时第三方依赖；构建复用 uv 自带后端，没有下载新增开发依赖。依赖/构建输出和日志位于忽略目录，没有新服务或监听端口。
- 检查过程中修正了场景测试误计的事件数（正确为 14），并使观察拒绝不适用的筛选参数；最终测试全部通过，没有待修复失败。

## 接口和后续限制

即时采购/结算/履约、有限供给、共享库存、示例时序、脚本回复和成交额榜单均为 TEST 规则。正式消费者、Seller/Supplier 策略、时间尺度、奖励、推荐、履约及复杂结算仍未定。

Engine 用 listing_id、step、同步 Result 和带 audience 的事件；Vue v0.1 用 productId、UTC、异步 receipt/revision/subscribe。差异表见 ENGINE.md，没有把草案升级成正式 API。

具备进入“FastAPI + PostgreSQL 调用真实 Engine”集成开发的基础，但尚无真实共享平台。下一任务必须先确定 DTO、认证/场次绑定、持久幂等、状态恢复/版本、跨进程单写者和数据库提交失败时的 Engine 发布边界。本任务完成后停止，不自动实施后续阶段。

验收基线 main 保持 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。本交接记录所在的 C 收尾提交为可接手最终代码；用 `git rev-parse HEAD` 获取完整哈希并核对 `origin/feat/sb-core-skeleton`，不依赖文档自引用哈希或其他机器临时目录。
