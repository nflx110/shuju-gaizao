# 爱奇艺 Mac 小工具

爱奇艺 Mac 客户端调试小工具：日志、缓存、LWA、环境信息、JFrog 安装包、接口签名。

## 运行

需要 Homebrew Python 3.13（系统自带 Python 的 Tk 在部分 macOS 上会崩溃）：

```bash
brew install python@3.13 python-tk@3.13
```

不要双击 `.app`（从 GitHub 下载后系统会拦截未签名应用）。请双击 **`启动.command`**。若仍提示无法打开，在终端执行：

```bash
cd ~/Downloads/pc-tools-mac-main
xattr -cr .
chmod +x 启动.command
./启动.command
```

或：

```bash
/opt/homebrew/bin/python3.13 main.py
```

## 安装包地址

Mac 包走 Artifactory：

`http://jfrog.cloud.qiyi.domain/ui/native/iqiyi-generic-pca-ci/mac/develop/`

- **Trunk**：测试包
- **Release**：正式包
- **AppStore**：商店包

下载的是 `iqiyi_mac_*.dmg`（AppStore 为 `iqiyi_appstore_mac_*.dmg`）。

## 功能

- 打开客户端 / LStyle 数据目录
- 环境信息（版本、LWA、设备号、hosts）
- 替换 LWA、拷贝/删除日志、写 logconfig、清缓存
- 一键安装最新包、按构建版本选包
- 接口签名、QAMP 监控数量
