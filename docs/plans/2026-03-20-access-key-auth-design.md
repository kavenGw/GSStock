# 简单密钥认证机制设计

## 概述

为部署场景添加全局访问控制，所有请求需通过密钥验证才能访问，防止未授权访问。

## 核心方案

使用 Flask `before_request` 钩子全局拦截，环境变量配置密钥，Session 保持登录状态。

## 认证流程

```
请求进入 → before_request 钩子
  → 是白名单路径（/login, /static/）？→ 放行
  → ACCESS_KEY 未配置？→ 放行（本地开发免密）
  → session['authenticated'] == True？→ 放行
  → 重定向到 /login?next=原始URL
```

登录流程：
```
GET /login → 显示密钥输入页
POST /login → hmac.compare_digest 比对密钥
  → 匹配：session['authenticated']=True, session.permanent=True, 验证 next URL 安全性后重定向
  → 不匹配：flash 错误信息，留在登录页
```

## 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ACCESS_KEY` | 访问密钥，为空则不启用认证 | 空（不启用） |

Session 有效期：7 天（`PERMANENT_SESSION_LIFETIME = timedelta(days=7)`）

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/middleware/auth.py` | 新增 | `init_auth(app)` 注册 `before_request` 钩子 |
| `app/routes/auth.py` | 新增 | `auth_bp` 蓝图，`/login` GET/POST、`/logout` POST |
| `app/templates/login.html` | 新增 | Bootstrap 5 居中卡片登录页 |
| `app/__init__.py` | 修改 | 注册 `auth_bp`，调用 `init_auth(app)` |
| `config.py` | 修改 | 添加 `ACCESS_KEY`、`PERMANENT_SESSION_LIFETIME` |
| `.env.sample` | 修改 | 添加 `ACCESS_KEY=` |
| `CLAUDE.md` | 修改 | 同步 `ACCESS_KEY` 环境变量说明 |

现有路由文件零修改。

## 实现细节

### 中间件（auth.py）

- 白名单：`/login`、`/static/` 前缀
- `ACCESS_KEY` 为空时跳过认证（`create_app()` 时判断，不注册钩子）
- 密钥比较使用 `hmac.compare_digest` 防时序攻击

### 登录页

- 复用项目 Bootstrap 5 风格
- 居中卡片，password 输入框 + 登录按钮
- flash 消息显示错误
- 支持 `next` 参数登录后跳转，需验证 URL 为站内地址（防开放重定向）

### 登出

- `POST /logout` 清除 session，重定向 `/login`（POST 防止 CSRF 误登出）
- 通过 `context_processor` 注入 `auth_enabled` 变量，导航栏条件显示登出按钮

### Session

- `session.permanent = True` + `PERMANENT_SESSION_LIFETIME = 7天`
- `session['authenticated'] = True` 作为认证标记

## 安全考虑

- 常量时间比较防时序攻击
- Session cookie 由 Flask SECRET_KEY 签名
- ACCESS_KEY 不在日志中输出
- 未配置 ACCESS_KEY 时完全跳过认证，保持本地开发体验
- `next` 参数重定向前验证为站内 URL，防止开放重定向攻击
- 登出使用 POST 方法，防止 CSRF 误登出
- 启用认证时 `SECRET_KEY` 必须配置为固定值（否则重启后 session 失效）
