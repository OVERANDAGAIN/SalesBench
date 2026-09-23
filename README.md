# SalesBench

SalesBench 总工程：买方前端、平台后端与未来独立 Python 实验主体按职责组织。

当前任务：SB-002B，机器 3050，分支 `chore/sb-002b-bootstrap`。
本轮依次实施基础入口、接口 v0.1 草案、Vue 买方界面与异步本地演示服务。
Python 主体尚未提供；不建设替代内核、业务数据库、Seller 后台或 Agent 管理界面。

当前已完成 A 基础工程、B 接口 v0.1 草案和 C 的 Vue 买方端实现。B 未与 Python 主体确认；C 待用户视觉验收。
本地演示刷新即重置；消息先发送成功，稍后出现预设回复；购买与余额、库存、订单和演示榜单共用同一服务。

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
- [本轮验证与截图](docs/verification/SB-002B/README.md)
- [任务进度与接力](docs/handoffs/SB-002B.md)
- [开发约定](AGENTS.md)
- [原型材料](references/ui-v1/2026-09-23/HANDOFF_UI.md)

原型五页固定为：排行榜、商品推荐、公共交流、私聊、我的。
原型和后续本地模拟的排名、推荐、回复、购买均不是正式实验规则。
