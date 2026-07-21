import importlib.util
from pathlib import Path


def test_gunicorn_binds_localhost_only():
    conf_path = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("gunicorn_conf", conf_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.bind == "127.0.0.1:5000"
