// 骨架屏工具
const Skeleton = {
    show(containerId, type, count = 3) {
        const container = document.getElementById(containerId);
        if (!container) return;
        let html = '';
        for (let i = 0; i < count; i++) {
            if (type === 'card') {
                html += `<div class="skeleton-card skeleton">
                    <div class="skeleton skeleton-text w-60"></div>
                    <div class="skeleton skeleton-price"></div>
                    <div class="skeleton skeleton-change"></div>
                    <div class="skeleton skeleton-info"></div>
                </div>`;
            } else if (type === 'table-row') {
                html += `<div class="skeleton-table-row">
                    <div class="skeleton skeleton-cell skeleton-cell-sm"></div>
                    <div class="skeleton skeleton-cell"></div>
                    <div class="skeleton skeleton-cell skeleton-cell-sm"></div>
                    <div class="skeleton skeleton-cell skeleton-cell-sm"></div>
                </div>`;
            } else if (type === 'chart') {
                html = `<div class="skeleton skeleton-chart"></div>`;
                break;
            } else if (type === 'wyckoff') {
                html += `<div class="skeleton-wyckoff skeleton">
                    <div class="d-flex align-items-center">
                        <div class="skeleton skeleton-circle"></div>
                        <div class="skeleton skeleton-name"></div>
                    </div>
                    <div class="skeleton skeleton-tags"></div>
                </div>`;
            }
        }
        container.dataset.skeletonActive = 'true';
        container.innerHTML = html;
    },

    hide(containerId) {
        const container = document.getElementById(containerId);
        if (container && container.dataset.skeletonActive === 'true') {
            container.innerHTML = '';
            delete container.dataset.skeletonActive;
        }
    },

    isActive(containerId) {
        const container = document.getElementById(containerId);
        return container && container.dataset.skeletonActive === 'true';
    }
};

window.Skeleton = Skeleton;

document.addEventListener('DOMContentLoaded', function() {
    initIndexPage();
    initTrendChart();
    initSectorManageModal();
});

function initIndexPage() {
    const dateSelector = document.getElementById('dateSelector');
    const positionTable = document.getElementById('positionTable');
    const categoryFilter = document.getElementById('categoryFilter');

    if (!dateSelector) return;

    bindStockNameClick();

    // 分类筛选
    if (categoryFilter) {
        categoryFilter.addEventListener('change', () => {
            const url = new URL(window.location);
            url.searchParams.set('category', categoryFilter.value);
            window.location.href = url.toString();
        });
    }

    // 股票分类设置
    document.querySelectorAll('.stock-category-select').forEach(select => {
        select.addEventListener('change', async () => {
            const row = select.closest('tr');
            const stockCode = row.dataset.stockCode;
            const categoryId = select.value ? parseInt(select.value) : null;

            await fetch(`/categories/stock/${stockCode}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category_id: categoryId })
            });
        });
    });

    // 权重设置
    bindWeightInputs();

    dateSelector.addEventListener('change', async () => {
        const date = dateSelector.value;
        const response = await fetch(`/positions/${date}`);

        if (!response.ok) {
            alert('加载数据失败');
            return;
        }

        const data = await response.json();
        window.currentDate = date;
        window.currentRebalanceData = data.rebalance_data || {};
        renderPositions(data.positions, data.advices, data.summary, data.rebalance_data);

        // 重新加载走势图
        if (window.Charts) {
            const trendFilter = document.getElementById('trendCategoryFilter');
            const category = trendFilter ? trendFilter.value : 'all';
            Charts.loadTrendData(date, category);
        }
    });

    function renderPositions(positions, advices, summary, rebalanceData = {}) {
        positionTable.innerHTML = '';
        positions.forEach(p => {
            const advice = advices[p.stock_code] || {};
            const rb = rebalanceData[p.stock_code] || {};

            // 偏差显示
            const deviationClass = rb.deviation > 2 ? 'profit' : rb.deviation < -2 ? 'loss' : '';
            const deviationText = rb.deviation !== undefined ? (rb.deviation > 0 ? '+' : '') + rb.deviation.toFixed(2) + '%' : '--';

            // 操作建议
            let operationHtml = '--';
            if (rb.operation === 'buy') {
                operationHtml = `<span class="badge bg-success">买入 ${rb.shares}股</span>`;
            } else if (rb.operation === 'sell') {
                operationHtml = `<span class="badge bg-danger">卖出 ${rb.shares}股</span>`;
            } else if (rb.operation === 'hold') {
                operationHtml = `<span class="badge bg-secondary">持有</span>`;
            }

            const row = document.createElement('tr');
            row.dataset.stockCode = p.stock_code;
            row.innerHTML = `
                <td>
                    <span class="stock-name-link" data-stock-code="${p.stock_code}" data-stock-name="${p.stock_name}">${p.stock_name}</span>
                </td>
                <td class="category-cell">
                    <select class="form-select form-select-sm stock-category-select">
                        <option value="">未分类</option>
                    </select>
                </td>
                <td>
                    <input type="number" step="0.1" min="0.1" max="99.9"
                           class="form-control form-control-sm weight-input"
                           data-stock-code="${p.stock_code}"
                           value="${rb.weight || 1.0}"
                           style="width: 70px">
                </td>
                <td>${rb.actual_pct !== undefined ? rb.actual_pct.toFixed(2) + '%' : '--'}</td>
                <td>${rb.target_pct !== undefined ? rb.target_pct.toFixed(2) + '%' : '--'}</td>
                <td class="${deviationClass}">${deviationText}</td>
                <td>${operationHtml}</td>
                <td class="sparkline-cell" data-cost-price="${p.cost_price.toFixed(3)}" data-current-price="${p.current_price.toFixed(3)}">
                    <canvas id="sparkline-${p.stock_code}" class="sparkline-canvas"></canvas>
                </td>
                <td class="advice-cell">
                    <input type="number" step="0.01" placeholder="支撑位"
                           class="form-control form-control-sm advice-input"
                           data-field="support_price"
                           value="${advice.support_price || ''}">
                    <input type="number" step="0.01" placeholder="压力位"
                           class="form-control form-control-sm advice-input"
                           data-field="resistance_price"
                           value="${advice.resistance_price || ''}">
                    <textarea placeholder="操作策略"
                              class="form-control form-control-sm advice-input"
                              data-field="strategy">${advice.strategy || ''}</textarea>
                </td>
            `;
            positionTable.appendChild(row);
        });

        // 更新统计卡片
        if (summary) {
            updateSummaryCard(summary);
        }

        bindAdviceInputs();
        bindStockNameClick();
        bindWeightInputs();

        // 渲染迷你图和饼图
        if (window.Charts) {
            Charts.renderPositionPieChart(positions);
            Charts.renderSparklines(positions);
        }
    }

    function updateSummaryCard(summary) {
        const summaryEl = document.getElementById('positionSummary');
        if (!summaryEl) return;

        document.getElementById('summaryMarketValue').textContent = `¥${summary.total_market_value.toFixed(2)}`;
        document.getElementById('summaryCost').textContent = `¥${summary.total_cost.toFixed(2)}`;

        const profitEl = document.getElementById('summaryProfit');
        const profitSign = summary.total_profit >= 0 ? '+' : '';
        profitEl.textContent = `${profitSign}${summary.total_profit.toFixed(2)} (${profitSign}${summary.total_profit_pct.toFixed(2)}%)`;
        profitEl.className = 'position-summary-value ' + (summary.total_profit > 0 ? 'profit' : summary.total_profit < 0 ? 'loss' : '');

        window.currentSummary = summary;
    }

    bindAdviceInputs();

    function bindAdviceInputs() {
        let saveTimeout;

        document.querySelectorAll('.advice-input').forEach(input => {
            input.addEventListener('input', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => saveAdvice(input), 500);
            });
        });
    }

    async function saveAdvice(input) {
        const row = input.closest('tr');
        const stockCode = row.dataset.stockCode;
        const date = window.currentDate;

        const adviceData = {
            stock_code: stockCode,
            date: date,
        };

        row.querySelectorAll('.advice-input').forEach(inp => {
            const field = inp.dataset.field;
            const value = inp.value.trim();
            if (field === 'strategy') {
                adviceData[field] = value || null;
            } else {
                adviceData[field] = value ? parseFloat(value) : null;
            }
        });

        await fetch('/advices/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(adviceData)
        });
    }
}

function bindStockNameClick() {
    document.querySelectorAll('.stock-name-link').forEach(el => {
        el.addEventListener('click', () => {
            const stockCode = el.dataset.stockCode;
            const stockName = el.dataset.stockName;
            if (window.Charts) {
                Charts.openStockDetailModal(stockCode, stockName);
            }
        });
    });
}

function bindWeightInputs() {
    document.querySelectorAll('.weight-input').forEach(input => {
        if (input.dataset.bound) return;
        input.dataset.bound = 'true';

        input.addEventListener('change', async function() {
            const stockCode = this.dataset.stockCode;
            const weight = parseFloat(this.value);

            if (isNaN(weight) || weight <= 0) {
                alert('权重必须大于 0');
                this.value = 1.0;
                return;
            }

            if (weight > 99.99) {
                alert('权重不能超过 99.99');
                this.value = 99.99;
                return;
            }

            const response = await fetch('/rebalance/api/weight', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_code: stockCode, weight: weight })
            });

            const data = await response.json();
            if (!data.success) {
                alert(data.error || '保存失败，请重试');
            } else {
                window.location.reload();
            }
        });
    });
}

function initTrendChart() {
    const trendFilter = document.getElementById('trendCategoryFilter');
    if (!trendFilter) return;

    // 初始加载
    if (window.currentDate && window.Charts) {
        Charts.loadTrendData(window.currentDate, 'all');
    }

    // 分类筛选
    trendFilter.addEventListener('change', () => {
        if (window.Charts && window.Charts.trendData) {
            Charts.renderTrendChart(null, trendFilter.value);
        }
    });
}

function initSectorManageModal() {
    const modal = document.getElementById('sectorManageModal');
    const sectorTree = document.getElementById('sectorTree');
    const createForm = document.getElementById('createSectorForm');

    if (!modal || !sectorTree || !createForm) return;

    // Modal打开时加载板块树
    modal.addEventListener('shown.bs.modal', loadSectorTree);

    // Modal关闭时刷新下拉框
    modal.addEventListener('hidden.bs.modal', refreshSectorDropdowns);

    // 创建一级板块
    createForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('newSectorName');
        const name = input.value.trim();
        if (!name) return;

        const res = await fetch('/categories', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        input.value = '';
        loadSectorTree();
    });

    // 事件委托：处理子板块添加、编辑、删除
    sectorTree.addEventListener('click', async (e) => {
        const btn = e.target;

        // 添加子板块
        if (btn.classList.contains('add-child-btn')) {
            const parentId = btn.dataset.parentId;
            const name = prompt('输入子板块名称');
            if (!name || !name.trim()) return;

            const res = await fetch('/categories', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name.trim(), parent_id: parseInt(parentId)})
            });
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }
            loadSectorTree();
        }

        // 编辑板块
        if (btn.classList.contains('edit-sector-btn')) {
            const id = btn.dataset.id;
            const oldName = btn.dataset.name;
            const newName = prompt('编辑板块名称', oldName);
            if (!newName || newName.trim() === oldName) return;

            const res = await fetch(`/categories/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: newName.trim()})
            });
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }
            loadSectorTree();
        }

        // 删除板块
        if (btn.classList.contains('delete-sector-btn')) {
            const id = btn.dataset.id;
            const hasChildren = btn.dataset.hasChildren === 'true';
            const msg = hasChildren
                ? '确定删除此板块？其子板块和关联股票将一并处理。'
                : '确定删除此板块？关联的股票将变为未设板块。';
            if (!confirm(msg)) return;

            const res = await fetch(`/categories/${id}`, {method: 'DELETE'});
            if (res.ok) {
                loadSectorTree();
            }
        }
    });
}

async function loadSectorTree() {
    const sectorTree = document.getElementById('sectorTree');
    if (!sectorTree) return;

    const res = await fetch('/categories/tree');
    const data = await res.json();
    const categories = data.categories || [];

    if (categories.length === 0) {
        sectorTree.innerHTML = '<div class="text-center text-muted py-3">暂无板块</div>';
        return;
    }

    let html = '';
    categories.forEach(parent => {
        const hasChildren = parent.children && parent.children.length > 0;
        html += `
            <div class="card mb-2">
                <div class="card-header d-flex justify-content-between align-items-center py-2">
                    <span class="fw-bold">${parent.name}</span>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-success add-child-btn" data-parent-id="${parent.id}">+子</button>
                        <button class="btn btn-outline-primary edit-sector-btn" data-id="${parent.id}" data-name="${parent.name}">编辑</button>
                        <button class="btn btn-outline-danger delete-sector-btn" data-id="${parent.id}" data-has-children="${hasChildren}">删除</button>
                    </div>
                </div>
                ${hasChildren ? `
                <ul class="list-group list-group-flush">
                    ${parent.children.map(child => `
                    <li class="list-group-item d-flex justify-content-between align-items-center py-2">
                        <span class="ms-3">${child.name}</span>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary edit-sector-btn" data-id="${child.id}" data-name="${child.name}">编辑</button>
                            <button class="btn btn-outline-danger delete-sector-btn" data-id="${child.id}" data-has-children="false">删除</button>
                        </div>
                    </li>
                    `).join('')}
                </ul>
                ` : ''}
            </div>
        `;
    });

    sectorTree.innerHTML = html;
}

async function refreshSectorDropdowns() {
    const res = await fetch('/categories/tree');
    const data = await res.json();
    const categories = data.categories || [];

    // 更新顶部筛选器
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        const currentValue = categoryFilter.value;
        let options = `<option value="all">全部板块</option><option value="uncategorized">未设板块</option>`;
        categories.forEach(parent => {
            options += `<optgroup label="${parent.name}">`;
            options += `<option value="${parent.id}">${parent.name}（全部）</option>`;
            (parent.children || []).forEach(child => {
                options += `<option value="${child.id}">${child.name}</option>`;
            });
            options += `</optgroup>`;
        });
        categoryFilter.innerHTML = options;
        categoryFilter.value = currentValue;
    }

    // 更新走势图筛选器
    const trendFilter = document.getElementById('trendCategoryFilter');
    if (trendFilter) {
        const currentValue = trendFilter.value;
        let options = `<option value="all">全部板块</option><option value="uncategorized">未设板块</option>`;
        categories.forEach(parent => {
            options += `<optgroup label="${parent.name}">`;
            options += `<option value="${parent.id}">${parent.name}（全部）</option>`;
            (parent.children || []).forEach(child => {
                options += `<option value="${child.id}">${child.name}</option>`;
            });
            options += `</optgroup>`;
        });
        trendFilter.innerHTML = options;
        trendFilter.value = currentValue;
    }

    // 更新所有股票板块下拉框
    document.querySelectorAll('.stock-category-select').forEach(select => {
        const currentValue = select.value;
        let options = `<option value="">未设板块</option>`;
        categories.forEach(parent => {
            if (parent.children && parent.children.length > 0) {
                options += `<optgroup label="${parent.name}">`;
                parent.children.forEach(child => {
                    options += `<option value="${child.id}">${child.name}</option>`;
                });
                options += `</optgroup>`;
            } else {
                options += `<option value="${parent.id}">${parent.name}</option>`;
            }
        });
        select.innerHTML = options;
        select.value = currentValue;
    });

    // 更新全局缓存
    window.categoryTree = categories;
}
