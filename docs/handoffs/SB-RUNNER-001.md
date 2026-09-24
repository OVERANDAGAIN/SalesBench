# SB-RUNNER-001 接手记录

2026-09-24，执行端 **5070**，实际工程 `D:\SalesBench`。任务：Market Wave Runner；用户确认 LLM-first 的 Round → Tick → configurable Wave，V1 为 SELLER_STRATEGY → BUYER_ACTION。

## Git 与接手点

- 沿用本次用户授权的当前任务分支 `feat/sb-core-skeleton`，没有创建新分支、合并/变基/修改 main。
- 开工 HEAD 与 origin 任务分支均为 `c22978001cabb8613919b1daf2ba3eec01ed5eff`；fetch 后 ahead/behind 0/0。该点回退此前协议文档，文件树与 Engine 交付 `d3cbc0352d85b1c6a1ca84472265a95f7efe5383` 一致。
- main 与 origin/main 保持用户验收基线 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`。
- 开工没有陌生已跟踪修改；`.idea/` 有 6 个用户未跟踪文件，保留且不暂存。结束前 SHA-256 与开工记录逐一一致，不宣称整个工作区无未跟踪文件。
- 本记录所在的 Runner 交付提交是可接手点。用 `git rev-parse HEAD origin/feat/sb-core-skeleton` 核对本地/远端同一完整哈希；最终实际提交与 push 结果由本次交付回复报告，不写自引用哈希。

## 已完成内容

独立 Runner 在 `engine/src/salesbench_engine/runner/`，模块职责、协议与限制见 [RUNNER.md](../RUNNER.md)。Engine 包升级至 0.2.0，运行时依赖仍为零；锁文件仅改本地包版本。

实现 Round 采购、固定 Tick、配置化 Wave 定义及状态机；同 Wave 授权冻结观察、并发 Driver 收集、执行中不公开中间状态、正常 Wave 统一发布；有限有序动作批次、确定性全 Wave 购买顺序、单进程动作去重；observation/action/result/resolution journal；初始 setup + recorded trace 的确定性重放。正常 Round 只调用一次 Engine.advance(1)，没有真实时间推进。

ScriptedDriver 与 LLMDriver 使用相同批次校验链。LLMDriver 有具体请求构造、注入 ModelAdapter、token 预算和元数据记录，通过异步 fake adapter 测试。没有真实模型 SDK、provider 配置、凭据或实际模型调用。

Engine 改动限定为 Listing 的 offer/content revision、Purchase 必填 expected_offer_revision、Engine 内报价版本校验和 Order 固化成交版本；既有示例与测试迁移到新构造器。金额/库存/权限/单动作原子性仍由 Engine 负责。Offer revision 对实际改价/上下架递增，content revision 对实际描述改变递增，同值赋值/库存变化不增加报价版本，ABA 旧报价失败。

frontend、backend、references 与开工点无差异；没有新 API、数据库、网络适配器、桌面客户端或服务端口。无须重复既有 Vue 视觉验收、浏览器、前后端构建或 health；本次不把历史验证算成本次结果。

## 验证

运行使用已有 Python **3.12.14**、uv **0.8.22**、PowerShell **7.6.5** 和 `.local/runtime.json`。锁定安装成功，没有新增第三方依赖或更改全局 PATH/系统设置。

| 检查 | 本次结果 |
| --- | --- |
| `pwsh -File scripts/engine.ps1 test` | **61 项 unittest 全部通过**（原 36 + 报价版本 3 + Runner/Driver 22） |
| 正反模型完成顺序 / 并发度 1 与 4 / 不同 provider 元数据 | 相同意图下经济状态、发布、purchase winner 和逻辑 journal 一致 |
| 冻结观察与权限 | 多 Seller/Buyer 同 public 对象，各自账户/库存/私聊隔离；快返回不提前执行；执行中仍读旧发布 |
| Engine / batch | 同 Tick 调价、ABA、描述/库存版本、共享库存、失败候选继续、前缀保留/尾部 skipped、整批 invalid、重复成功/失败/冲突 |
| 故障与时间 | timeout/provider failure 不转 Wait；整 Wave 未执行；Engine 中途异常保留未发布前缀；取消清理；每正常 Round advance 一次 |
| journal / replay | 正常 trace、技术收集失败、记录的 action fault 前缀可重放；改动作/结果状态可发现不一致；不调用模型 |
| CLI | PowerShell runner-demo/replay 成功；仓库外 Python `-I` 独立 CLI 成功 |
| 打包 | wheel / sdist 构建成功；独立新环境仅安装 salesbench-engine 0.2.0 wheel，Runner demo/replay 与旧 scenario 均成功 |
| 依赖隔离 | 全包（包括 Runner 子包）AST 检查仅标准库/自身导入；wheel 检查环境仅含本地 Engine 包 |

测试日志与 journal 位于忽略的 `.local/SB-RUNNER-001/`，不作为跨机同步材料。新机器使用 Git 代码重建本机环境并重跑命令。打包验证环境为该目录中的 `wheel-venv/`，不进入 Git。全程没有启动临时服务，不需要停止其他程序。

## Demo 轨迹与命令

在根目录执行，journal 父目录需要存在：

```powershell
pwsh -File scripts/engine.ps1 install
pwsh -File scripts/engine.ps1 test
pwsh -File scripts/engine.ps1 runner-demo -Seed 7 -ResolutionSeed 7 -JournalPath .local/wave-trace.json
pwsh -File scripts/engine.ps1 replay -JournalPath .local/wave-trace.json
pwsh -File scripts/engine.ps1 build
```

示例 1 Supplier、3 Seller、4 Buyer、2 Product，2 Round × 每 Round 3 Tick。每 Round 独立采购，首 Tick 四位 Buyer 争买 seller-1/cup 最后一件；第二 Tick Seller 更新售价/描述并私聊回复。初始发布 0，14 次 Wave 完成发布，2 次 Round close 发布，终态发布 16、Engine step=2。

| 位置 | purchase resolver 顺序 | 成交 | 其他候选 |
| --- | --- | --- | --- |
| R1 / T1 | buyer-1 → buyer-4 → buyer-3 → buyer-2 | buyer-1，1 件，300 分，offer rev 1，step 0 | 3 次 OUT_OF_STOCK |
| R2 / T1 | buyer-1 → buyer-2 → buyer-4 → buyer-3 | buyer-1，1 件，350 分，offer rev 2，step 1 | 3 次 OUT_OF_STOCK |

6 次采购、2 个订单；余额（分）：supplier=1000，seller-1=2450，seller-2/3 各 1600，buyer-1=1350，buyer-2/3/4 各 2000。资金总额保持 14000。

完整经济状态 SHA-256：`fc5ea7d4858dd5124cfd135333004452cb3071590f5f6bcdcc5709da76e005be`。源码运行、独立 wheel 和 recorded trace replay 一致。该摘要包括 seed=7 的初始配置，不用它比较不同初始实验配置。

## Known Issues / Protocol Debt

1. **失败传播语义后续需正式确认**。V1 按确认方案保留成功前缀、失败后尾部 skipped，日志明确原因；消息失败可以阻止本批次末尾购买，本轮没有重新设计此规则。
2. 经济规则仍为 TEST：即时采购/收款、固定有限供给、共享库存；正式消费者、Seller 策略、奖励、排行榜、物流/退款/税费均未实现。Engine step 在 Runner 中表示已正常关闭的 Round 数，不是分钟/小时/天。
3. LLMDriver 只完成接口和 fake adapter 验证；真实 provider、模型策略/提示实验、人类输入、conversation micro-wave 未接入。合作取消/非阻塞 I/O 由未来 adapter 保证。
4. 单进程内存幂等，不是数据库事务、跨进程幂等或 crash recovery。异常 Wave 的成功前缀可能存在于 Engine 内存，published snapshot 仍停留在上一正常边界。
5. Journal 含私有观察、余额、订单、原始模型文本，只供可信宿主；不能提交 Git 或直接提供给参与者。完整历史/状态变化表适合小实验，未验证大规模存储/吞吐；超 token 预算会失败，不静默裁剪观察。
6. Replay 要求匹配协议/源码；对于记录的 action fault，仅按故障边界重放成功前缀，不宣称重现 bug。进程崩溃、缺 response 的取消 trace、损坏 journal 或非 action 实现异常不保证恢复。
7. 平台 v0.1 仍是 Vue 演示草案。后续要对齐 Listing/expected revision、publication/offer/content 与网络 revision、机会/receipt、逻辑时间与 UTC；FastAPI 必须通过 application/adapter 管理 Runner，不能绕过 Wave 直接按请求到达顺序购买。

具备后续“平台调用真实 Engine/Runner”的基础，但持久化版本/恢复、单写者、durable 幂等、数据库 commit 与 publish 协调仍需下一任务明确。当前任务完成后停止，不自动进入 FastAPI/PostgreSQL/Vue 联调。
