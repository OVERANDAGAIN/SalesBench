# 本轮验证与截图

本目录是 SB-002B 本轮实际验证证据；不替代用户视觉验收，也不表示研究协议定案。

## 自动检查

- 前端 `typecheck`、`build`；Vitest 模拟服务 18 项测试。
- 后端 pytest 2 项：无数据库/凭据的进程健康检查、业务路由未实现。
- `scripts/verify-health.ps1`：真实 HTTP、Vite 限定代理、后端重启检查，自动清理自有进程。
- `frontend/tests/browser/run.mjs`：本机 Edge、桌面/窄屏真实页面与交互；结构化结果见 `browser-results.json`。
- 模拟服务测试使用可控时间/失败/外部变更，不安装训练环境。

## 已发现并修复

1. 第一轮类型检查发现负向测试的非法身份字段需要明确通过 unknown 传入，已修正测试类型表达；没有放宽业务类型或校验。
2. 第一轮浏览器检查发现购买成功弹窗先于后台刷新结束出现，立即点击继续浏览会被 busy 状态忽略。调整成功展示时机，保留提交期间防重复操作；后续整套浏览器流程通过。
3. 初次后端 TestClient 有上游弃用提示，改用已安装的 httpx ASGITransport 测试，不屏蔽警告、不关闭测试、不新增 httpx2。
4. pnpm 11 已改变配置来源，首次 `.npmrc` 中的缓存设置未生效；后续排查中通用 CLI 缓存参数也不适用于 `run`。依据官方 v11 说明改为 `pnpm_config_*` 进程变量及工作区 YAML，并重新验证启动包装脚本。C 盘初期元数据残留计入空间记录，没有覆盖或删除其他用途内容。

## 原型对照

原型：`references/ui-v1/2026-09-23/source/SalesBench_V1/screenshots/`。
本轮读取了历史截图并与当前截图对照。布局、五页顺序、商家归属、主色、卡片和弹窗结构延续原型；原 CSS 与三张 WebP 直接复用。
可见变化是本地 Vue 演示标识、加载/失败提示、异步回复时序、发送等待状态与必要的窄屏长文本换行。运行系统/字体和截图尺寸不同，不声称逐像素一致。
截图仅包含演示种子和测试消息，没有真人账号、私聊或数据库数据。

## 当前截图

| 页面/场景 | 桌面 | 窄屏 |
|---|---|---|
| 排行榜 | [桌面](desktop-ranking.png) | [窄屏](mobile-ranking.png) |
| 商品推荐 | [桌面](desktop-products.png) | [窄屏](mobile-products.png) |
| 公共交流 | [桌面](desktop-public-sent.png) | [窄屏](mobile-public.png) |
| 私聊 | [桌面](desktop-private-sent.png) | [窄屏](mobile-private.png) |
| 我的/已购买 | [桌面](desktop-account-purchased.png) | [窄屏](mobile-account-purchased.png) |
| 商品详情 | [桌面](desktop-detail.png) | [窄屏](mobile-detail.png) |
| 购买确认 | [桌面](desktop-checkout.png) | [窄屏](mobile-checkout.png) |

[购买完成](desktop-purchase-result.png) · [读取失败](scenario-read-failure.png) · [价格变化拒绝](scenario-price-change.png) · [外部消息刷新](scenario-external-message.png)

长页面截图保留页面全高；固定底部导航位于拍摄时的视口底部。弹窗截图使用实际视口范围。

## 未验证/未实现

- 用户视觉验收、真实移动设备软键盘和所有浏览器/操作系统组合。
- Python 主体对接、正式算法、正式 API、服务端身份授权、真实多人同步、数据库事务与持久幂等。
- 无 WebMCP 注册、模型调用、Seller 后台、Agent 管理 UI 或公网部署。
