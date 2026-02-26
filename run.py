import os
import sys
import webbrowser
import threading
import traceback
from app import create_app


def open_browser():
    webbrowser.open('http://127.0.0.1:5000')


def main():
    """启动应用，捕获错误以便查看"""
    try:
        app = create_app()
        # 仅在主进程打开浏览器（避免 reloader 子进程重复打开）
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            threading.Timer(1.5, open_browser).start()
        app.run(debug=True)
    except Exception as e:
        print("\n" + "=" * 60)
        print("启动失败！错误信息如下：")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        print("\n按回车键退出...")
        input()
        sys.exit(1)


# 兼容 flask run（作为模块导入时创建 app，python run.py 走 main()）
app = None
if __name__ != '__main__':
    try:
        app = create_app()
    except Exception as e:
        print(f"应用创建失败: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
