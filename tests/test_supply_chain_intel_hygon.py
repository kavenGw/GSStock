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


# ============ 2. 路由 JSON 契约 ============

import pytest
from flask import Flask


@pytest.fixture
def client():
    """轻量路由测试：跳过 create_app（API 端点不渲染模板，无需 app context）"""
    from app.routes import supply_chain_bp
    app = Flask(__name__)
    app.register_blueprint(supply_chain_bp, url_prefix='/supply-chain')
    return app.test_client()


def test_extra_core_uses_custom_relation_label(client):
    """海光 extra_core 与 Intel core 之间的边 label 应为 'Zen 授权'"""
    resp = client.get('/supply-chain/api/cpu')
    data = resp.get_json()
    nodes = {n['id']: n for n in data['nodes']}

    intel_id = next(n['id'] for n in data['nodes']
                    if n['category'] == 'core' and 'INTC' in n['name'])
    hygon_id = next(n['id'] for n in data['nodes']
                    if n['category'] == 'core' and '688041' in n['name'])

    edge = next(e for e in data['edges']
                if e['source'] == intel_id and e['target'] == hygon_id)
    assert edge['label'] == 'Zen 授权', \
        f"海光边 label 应为 'Zen 授权'，实际：{edge.get('label')}"


def test_extra_core_default_label_unchanged(client):
    """未配置 relation_label 的 extra_core（如 AMD）边 label 应回退为 '同业'"""
    resp = client.get('/supply-chain/api/cpu')
    data = resp.get_json()

    intel_id = next(n['id'] for n in data['nodes']
                    if n['category'] == 'core' and 'INTC' in n['name'])
    amd_id = next(n['id'] for n in data['nodes']
                  if n['category'] == 'core' and 'AMD' in n['name'])

    edge = next(e for e in data['edges']
                if e['source'] == intel_id and e['target'] == amd_id)
    assert edge['label'] == '同业', \
        f"AMD 边 label 应保持 '同业' 默认，实际：{edge.get('label')}"
