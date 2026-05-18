import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / 'tests' / 'fixtures' / 'docs_stub'

def run_lint(target_dir: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'lint_docs_frontmatter.py'),
         '--root', str(target_dir)],
        capture_output=True, text=True, encoding='utf-8',
    )
    return proc.returncode, proc.stdout + proc.stderr

def test_lint_passes_on_valid(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'sample.md').write_text(
        (FIX / 'valid_buffett.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code == 0, out

def test_lint_fails_on_missing_required(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'bad.md').write_text(
        (FIX / 'missing_required.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code != 0
    assert 'sector' in out

def test_lint_fails_on_bad_enum(tmp_path):
    (tmp_path / 'sectors' / 'semiconductor' / 'storage').mkdir(parents=True)
    (tmp_path / 'sectors' / 'semiconductor' / 'storage' / 'bad.md').write_text(
        (FIX / 'bad_enum.md').read_text(encoding='utf-8'), encoding='utf-8')
    code, out = run_lint(tmp_path)
    assert code != 0
    assert 'not in' in out
