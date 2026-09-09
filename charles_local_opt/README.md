# Charles 本地防崩溃优化

仅改本机 Charles 配置：限制堆内存和会话体积、清理失效 Ignore 与旧证书。

不修改 `/Applications/Charles.app`，避免破坏官方签名和 ProxyHelper。

## 使用

```bash
python3 optimize_charles.py
```

或双击：

- `启动Charles（防崩溃）.command`
- `一键开关.command`（工具开关）
