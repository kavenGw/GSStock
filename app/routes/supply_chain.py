from flask import render_template, jsonify
from app.routes import supply_chain_bp
from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS, get_supply_chain, get_all_stock_codes


@supply_chain_bp.route('/')
def index():
    chains = []
    for key, graph in SUPPLY_CHAIN_GRAPHS.items():
        chains.append({
            'key': key,
            'name': graph['name'],
            'code': graph['code'],
            'description': graph['description'],
        })
    return render_template('supply_chain.html', chains=chains)


@supply_chain_bp.route('/api/<name>')
def get_graph_data(name):
    graph = get_supply_chain(name)
    if not graph:
        return jsonify({'error': 'not found'}), 404

    nodes = []
    edges = []
    node_id = 0

    # 核心节点
    core_id = node_id
    nodes.append({
        'id': core_id,
        'name': f"{graph['name']}\n({graph['code']})",
        'category': 'core',
        'symbolSize': 60,
        'detail': {
            'technologies': graph['core']['technologies'],
            'products': graph['core']['products'],
            'customers': graph['core']['customers'],
        },
    })
    node_id += 1

    # 上游
    for cat_name, cat_info in graph.get('upstream', {}).items():
        group_id = node_id
        nodes.append({
            'id': group_id,
            'name': cat_name,
            'category': 'upstream_group',
            'symbolSize': 35,
            'detail': {'description': cat_info['description']},
        })
        edges.append({'source': group_id, 'target': core_id, 'label': '供应'})
        node_id += 1
        for code, info in cat_info.get('companies', {}).items():
            nodes.append({
                'id': node_id,
                'name': f"{info['name']}\n({code})",
                'category': 'upstream',
                'symbolSize': 25,
                'detail': {'code': code, 'role': info['role'], 'tag': info.get('tag', '')},
            })
            edges.append({'source': node_id, 'target': group_id})
            node_id += 1

    # 中游
    for cat_name, cat_info in graph.get('midstream', {}).items():
        group_id = node_id
        nodes.append({
            'id': group_id,
            'name': cat_name,
            'category': 'midstream_group',
            'symbolSize': 35,
            'detail': {'description': cat_info['description']},
        })
        edges.append({'source': core_id, 'target': group_id, 'label': '代工/封装'})
        node_id += 1
        for code, info in cat_info.get('companies', {}).items():
            nodes.append({
                'id': node_id,
                'name': f"{info['name']}\n({code})",
                'category': 'midstream',
                'symbolSize': 25,
                'detail': {'code': code, 'role': info['role']},
            })
            edges.append({'source': group_id, 'target': node_id})
            node_id += 1

    # 下游
    for cat_name, cat_info in graph.get('downstream', {}).items():
        nodes.append({
            'id': node_id,
            'name': cat_name,
            'category': 'downstream',
            'symbolSize': 30,
            'detail': {'description': cat_info['description']},
        })
        edges.append({'source': core_id, 'target': node_id, 'label': '应用'})
        node_id += 1

    # 竞争对手
    for code, info in graph.get('competitors', {}).items():
        nodes.append({
            'id': node_id,
            'name': f"{info['name']}\n({code})",
            'category': 'competitor',
            'symbolSize': 22,
            'detail': {'code': code, 'market': info['market']},
        })
        edges.append({'source': node_id, 'target': core_id, 'relation': 'compete'})
        node_id += 1

    return jsonify({
        'name': graph['name'],
        'code': graph['code'],
        'core': graph['core'],
        'trends': graph['trends'],
        'nodes': nodes,
        'edges': edges,
        'stock_codes': get_all_stock_codes(name),
    })
