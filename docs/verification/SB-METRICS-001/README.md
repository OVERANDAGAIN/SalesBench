# SB-METRICS-001 本次验证

2026-09-24，5070，真实 Windows / Edge 153.0.4234.48 / PostgreSQL 17.11。分支 feat/sb-core-skeleton，起点 7807df8d20a8c0f77e680bd099af262ba02c217e。这里是本任务运行结果，不复用历史截图。

## 自动验证

执行 `pwsh -File scripts/run.ps1 check -EvidenceDir docs/verification/SB-METRICS-001`，最终完整通过：

| 验证 | 结果 |
| --- | --- |
| Engine / Runner | 64 passed，源码未改 |
| Backend / 真实 PostgreSQL | 45 passed（含 14 项新 Metrics 用例）；隔离 schema 从空迁移 |
| Vue unit | 28 passed（含 2 项新展示/推荐顺序用例） |
| Vue typecheck / production build | 通过 |
| 生产预览 | 真实绑定入口，无 demo controller |
| 四角色真实市场 | 9 组完整验收，2 Round × 3 Tick，包含利润榜/API/导出/重启 |
| 历史 demo UI | 9 组行为回归通过；仅历史 UI，不作为真实市场证据 |

原依赖有两条弃用警告（Starlette/httpx、anyio BlockingPortal），本轮未升级依赖。首次完整回归发现提交与物化之间的读竞态；加有限补齐重读和确定性竞态测试后完整通过。最终日志 [full-check.txt](full-check.txt)，真实市场 [results.json](results.json)，PG/全历史重放校验 [database-verification.json](database-verification.json)。

## 本次持久场次与轨迹

`manual-67b69526cc514dcc9d74fbc0fd354454`，正常完成 publication 16、Engine step 2。PG 保存 28 batch receipts、33 action receipts、17 publications、263 journal entries；新增 17 metric_snapshots、7 leaderboard_snapshots。榜单来源版本为 0/3/5/7/11/13/15。全 committed trace 重新 derive 与两表所有历史 payload 完全一致；旧 NULL policy 场次仍可原样恢复。

| 关键时点 | 公开 A/B 利润（分） | 说明 |
| --- | --- | --- |
| 初始 0 | 0 / 0 | previous_rank=null，ID 稳定排序 |
| 采购 1 / Seller 2 / 首 Buyer pending | 0 / 0 | 宿主已是 -100/-300，公开榜不抢跑 |
| 首 Tick 3 | 200 / -300 | A 售 300，B 未售；负利润真实展示 |
| 第二 Tick 5 | 200 / 200 | 同利润 A 在前只是 ID tie-break |
| Round close 8 | 200 / 200（来源 7） | 浏览器刷新与 API/PG 实际停启后报告完全相同 |
| 第二 Round 采购 9 | 200 / 200（来源 7） | 宿主 A 为 0，未提前公开 |
| Tick 11 | 900 / 200 | 两 Buyer 各买 A 450 |
| 最终 16 | 900 / 200（来源 15） | completed 保留最终 Tick 榜 |

四角色每个检查点都核对相同 snapshot；参与者无法访问 admin metrics/leaderboard（403），公共 row 只含五个授权字段。实际网络全部命中 sb-platform-v1，停服务不回退 demo。商品顺序保持 seller-a/cup、seller-b/cup，Vue 单测另验证排名反转也不改商品顺序。

## 宿主样例与导出

| Seller | 初始资金 | 当前资金 | 销售收入 | 采购支出 | 开发利润 | 订单/售出/剩余库存 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 5000 | 5900 | 1200 | 300 | 900 | 3 / 3 / 0 |
| B | 5000 | 5200 | 500 | 300 | 200 | 1 / 1 / 2 |

Buyer 1 余额 750 分、3 单、支出 1250；Buyer 2 余额 1550 分、1 单、支出 450、失败 purchase 1。共 4 单/4 件，GMV 1700，6 Tick；成功动作 32、业务失败 1、skipped 0、技术失败 0、公共/私聊各 2 条。

这些是固定工程测试数据，可公开作样例。实际研究财务指标仍属可信宿主材料；本目录不包含凭据、绑定文件、私聊正文导出或 raw journal。

- [完整 JSON](metrics-json/metrics.json)
- [Seller CSV](metrics-csv/sellers.csv)、[Buyer CSV](metrics-csv/buyers.csv)、[Session CSV](metrics-csv/session.csv)
- [Tick CSV](metrics-csv/ticks.csv)、[价格 CSV](metrics-csv/prices.csv)、[利润 CSV](metrics-csv/profits.csv)、[排名 CSV](metrics-csv/ranks.csv)、[版本 manifest](metrics-csv/manifest.json)

## 真实浏览器截图

- [Buyer 负利润榜](buyer-profit-negative.png)、[Seller 同版本榜](seller-profit-negative.png)
- [Buyer 最终榜](buyer-ranking.png)、[Seller 最终状态](seller-final.png)
- [pending](buyer-pending.png)、[库存竞争失败](buyer-failed-purchase.png)、[最终余额](buyer-final-account.png)
- [商品](buyer-products.png)、[H5 商品](h5-buyer-products.png)、[公开消息](buyer-public.png)、[本人私聊](buyer-private.png)

截图里的消息是脚本固定验收文本，不是真实参与者资料；瞬时 toast 可能仍显示最近的草稿提示，经济结果以顶部 receipt 和 server observation 为准。自动浏览器验证不等于用户本轮人工视觉验收。
