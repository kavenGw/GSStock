"""timing_stats.py：timing-baseline.md 统计表重算与漂移检查。"""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'timing_stats',
    Path(__file__).resolve().parent.parent / '.claude/skills/stock-research/scripts/timing_stats.py')
timing_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(timing_stats)

SAMPLE = """# 基线

## 统计

| 指标 | 值 |
|---|---|
| 完整轮数 | **4**（另有 1 轮不计入：甲）|
| 中位数 | **50.0min** |
| 四分位（P25 / P75） | **40.0 / 65.0min** |
| 区间 | **40** – 80min |
| 均值 | 55.0min |

## 全轮次汇总

### 早期

| 标的 | 形态 | 净耗时 |
|---|---|---|
| 零跑 | 港股 | ~40 |
| 紫金 | A+H | 60 |

### 逐轮

| 日期 | 标的 | 形态 | 净耗时 |
|---|---|---|---|
| 08-28 | *甲* | *首建 · 判掉* | *55（不计入）* |
| 08-29 | 乙 | 首建 | 40 |
| 08-30 | 丙 | 变体 | 80（A1 8.4）|

## 近五轮分棒明细

| 棒 | 起止 | 净耗时 |
|---|---|---|
| 先做 | 09:45–09:52 | 7 |
"""


def test_parse_skips_excluded_and_detail_tables():
    included, excluded = timing_stats.parse_rounds(SAMPLE)
    assert included == [40.0, 60.0, 40.0, 80.0]
    assert excluded == ['甲']


def test_compute_matches_written_table(tmp_path):
    p = tmp_path / 'tb.md'
    p.write_text(SAMPLE, encoding='utf-8')
    assert timing_stats.main(['--file', str(p), '--check']) == 0


def test_check_detects_drift(tmp_path, capsys):
    p = tmp_path / 'tb.md'
    p.write_text(SAMPLE.replace('**50.0min**', '**58.0min**'), encoding='utf-8')
    assert timing_stats.main(['--file', str(p), '--check']) == 1
    assert 'DRIFT' in capsys.readouterr().out


def test_real_baseline_is_consistent():
    assert timing_stats.main(['--check']) == 0
