# Intel 产业链：海光信息升级与国产配套协同

**日期**：2026-04-30
**作者**：kavenGw
**Scope**：`app/config/supply_chain.py` 中 `cpu` 图谱 + `app/routes/supply_chain.py` 路由

---

## 背景

当前 Intel 产业链图谱中海光信息（688041）的状态：

- 仅出现在 `competitors`，仅有 `name` + `market` 字段
- AMD 已是 `extra_cores`（双核心），海光未对等表达
- 海光实际是通富/华天/深南/兴森/长电的下游客户，「Intel→海光→国产封测/基板」的国产替代闭环未在图谱体现
- AMD Zen 授权给海光的产业链衍生关系仅在 AMD description 一行带过

## 目标

1. 海光信息升级为 `extra_cores`（与 AMD 对等的核心节点）
2. 路由层支持 `extra_core` 节点的自定义关系标签（`relation_label`）
3. 路由层支持 `extra_core` 节点的产业链配套字段（`supply_chain`），自动建立到既有节点的边
4. 仅修改本次 scope 内的 cpu 图谱；路由能力一次到位以便其他图谱（NVIDIA/HBM）后续复用

## 非目标

- 不动 `app/seeds/cpu_category.py`（海光 advice 已完整）
- 不修改 NVIDIA/HBM 图谱中海光的 competitors 条目
- 不修改 `app/templates/supply_chain.html`（前端通过 nodes/edges JSON 消费数据，无需改）
- 不引入 `tag` 字段到 extra_core 或 supply_chain 子条目

---

## 设计

### 1. 数据结构变更（`app/config/supply_chain.py`）

#### 1.1 cpu 图谱 `extra_cores` 追加海光条目

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

#### 1.2 cpu 图谱 `competitors` 移除海光

```python
'competitors': {
    '688047': {'name': '龙芯中科', 'market': 'A'},
},
```

理由：龙芯走 LoongArch 自研路线是 Intel 真正的竞争路线；海光走 Zen 授权衍生，本质是 x86 阵营的国产替代分支，作为 extra_core 表达更准确，避免节点重复。

### 2. 路由变更（`app/routes/supply_chain.py`）

#### 2.1 extra_core 边 label 支持自定义

第 60 行：
```python
'label': extra.get('relation_label', '同业'),
```
未配置 `relation_label` 的图谱（如 lumentum/nvidia 当前的 extra_cores）回退为 `'同业'`，零回归。

#### 2.2 extra_core 的 supply_chain 配套关系

**核心难点**：路由顺序是 `core → extra_cores → upstream → midstream → downstream → competitors`。extra_cores 处理时，配套公司节点尚未建立。

**解决方案**：

1. 在路由起始处声明：
   ```python
   code_to_node_id: dict[str, int] = {}
   pending_supply_edges: list[tuple[int, dict]] = []
   ```

2. 在 upstream/midstream/downstream 的公司节点构建处填充 `code_to_node_id[code] = node_id`

3. extra_cores 处理时，若 dict 含 `supply_chain` 字段：
   ```python
   if extra.get('supply_chain'):
       pending_supply_edges.append((extra_node_id, extra['supply_chain']))
   ```

4. competitors 处理完成后追加新阶段：
   ```python
   for extra_node_id, supply_chain in pending_supply_edges:
       for code, info in supply_chain.items():
           target_id = code_to_node_id.get(code)
           if target_id is None:
               continue
           edges.append({
               'source': extra_node_id,
               'target': target_id,
               'label': '配套',
               'relation': 'supply',
           })
   ```

**边方向**：海光 → 配套公司，与现有 midstream `core → group → company` 方向一致。

**容错**：`code_to_node_id.get(code)` 为 None 时 silently skip（保持路由现有"无 logger"风格）。

### 3. 影响面

| 模块 | 改动 | 回归风险 |
|------|------|---------|
| `app/config/supply_chain.py` cpu 图谱 | extra_cores 新增 1 条、competitors 删除 1 条 | 无（数据增量+合理删除） |
| `app/routes/supply_chain.py` | extra_core label 自定义、supply_chain 边构建 | 其他图谱用 `.get()` 默认值回退，零行为变化 |
| `app/templates/supply_chain.html` | 不动 | — |
| `app/seeds/cpu_category.py` | 不动 | — |

---

## 验证

### 数据层验证

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "
from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS
cpu = SUPPLY_CHAIN_GRAPHS['cpu']
extras = {e['code']: e for e in cpu['extra_cores']}
assert '688041' in extras, '海光未升级 extra_core'
assert extras['688041'].get('relation_label') == 'Zen 授权'
assert len(extras['688041']['supply_chain']) == 5
assert '688041' not in cpu['competitors'], 'competitors 未清理海光'
print('OK')
"
```

### 路由层验证

启动应用后 GET `/supply-chain/api/cpu`，预期：

- `nodes` 中 `category='core'` 至少 3 个：Intel（INTC）+ AMD + 海光（688041）
- `edges` 中存在 1 条 `source=Intel core, target=海光 core, label='Zen 授权'`
- `edges` 中存在 5 条 `source=海光 core, target=封测/基板节点, label='配套', relation='supply'`
- `nodes` 中 `category='competitor'` 不应再出现 688041，应仅含 688047 龙芯中科

### 视觉验证

访问 `/supply-chain/` → 选「Intel」图谱 → 确认：

- 海光节点居中显示（与 AMD 对等大小）
- 海光与 Intel 之间的边标签显示「Zen 授权」
- 海光向通富/华天/深南/兴森/长电分别有 5 条「配套」边
- 边密度在可接受范围（不过分密集影响可读性）

### 回归验证

访问其他图谱确认未受影响：
- `/supply-chain/api/lumentum`：extra_cores 节点边 label 应仍为「同业」
- `/supply-chain/api/nvidia`：海光仍出现在 competitors（本次 scope 不动）
- `/supply-chain/api/hbm`：海光仍出现在 competitors（本次 scope 不动）

---

## 后续可选事项（非本次 scope）

- NVIDIA/HBM 图谱中海光的 competitors 条目可后续补 description（与本次解耦）
- 海光 extra_core 的 description 后续可补 DCU 出货、信创订单等数据点（视图谱信息密度）
- 路由层 `code_to_node_id` 抽象后，可支持其他图谱也使用 `supply_chain` 字段（如 NVIDIA 图谱里加海光的 DCU 配套）

---

## Commit 计划

单个 commit：
```
feat: Intel 产业链海光升级为 extra_core 并建立国产封测/基板配套关系

- 海光 688041 从 competitors 升级到 extra_cores，relation_label='Zen 授权'
- 新增 supply_chain 字段映射 5 家配套公司（通富/华天/深南/兴森/长电）
- 路由层支持 extra_core 自定义 relation_label 和 supply_chain 边构建
- 其他图谱通过 .get() 回退默认值，零回归
```
