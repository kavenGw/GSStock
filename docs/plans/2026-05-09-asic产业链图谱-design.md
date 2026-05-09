# ASIC 全景产业链图谱 - 设计文档

> 日期：2026-05-09
> 状态：设计待评审 → 实施
> 关联：`app/config/supply_chain.py` 的 `SUPPLY_CHAIN_GRAPHS` 字典新增 `asic` 条目

## 0. 执行摘要

新增一张 ASIC 全景产业链图谱，覆盖**全球（博通系 / Marvell / Alchip）+ 国产（寒武纪 / 海光 / 华为昇腾 / 平头哥 / 燧原 / 沐曦）**两条设计主线，A 股映射端聚焦封测、FCBGA 基板、AI PCB、HBM 接口、光模块互联、服务器整机六大配套环节。

- **Key**: `asic`
- **Name**: `ASIC 算力芯片`
- **Core**: 博通 AVGO（market: US）
- **Competitors**: Broadcom / Marvell / 寒武纪 / 海光信息
- **与现有图谱关系**：
  - `ascend`（华为昇腾）：保留为深化专题；asic 图含昇腾设计层但不重复封闭链细节
  - `nvidia`（GPU）：平行链路，重叠的封测/PCB/光模块标的在 asic 图 role 末尾加 `(同属 nvidia 产业链)`
  - `cpu`（Intel/AMD/海光）：海光信息既是 CPU 也是 ASIC（DCU 加速卡），asic 图中 role 注明 `(同属 cpu 产业链)`
- **反向引用方向**：单向 — 仅在 asic 图标注同属 ascend/nvidia/cpu，原 3 张图不动

## 1. 背景与动机

### 1.1 现有 14 张图谱的算力覆盖盲区

| 图谱 | 覆盖范围 | 不覆盖 |
|------|---------|-------|
| `nvidia` | NVIDIA GPU、HBM、CoWoS、光模块 | 云厂自研 ASIC、国产 ASIC |
| `ascend` | 华为昇腾闭源链 | 非华为系 ASIC |
| `cpu` | x86 与海光 CPU | TPU/MTIA/Trainium 等 ASIC 设计端 |

→ 全球云厂 ASIC 自研化（TPU 7 / MTIA / Trainium2）与国产替代（寒武纪 / 海光 DCU）同步起量，需要独立图谱呈现。

### 1.2 投资视角

A 股投资者关注 ASIC 的核心是**配套链涨价/份额提升**，而非设计公司本身（博通/寒武纪估值已偏离 buffett 范畴）。重点是：

- **FCBGA 基板**：深南、兴森（AI ASIC 比 CPU 更大尺寸 / 更高层数）
- **AI PCB**：沪电、胜宏（800G 板卡）
- **CoWoS 设备国产替代**：北方华创 / 中微 / 拓荆 / 华海清科
- **光模块**：旭创 / 新易盛 / 天孚 / 光迅（ASIC 集群互联，已在 lumentum 图覆盖，本图重复列入并标注同属链）

## 2. 数据结构设计

### 2.1 顶层结构

```python
'asic': {
    'name': 'ASIC 算力芯片',
    'core': {
        'name': 'Broadcom 博通',
        'code': 'AVGO',
        'market': 'US',
    },
    'description': (
        'ASIC（专用集成电路）算力芯片产业链，覆盖全球云厂自研 ASIC（Google TPU、Meta MTIA、'
        'AWS Trainium、字节自研）与国产 AI ASIC（寒武纪、海光、华为昇腾、平头哥、燧原、沐曦）'
        '两条主线。设计端由 Broadcom / Marvell / Alchip 主导全球代工设计，国产以寒武纪 / 海光为核心。'
        '中国 A 股映射端聚焦 FCBGA 封装基板、高多层 AI PCB、CoWoS 设备国产替代、HBM 接口与分销、'
        '光模块卡间互联、AI 服务器整机六大配套环节，不少标的与 nvidia / ascend / cpu 产业链交叠。'
    ),
    'upstream': { ... },
    'midstream': { ... },
    'downstream': { ... },
    'competitors': {
        'AVGO':   {'name': 'Broadcom 博通', 'market': 'US'},
        'MRVL':   {'name': 'Marvell',       'market': 'US'},
        '688256': {'name': '寒武纪',         'market': 'A'},
        '688041': {'name': '海光信息',       'market': 'A'},
    },
}
```

### 2.2 三层骨架

```
upstream  → 设计 IP / EDA / 晶圆代工 / 先进封装设备 / HBM 制造
midstream → ASIC 设计公司（全球+国产） / 封测 / FCBGA 基板
downstream → 服务器 ODM / AI PCB / 光模块 / 散热与电源
```

### 2.3 upstream 上游（4 子类）

| 子类 | 标的（A 股） | 角色文案 | tag |
|------|------|---------|-----|
| **设计 IP / EDA** | 688521 芯原 | RISC-V / NPU IP，国产 ASIC 设计平台 | not_analyzed |
| **晶圆代工** | 688981 中芯国际 | 寒武纪 / 海光主要代工承接，14nm 已稳定 | not_analyzed |
|  | 688347 华虹半导体 | 28nm 特色工艺，承接部分 ASIC | not_analyzed |
| **CoWoS 设备国产替代** | 002371 北方华创 | 薄膜沉积 / 刻蚀（同属 nvidia 产业链） | (留空，已分析) |
|  | 688012 中微公司 | 刻蚀设备（同属 nvidia 产业链） | (留空，已分析) |
|  | 688072 拓荆科技 | 薄膜沉积，CoWoS 替代关键节点 | not_analyzed |
|  | 688120 华海清科 | CMP 设备，国产唯一 | not_analyzed |
| **HBM 配套** | 688008 澜起科技 | DDR5 / HBM 内存接口 RCD / MRCD / MDB | not_analyzed |
|  | 300475 香农芯创 | SK 海力士 HBM 国内分销 | not_analyzed |

> 海外参考（仅文本描述）：TSM 台积电、SK 海力士 000660.KS、三星电子 005930.KS。

### 2.4 midstream 中游（4 子类）

| 子类 | 标的 | 角色文案 | tag |
|------|------|---------|-----|
| **全球 ASIC 设计** | AVGO Broadcom (US) | 全球 ASIC 代工设计龙头：Google TPU / Meta MTIA / 字节 | (海外，无 tag) |
|  | MRVL Marvell (US) | AWS Trainium / Inferentia 设计代工 | (海外) |
| **国产 ASIC 设计** | 688256 寒武纪 | 国产通用 AI ASIC 设计龙头，思元 590 量产 | not_analyzed |
|  | 688041 海光信息 | DCU 加速卡（GPGPU 形态 ASIC），深算二号量产（同属 cpu 产业链） | not_analyzed |
|  | (文本) 华为昇腾 | 昇腾 910C，深化链路见 ascend 图谱 | — |
|  | (文本) 平头哥 / 燧原 / 沐曦 | 阿里平头哥含光，燧原邃思，沐曦曦云 — 均未上市 | — |
| **封测** | 002156 通富微电 | AMD 合资 TFAMD，海光 / 寒武纪封测主力（同属 cpu/nvidia 产业链） | (留空，已分析) |
|  | 600584 长电科技 | FCBGA / Chiplet / CoWoS-S 替代封装（同属 cpu/nvidia 产业链） | not_analyzed |
|  | 002185 华天科技 | 国产 ASIC / SoC 封测（同属 cpu 产业链） | not_analyzed |
|  | 688362 甬矽电子 | 中高端封测，承接寒武纪部分订单 | not_analyzed |
| **FCBGA 封装基板** | 002916 深南电路 | FCBGA 国产龙头，AI ASIC 大尺寸高层数（同属 cpu/PCB 产业链） | (留空，已分析) |
|  | 002436 兴森科技 | FCBGA 小批量供货北美 ASIC 客户（同属 cpu 产业链） | (留空，已分析) |

### 2.5 downstream 下游（4 子类）

| 子类 | 标的 | 角色文案 | tag |
|------|------|---------|-----|
| **服务器整机 ODM** | 601138 工业富联 | 全球最大 AI 服务器代工，TPU / Trainium 整机集成（同属 cpu/nvidia/ascend 产业链） | (留空，已分析) |
|  | 000977 浪潮信息 | 国产 AI 服务器龙头，海光 / 寒武纪整机（同属 cpu 产业链） | not_analyzed |
|  | 603019 中科曙光 | 海光大股东，DCU 整机捆绑 | not_analyzed |
| **AI PCB** | 002463 沪电股份 | 800G / 1.6T 板卡 PCB（同属 nvidia 产业链） | (留空，已分析) |
|  | 300476 胜宏科技 | 高多层 AI PCB | not_analyzed |
|  | 688183 生益电子 | AI 服务器 PCB | not_analyzed |
| **光模块互联** | 300308 中际旭创 | 800G / 1.6T 光模块（同属 lumentum/nvidia 产业链） | (留空，已分析) |
|  | 300502 新易盛 | 400G / 800G 光模块（同属 lumentum 产业链） | (留空，已分析) |
|  | 300394 天孚通信 | 光引擎 / 连接器（同属 lumentum 产业链） | (留空，已分析) |
|  | 002281 光迅科技 | 光芯片 EML / DFB（同属 lumentum 产业链） | (留空，已分析) |
| **散热 / 电源** | 002837 英维克 | 液冷温控龙头 | not_analyzed |
|  | 300870 欧陆通 | AI 服务器电源 | not_analyzed |

### 2.6 tag 策略

- 默认全部 `not_analyzed`
- 已有 buffett 分析文档的股票（通过 `Glob "docs/analysis/*<code>*"` 验证）→ **留空 tag 字段**，前端默认状态
- frontEC / don_buy / keep_watching 待后续单股分析时按需更新

**待验证名单**（实施第一步用 `Glob "docs/**/*<code>*.md"` 和股票名 grep 双路确认，存在则留空 tag）：

候选股票（基于近期 commits 与现有图谱已标注 frontEC 推断，需实施时校验）：
- 002463 沪电股份、002916 深南电路、002436 兴森科技、002156 通富微电
- 300308 中际旭创、300502 新易盛、300394 天孚通信、002281 光迅科技
- 688012 中微公司、002371 北方华创、601138 工业富联、300620 光库科技

> 实施时第一步即批量 Glob 验证，避免设计阶段误标。未命中文档的标的回落 `not_analyzed`。

## 3. 同属链反向引用规则

仅在 asic 图的 role 文案末尾追加 `(同属 X 产业链)`，原图（ascend/nvidia/cpu/lumentum）不修改。

| 同属链 | 涉及股票 |
|--------|---------|
| 同属 nvidia 产业链 | 002371、688012、002156、600584、002463、300308 |
| 同属 cpu 产业链 | 002156、600584、002185、002916、002436、601138、000977 |
| 同属 ascend 产业链 | 601138 |
| 同属 lumentum 产业链 | 300308、300502、300394、002281 |

多产业链共属时合并标注，如：`...（同属 cpu/nvidia/ascend 产业链）`。

## 4. 实施计划（拆分给 writing-plans）

实施单一文件（`app/config/supply_chain.py`），无路由 / 模板 / seed 改动（产业链路由按 dict 遍历自动注册）。

预计步骤：
1. 在 `SUPPLY_CHAIN_GRAPHS` 字典末尾追加 `'asic': { ... }` 条目（约 200 行）
2. 用 `docs/analysis/` 现有分析交叉校验 tag 留空名单
3. 启动 `python run.py` 验证 `/supply-chain/asic` 路由可访问，前端图谱渲染正常
4. 通过 `Grep "asic"` 在 `app/templates/supply_chain.html` 确认无需新增模板分支

## 5. 验证清单

- [ ] `from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS; print(SUPPLY_CHAIN_GRAPHS['asic']['name'])` 不报错
- [ ] 浏览器访问 `/supply-chain/api/asic` 返回完整 JSON
- [ ] 浏览器访问 `/supply-chain/?graph=asic` 渲染三层结构
- [ ] competitors 区四个标的实时价格正常显示
- [ ] 重叠股票（如 002916 深南电路）在 cpu / asic 两图均能正常出现，前端无报错

## 6. 风险与注意事项

1. **stock_code 唯一约束**：`StockCategory.stock_code` 唯一，不影响图谱（图谱不写库）。但若新引入未在 `Stock` 表的标的（如 688521 芯原、688347 华虹、688072 拓荆、688120 华海清科、688362 甬矽、300476 胜宏、688183 生益电子、002837 英维克、300870 欧陆通），前端实时价显示可能失败 → 实施时确认 `app/seeds/` 是否已包含这些代码，未包含则需追加 seed。
2. **tag 留空 vs not_analyzed 的前端差异**：参照 `app/templates/supply_chain.html` 的 `TAG_LABELS`，留空显示无 badge，not_analyzed 显示「未分析」灰 badge。本设计依赖此区分。
3. **未上市主体的展示**：仅在 description / 子类 header 文本中提及，不进 companies 字典，避免前端点击跳转 404。
