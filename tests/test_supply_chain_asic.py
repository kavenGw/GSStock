"""ASIC 全景产业链图谱契约测试"""
import pytest
from flask import Flask

from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS


def test_asic_top_level_present():
    assert 'asic' in SUPPLY_CHAIN_GRAPHS
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    assert asic['name'] == 'ASIC 算力芯片'
    core = asic['core']
    assert core['code'] == 'AVGO'
    assert core['market'] == 'US'
    assert 'Broadcom' in core['name'] or '博通' in core['name']


def test_asic_three_layers_present():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    for key in ('upstream', 'midstream', 'downstream'):
        assert key in asic, f'缺 {key} 层'


def test_asic_competitors_four_entries():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    competitors = asic.get('competitors', {})
    expected = {'AVGO', 'MRVL', '688256', '688041'}
    assert set(competitors.keys()) == expected, \
        f'competitors 应有 {expected}，实际 {set(competitors.keys())}'
