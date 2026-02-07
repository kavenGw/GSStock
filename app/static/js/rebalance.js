document.addEventListener('DOMContentLoaded', function() {
    loadStockList();
    loadSavedPlans();
    bindEvents();
});

function bindEvents() {
    document.getElementById('calculateBtn').addEventListener('click', calculate);

    const targetInput = document.getElementById('targetValue');
    targetInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') calculate();
    });

    // 格式化目标市值输入（千位分隔符）
    targetInput.addEventListener('input', function(e) {
        let value = this.value.replace(/[^\d]/g, '');
        if (value) {
            this.value = parseInt(value, 10).toLocaleString('zh-CN');
        }
    });
}

async function loadSavedPlans() {
    try {
        const response = await fetch('/rebalance/api/plans');
        const data = await response.json();

        if (!data.success) return;

        // 恢复目标总市值
        if (data.target_value && data.target_value > 0) {
            document.getElementById('targetValue').value = parseInt(data.target_value, 10).toLocaleString('zh-CN');
        }

        // 恢复操作建议
        if (data.items && data.items.length > 0) {
            renderSavedResults(data.items);
        }
    } catch (error) {
        console.error('加载保存的计划失败:', error);
    }
}

function renderSavedResults(items) {
    const resultEmpty = document.getElementById('resultEmpty');
    const resultTable = document.getElementById('resultTable');
    const resultBody = document.getElementById('resultBody');

    resultEmpty.style.display = 'none';
    resultTable.style.display = 'table';
    resultBody.innerHTML = '';

    items.forEach(item => {
        const row = document.createElement('tr');

        let operationClass = 'text-muted';
        let operationText = '持有';
        let sharesText = '--';

        if (item.operation === 'buy') {
            operationClass = 'text-success';
            operationText = '买入';
            sharesText = item.shares > 0 ? `${item.shares}股` : '--';
        } else if (item.operation === 'sell') {
            operationClass = 'text-danger';
            operationText = '卖出';
            sharesText = item.shares > 0 ? `${item.shares}股` : '--';
        }

        let diffClass = 'text-muted';
        if (item.diff > 0) diffClass = 'text-success';
        else if (item.diff < 0) diffClass = 'text-danger';

        row.innerHTML = `
            <td>${item.stock_code}</td>
            <td>${item.stock_name}</td>
            <td class="text-end">${formatCurrency(item.target_value)}</td>
            <td class="text-end">${item.current_value > 0 ? formatCurrency(item.current_value) : '--'}</td>
            <td class="text-end ${diffClass}">${item.diff > 0 ? '+' : ''}${formatCurrency(item.diff)}</td>
            <td class="text-center ${operationClass}"><strong>${operationText}</strong> ${sharesText}</td>
        `;
        resultBody.appendChild(row);
    });
}

async function loadStockList() {
    const loading = document.getElementById('stockListLoading');
    const empty = document.getElementById('stockListEmpty');
    const table = document.getElementById('stockTable');
    const currentValue = document.getElementById('currentValue');

    try {
        const response = await fetch('/rebalance/api/stocks');
        const data = await response.json();

        loading.style.display = 'none';

        if (!data.success || !data.stocks || data.stocks.length === 0) {
            empty.style.display = 'block';
            table.style.display = 'none';
            currentValue.textContent = '¥0.00';
            return;
        }

        empty.style.display = 'none';
        table.style.display = 'table';
        currentValue.textContent = formatCurrency(data.current_value);

        renderStockList(data.stocks);
    } catch (error) {
        loading.style.display = 'none';
        empty.style.display = 'block';
        empty.textContent = '加载失败，请刷新重试';
    }
}

function renderStockList(stocks) {
    const tbody = document.getElementById('stockBody');
    tbody.innerHTML = '';

    stocks.forEach(stock => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="text-center">
                <input type="checkbox" class="form-check-input stock-checkbox"
                       data-stock-code="${stock.stock_code}"
                       ${stock.selected ? 'checked' : ''}>
            </td>
            <td>${stock.stock_code}</td>
            <td>${stock.stock_name}</td>
            <td>
                <input type="number" step="0.01" min="0.01" max="99.99"
                       class="form-control form-control-sm weight-input"
                       data-stock-code="${stock.stock_code}"
                       value="${stock.weight}"
                       style="width: 70px;">
            </td>
            <td class="text-end">${stock.market_value > 0 ? formatCurrency(stock.market_value) : '--'}</td>
        `;
        tbody.appendChild(row);
    });

    bindStockEvents();
}

function bindStockEvents() {
    document.querySelectorAll('.stock-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', async function() {
            const stockCode = this.dataset.stockCode;
            const selected = this.checked;

            await fetch('/rebalance/api/selection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_code: stockCode, selected: selected })
            });
        });
    });

    document.querySelectorAll('.weight-input').forEach(input => {
        input.addEventListener('change', async function() {
            const stockCode = this.dataset.stockCode;
            const weight = parseFloat(this.value);

            if (isNaN(weight) || weight <= 0) {
                alert('权重必须大于 0');
                loadStockList();
                return;
            }

            if (weight > 99.99) {
                alert('权重不能超过 99.99');
                loadStockList();
                return;
            }

            const response = await fetch('/rebalance/api/weight', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_code: stockCode, weight: weight })
            });

            const data = await response.json();
            if (!data.success) {
                alert(data.error || '保存失败');
                loadStockList();
            }
        });
    });
}

async function calculate() {
    const rawValue = document.getElementById('targetValue').value.replace(/,/g, '');
    const targetValue = parseFloat(rawValue);

    if (isNaN(targetValue) || targetValue <= 0) {
        alert('请输入有效的目标市值');
        return;
    }

    const resultEmpty = document.getElementById('resultEmpty');
    const resultTable = document.getElementById('resultTable');

    resultEmpty.textContent = '计算中...';
    resultEmpty.style.display = 'block';
    resultTable.style.display = 'none';

    try {
        const response = await fetch('/rebalance/api/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_value: targetValue })
        });

        const data = await response.json();

        if (!data.success) {
            resultEmpty.textContent = data.error || '计算失败';
            return;
        }

        renderResults(data);
    } catch (error) {
        resultEmpty.textContent = '计算失败，请重试';
    }
}

function renderResults(data) {
    const resultEmpty = document.getElementById('resultEmpty');
    const resultTable = document.getElementById('resultTable');
    const resultBody = document.getElementById('resultBody');

    if (!data.items || data.items.length === 0) {
        resultEmpty.textContent = '无操作建议';
        resultEmpty.style.display = 'block';
        resultTable.style.display = 'none';
        return;
    }

    resultEmpty.style.display = 'none';
    resultTable.style.display = 'table';
    resultBody.innerHTML = '';

    data.items.forEach(item => {
        const row = document.createElement('tr');

        let operationClass = 'text-muted';
        let operationText = '持有';
        let sharesText = '--';

        if (item.operation === 'buy') {
            operationClass = 'text-success';
            operationText = '买入';
            sharesText = item.shares > 0 ? `${item.shares}股` : '--';
        } else if (item.operation === 'sell') {
            operationClass = 'text-danger';
            operationText = '卖出';
            sharesText = item.shares > 0 ? `${item.shares}股` : '--';
        }

        let diffClass = 'text-muted';
        if (item.diff > 0) diffClass = 'text-success';
        else if (item.diff < 0) diffClass = 'text-danger';

        row.innerHTML = `
            <td>${item.stock_code}</td>
            <td>${item.stock_name}</td>
            <td class="text-end">${formatCurrency(item.target_value)}</td>
            <td class="text-end">${item.current_value > 0 ? formatCurrency(item.current_value) : '--'}</td>
            <td class="text-end ${diffClass}">${item.diff > 0 ? '+' : ''}${formatCurrency(item.diff)}</td>
            <td class="text-center ${operationClass}"><strong>${operationText}</strong> ${sharesText}</td>
        `;
        resultBody.appendChild(row);
    });
}

function formatCurrency(value) {
    return value.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' });
}
