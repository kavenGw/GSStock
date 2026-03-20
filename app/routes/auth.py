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
    if not current_app.config.get('ACCESS_KEY') or session.get('authenticated'):
        return redirect('/')

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
