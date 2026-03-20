from flask import session, request, redirect, url_for


def init_auth(app):
    """注册全局认证钩子。ACCESS_KEY 为空时不启用。"""
    access_key = app.config.get('ACCESS_KEY', '')
    if not access_key:
        return

    @app.before_request
    def require_auth():
        if (request.endpoint == 'auth.login'
                or request.path.startswith('/static/')
                or request.path == '/favicon.ico'):
            return
        if not session.get('authenticated'):
            return redirect(url_for('auth.login', next=request.url))
