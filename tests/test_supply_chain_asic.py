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


def test_asic_upstream_categories():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    upstream = asic['upstream']
    expected_keys = {'design_ip', 'foundry', 'cowos_equipment', 'hbm'}
    assert set(upstream.keys()) == expected_keys, \
        f'upstream 应有 {expected_keys}，实际 {set(upstream.keys())}'

    for cat_key, cat in upstream.items():
        assert 'name' in cat and 'companies' in cat, f'{cat_key} 缺字段'
        for code, info in cat['companies'].items():
            assert info.get('name') and info.get('role'), \
                f'upstream/{cat_key}/{code} 缺 name 或 role'


def test_asic_upstream_key_companies():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    upstream = asic['upstream']
    assert '688521' in upstream['design_ip']['companies'], '芯原应在设计 IP'
    assert '688981' in upstream['foundry']['companies'], '中芯国际应在晶圆代工'
    assert '002371' in upstream['cowos_equipment']['companies'], '北方华创应在 CoWoS 设备'
    assert '688008' in upstream['hbm']['companies'], '澜起科技应在 HBM'


def test_asic_midstream_categories():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    midstream = asic['midstream']
    expected_keys = {'global_design', 'domestic_design', 'packaging', 'fcbga_substrate'}
    assert set(midstream.keys()) == expected_keys, \
        f'midstream 应有 {expected_keys}，实际 {set(midstream.keys())}'


def test_asic_midstream_key_companies():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    mid = asic['midstream']
    assert 'AVGO' in mid['global_design']['companies'], 'Broadcom 应在全球设计层'
    assert 'MRVL' in mid['global_design']['companies'], 'Marvell 应在全球设计层'
    assert '688256' in mid['domestic_design']['companies'], '寒武纪应在国产设计层'
    assert '688041' in mid['domestic_design']['companies'], '海光应在国产设计层'
    assert '002156' in mid['packaging']['companies'], '通富微电应在封测层'
    assert '002916' in mid['fcbga_substrate']['companies'], '深南电路应在 FCBGA 层'


def test_asic_midstream_global_design_us_market():
    asic = SUPPLY_CHAIN_GRAPHS['asic']
    avgo = asic['midstream']['global_design']['companies']['AVGO']
    assert avgo.get('market') == 'US', '全球设计 AVGO 必须标 market=US'
    mrvl = asic['midstream']['global_design']['companies']['MRVL']
    assert mrvl.get('market') == 'US'
