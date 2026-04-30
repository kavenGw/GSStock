# Intel 产业链海光完善 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Intel 产业链图谱中的海光信息（688041）从 `competitors` 升级为 `extra_cores`，并通过路由层支持自定义 `relation_label` 和 `supply_chain` 字段，建立海光与 5 家国产封测/基板配套公司之间的产业链协同边。

**Architecture:** 仅修改 `app/config/supply_chain.py`（cpu 图谱配置）和 `app/routes/supply_chain.py`（API 路由）。前端 `supply_chain.html` 通过 nodes/edges JSON 消费数据，无需改动。新增三个 pytest 文件锁定数据结构与路由行为契约。

**Tech Stack:** Python 3 / Flask Blueprint / pytest / dict 配置数据。

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `app/config/supply_chain.py` | Modify | cpu 图谱：新增 extra_cores 海光条目、清理 competitors |
| `app/routes/supply_chain.py` | Modify | extra_core 自定义 relation_label、supply_chain 边构建 |
| `tests/test_supply_chain_intel_hygon.py` | Create | 配置数据结构 + 路由 JSON 输出契约 |

---

## Task 1：升级海光为 extra_core，清理 competitors

**Files:**
- Test: `tests/test_supply_chain_intel_hygon.py` (create)
- Modify: `app/config/supply_chain.py:80-136` (cpu 图谱 dict)

- [ ] **Step 1: 写失败测试**

新建 `tests/test_supply_chain_intel_hygon.py`：

```python
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
    assert '海光' not in hygon.get('description', '') or 'C86' in hygon['description'], \
        'description 应描述 C86/Zen 授权背景'


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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py -v
```

预期：3 个测试全部 FAIL（海光仍在 competitors，extra_cores 只有 AMD）。

- [ ] **Step 3: 修改 cpu 图谱配置**

打开 `app/config/supply_chain.py`，定位 cpu 图谱（line 80 起）：

**3a. 在 `extra_cores` 列表追加海光条目**（第 95 行 AMD 条目后）：

```python
        'extra_cores': [
            {
                'code': 'AMD',
                'name': 'AMD',
                'market': 'US',
                'description': 'x86 CPU/GPU 双线龙头，Zen 架构授权海光',
            },
            {
                'code': '688041',
                'name': '海光信息',
                'market': 'A',
                'description': 'Hygon C86 架构（AMD Zen 授权）国产 x86 龙头，CPU + DCU AI 加速卡双主线，信创/AI 算力主力供应商',
                'relation_label': 'Zen 授权',
                'supply_chain': {
                    '002156': {'role': 'DCU/CPU 封测主力供应商'},
                    '002185': {'role': '国产 SoC/CPU 封测配套'},
                    '002916': {'role': 'FC-BGA 封装基板国产替代'},
                    '002436': {'role': 'FC-BGA 基板备选供应商'},
                    '600584': {'role': 'Chiplet/FCBGA 高端封装'},
                },
            },
        ],
```

**3b. 在 `competitors` 中删除海光**（第 127-130 行）：

```python
        'competitors': {
            '688047': {'name': '龙芯中科', 'market': 'A'},
        },
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py -v
```

预期：3 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tests/test_supply_chain_intel_hygon.py app/config/supply_chain.py
git commit -m "feat(supply_chain): 海光信息从 Intel 图谱 competitors 升级为 extra_core

- 新增 supply_chain 字段映射 5 家国产封测/基板配套（通富/华天/深南/兴森/长电）
- relation_label='Zen 授权' 描述与 AMD 的衍生关系
- competitors 仅保留龙芯（自研 LoongArch 路线）"
```

---

## Task 2：路由支持 extra_core 自定义 relation_label

**Files:**
- Test: `tests/test_supply_chain_intel_hygon.py` (append)
- Modify: `app/routes/supply_chain.py:60`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_supply_chain_intel_hygon.py` 末尾追加：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py::test_extra_core_uses_custom_relation_label tests/test_supply_chain_intel_hygon.py::test_extra_core_default_label_unchanged -v
```

预期：第 1 个 FAIL（label 实际是硬编码 '同业'），第 2 个 PASS。

- [ ] **Step 3: 修改路由的 extra_core 边 label**

打开 `app/routes/supply_chain.py`，定位第 57-62 行：

**修改前：**
```python
        edges.append({
            'source': core_id,
            'target': node_id,
            'label': '同业',
            'relation': 'alliance',
        })
```

**修改后：**
```python
        edges.append({
            'source': core_id,
            'target': node_id,
            'label': extra.get('relation_label', '同业'),
            'relation': 'alliance',
        })
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py -v
```

预期：5 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add tests/test_supply_chain_intel_hygon.py app/routes/supply_chain.py
git commit -m "feat(supply_chain): extra_core 支持自定义 relation_label

- 路由读 extra['relation_label']，未配置则回退 '同业'
- 其他图谱（lumentum/nvidia 等）零回归"
```

---

## Task 3：路由支持 supply_chain 边构建

**Files:**
- Test: `tests/test_supply_chain_intel_hygon.py` (append)
- Modify: `app/routes/supply_chain.py:25-145` (引入 code_to_node_id + pending_supply_edges)

- [ ] **Step 1: 追加失败测试**

在 `tests/test_supply_chain_intel_hygon.py` 末尾追加：

```python
def test_hygon_has_five_supply_chain_edges(client):
    """海光应有 5 条 label='配套' 边连向通富/华天/深南/兴森/长电"""
    resp = client.get('/supply-chain/api/cpu')
    data = resp.get_json()

    hygon_id = next(n['id'] for n in data['nodes']
                    if n['category'] == 'core' and '688041' in n['name'])

    supply_edges = [e for e in data['edges']
                    if e['source'] == hygon_id and e.get('label') == '配套']
    assert len(supply_edges) == 5, \
        f"海光应有 5 条配套边，实际：{len(supply_edges)}"

    target_codes = set()
    for e in supply_edges:
        target_node = next(n for n in data['nodes'] if n['id'] == e['target'])
        # node name 格式 '名称\n(code)'
        code = target_node['name'].split('(')[-1].rstrip(')')
        target_codes.add(code)
        assert e.get('relation') == 'supply', f"配套边 relation 应为 'supply'"

    assert target_codes == {'002156', '002185', '002916', '002436', '600584'}, \
        f"配套目标公司不匹配：{target_codes}"


def test_no_supply_edges_for_graphs_without_supply_chain(client):
    """未配置 supply_chain 的图谱（lumentum）不应产生 '配套' 边，零回归"""
    resp = client.get('/supply-chain/api/lumentum')
    data = resp.get_json()
    supply_edges = [e for e in data['edges'] if e.get('label') == '配套']
    assert supply_edges == [], f"lumentum 不应有配套边，实际：{len(supply_edges)} 条"


def test_hygon_no_longer_in_competitors_nodes(client):
    """海光升级后，nodes 中 category=competitor 的 688041 应消失"""
    resp = client.get('/supply-chain/api/cpu')
    data = resp.get_json()
    competitor_codes = [
        n['name'].split('(')[-1].rstrip(')')
        for n in data['nodes'] if n['category'] == 'competitor'
    ]
    assert '688041' not in competitor_codes, '海光不应同时存在于 competitor 节点'
    assert '688047' in competitor_codes, '龙芯应保留为 competitor 节点'
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py -v
```

预期：`test_hygon_has_five_supply_chain_edges` FAIL（路由还没读 supply_chain），其他 PASS。

- [ ] **Step 3: 改造路由引入 code_to_node_id + pending_supply_edges**

打开 `app/routes/supply_chain.py`，整体改造 `get_graph_data` 函数。

**3a. 在 `node_id = 0` 后（line 27 后）新增两个累积变量：**

```python
    nodes = []
    edges = []
    node_id = 0
    code_to_node_id: dict[str, int] = {}
    pending_supply_edges: list[tuple[int, dict]] = []
```

**3b. 在 extra_cores 循环中（line 45-63），处理 supply_chain 字段：**

修改 extra_cores 循环（找到 line 45 `for extra in graph.get('extra_cores', []) or []:`），在 `node_id += 1` 之前插入 supply_chain 暂存逻辑：

```python
    for extra in graph.get('extra_cores', []) or []:
        nodes.append({
            'id': node_id,
            'name': f"{extra['name']}\n({extra['code']})",
            'category': 'core',
            'symbolSize': 55,
            'detail': {
                'code': extra['code'],
                'market': extra.get('market', ''),
                'description': extra.get('description', ''),
            },
        })
        edges.append({
            'source': core_id,
            'target': node_id,
            'label': extra.get('relation_label', '同业'),
            'relation': 'alliance',
        })
        if extra.get('supply_chain'):
            pending_supply_edges.append((node_id, extra['supply_chain']))
        node_id += 1
```

**3c. 在 upstream 公司节点构建处填充 code_to_node_id**

定位 line 77-86 上游公司循环，在 `nodes.append(...)` 后增加：

```python
        for code, info in cat_info.get('companies', {}).items():
            nodes.append({
                'id': node_id,
                'name': f"{info['name']}\n({code})",
                'category': 'upstream',
                'symbolSize': 25,
                'detail': {'code': code, 'role': info['role'], 'tag': info.get('tag', '')},
            })
            edges.append({'source': node_id, 'target': group_id})
            code_to_node_id[code] = node_id
            node_id += 1
```

**3d. 在 midstream 公司节点构建处填充 code_to_node_id**

定位 line 100-109，同样在公司节点 append 后追加 `code_to_node_id[code] = node_id`：

```python
        for code, info in cat_info.get('companies', {}).items():
            nodes.append({
                'id': node_id,
                'name': f"{info['name']}\n({code})",
                'category': 'midstream',
                'symbolSize': 25,
                'detail': {'code': code, 'role': info['role'], 'tag': info.get('tag', '')},
            })
            edges.append({'source': group_id, 'target': node_id})
            code_to_node_id[code] = node_id
            node_id += 1
```

**3e. 在 downstream 公司节点构建处填充 code_to_node_id**

定位 line 123-132，同样追加：

```python
        for code, info in cat_info.get('companies', {}).items():
            nodes.append({
                'id': node_id,
                'name': f"{info['name']}\n({code})",
                'category': 'downstream',
                'symbolSize': 22,
                'detail': {'code': code, 'role': info['role'], 'tag': info.get('tag', '')},
            })
            edges.append({'source': group_id, 'target': node_id})
            code_to_node_id[code] = node_id
            node_id += 1
```

**3f. 在 competitors 循环结束后、`return jsonify(...)` 之前（line 144 后），追加配套边构建：**

```python
    # extra_core 的 supply_chain 配套边（延迟到所有公司节点建完后）
    for extra_node_id, supply_chain in pending_supply_edges:
        for code, info in supply_chain.items():
            target_id = code_to_node_id.get(code)
            if target_id is None:
                continue  # 配套公司未在上中下游出现，silently skip
            edges.append({
                'source': extra_node_id,
                'target': target_id,
                'label': '配套',
                'relation': 'supply',
            })

    return jsonify({
```

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_supply_chain_intel_hygon.py -v
```

预期：8 个测试全部 PASS。

- [ ] **Step 5: 回归校验其他图谱 JSON 结构未损**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "
from app.routes import supply_chain_bp
from flask import Flask
app = Flask(__name__)
app.register_blueprint(supply_chain_bp, url_prefix='/supply-chain')
client = app.test_client()
for name in ['lumentum', 'cpu', 'nvidia', 'hbm', 'worldcup_2026']:
    r = client.get(f'/supply-chain/api/{name}')
    assert r.status_code == 200, f'{name} 路由失败'
    data = r.get_json()
    assert 'nodes' in data and 'edges' in data, f'{name} JSON 结构异常'
    print(f'{name}: {len(data[\"nodes\"])} nodes, {len(data[\"edges\"])} edges')
print('OK')
"
```

预期：5 个图谱全部返回 200，输出节点/边数量。

- [ ] **Step 6: Commit**

```bash
git add tests/test_supply_chain_intel_hygon.py app/routes/supply_chain.py
git commit -m "feat(supply_chain): extra_core 支持 supply_chain 字段构建配套边

- 维护 code_to_node_id 映射 + pending_supply_edges 延后构建
- 海光向通富/华天/深南/兴森/长电产生 5 条 label='配套' 边
- 其他图谱未配 supply_chain，零回归"
```

---

## Task 4：浏览器视觉验证

- [ ] **Step 1: 启动应用**

```bash
python run.py
```

- [ ] **Step 2: 浏览器打开 Intel 图谱**

访问 `http://127.0.0.1:5000/supply-chain/`，下拉选「Intel」。

- [ ] **Step 3: 视觉确认（人工检查）**

- 海光节点（与 AMD 相近大小）出现在中心区域
- Intel ↔ 海光 边显示「Zen 授权」标签
- Intel ↔ AMD 边显示「同业」标签
- 海光向 通富微电(002156) / 华天科技(002185) / 深南电路(002916) / 兴森科技(002436) / 长电科技(600584) 5 个节点连出可见边
- 龙芯中科(688047) 仍作为 competitor 节点存在
- 海光不在 competitor 区域重复出现

- [ ] **Step 4: 关闭应用，清理**

如视觉验证发现问题，回到对应 Task 修复，否则任务完成。

---

## 回归与边界

| 风险 | 缓解 |
|------|------|
| 其他图谱 extra_cores 未配 relation_label | `.get(..., '同业')` 默认值回退，已在 Task 2 测试覆盖 |
| 其他图谱 extra_cores 未配 supply_chain | `extra.get('supply_chain')` 为 falsy 不入 pending 列表，零回归，已在 Task 3 测试覆盖 |
| supply_chain 引用的 code 未在上中下游出现 | `code_to_node_id.get(code)` 为 None 时 silently skip，不抛错 |
| 路由层无现成单测样板 | Task 2 引入 Flask test client，跳过 create_app（CLAUDE.md 已说明 API 端点无 base.html 依赖） |

---

## 设计文档参考

完整背景见 `docs/plans/2026-04-30-intel-海光产业链完善-design.md`。
