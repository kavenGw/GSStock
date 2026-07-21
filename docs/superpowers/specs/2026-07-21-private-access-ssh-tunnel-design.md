# 云服务器私有访问设计（gunicorn 本机监听 + SSH 隧道）

日期：2026-07-21
状态：已批准

## 背景与目标

项目部署在 Linux 云服务器上，当前 `gunicorn.conf.py` 以 `bind = "0.0.0.0:5000"` 直接暴露公网，应用无任何鉴权，任何人扫到 IP:5000 即可查看持仓数据。

目标：**只有用户本人（固定的自己电脑）可以访问**，公网完全不可见。

约束与场景确认：

- 仅从自己的 Windows 电脑访问，不需要手机访问
- SSH 登录服务器用密码（非密钥），隧道用 sshpass 免交互
- 本机已有 WSL Ubuntu（Windows 侧无 sshpass，sshpass 装在 WSL 内）

## 方案选择

- **方案 1（采用）**：gunicorn 只监听 `127.0.0.1` + 本机 SSH 隧道访问。一行配置改动 + 一个本地脚本，公网完全不可见，不受本机 IP 变化影响。
- 方案 2（否决）：保持 `0.0.0.0` 监听，仅靠云安全组 IP 白名单。家庭宽带 IP 会变需反复改规则，且仅一层防护，误配即裸奔。

## 设计

### 1. 服务器侧（唯一代码改动）

`gunicorn.conf.py`：

```python
bind = "127.0.0.1:5000"
```

影响面：

- 仅影响 Linux 部署（gunicorn 读此配置）；Windows 本地开发走 `run.py` / Flask debug，不读该文件
- Slack 推送、行情抓取等出站功能不受影响

### 2. 电脑侧（隧道脚本）

- WSL Ubuntu 内一次性安装：`sudo apt install sshpass`
- 仓库提供模板 `scripts/tunnel.bat.sample`（占位符，不含真实凭据）；用户复制为 `scripts/tunnel.local.bat` 填入服务器 IP/用户/密码
- `scripts/tunnel.local.bat` 加入 `.gitignore`，真实凭据绝不进 git

脚本内容（模板）：

```bat
wsl -d Ubuntu sshpass -p "密码" ssh -N -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60 -L 5000:127.0.0.1:5000 用户@服务器IP
```

使用方式：双击 `tunnel.local.bat`，窗口保持打开即隧道在线；浏览器访问 `http://localhost:5000`（WSL2 默认 localhost 端口互通）。

参数说明：

- `-N`：只转发端口，不开远程 shell
- `StrictHostKeyChecking=accept-new`：首次连接自动接受主机密钥，避免 sshpass 遇交互确认静默失败
- `ServerAliveInterval=60`：心跳防闲置断连

### 3. 可选加固（手工操作，不入库）

- 云厂商安全组删除 5000 端口入站规则（双保险）
- 后续如愿意可改 SSH 密钥登录并禁密码，防爆破（非本次范围）

## 风险与取舍

- 密码明文存于本地 `tunnel.local.bat`：sshpass 方案固有取舍，安全性依托本机不共用 + 文件不进 git，用户已确认接受
- 隧道窗口关闭即断连，需重开脚本（可接受，无守护需求）

## 验收标准

1. 服务器重启 gunicorn 后，公网 `http://服务器IP:5000` 不可达（连接拒绝/超时）
2. 本机运行 `tunnel.local.bat` 后，浏览器 `http://localhost:5000` 正常打开应用
3. `git status` 确认 `tunnel.local.bat` 不被 git 跟踪
