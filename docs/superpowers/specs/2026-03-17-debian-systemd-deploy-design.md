# Debian systemd 部署设计

## 目标

在 Debian 服务器上通过 systemd 管理 stock 服务，git pull 后即可运行。

## 架构

```
systemd (gsstock.service)
  └── gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4
        └── run:app (Flask WSGI)
```

## 部署环境

- 路径：`/home/kaven/stock/`
- 用户：`kaven`
- Python：系统 Python（无虚拟环境）
- 无 Nginx 反向代理

## 需要创建的文件

### 1. `gsstock.service`

项目根目录，部署时软链到 `/etc/systemd/system/`。

关键配置：
- `User=kaven`
- `WorkingDirectory=/home/kaven/stock`
- `EnvironmentFile=/home/kaven/stock/.env`
- `ExecStart=gunicorn -c gunicorn.conf.py run:app`
- `Restart=on-failure`，`RestartSec=5`
- 输出到 journald

### 2. `gunicorn.conf.py`

项目根目录，gunicorn 配置：
- `bind = "0.0.0.0:5000"`
- `workers = 1`
- `threads = 4`
- `timeout = 120`（APScheduler 启动可能较慢）
- `accesslog = "-"`（输出到 stdout → journald）
- `errorlog = "-"`

### 不修改的文件

- `run.py` — 已有 `app = create_app()` 兼容 `run:app` WSGI 入口

## 部署流程

```bash
# 首次部署
cd /home/kaven/stock
pip install -r requirements.txt
sudo ln -s /home/kaven/stock/gsstock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gsstock
sudo systemctl start gsstock

# 日常更新
cd /home/kaven/stock
git pull
pip install -r requirements.txt
sudo systemctl restart gsstock

# 查看日志
journalctl -u gsstock -f
```
