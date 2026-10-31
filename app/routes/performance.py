import logging

from flask import abort, current_app, render_template, url_for
import markdown

from app.routes import performance_bp
from app.services.performance import ANALYTICS_ROOT, load_companies, performance_rows, research_path

logger = logging.getLogger(__name__)


@performance_bp.route('/')
def index():
    root = current_app.config.get('PERFORMANCE_ROOT', ANALYTICS_ROOT)
    try:
        rows = performance_rows(load_companies(root))
    except ValueError:
        logger.exception('研究业绩文件校验失败')
        return render_template('performance.html', rows=[], periods=[], error=True), 503
    for row in rows:
        row['research_url'] = url_for('performance.research', document=row['source_doc'])
    periods = sorted({row['period'] for row in rows}, reverse=True)
    return render_template('performance.html', rows=rows, periods=periods, error=False)


@performance_bp.route('/research/<path:document>')
def research(document):
    root = current_app.config.get('PERFORMANCE_ROOT', ANALYTICS_ROOT)
    try:
        path = research_path(document, root)
    except ValueError:
        abort(404)
    text = path.read_text(encoding='utf-8')
    if text.startswith('---\n'):
        text = text.split('---', 2)[-1].lstrip()
    content = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
    return render_template('performance_research.html', title=path.parent.name, content=content)
