# SB-PLATFORM-001 接手记录

2026-09-24，执行端 **5070**，工程 **`D:\SalesBench`**。用户在验收 SB-RUNNER-001 后授权建设 Persistent Market Service；没有改变研究 protocol，没有接入 Vue/真实 LLM/HumanDriver。

## Git 与接手点

- 当前授权分支 `feat/sb-core-skeleton`，开工 HEAD / origin 分支为 `be7bb73335d2c59f22035aef5ceca564f863184a`；fetch 后 ahead/behind 0/0。
- main / origin/main 保持 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`，没有修改、推送、合并、变基或强推 main。
- 开工无陌生已跟踪修改；`.idea/` 的 6 个用户未跟踪文件保留，收尾 SHA-256 与开工记录全部相同，没有暂存它们。
- 本记录所在的平台交付提交为接手点；最终完整 commit 和 push 结果由交付回复报告。换机先核对 `git rev-parse HEAD origin/feat/sb-core-skeleton`，只依赖 Git 代码和文档，不同步本机数据库/缓存/凭据。

## 交付结构与数据

- `backend/app/service.py`：统一 MarketService，创建/actor binding、观察/receipt、持久 submit、fenced claim、一次性 Runner 候选、事务提交和恢复。
- `backend/app/api.py` / `contracts.py`：`sb-platform-v1` HTTP envelope、管理/actor bearer、授权读取、有限批次提交、receipt、runtime 和通知游标。
- `backend/app/persistence.py` / `migrations/`：SQLAlchemy 10 张业务表、Alembic `sb_platform_001`，PostgreSQL JSONB 保存 canonical transcript 与读取投影。
- `backend/app/main.py`：一个 Uvicorn worker 的后台推进；只读 DB 已提交状态，/health 仍仅检查进程响应；启动不会自动做 DDL。
- `backend/app/cli.py` / `scripts/platform.ps1`：本机建库、迁移、测试、serve、demo、recover、PG 启停。`scripts/run.ps1` 后端入口会加载本机平台配置。
- Engine **0.2.1**：新增 `Boundary`、`advance_boundary`、`pending_observations`、`restore_committed`；原完整 run 使用同一执行路径。没有改领域经济规则、采购节奏、Wave 内容、purchase priority、资金/库存或 revision 语义，运行时仍零第三方依赖。

权威恢复材料是 manifest setup + 已提交 Runner journal。Listing 版本、账户、库存、订单、消息、事件/ID 从原 Engine 确定性重放恢复。数据库不重新计算任何 purchase。SQL 中另存 batch/action receipt、resolution、semantic event、publication、本人 projection 和 outbox，方便访问和审计。完整数据模型/API 见 [PLATFORM.md](../PLATFORM.md)。

## 事务和恢复能力

durable submit 先提交意图；同 Wave 齐备后短事务 claim fence，锁外恢复并执行一个既有边界，再锁 session 核对 fence/base version/base trace。只有当前 writer 可将 journal、结果、回执、授权 projection、runtime 和通知在同一事务提交。HTTP 从不读取候选 Runner 的中间发布。

- Engine 执行后 DB commit 失败：候选丢弃，从上次 committed transcript 恢复。
- commit acknowledgement 丢失：返回 COMMIT_UNKNOWN，保留原 request ID/内容，查 DB receipt；不盲目重复成交。
- commit 成功后进程退出：新进程读取已落库的同一 receipt/projection/outbox，无二次内存 publish。
- 每场 fencing 阻止旧 writer 晚提交；相同请求的 DB 主键与相同机会的唯一约束阻止跨进程重复消费。
- 旧 observation 明确持久拒绝；旧 price/offer revision 最终由 Engine 的 PRICE_CHANGED/STALE_LISTING 拒绝。
- 重启可继续尚未收齐的 Wave；已完成/已失败 session 保持终态。Round close 重试只推进一次 step。
- 原 Runner 可记录的 action fault 保留审计前缀但不发布部分 Wave；actor receipt 为 aborted。无法按 restore contract 重放的失败候选不提交，上一边界保留。
- 损坏 trace、源码或规则版本不一致明确失败关闭。没有 snapshot 反序列化、自动 trace 升级或忽略校验。

## 本次实测

| 验证 | 实际结果 |
| --- | --- |
| 独立 Engine / Runner | **64 项 unittest 全部通过**（原 61 + 边界恢复 3） |
| 后端平台 / health | **27 项 pytest 全部通过**；真实 PostgreSQL，不使用 SQLite，不跳过持久测试 |
| 空库迁移 | 本机新库从空 `upgrade head` 成功；每个集成测试从空随机 schema 迁移；Alembic check 与模型一致 |
| 两个真实客户端 | 两个 localhost httpx 客户端访问同一 Uvicorn session、相同公开版本、独立资金/私聊；原进程退出后新进程继续 pending Wave |
| 幂等 / 故障 | 并发跨 service 重复 purchase；intent/boundary COMMIT 前/后 acknowledgement 故障；子进程 os._exit 在提交前/后强制退出，均无重复成交 |
| 提交一致性 | 旧 fenced candidate 拒绝；候选提交被阻塞时 reader 仍见完整旧版本；完成后 receipt/publication/projection/outbox 一致 |
| 经济与权限 | 最后库存竞争、旧价格/ABA revision、私聊/经营数据/receipt/session 隔离、禁止伪造 actor；业务失败/skipped 保持原语义 |
| 恢复与时钟 | 每边界 trace 重放、部分 Wave 重启、Round close unknown 不重复 advance、action fault 成功前缀审计、不可重放故障保留上个边界 |
| 数据库实际重启 | demo 完成后 pg-stop → pg-start → 新进程 recover，版本与经济状态摘要一致 |
| 打包 / 独立性 | Engine 0.2.1 wheel/sdist 构建；独立新 venv 仅安装该 wheel，`python -I` Runner demo/replay 成功，经济摘要与旧 Runner demo 基线一致 |
| 范围与工作区 | frontend/references 无改动，不重复 UI/浏览器验收；`.idea/` 6 文件哈希不变；未改 main |

测试有 2 条上游 deprecation warning（Starlette TestClient 的 httpx 兼容路径、AnyIO BlockingPortal alias），不影响通过；没有为消除警告新增 httpx2 或改变既有 HTTP 工具。日志在忽略的 `.local/SB-PLATFORM-001/`；这些本机日志不是跨机交付依赖。实际 TCP/Uvicorn 重启测试由自己创建的 PID 启停，不终止其他服务。

## Demo 轨迹

```powershell
pwsh -File scripts/platform.ps1 pg-start
pwsh -File scripts/platform.ps1 install
pwsh -File scripts/platform.ps1 migrate
pwsh -File scripts/platform.ps1 demo
pwsh -File scripts/platform.ps1 recover -SessionId '<demo 的 session_id>'
pwsh -File scripts/platform.ps1 serve
# serve Ctrl+C 后：
pwsh -File scripts/platform.ps1 pg-stop
```

平台 demo 的所有 actor 都通过 MarketService observe/submit，使用持久化批次进入 Runner；1 Supplier、3 Seller、4 Buyer、2 Product、2 Round × 3 Tick。初始 publication 0；14 次 Wave 提交 + 2 次 Round close 后为 publication **16**，Engine step **2**。

| 位置 | 成交 | 报价版本 | 其他 Buyer |
| --- | --- | --- | --- |
| R1/T1 Buyer Wave | buyer-1，1 件，300 分 | 1 | 库存不足，不重复扣款 |
| R2/T1 Buyer Wave | buyer-1，1 件，350 分 | 2 | 库存不足，不重复扣款 |

本机实际 session：`demo-36ea072eb86e456ca1cf9ab550bdf387`；完整经济状态摘要 **`38150e789f73e93e5b8a1e40a598c27260163d8ce7e3bae06417ce53fcb9700d`**。完成后新进程恢复、实际 PG 停止/启动后恢复均相同。该 session 数据只存在本机，换机重新跑 demo 会创建新 session ID。CLI 不输出 token 或全量私有 journal。

平台 demo 与历史 Runner CLI 的测试消息文字略不同，因此全状态摘要不同；独立 Runner CLI 本次仍得到历史摘要 `fc5ea7d4858dd5124cfd135333004452cb3071590f5f6bcdcc5709da76e005be`，不把不同输入的摘要差异当 protocol 变化。

## 本机环境与服务收尾

实际 Python **3.12.14**、uv **0.8.22**、PostgreSQL **17.11**（EDB 17.11-4）、SQLAlchemy **2.0.54**、Alembic **1.20.0**、psycopg **3.3.6**。backend 与 engine 锁定安装均成功。无需登录/管理员权限；没有尚待用户处理的环境阻塞。

工具 `D:\DevTools\postgresql\17.11-4\pgsql`，数据 `D:\DevData\SalesBench\postgres-17`，日志同级 `postgres-17.log`；数据库 `salesbench_platform`。连接/随机管理 token 仅在忽略的 `.local/platform.json`，工具路径在 `.local/runtime.json`，不能提交/复制凭据。详情与来源见 [ENVIRONMENT.md](../ENVIRONMENT.md)。

收尾时已停止本任务 PostgreSQL，API 测试进程均清理；**8000 / 55432 无监听**，数据目录保留。仅有本地启动命令，无 Windows 自动服务。重新使用先 pg-start，数据不需重新初始化。

空间保守统计：PG 程序 141,033,226 bytes、ZIP 379,726,839、数据 71,178,064；加整个 backend venv 62,726,418、uv 缓存 69,475,264、本任务 `.local` 2,395,228，合计约 0.68 GiB，包含既有后端/uv 内容，低于新增 5 GiB 上限；文件逻辑长度可能重复计数硬链接，不宣称物理占用精确值。没有模型/GPU/浏览器/Docker/WSL/Redis/Celery/Kafka。

## Known Issues / Protocol Debt 与下一接手点

1. **失败传播语义后续需正式确认**；保留 V1 成功前缀 + 尾部 skipped，没有重新设计。
2. 只保证文档列明的本地 DB durable boundary / 重启模式；不保证磁盘丢失/数据库损坏/备份灾备、分布式高可用或恶意数据篡改。未知实现 bug 不自动修复，源码/trace 不匹配需要对应版本。
3. 完整历史重放和 JSONB 观察适合小实验，未做规模优化/压缩/检查点。fencing 不代表多 worker 的吞吐或公平进展承诺；运行基线仍单 worker。
4. 缺输入持续 pending；无自动代填 Wait、HumanDriver、真实 provider，未定义新 deadline 研究语义。
5. actor token 是最小 session binding，非正式用户登录系统；管理 token、开发 DB owner 和 localhost 配置不能当生产部署方案。
6. outbox 已持久化，但只有轮询通知边界，没有 WebSocket/SSE、delivery daemon 或网络 exactly-once；failed runtime 可在 publication 不变时改变，客户端需查 receipt/runtime。
7. Vue 仍使用原 BuyerService 本地演示。真实 API 与旧 v0.1 草案待映射项为 Listing/purchase revision、机会批次、publication/offer/content/通知版本、逻辑时间、unknown receipt、用户与 actor 身份；本任务不承担完整 Vue 联调。
8. 经济规则、消费者/Seller 策略仍是原 TEST 范围；不加入正式排行榜/奖励/物流/退款/税费。

已具备下一任务通过该 application boundary 接入 Vue 或 Agent 的基础，接手先读 PLATFORM.md，核对分支与本机配置，pg-start/migrate 后运行平台与独立 Engine 测试。本任务在此停止；后续接入或研究机制变更必须等待新指令。
