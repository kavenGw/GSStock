/**
 * 交易策略页面脚本
 */
const StrategyPage = {
    strategyModal: null,
    executeModal: null,
    currentFilter: null,
    showInactive: false,

    init() {
        this.strategyModal = new bootstrap.Modal(document.getElementById('strategyModal'));
        this.executeModal = new bootstrap.Modal(document.getElementById('executeModal'));

        // 设置默认日期为今天
        document.getElementById('executeDate').value = new Date().toISOString().split('T')[0];

        // 加载执行记录
        this.loadExecutions();
    },

    // 显示新增策略模态框
    showAddModal() {
        document.getElementById('strategyModalTitle').textContent = '新增策略';
        document.getElementById('strategyForm').reset();
        document.getElementById('strategyId').value = '';
        document.getElementById('strategyCategory').value = 'general';
        document.getElementById('actionType').value = 'switch';
        document.getElementById('strategyPriority').value = '0';
        this.strategyModal.show();
    },

    // 编辑策略
    async edit(id) {
        try {
            const resp = await fetch(`/strategies/api/${id}`);
            const data = await resp.json();
            if (!data.success) {
                alert(data.error || '获取策略失败');
                return;
            }

            const s = data.strategy;
            document.getElementById('strategyModalTitle').textContent = '编辑策略';
            document.getElementById('strategyId').value = s.id;
            document.getElementById('strategyName').value = s.name || '';
            document.getElementById('strategyCategory').value = s.category || 'general';
            document.getElementById('triggerMarket').value = s.trigger_market || '';
            document.getElementById('triggerIndex').value = s.trigger_index || '';
            document.getElementById('triggerCondition').value = s.trigger_condition || '';
            document.getElementById('actionType').value = s.action_type || 'switch';
            document.getElementById('sellTarget').value = s.sell_target || '';
            document.getElementById('buyTarget').value = s.buy_target || '';
            document.getElementById('strategyDescription').value = s.description || '';
            document.getElementById('strategyPriority').value = s.priority || 0;
            document.getElementById('strategyNotes').value = s.notes || '';

            this.strategyModal.show();
        } catch (e) {
            alert('获取策略失败: ' + e.message);
        }
    },

    // 保存策略
    async save() {
        const id = document.getElementById('strategyId').value;
        const data = {
            name: document.getElementById('strategyName').value.trim(),
            category: document.getElementById('strategyCategory').value,
            trigger_market: document.getElementById('triggerMarket').value || null,
            trigger_index: document.getElementById('triggerIndex').value.trim() || null,
            trigger_condition: document.getElementById('triggerCondition').value.trim(),
            action_type: document.getElementById('actionType').value,
            sell_target: document.getElementById('sellTarget').value.trim() || null,
            buy_target: document.getElementById('buyTarget').value.trim() || null,
            description: document.getElementById('strategyDescription').value.trim() || null,
            priority: parseInt(document.getElementById('strategyPriority').value) || 0,
            notes: document.getElementById('strategyNotes').value.trim() || null,
        };

        if (!data.name || !data.trigger_condition || !data.action_type) {
            alert('请填写必填字段');
            return;
        }

        try {
            const url = id ? `/strategies/api/${id}` : '/strategies/api/create';
            const method = id ? 'PUT' : 'POST';

            const resp = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await resp.json();
            if (!result.success) {
                alert(result.error || '保存失败');
                return;
            }

            this.strategyModal.hide();
            location.reload();
        } catch (e) {
            alert('保存失败: ' + e.message);
        }
    },

    // 删除策略
    async delete(id) {
        if (!confirm('确定要删除这个策略吗？相关的执行记录也会被删除。')) {
            return;
        }

        try {
            const resp = await fetch(`/strategies/api/${id}`, { method: 'DELETE' });
            const result = await resp.json();

            if (!result.success) {
                alert(result.error || '删除失败');
                return;
            }

            location.reload();
        } catch (e) {
            alert('删除失败: ' + e.message);
        }
    },

    // 切换启用状态
    async toggle(id) {
        try {
            const resp = await fetch(`/strategies/api/${id}/toggle`, { method: 'POST' });
            const result = await resp.json();

            if (!result.success) {
                alert(result.error || '操作失败');
                return;
            }

            location.reload();
        } catch (e) {
            alert('操作失败: ' + e.message);
        }
    },

    // 显示执行记录模态框
    async execute(id) {
        try {
            const resp = await fetch(`/strategies/api/${id}`);
            const data = await resp.json();
            if (!data.success) {
                alert(data.error || '获取策略失败');
                return;
            }

            const s = data.strategy;
            document.getElementById('executeForm').reset();
            document.getElementById('executeStrategyId').value = s.id;
            document.getElementById('executeStrategyName').value = s.name;
            document.getElementById('executeDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('executeTriggeredBy').value = s.trigger_condition || '';
            document.getElementById('executeResult').value = 'success';

            this.executeModal.show();
        } catch (e) {
            alert('获取策略失败: ' + e.message);
        }
    },

    // 保存执行记录
    async saveExecution() {
        const data = {
            strategy_id: parseInt(document.getElementById('executeStrategyId').value),
            execution_date: document.getElementById('executeDate').value,
            triggered_by: document.getElementById('executeTriggeredBy').value.trim() || null,
            action_taken: document.getElementById('executeActionTaken').value.trim() || null,
            result: document.getElementById('executeResult').value,
            profit_loss: parseFloat(document.getElementById('executeProfitLoss').value) || null,
            notes: document.getElementById('executeNotes').value.trim() || null,
        };

        try {
            const resp = await fetch('/strategies/api/executions/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await resp.json();
            if (!result.success) {
                alert(result.error || '保存失败');
                return;
            }

            this.executeModal.hide();
            this.loadExecutions();
            this.updateStatistics();
        } catch (e) {
            alert('保存失败: ' + e.message);
        }
    },

    // 加载执行记录
    async loadExecutions() {
        const tbody = document.getElementById('executionList');

        try {
            const resp = await fetch('/strategies/api/executions?limit=20');
            const data = await resp.json();

            if (!data.success) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">加载失败</td></tr>';
                return;
            }

            if (data.executions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">暂无执行记录</td></tr>';
                return;
            }

            tbody.innerHTML = data.executions.map(e => `
                <tr>
                    <td>${e.execution_date || '-'}</td>
                    <td><strong>${e.strategy_name || '-'}</strong></td>
                    <td class="text-truncate" style="max-width: 150px;" title="${e.triggered_by || ''}">${e.triggered_by || '-'}</td>
                    <td class="text-truncate" style="max-width: 150px;" title="${e.action_taken || ''}">${e.action_taken || '-'}</td>
                    <td>
                        <span class="badge ${e.result === 'success' ? 'bg-success' : e.result === 'partial' ? 'bg-warning' : 'bg-secondary'}">
                            ${e.result === 'success' ? '成功' : e.result === 'partial' ? '部分' : '跳过'}
                        </span>
                    </td>
                    <td class="${e.profit_loss >= 0 ? 'text-success' : 'text-danger'}">
                        ${e.profit_loss !== null ? (e.profit_loss >= 0 ? '+' : '') + e.profit_loss.toFixed(2) : '-'}
                    </td>
                    <td>
                        <button class="btn btn-outline-danger btn-sm" onclick="StrategyPage.deleteExecution(${e.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">加载失败</td></tr>';
        }
    },

    // 删除执行记录
    async deleteExecution(id) {
        if (!confirm('确定要删除这条执行记录吗？')) {
            return;
        }

        try {
            const resp = await fetch(`/strategies/api/executions/${id}`, { method: 'DELETE' });
            const result = await resp.json();

            if (!result.success) {
                alert(result.error || '删除失败');
                return;
            }

            this.loadExecutions();
            this.updateStatistics();
        } catch (e) {
            alert('删除失败: ' + e.message);
        }
    },

    // 更新统计信息
    async updateStatistics() {
        try {
            const resp = await fetch('/strategies/api/statistics');
            const data = await resp.json();

            if (data.success) {
                document.getElementById('stat-total').textContent = data.statistics.total_strategies;
                document.getElementById('stat-active').textContent = data.statistics.active_strategies;
                document.getElementById('stat-executions').textContent = data.statistics.total_executions;

                const profitEl = document.getElementById('stat-profit');
                const profit = data.statistics.total_profit;
                profitEl.textContent = profit.toFixed(2);
                profitEl.className = `h4 mb-1 ${profit >= 0 ? 'text-success' : 'text-danger'}`;
            }
        } catch (e) {
            console.error('更新统计失败:', e);
        }
    },

    // 按分类过滤
    filterCategory(category, btn) {
        this.currentFilter = category;

        // 更新按钮状态
        document.querySelectorAll('.btn-group .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        this.applyFilter();
    },

    // 切换显示已禁用
    toggleInactive() {
        this.showInactive = document.getElementById('showInactive').checked;
        this.applyFilter();
    },

    // 应用过滤
    applyFilter() {
        const rows = document.querySelectorAll('#strategyList tr[data-id]');

        rows.forEach(row => {
            const category = row.dataset.category;
            const active = row.dataset.active === 'true';

            let show = true;

            // 分类过滤
            if (this.currentFilter && category !== this.currentFilter) {
                show = false;
            }

            // 启用状态过滤
            if (!this.showInactive && !active) {
                show = false;
            }

            row.style.display = show ? '' : 'none';
        });

        // 显示/隐藏空状态
        const visibleRows = document.querySelectorAll('#strategyList tr[data-id]:not([style*="display: none"])');
        const emptyRow = document.getElementById('emptyRow');
        if (emptyRow) {
            emptyRow.style.display = visibleRows.length === 0 ? '' : 'none';
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => StrategyPage.init());
