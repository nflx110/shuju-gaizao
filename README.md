# 数据改造工具

本地工具集：瀑布流广告位置解析、暖风数据解析、Charles 辅助脚本、爱奇艺 Mac 小工具。

## 目录

| 文件夹 | 说明 |
| --- | --- |
| `瀑布流广告位置解析/` | 对照爱奇艺「猜你喜欢」瀑布流广告插位，含本机 AI 识图服务 |
| `暖风智能数据解析/` | 暖风数据解析单页 |
| `Charles本地防崩溃优化/` | 限制 Charles 堆内存和会话体积，减少崩溃 |
| `Charles Mixer对比/` | 从本机 Charles 拉包，做 mixer response 对比 |
| `爱奇艺Mac小工具/` | Mac 客户端调试：日志、缓存、LWA、安装包、签名 |
| `视频压缩/` | 把录屏压到 10MB 以内，网页本地压缩或双击 `压缩到10M.command` |
| `广告数据样本/` | 鸿蒙/开屏/Banner 等广告 JSON 样本 |
| `个人素材/` | 个人照片与表情，不入库 |

## 在线地址

- 工具首页：https://nflx110.github.io/shuju-gaizao/
- 瀑布流广告位置解析：https://nflx110.github.io/shuju-gaizao/瀑布流广告位置解析.html
- 暖风智能数据解析：https://nflx110.github.io/shuju-gaizao/暖风智能数据解析.html
- 录屏压缩到 10MB：https://nflx110.github.io/shuju-gaizao/视频压缩/
- 仓库：https://github.com/nflx110/shuju-gaizao

截图 AI 识别仍需在本机启动服务，在线页只能做接口粘贴和对照。

## 瀑布流广告位置解析

对照爱奇艺「猜你喜欢」瀑布流广告插位。

1. 进入目录：`cd 瀑布流广告位置解析`
2. 安装依赖：`npm install`
3. 启动识图服务：双击 `启动AI识别服务.command`，或执行 `node shot_ai_server.mjs`
4. 浏览器打开：`http://127.0.0.1:8788/瀑布流广告位置解析.html`

也可直接用浏览器打开 `瀑布流广告位置解析/瀑布流广告位置解析.html`（不走 AI 识图时）。

## 录屏压缩到 10MB

网页版（浏览器本地压缩，视频不上传）：

https://nflx110.github.io/shuju-gaizao/视频压缩/

本机双击 `视频压缩/压缩到10M.command` 更快。原文件不动，会在旁边生成 `*_10M.mp4`。

也可命令行：

```bash
/opt/homebrew/bin/python3.13 视频压缩/app.py ~/Desktop/录屏.mp4 10
```

首次若没有 ffmpeg，启动器会尝试 `brew install ffmpeg`。

## 说明

请勿把 API Key、`.env` 或个人照片提交进 Git。
