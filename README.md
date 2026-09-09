# 数据改造工具

本地工具集：瀑布流广告位置解析、暖风数据解析、Charles 辅助脚本。

## 在线地址

- 工具首页：https://nflx110.github.io/shuju-gaizao/
- 瀑布流广告位置解析：https://nflx110.github.io/shuju-gaizao/瀑布流广告位置解析.html
- 仓库：https://github.com/nflx110/shuju-gaizao

截图 AI 识别仍需在本机启动服务，在线页只能做接口粘贴和对照。

## 瀑布流广告位置解析

对照爱奇艺「猜你喜欢」瀑布流广告插位。

1. 安装依赖：`npm install`
2. 启动识图服务：双击 `启动AI识别服务.command`，或执行 `node shot_ai_server.mjs`
3. 浏览器打开：`http://127.0.0.1:8788/瀑布流广告位置解析.html`

也可直接用浏览器打开 `瀑布流广告位置解析.html`（不走 AI 识图时）。

## 说明

请勿把 API Key、`.env` 或个人照片提交进 Git。
