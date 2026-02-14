import sys
import traceback
from app import create_app


def main():
    """启动应用，捕获错误以便查看"""
    try:
        app = create_app()
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


# 为了兼容 Flask 的 flask run 命令
app = None
try:
    app = create_app()
except Exception as e:
    print(f"应用创建失败: {e}")
    traceback.print_exc()

if __name__ == '__main__':
    main()
