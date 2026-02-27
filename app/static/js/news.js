const News = {
    POLL_INTERVAL: 180000, // 3分钟
    currentTab: 'all',
    items: [],
    pollTimer: null,

    async init() {
        this.bindEvents();
        await this.loadData();
        this.startPolling();
    },

    bindEvents() {
        document.getElementById('btnLoadMore').addEventListener('click', () => this.loadMore());
        document.querySelectorAll('#newsTabs .nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('#newsTabs .nav-link').forEach(l => l.classList.remove('active'));
                e.target.classList.add('active');
                this.currentTab = e.target.dataset.tab;
                this.items = [];
                this.loadItems();
            });
        });
    },

    async loadData() {
        try {
            const [itemsResp, pollResp] = await Promise.all([
                fetch(`/news/items?tab=${this.currentTab}&limit=30`),
                fetch('/news/poll'),
            ]);
            const itemsData = await itemsResp.json();
            const pollData = await pollResp.json();

            if (itemsData.success) {
                this.items = itemsData.items;
            }
            if (pollData.success && pollData.new_count > 0) {
                this.mergeNewItems(pollData.new_items);
            }
            this.renderItems();
            this.showContent();
        } catch (e) {
            console.error('加载失败:', e);
            this.items = [];
            this.showContent();
        }
    },

    mergeNewItems(newItems) {
        const existingIds = new Set(this.items.map(i => i.id));
        const unique = newItems.filter(i => !existingIds.has(i.id));
        if (unique.length) {
            this.items = [...unique, ...this.items];
        }
    },

    async loadItems() {
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30`);
            const data = await resp.json();
            if (data.success) {
                this.items = data.items;
            }
            this.renderItems();
            this.showContent();
        } catch (e) {
            console.error('加载快讯失败:', e);
            this.items = [];
            this.showContent();
        }
    },

    async loadMore() {
        if (!this.items.length) return;
        const lastId = this.items[this.items.length - 1].id;
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30&before_id=${lastId}`);
            const data = await resp.json();
            if (data.success && data.items.length) {
                this.items = this.items.concat(data.items);
                this.renderItems();
            }
        } catch (e) {
            console.error('加载更多失败:', e);
        }
    },

    startPolling() {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.pollTimer = setInterval(() => this.poll(), this.POLL_INTERVAL);
    },

    async poll() {
        try {
            const resp = await fetch('/news/poll');
            const data = await resp.json();
            if (!data.success || data.new_count === 0) return;

            if (data.new_count <= 3) {
                this.insertNewItems(data.new_items);
            } else {
                await this.insertSummaryCard(data.new_items);
            }
            this.updateStatus();
        } catch (e) {
            console.error('轮询失败:', e);
        }
    },

    insertNewItems(newItems) {
        this.mergeNewItems(newItems);
        const container = document.getElementById('newsList');
        const fragment = document.createDocumentFragment();

        for (const item of newItems) {
            const el = this.createItemElement(item);
            el.classList.add('news-item-new');
            fragment.appendChild(el);
        }

        const firstChild = container.firstChild;
        container.insertBefore(fragment, firstChild);

        setTimeout(() => {
            container.querySelectorAll('.news-item-new').forEach(el => {
                el.classList.remove('news-item-new');
            });
        }, 3000);
    },

    async insertSummaryCard(newItems) {
        this.mergeNewItems(newItems);

        const ids = newItems.map(i => i.id);
        let summary = null;

        try {
            const resp = await fetch('/news/summarize', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({item_ids: ids}),
            });
            const data = await resp.json();
            if (data.success) {
                summary = data.summary;
            }
        } catch (e) {
            console.error('AI摘要失败:', e);
        }

        if (!summary) {
            this.insertNewItems(newItems);
            return;
        }

        const container = document.getElementById('newsList');
        const card = document.createElement('div');
        card.className = 'news-summary-card mb-2 p-3 border rounded bg-light news-item-new';
        card.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold text-primary">
                    <i class="bi bi-clipboard-data"></i> ${newItems.length}条新快讯整理
                </span>
                <button class="btn btn-sm btn-link text-muted p-0 summary-toggle"
                        onclick="News.toggleSummaryDetail(this)">
                    展开 ▼
                </button>
            </div>
            <div class="summary-text">${summary}</div>
            <div class="summary-detail" style="display:none">
                ${newItems.map(i => `
                    <div class="small text-muted border-top pt-1 mt-1">
                        <span class="me-1">${i.display_time}</span> ${i.content}
                    </div>
                `).join('')}
            </div>
        `;

        container.insertBefore(card, container.firstChild);
        setTimeout(() => card.classList.remove('news-item-new'), 3000);
    },

    toggleSummaryDetail(btn) {
        const card = btn.closest('.news-summary-card');
        const detail = card.querySelector('.summary-detail');
        const isHidden = detail.style.display === 'none';
        detail.style.display = isHidden ? '' : 'none';
        btn.textContent = isHidden ? '收起 ▲' : '展开 ▼';
    },

    createItemElement(item) {
        const categoryConfig = {
            stock: { label: '股票', color: 'primary' },
            metal: { label: '商品', color: 'warning' },
            ai: { label: 'AI', color: 'info' },
            other: { label: '', color: 'secondary' },
        };
        const cat = categoryConfig[item.category] || categoryConfig.other;
        const scoreIcon = item.score >= 2
            ? '<span class="text-danger me-1">●</span>'
            : '<span class="text-muted me-1">○</span>';
        const catBadge = cat.label
            ? `<span class="badge bg-${cat.color} ms-1">${cat.label}</span>`
            : '';

        const div = document.createElement('div');
        div.className = 'd-flex align-items-start py-2 border-bottom news-item';
        div.dataset.id = item.id;
        div.innerHTML = `
            <div class="me-2 text-nowrap">
                ${scoreIcon}
                <small class="text-muted">${item.display_time}</small>
            </div>
            <div class="flex-grow-1">
                <span>${item.content}</span>${catBadge}
            </div>
        `;
        return div;
    },

    renderItems() {
        const container = document.getElementById('newsList');
        if (!this.items.length) {
            container.innerHTML = '<p class="text-muted text-center py-4">暂无快讯</p>';
            document.getElementById('btnLoadMore').style.display = 'none';
            return;
        }

        let html = '';
        let lastDate = '';
        for (const item of this.items) {
            if (item.display_date && item.display_date !== lastDate) {
                lastDate = item.display_date;
                html += `<div class="text-muted small fw-bold mt-3 mb-2 border-bottom pb-1">${lastDate}</div>`;
            }
            const cat = {
                stock: { label: '股票', color: 'primary' },
                metal: { label: '商品', color: 'warning' },
                ai: { label: 'AI', color: 'info' },
                other: { label: '', color: 'secondary' },
            }[item.category] || { label: '', color: 'secondary' };
            const scoreIcon = item.score >= 2
                ? '<span class="text-danger me-1">●</span>'
                : '<span class="text-muted me-1">○</span>';
            const catBadge = cat.label
                ? `<span class="badge bg-${cat.color} ms-1">${cat.label}</span>`
                : '';

            html += `
                <div class="d-flex align-items-start py-2 border-bottom news-item" data-id="${item.id}">
                    <div class="me-2 text-nowrap">
                        ${scoreIcon}
                        <small class="text-muted">${item.display_time}</small>
                    </div>
                    <div class="flex-grow-1">
                        <span>${item.content}</span>${catBadge}
                    </div>
                </div>`;
        }
        container.innerHTML = html;
        document.getElementById('btnLoadMore').style.display = 'inline-block';
    },

    showContent() {
        document.getElementById('loadingState').style.display = 'none';
        if (this.items.length) {
            document.getElementById('contentArea').style.display = '';
            document.getElementById('emptyState').style.display = 'none';
        } else {
            document.getElementById('contentArea').style.display = 'none';
            document.getElementById('emptyState').style.display = '';
        }
        this.updateStatus();
    },

    updateStatus() {
        document.getElementById('newsStatus').textContent = `${this.items.length} 条快讯`;
    },
};

document.addEventListener('DOMContentLoaded', () => News.init());
