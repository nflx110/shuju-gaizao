# Charles Mixer 对比

从本机 Charles 实时拉取抓包，筛选后做 mixer response 对比。

仅访问本机 `127.0.0.1:8888`，不改 Charles 安装包。

## 使用

1. 先打开 Charles（代理端口 8888）
2. 双击 `启动.command`，或执行：

```bash
python3 app.py
```

3. 浏览器打开 http://127.0.0.1:8765
