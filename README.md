# SalesBench

SalesBench 总工程：买方 Web/H5 前端、平台后端与独立 Python 实验内核按职责组织。

当前任务：SB-CORE-001，机器 5070，分支 `feat/sb-core-skeleton`。
独立 `engine/` 已实现采购、库存、上架/调价、公开/私聊、购买、资金/订单和逻辑 step 的确定性内存骨架。消费者与 Seller 正式策略尚未实现，当前经济行为是 TEST 规则。

SB-002B 基础工程和 Vue 买方端已经用户验收；接口 v0.1 仍是待对齐草案。
本地演示刷新即重置；消息先发送成功，稍后出现预设回复；购买与余额、库存、订单和演示榜单共用同一服务。
Vue 仍运行自己的本地演示，FastAPI 仍只有 `/health`；尚未调用 Python Engine，没有真实业务 API、共享数据库或跨浏览器状态。参与者和未来 Seller 人工客户端仅采用 Web/H5，不建设桌面原生客户端。

## 独立 Engine

```powershell
pwsh -File .\scripts\engine.ps1 install
pwsh -File .\scripts\engine.ps1 test
pwsh -File .\scripts\engine.ps1 demo -Seed 7
```

使用本机 `.local/runtime.json` 中的 Python 3.12/uv，无需启动任何服务。设计、TEST 规则、完整命令及未来平台接入边界见 [ENGINE.md](docs/ENGINE.md)，本任务交接见 [SB-CORE-001](docs/handoffs/SB-CORE-001.md)。

## 本机快速开始

```powershell
Set-Location D:\SalesBench
pwsh -File .\scripts\run.ps1 frontend
```

打开 http://127.0.0.1:5173 。该终端按 Ctrl+C 停止。当前机器工具路径已保存在忽略的 `.local/runtime.json`。
其他机器先按环境文档配置各自真实工具位置并执行锁定安装。
API 单独启动：`pwsh -File .\scripts\run.ps1 backend`；`GET http://127.0.0.1:8000/health` 只说明进程响应。
完整检查、安装、构建预览和停止方式见环境文档。

- [共同计划](docs/PLAN.md)
- [环境与命令](docs/ENVIRONMENT.md)
- [接口与职责 v0.1 草案](docs/INTERFACES.md)
- [Engine 任务进度与接力](docs/handoffs/SB-CORE-001.md)
- [历史 Vue 验证与截图](docs/verification/SB-002B/README.md)
- [SB-002B 历史接力](docs/handoffs/SB-002B.md)
- [开发约定](AGENTS.md)
- [原型材料](references/ui-v1/2026-09-23/HANDOFF_UI.md)

原型五页固定为：排行榜、商品推荐、公共交流、私聊、我的。
原型和后续本地模拟的排名、推荐、回复、购买均不是正式实验规则。
