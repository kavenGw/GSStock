document.addEventListener('DOMContentLoaded', function() {
    initDailyRecordPage();
});

function initDailyRecordPage() {
    const positionZone = document.getElementById('positionUploadZone');
    const tradeZone = document.getElementById('tradeUploadZone');

    if (!positionZone || !tradeZone) return;

    let positionData = [];
    let tradeData = [];
    let accountData = {};
    let transferData = { type: '', amount: 0, note: '' };

    // 每个区域的上传状态
    const uploadState = {
        position: { files: [], results: [] },
        trade: { files: [], results: [] }
    };

    initTransferControls();

    initUploadZone(positionZone, 'positionFileInput', 'position');
    initUploadZone(tradeZone, 'tradeFileInput', 'trade');

    document.getElementById('targetDate')?.addEventListener('change', async () => {
        await loadExistingTransfers();
        if (accountData.total_asset) {
            await calculateDailyProfit();
            renderAccountInfo();
        }
    });

    loadExistingTransfers();

    function initTransferControls() {
        const transferType = document.getElementById('transferType');
        const transferAmount = document.getElementById('transferAmount');
        const transferNote = document.getElementById('transferNote');

        if (!transferType || !transferAmount) return;

        transferType.addEventListener('change', async () => {
            const hasTransfer = transferType.value !== '';
            transferAmount.disabled = !hasTransfer;
            transferNote.disabled = !hasTransfer;
            if (!hasTransfer) {
                transferAmount.value = '';
                transferNote.value = '';
            }
            transferData.type = transferType.value;
            updateSaveButton();
            if (accountData.total_asset) {
                await calculateDailyProfit();
                renderAccountInfo();
            }
        });

        transferAmount.addEventListener('input', async () => {
            transferData.amount = parseFloat(transferAmount.value) || 0;
            if (accountData.total_asset) {
                await calculateDailyProfit();
                renderAccountInfo();
            }
        });

        transferNote.addEventListener('input', () => {
            transferData.note = transferNote.value;
        });
    }

    async function loadExistingTransfers() {
        const targetDate = document.getElementById('targetDate').value;
        try {
            const response = await fetch(`/daily-record/api/prev-asset/${targetDate}`);
            const data = await response.json();

            const existingDiv = document.getElementById('existingTransfers');
            const listDiv = document.getElementById('existingTransfersList');

            if (data.transfer && data.transfer.transfers && data.transfer.transfers.length > 0) {
                existingDiv.style.display = 'block';
                listDiv.innerHTML = data.transfer.transfers.map(t => {
                    const typeText = t.transfer_type === 'in' ? '转入' : '转出';
                    const colorClass = t.transfer_type === 'in' ? 'text-success' : 'text-danger';
                    return `<span class="badge ${colorClass} me-2">${typeText} ${t.amount.toLocaleString()}${t.note ? ` (${t.note})` : ''}</span>`;
                }).join('');
            } else {
                existingDiv.style.display = 'none';
            }
        } catch (error) {
            console.error('加载已有转账失败:', error);
        }
    }

    function initUploadZone(zone, inputId, type) {
        const fileInput = document.getElementById(inputId);

        zone.addEventListener('click', () => fileInput.click());

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files, type);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleFiles(fileInput.files, type);
                fileInput.value = '';
            }
        });
    }

    // 接收文件，创建文件项，并行发起上传
    function handleFiles(files, type) {
        const fileArray = Array.from(files);
        if (fileArray.length > 10) {
            alert('最多支持10张图片');
            return;
        }

        const state = uploadState[type];

        fileArray.forEach(file => {
            const item = {
                id: Date.now() + '_' + Math.random().toString(36).substr(2, 6),
                file: file,
                name: file.name,
                status: 'waiting',
                result: null,
                error: null
            };
            state.files.push(item);
        });

        renderFileList(type);

        // 并行上传所有新文件
        const newItems = state.files.filter(f => f.status === 'waiting');
        newItems.forEach(item => uploadSingleFile(item, type));
    }

    async function uploadSingleFile(item, type) {
        item.status = 'uploading';
        renderFileList(type);

        const formData = new FormData();
        formData.append('file', item.file);
        formData.append('type', type);

        try {
            const response = await fetch('/daily-record/upload-single', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                item.status = 'completed';
                item.result = data;
            } else {
                item.status = 'failed';
                item.error = data.error || '识别失败';
            }
        } catch (error) {
            item.status = 'failed';
            item.error = error.message;
        }

        renderFileList(type);
        checkAllCompleted(type);
    }

    // 全部完成后调用 merge 合并
    async function checkAllCompleted(type) {
        const state = uploadState[type];
        const pending = state.files.filter(f => f.status === 'waiting' || f.status === 'uploading');
        if (pending.length > 0) return;

        const successItems = state.files.filter(f => f.status === 'completed' && f.result);
        if (successItems.length === 0) return;

        // 收集所有成功结果
        const resultData = successItems.map(f => f.result);

        // 加上已有数据
        if (type === 'position' && positionData.length > 0) {
            resultData.unshift({ positions: positionData, account: {} });
        }
        if (type === 'trade' && tradeData.length > 0) {
            resultData.unshift({ trades: tradeData });
        }

        try {
            const response = await fetch('/daily-record/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type, data: resultData })
            });

            const data = await response.json();

            if (data.success) {
                if (type === 'position') {
                    positionData = data.merged || [];

                    if (data.account && data.account.total_asset) {
                        const hasExisting = accountData.total_asset !== undefined;
                        if (hasExisting) {
                            accountData.total_asset = (accountData.total_asset || 0) + data.account.total_asset;
                        } else {
                            accountData = { total_asset: data.account.total_asset };
                        }
                        await calculateDailyProfit();
                        renderAccountInfo();
                    }
                    renderPositionTable();
                } else {
                    tradeData = data.trades || [];
                    renderTradeTable();
                }
            }
        } catch (error) {
            console.error('合并失败:', error);
        }

        // 清空已处理的文件项
        state.files = [];
        state.results = [];
        renderFileList(type);
    }

    function renderFileList(type) {
        const listEl = document.getElementById(`${type}FileList`);
        const progressEl = document.getElementById(`${type}TotalProgress`);
        const state = uploadState[type];

        if (state.files.length === 0) {
            listEl.innerHTML = '';
            progressEl.style.display = 'none';
            return;
        }

        const total = state.files.length;
        const completed = state.files.filter(f => f.status === 'completed').length;
        const failed = state.files.filter(f => f.status === 'failed').length;
        const done = completed + failed;

        listEl.innerHTML = state.files.map(item => {
            let statusHtml = '';
            switch (item.status) {
                case 'waiting':
                    statusHtml = '<span class="text-muted">等待中</span>';
                    break;
                case 'uploading':
                    statusHtml = '<span class="text-primary"><span class="spinner-border spinner-border-sm"></span> 识别中</span>';
                    break;
                case 'completed':
                    statusHtml = '<span class="text-success">&#10003; 完成</span>';
                    break;
                case 'failed':
                    statusHtml = `<span class="text-danger">&#10007; ${item.error}</span>`;
                    break;
            }
            return `<div class="file-item">
                <span class="file-name">${item.name}</span>
                <span class="file-status">${statusHtml}</span>
            </div>`;
        }).join('');

        progressEl.style.display = 'block';
        progressEl.querySelector('small').textContent = `进度: ${done}/${total}` + (failed > 0 ? ` (${failed}个失败)` : '');
    }

    async function calculateDailyProfit() {
        if (!accountData.total_asset) return;

        const targetDate = document.getElementById('targetDate').value;
        try {
            const response = await fetch(`/daily-record/api/prev-asset/${targetDate}`);
            const data = await response.json();

            if (data.success && data.has_prev && data.prev_total_asset) {
                // 已有转账的净转入
                let netTransfer = 0;
                if (data.transfer) {
                    netTransfer = data.transfer.net_transfer || 0;
                }
                // 加上当前输入的新转账
                if (transferData.type && transferData.amount > 0) {
                    netTransfer += transferData.type === 'in' ? transferData.amount : -transferData.amount;
                }

                const dailyProfit = accountData.total_asset - data.prev_total_asset - netTransfer;
                const dailyProfitPct = (dailyProfit / data.prev_total_asset) * 100;
                accountData.daily_profit = dailyProfit;
                accountData.daily_profit_pct = dailyProfitPct;
                accountData.prev_date = data.prev_date;
                accountData.prev_total_asset = data.prev_total_asset;
            } else {
                delete accountData.daily_profit;
                delete accountData.daily_profit_pct;
                delete accountData.prev_date;
                delete accountData.prev_total_asset;
            }
        } catch (error) {
            console.error('获取前日资产失败:', error);
        }
    }

    function renderAccountInfo() {
        const container = document.getElementById('accountInfoContainer');
        if (!container) return;

        if (!accountData.total_asset && accountData.daily_profit === undefined) {
            container.style.display = 'none';
            return;
        }

        const cardBody = container.querySelector('.card-body');
        if (!cardBody) return;

        let html = '<div class="account-info-grid">';
        if (accountData.total_asset) {
            html += `<div class="account-info-item">
                <span class="label">总资产</span>
                <span class="value">¥${accountData.total_asset.toLocaleString('zh-CN', {minimumFractionDigits: 2})}</span>
            </div>`;
        }
        if (accountData.daily_profit !== undefined) {
            const profitClass = accountData.daily_profit >= 0 ? 'profit' : 'loss';
            const profitSign = accountData.daily_profit >= 0 ? '+' : '';
            let pctStr = '';
            if (accountData.daily_profit_pct !== undefined) {
                pctStr = ` (${profitSign}${accountData.daily_profit_pct.toFixed(2)}%)`;
            }
            html += `<div class="account-info-item">
                <span class="label">当日盈亏</span>
                <span class="value ${profitClass}">${profitSign}${accountData.daily_profit.toLocaleString('zh-CN', {minimumFractionDigits: 2})}${pctStr}</span>
            </div>`;
        } else if (accountData.total_asset) {
            html += `<div class="account-info-item">
                <span class="label">当日盈亏</span>
                <span class="value text-muted">无前日数据</span>
            </div>`;
        }
        html += '</div>';

        cardBody.innerHTML = html;
        container.style.display = 'block';
    }

    function renderPositionTable() {
        const preview = document.getElementById('positionPreview');
        const tbody = document.getElementById('positionTableBody');
        const countEl = document.getElementById('positionCount');

        if (positionData.length === 0) {
            preview.style.display = 'none';
            updateSaveButton();
            return;
        }

        tbody.innerHTML = '';
        positionData.forEach((p, idx) => {
            const row = document.createElement('tr');
            row.dataset.index = idx;

            if (p.unmatched) {
                row.classList.add('table-warning');
            }

            let statusHtml = '';
            if (p.unmatched) {
                statusHtml += `<span class="badge bg-warning text-dark">未匹配</span>`;
            }
            if (p.merged_count > 1) {
                statusHtml += `<span class="badge bg-info">已合并${p.merged_count}条</span>`;
            }
            if (p.alias_matched) {
                statusHtml += `<span class="badge bg-secondary">别名匹配</span>`;
            }

            let actionHtml = '<button class="btn btn-sm btn-outline-danger delete-row">×</button>';
            if (p.unmatched) {
                actionHtml = `<button class="btn btn-sm btn-outline-primary add-alias-btn" data-name="${p.stock_name || ''}">添加别名</button> ` + actionHtml;
            }

            row.innerHTML = `
                <td><input type="text" class="form-control form-control-sm stock-code" value="${p.stock_code || ''}"></td>
                <td>${statusHtml}</td>
                <td><input type="text" class="form-control form-control-sm stock-name" value="${p.stock_name || ''}"></td>
                <td><input type="number" class="form-control form-control-sm quantity" value="${p.quantity || ''}"></td>
                <td><input type="number" class="form-control form-control-sm total-amount" step="0.01" value="${p.total_amount ? p.total_amount.toFixed(2) : ''}"></td>
                <td><input type="number" class="form-control form-control-sm current-price" step="0.001" value="${p.current_price ? p.current_price.toFixed(3) : ''}"></td>
                <td>${actionHtml}</td>
            `;
            tbody.appendChild(row);

            row.querySelector('.delete-row').addEventListener('click', () => {
                positionData.splice(idx, 1);
                renderPositionTable();
            });

            const addAliasBtn = row.querySelector('.add-alias-btn');
            if (addAliasBtn) {
                addAliasBtn.addEventListener('click', async () => {
                    const stockName = addAliasBtn.dataset.name;
                    document.getElementById('aliasOriginalName').textContent = stockName;

                    await loadStockListForAlias();

                    const modal = new bootstrap.Modal(document.getElementById('addAliasModal'));
                    modal.show();
                });
            }
        });

        countEl.textContent = positionData.length;
        preview.style.display = 'block';
        updateSaveButton();
    }

    function renderTradeTable() {
        const preview = document.getElementById('tradePreview');
        const tbody = document.getElementById('tradeTableBody');
        const countEl = document.getElementById('tradeCount');

        if (tradeData.length === 0) {
            preview.style.display = 'none';
            updateSaveButton();
            return;
        }

        tbody.innerHTML = '';
        tradeData.forEach((t, idx) => {
            const row = document.createElement('tr');
            row.dataset.index = idx;
            const amount = (t.quantity || 0) * (t.price || 0);
            row.innerHTML = `
                <td>
                    <select class="form-select form-select-sm trade-type">
                        <option value="buy" ${t.trade_type === 'buy' ? 'selected' : ''}>买入</option>
                        <option value="sell" ${t.trade_type === 'sell' ? 'selected' : ''}>卖出</option>
                    </select>
                </td>
                <td><input type="text" class="form-control form-control-sm stock-code" value="${t.stock_code || ''}"></td>
                <td><input type="text" class="form-control form-control-sm stock-name" value="${t.stock_name || ''}"></td>
                <td><input type="number" class="form-control form-control-sm quantity" value="${t.quantity || ''}"></td>
                <td><input type="number" class="form-control form-control-sm price" step="0.001" value="${t.price ? t.price.toFixed(3) : ''}"></td>
                <td class="amount">${amount.toFixed(2)}</td>
                <td><button class="btn btn-sm btn-outline-danger delete-row">×</button></td>
            `;
            tbody.appendChild(row);

            row.querySelector('.quantity').addEventListener('input', () => updateAmount(row));
            row.querySelector('.price').addEventListener('input', () => updateAmount(row));

            row.querySelector('.delete-row').addEventListener('click', () => {
                tradeData.splice(idx, 1);
                renderTradeTable();
            });
        });

        countEl.textContent = tradeData.length;
        preview.style.display = 'block';
        updateSaveButton();
    }

    function updateAmount(row) {
        const quantity = parseFloat(row.querySelector('.quantity').value) || 0;
        const price = parseFloat(row.querySelector('.price').value) || 0;
        row.querySelector('.amount').textContent = (quantity * price).toFixed(2);
    }

    function updateSaveButton() {
        const saveBtn = document.getElementById('saveAllBtn');
        const hasTransfer = transferData.type && transferData.amount > 0;
        saveBtn.disabled = (positionData.length === 0 && tradeData.length === 0 && !hasTransfer);

        const calcFeeBtn = document.getElementById('calcFeeBtn');
        if (calcFeeBtn) {
            calcFeeBtn.disabled = !accountData.total_asset || positionData.length === 0;
        }
    }

    document.getElementById('addPositionBtn')?.addEventListener('click', () => {
        positionData.push({
            stock_code: '',
            stock_name: '',
            quantity: 0,
            total_amount: 0,
            current_price: 0
        });
        renderPositionTable();
    });

    document.getElementById('addTradeBtn')?.addEventListener('click', () => {
        tradeData.push({
            stock_code: '',
            stock_name: '',
            trade_type: 'buy',
            quantity: 0,
            price: 0
        });
        renderTradeTable();
    });

    document.getElementById('saveAllBtn')?.addEventListener('click', async () => {
        const positions = collectPositionData();
        const trades = collectTradeData();

        if (!validateData(positions, trades)) {
            return;
        }

        await saveData(positions, trades, false);
    });

    async function saveData(positions, trades, overwriteStocks) {
        const targetDate = document.getElementById('targetDate').value;

        const transfer = transferData.type && transferData.amount > 0 ? {
            type: transferData.type,
            amount: transferData.amount,
            note: transferData.note
        } : null;

        const account = { ...accountData };

        try {
            const response = await fetch('/daily-record/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: targetDate,
                    positions: positions,
                    trades: trades,
                    account: account,
                    transfer: transfer,
                    overwrite: true,
                    overwrite_stocks: overwriteStocks
                })
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = data.redirect;
            } else if (data.has_conflicts) {
                const conflictMsg = data.conflicts.map(c =>
                    `${c.code}: "${c.old_name}" → "${c.new_name}"`
                ).join('\n');

                if (confirm(`以下股票名称与本地记录不一致:\n\n${conflictMsg}\n\n是否覆盖本地记录？`)) {
                    await saveData(positions, trades, true);
                }
            } else {
                alert(data.error || '保存失败');
            }
        } catch (error) {
            alert('保存失败: ' + error.message);
        }
    }

    function collectPositionData() {
        const tbody = document.getElementById('positionTableBody');
        const positions = [];

        tbody.querySelectorAll('tr').forEach(row => {
            const stockCode = row.querySelector('.stock-code').value.trim();
            if (!stockCode) return;

            positions.push({
                stock_code: stockCode,
                stock_name: row.querySelector('.stock-name').value.trim(),
                quantity: parseInt(row.querySelector('.quantity').value) || 0,
                total_amount: parseFloat(row.querySelector('.total-amount').value) || 0,
                current_price: parseFloat(row.querySelector('.current-price').value) || 0
            });
        });

        return positions;
    }

    function collectTradeData() {
        const tbody = document.getElementById('tradeTableBody');
        const trades = [];

        tbody.querySelectorAll('tr').forEach(row => {
            const stockCode = row.querySelector('.stock-code').value.trim();
            if (!stockCode) return;

            trades.push({
                stock_code: stockCode,
                stock_name: row.querySelector('.stock-name').value.trim(),
                trade_type: row.querySelector('.trade-type').value,
                quantity: parseInt(row.querySelector('.quantity').value) || 0,
                price: parseFloat(row.querySelector('.price').value) || 0
            });
        });

        return trades;
    }

    function validateData(positions, trades) {
        let valid = true;

        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

        document.querySelectorAll('#positionTableBody tr').forEach(row => {
            const codeInput = row.querySelector('.stock-code');
            const code = codeInput.value.trim();

            if (code && !/^\d{6}$/.test(code)) {
                codeInput.classList.add('is-invalid');
                valid = false;
            }

            const quantityInput = row.querySelector('.quantity');
            if (quantityInput.value && parseFloat(quantityInput.value) <= 0) {
                quantityInput.classList.add('is-invalid');
                valid = false;
            }

            const priceInput = row.querySelector('.current-price');
            if (priceInput.value && parseFloat(priceInput.value) <= 0) {
                priceInput.classList.add('is-invalid');
                valid = false;
            }
        });

        document.querySelectorAll('#tradeTableBody tr').forEach(row => {
            const codeInput = row.querySelector('.stock-code');
            const code = codeInput.value.trim();

            if (code && !/^\d{6}$/.test(code)) {
                codeInput.classList.add('is-invalid');
                valid = false;
            }

            const quantityInput = row.querySelector('.quantity');
            if (quantityInput.value && parseFloat(quantityInput.value) <= 0) {
                quantityInput.classList.add('is-invalid');
                valid = false;
            }

            const priceInput = row.querySelector('.price');
            if (priceInput.value && parseFloat(priceInput.value) <= 0) {
                priceInput.classList.add('is-invalid');
                valid = false;
            }
        });

        if (!valid) {
            alert('请检查输入数据（红色高亮的字段）');
        }

        return valid;
    }

    async function loadStockListForAlias() {
        const select = document.getElementById('aliasStockSelect');
        select.innerHTML = '<option value="">加载中...</option>';

        try {
            const response = await fetch('/stock');
            const data = await response.json();

            select.innerHTML = '<option value="">请选择股票</option>';
            if (data.stocks && data.stocks.length > 0) {
                data.stocks.forEach(stock => {
                    const option = document.createElement('option');
                    option.value = stock.stock_code;
                    option.textContent = `${stock.stock_code} - ${stock.stock_name}`;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('加载股票列表失败:', error);
            select.innerHTML = '<option value="">加载失败</option>';
        }
    }

    async function remergePositionData() {
        if (positionData.length === 0) return;

        try {
            const response = await fetch('/daily-record/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'position',
                    data: [{ positions: positionData, account: {} }]
                })
            });

            const data = await response.json();

            if (data.success) {
                positionData = data.merged || [];
                renderPositionTable();
            }
        } catch (error) {
            console.error('重新合并失败:', error);
        }
    }

    document.getElementById('calcFeeBtn')?.addEventListener('click', async () => {
        const btn = document.getElementById('calcFeeBtn');
        const resultDiv = document.getElementById('feeResult');
        btn.disabled = true;
        btn.textContent = '计算中...';

        const targetDate = document.getElementById('targetDate').value;
        const positions = collectPositionData();
        const trades = collectTradeData();

        const newTransfer = (transferData.type && transferData.amount > 0)
            ? { type: transferData.type, amount: transferData.amount }
            : null;

        try {
            const response = await fetch('/daily-record/api/calc-fee', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: targetDate,
                    positions: positions,
                    trades: trades,
                    total_asset: accountData.total_asset,
                    transfer: newTransfer
                })
            });

            const data = await response.json();
            if (data.success) {
                const d = data.detail;
                resultDiv.innerHTML = `
                    <div class="account-info-grid">
                        <div class="account-info-item">
                            <span class="label">理论盈亏</span>
                            <span class="value">${d.theoretical_profit >= 0 ? '+' : ''}${d.theoretical_profit.toLocaleString('zh-CN', {minimumFractionDigits: 2})}</span>
                        </div>
                        <div class="account-info-item">
                            <span class="label">实际盈亏</span>
                            <span class="value">${d.actual_profit >= 0 ? '+' : ''}${d.actual_profit.toLocaleString('zh-CN', {minimumFractionDigits: 2})}</span>
                        </div>
                        <div class="account-info-item">
                            <span class="label">手续费</span>
                            <span class="value text-danger">${data.fee.toLocaleString('zh-CN', {minimumFractionDigits: 2})}</span>
                        </div>
                    </div>`;
                resultDiv.style.display = 'block';
            } else {
                resultDiv.innerHTML = `<span class="text-danger">${data.error}</span>`;
                resultDiv.style.display = 'block';
            }
        } catch (error) {
            resultDiv.innerHTML = `<span class="text-danger">计算失败: ${error.message}</span>`;
            resultDiv.style.display = 'block';
        }

        btn.disabled = false;
        btn.textContent = '计算手续费';
    });

    document.getElementById('saveAliasBtn')?.addEventListener('click', async () => {
        const aliasName = document.getElementById('aliasOriginalName').textContent;
        const stockCode = document.getElementById('aliasStockSelect').value;

        if (!stockCode) {
            alert('请选择股票');
            return;
        }

        try {
            const response = await fetch('/stock/aliases', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    alias_name: aliasName,
                    stock_code: stockCode
                })
            });

            const data = await response.json();

            if (response.ok) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('addAliasModal'));
                modal.hide();

                await remergePositionData();
            } else {
                alert(data.error || '保存别名失败');
            }
        } catch (error) {
            alert('保存别名失败: ' + error.message);
        }
    });
}
