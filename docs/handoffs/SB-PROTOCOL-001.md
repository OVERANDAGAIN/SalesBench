# SB-PROTOCOL-001 接力记录

2026-09-23；工作目录 `D:\SalesBench`，沿用 5070 执行端约定；分支 `feat/sb-core-skeleton`；远端 `https://github.com/OVERANDAGAIN/SalesBench.git`。

## 开工核对与范围

- 本地 HEAD 和远端任务分支均为 `d3cbc0352d85b1c6a1ca84472265a95f7efe5383`。首次直接连接 GitHub 失败，使用本机已有 `127.0.0.1:7890` 代理对单次请求成功核对；未改全局代理/系统设置。
- 已读 AGENTS、PLAN、ENVIRONMENT、INTERFACES、ENGINE、SB-CORE-001 handoff；已核对 Engine models/actions/environment/policies/rules 及 Vue domain types/网络占位服务。没有依赖其他账号聊天记录。
- 初始有未跟踪 `.idea/`，保留原状，不纳入提交。没有合并、变基、reset、clean、强推、删除分支或修改 main。
- 本轮授权为调研和 docs 设计；未修改 Engine/frontend/backend 业务源码、锁文件或原始 references，未启动 SB-RUNNER-001。

## 文档交付

入口 [PROTOCOL_DECISIONS](../PROTOCOL_DECISIONS.md)。其他文件各有唯一职责：

| 文件 | 内容 |
| --- | --- |
| [RESEARCH_SCHEDULING](../RESEARCH_SCHEDULING.md) | 五类一手资料、版本、事实/代码/推断/未知比较 |
| [ROUND_PROTOCOL](../ROUND_PROTOCOL.md) | round/phase/cycle、Seller 双屏障、Q/R/D、竞争、信息、时间、episode/config |
| [HUMAN_SCHEDULER](../HUMAN_SCHEDULER.md) | Ready、timer、pending reply、混合场次、断线与最小 UI 表达 |
| [RUNNER_DESIGN](../RUNNER_DESIGN.md) | 组件边界、状态机/伪代码、日志、故障、验收与 A/B/C 里程碑 |
| [PLATFORM_IMPLICATIONS](../PLATFORM_IMPLICATIONS.md) | DTO、DB implications、事务/恢复与 H5 接入草案 |
| [SB-RUNNER-001](../prompts/SB-RUNNER-001.md) | 下一任务可直接使用、严格限制为 Runner Skeleton 的实施 Prompt |

推荐：每 cycle 询问→集中回复→购买决策；Round 内冻结 Listing 条款和官方榜单；窗口内 seeded serial priority；Human Ready 非强制且只作用当前窗口；每正常 Round Close advance 一次。数量和秒数均为 Development Default，正式参数需 pilot。

## 来源限制

Market-Bench 本次依据供应链论文 v1，没有核实到相应官方运行源码；Business Arena 指定仓库版本只有论文/README/素材，不能核实内部调度。E-CommerceBench 与 Magentic 读取固定 commit 源文件；未执行外部代码。oTree 为 2026-09-23 检索的 latest 文档，未声称固定发行版。

只读调研缓存位于忽略的 `.local/SB-PROTOCOL-001/`，不进入 Git 或 references。后续接手依据文档中官方链接/commit，不依赖这些本机缓存。

## 本次验证与环境

本轮为文档变更：11 个本轮新增/更新文档的 51 处本地 Markdown 链接全部可解析；代码围栏成对，无替换乱码；阶段/预算/时间默认值复核，Human 示例正常窗口上限为 315 秒，小于 360 秒 watchdog；两 Buyer 的 SHA256 规范排序向量已独立计算并写入协议。固定来源版本已核对，论文版本日期与仓库提交日期分开记录。收尾检查差异范围、敏感内容与 `git diff --check`。

没有运行 Engine/前后端测试或浏览器验收，因为未修改业务代码；SB-CORE-001 的 36 项 Engine 测试是历史结果，不冒充本轮通过。文档静态核对不等于已实现 Runner、通过用户视觉验收或完成正式实验验证。

没有安装依赖、数据库、Docker/WSL、浏览器或模型，没有启动服务或监听端口，无本任务服务待清理。新增一手资料文本缓存 24 个文件，另有 1 份文档检查记录，合计 1,778,284 字节（约 1.70 MiB），均位于忽略目录；新增依赖/工具为 0。未调整全局 PATH、注册表、同步、安全或电源设置。

## 下一步与未完成项

研究确认、pilot、正式模型/奖励/排名/履约语义仍未完成；Runner、Human H5 接入、FastAPI business API、PostgreSQL、WebSocket、登录/被试系统均未实施。先以新任务执行 SB-RUNNER-001，A 验收后才另行启动 B/C。

## 提交与同步

设计文档主体提交 `8f746dde82209b0b9227a88c0ce9bca3da852498` 已推送至 `origin/feat/sb-core-skeleton`，远端查询确认一致。main 仍为 `2ab44d79e5d28d5c0c17b17e3cdb2a5768579408`，未修改。主体提交只涉及 11 份 docs 文件；业务源码、锁文件和 references 与开工基线无差异，暂存差异检查及敏感内容扫描通过。

本交接收尾提交只补记验证/同步状态；最终可接手提交为包含本记录的分支 HEAD。接手时运行 `git rev-parse HEAD` 并与远端任务分支核对，避免在文档内写入自身哈希。工作区仅保留原有未跟踪 `.idea/`。SB-PROTOCOL-001 已完成；停止，不实施 SB-RUNNER-001。
