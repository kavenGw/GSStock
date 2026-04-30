"""Intel 产业链海光升级 + 国产配套关系契约测试"""
from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS


# ============ 1. 配置数据结构契约 ============

def test_hygon_present_as_extra_core():
    """海光信息 688041 必须出现在 cpu 图谱的 extra_cores 中"""
    cpu = SUPPLY_CHAIN_GRAPHS['cpu']
    extras = {e['code']: e for e in cpu.get('extra_cores', [])}
    assert '688041' in extras, '海光未升级到 extra_cores'
    hygon = extras['688041']
    assert hygon['name'] == '海光信息'
    assert hygon['market'] == 'A'
    assert hygon['relation_label'] == 'Zen 授权'
    assert 'C86' in hygon['description'], 'description 应描述 C86 架构'
    assert 'Zen' in hygon['description'], 'description 应描述 Zen 授权背景'


def test_hygon_supply_chain_full_stack():
    """海光 supply_chain 应覆盖 5 家国产封测/基板配套：通富/华天/深南/兴森/长电"""
    cpu = SUPPLY_CHAIN_GRAPHS['cpu']
    hygon = next(e for e in cpu['extra_cores'] if e['code'] == '688041')
    expected = {'002156', '002185', '002916', '002436', '600584'}
    actual = set(hygon['supply_chain'].keys())
    assert actual == expected, f'缺失 {expected - actual}，多出 {actual - expected}'
    for code, info in hygon['supply_chain'].items():
        assert info.get('role'), f'{code} 缺 role 字段'


def test_hygon_removed_from_competitors():
    """升级到 extra_core 后，competitors 中不应再有海光，仅龙芯保留"""
    cpu = SUPPLY_CHAIN_GRAPHS['cpu']
    assert '688041' not in cpu['competitors'], 'competitors 中海光未清理（会导致节点重复）'
    assert '688047' in cpu['competitors'], '龙芯应保留为 competitor'
