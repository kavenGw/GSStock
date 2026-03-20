# 密钥认证机制实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为部署场景添加全局密钥认证，所有请求需验证 ACCESS_KEY 才能访问

**Architecture:** Flask `before_request` 钩子全局拦截，环境变量配置密钥，Session 保持 7 天登录状态。未配置 ACCESS_KEY 时跳过认证。

**Tech Stack:** Flask session, hmac.compare_digest, Bootstrap 5

**Spec:** `docs/plans/2026-03-20-access-key-auth-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `config.py` | 修改 | 添加 `ACCESS_KEY`、`PERMANENT_SESSION_LIFETIME` |
| `app/middleware/auth.py` | 新增 | `init_auth(app)` 注册 `before_request` 钩子 |
| `app/routes/auth.py` | 新增 | `auth_bp` 蓝图，登录/登出路由 |
| `app/templates/login.html` | 新增 | Bootstrap 5 居中卡片登录页 |
| `app/__init__.py` | 修改 | 注册蓝图、中间件、context_processor |
| `app/templates/base.html` | 修改 | 导航栏添加登出按钮 |
| `.env.sample` | 修改 | 添加 `ACCESS_KEY=` |
| `CLAUDE.md` | 修改 | 同步环境变量说明 |

---

### Task 1: 配置项

**Files:**
- Modify: `config.py:16-17`
- Modify: `.env.sample:9-11`

- [ ] **Step 1: config.py 添加 ACCESS_KEY 和 session 有效期**

在 `Config` 类中添加：

```python
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    ACCESS_KEY = os.environ.get('ACCESS_KEY', '')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    # ... 其余配置不变
```

- [ ] **Step 2: .env.sample 添加 ACCESS_KEY**

在 `# ============ 密钥配置 ============` 区段，`SECRET_KEY=` 后添加：

```
# 访问密钥，配置后所有页面需验证密钥才能访问，留空则不启用认证
# 启用认证时 SECRET_KEY 也必须配置为固定值（否则重启后需重新登录）
ACCESS_KEY=
```

- [ ] **Step 3: Commit**

```bash
git add config.py .env.sample
git commit -m "feat: add ACCESS_KEY and session lifetime config"
```

---

### Task 2: 认证中间件

**Files:**
- Create: `app/middleware/auth.py`

- [ ] **Step 1: 创建 auth.py**

```python
from flask import session, request, redirect, url_for


def init_auth(app):
    """注册全局认证钩子。ACCESS_KEY 为空时不启用。"""
    access_key = app.config.get('ACCESS_KEY', '')
    if not access_key:
        return

    @app.before_request
    def require_auth():
        # 白名单：登录页和静态资源
        if request.endpoint == 'auth.login' or request.path.startswith('/static/'):
            return
        if not session.get('authenticated'):
            return redirect(url_for('auth.login', next=request.url))
```

- [ ] **Step 2: Commit**

```bash
git add app/middleware/auth.py
git commit -m "feat: add before_request auth middleware"
```

---

### Task 3: 登录/登出路由

**Files:**
- Create: `app/routes/auth.py`

- [ ] **Step 1: 创建 auth.py 蓝图**

```python
import hmac
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app

auth_bp = Blueprint('auth', __name__)


def _is_safe_url(target):
    """验证重定向 URL 为站内地址"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 已认证或未启用认证，直接跳转首页
    if not current_app.config.get('ACCESS_KEY') or session.get('authenticated'):
        return redirect(url_for('briefing.index'))

    if request.method == 'POST':
        key = request.form.get('access_key', '')
        if hmac.compare_digest(key, current_app.config['ACCESS_KEY']):
            session['authenticated'] = True
            session.permanent = True
            next_url = request.form.get('next', '/')
            if not _is_safe_url(next_url):
                next_url = '/'
            return redirect(next_url)
        flash('密钥错误', 'danger')

    return render_template('login.html', next=request.args.get('next', '/'))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/auth.py
git commit -m "feat: add login/logout routes with safe redirect"
```

---

### Task 4: 登录页模板

**Files:**
- Create: `app/templates/login.html`

- [ ] **Step 1: 创建 login.html**

独立页面，不继承 base.html（未登录时不应显示导航栏）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录</title>
    <link href="{{ url_for('static', filename='vendor/css/bootstrap.min.css') }}" rel="stylesheet">
    <link href="{{ url_for('static', filename='vendor/css/bootstrap-icons.css') }}" rel="stylesheet">
    <style>
        body { background-color: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .login-card { max-width: 400px; width: 100%; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="card shadow">
            <div class="card-body p-4">
                <h4 class="card-title text-center mb-4"><i class="bi bi-shield-lock"></i> 访问验证</h4>
                {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
                {% endfor %}
                {% endif %}
                {% endwith %}
                <form method="POST" action="{{ url_for('auth.login') }}">
                    <input type="hidden" name="next" value="{{ next }}">
                    <div class="mb-3">
                        <input type="password" class="form-control form-control-lg" name="access_key"
                               placeholder="请输入访问密钥" autofocus required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100 btn-lg">登录</button>
                </form>
            </div>
        </div>
    </div>
    <script src="{{ url_for('static', filename='vendor/js/bootstrap.bundle.min.js') }}"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/login.html
git commit -m "feat: add login page template"
```

---

### Task 5: 注册蓝图和中间件到 create_app

**Files:**
- Modify: `app/__init__.py:210-226`（蓝图注册区）
- Modify: `app/__init__.py:276-280`（context_processor 区）

- [ ] **Step 1: 注册 auth_bp 蓝图**

在 `app/__init__.py` 第 210 行蓝图导入行之前，添加：

```python
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
```

- [ ] **Step 2: 调用 init_auth**

在蓝图注册之后（第 226 行之后），添加：

```python
    from app.middleware.auth import init_auth
    init_auth(app)
```

- [ ] **Step 3: 添加 auth_enabled context_processor**

在现有 `inject_readonly_mode` context_processor 中追加 `auth_enabled`：

将：
```python
    @app.context_processor
    def inject_readonly_mode():
        from app.utils.readonly_mode import is_readonly_mode
        return {'readonly_mode': is_readonly_mode()}
```

改为：
```python
    @app.context_processor
    def inject_global_vars():
        from app.utils.readonly_mode import is_readonly_mode
        return {
            'readonly_mode': is_readonly_mode(),
            'auth_enabled': bool(app.config.get('ACCESS_KEY')),
        }
```

- [ ] **Step 4: Commit**

```bash
git add app/__init__.py
git commit -m "feat: register auth blueprint, middleware and context_processor"
```

---

### Task 6: 导航栏添加登出按钮

**Files:**
- Modify: `app/templates/base.html:46-48`

- [ ] **Step 1: 在「我的」下拉菜单末尾添加登出项**

在 `base.html` 第 46 行（推送设置 `</li>` 之后、`</ul>` 之前）插入：

```html
                        {% if auth_enabled %}
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <form action="{{ url_for('auth.logout') }}" method="POST" class="d-inline">
                                <button type="submit" class="dropdown-item text-danger"><i class="bi bi-box-arrow-right"></i> 登出</button>
                            </form>
                        </li>
                        {% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: add logout button to navbar dropdown"
```

---

### Task 7: 文档同步

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.env.sample`（已在 Task 1 完成）

- [ ] **Step 1: CLAUDE.md 添加认证配置说明**

在 CLAUDE.md 的环境变量配置表区域（LLM 配置表之后），添加一个新区段：

```markdown
## 认证配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ACCESS_KEY` | 访问密钥，配置后所有页面需验证才能访问 | 空（不启用） |

启用认证时 `SECRET_KEY` 也必须配置为固定值，否则重启后 session 失效需重新登录。
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add ACCESS_KEY auth config to CLAUDE.md"
```

---

### Task 8: 手动验证

- [ ] **Step 1: 不配置 ACCESS_KEY，启动应用**

Run: `python run.py`

预期：所有页面正常访问，无登录拦截，导航栏无登出按钮。

- [ ] **Step 2: 配置 ACCESS_KEY，重启应用**

在 `.env` 中添加 `ACCESS_KEY=test123`，重启。

预期：
- 访问任意页面 → 重定向到 `/login`
- 输入错误密钥 → 显示「密钥错误」
- 输入 `test123` → 登录成功，跳转回原始页面
- 导航栏「我的」下拉菜单出现红色「登出」按钮
- 点击登出 → 回到登录页
- 关闭浏览器再打开 → 7 天内无需重新登录
