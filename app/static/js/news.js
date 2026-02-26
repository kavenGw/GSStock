const News = {
    REFRESH_INTERVAL: 60,
    currentTab: 'all',
    items: [],
    countdown: 0,
    countdownTimer: null,

    async init() {
        this.bindEvents();
        await this.loadData();
        this.startCountdown();
    },

    bindEvents() {
        document.getElementById('btnRefresh').addEventListener('click', () => this.manualRefresh());
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
            const [itemsResp, briefingResp] = await Promise.all([
                fetch(`/news/items?tab=${this.currentTab}&limit=30`),
                fetch('/news/briefing'),
            ]);
            const itemsData = await itemsResp.json();
            const briefingData = await briefingResp.json();

            if (itemsData.success) {
                this.items = itemsData.items;
            }
            this.renderItems();
            this.renderBriefing(briefingData.briefing);
            this.showContent();
        } catch (e) {
            console.error('加载失败:', e);
        }
    },

    async loadItems() {
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30`);
            const data = await resp.json();
            if (data.success) {
                this.items = data.items;
                this.renderItems();
                this.showContent();
            }
        } catch (e) {
            console.error('加载快讯失败:', e);
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

    async manualRefresh() {
        const btn = document.getElementById('btnRefresh');
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 刷新中...';
        try {
            await fetch('/news/refresh', { method: 'POST' });
            await this.loadData();
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新';
        }
    },

    renderItems() {
        const container = document.getElementById('newsList');
        if (!this.items.length) {
            container.innerHTML = '<p class="text-muted text-center py-4">暂无快讯</p>';
            document.getElementById('btnLoadMore').style.display = 'none';
            return;
        }

        const categoryConfig = {
            stock: { label: '股票', color: 'primary' },
            metal: { label: '商品', color: 'warning' },
            ai: { label: 'AI', color: 'info' },
            other: { label: '', color: 'secondary' },
        };

        let html = '';
        let lastDate = '';
        for (const item of this.items) {
            if (item.display_date && item.display_date !== lastDate) {
                lastDate = item.display_date;
                html += `<div class="text-muted small fw-bold mt-3 mb-2 border-bottom pb-1">${lastDate}</div>`;
            }
            const cat = categoryConfig[item.category] || categoryConfig.other;
            const scoreIcon = item.score >= 2 ? '<span class="text-danger me-1">●</span>' : '<span class="text-muted me-1">○</span>';
            const catBadge = cat.label ? `<span class="badge bg-${cat.color} ms-1">${cat.label}</span>` : '';

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

    renderBriefing(briefing) {
        const content = document.getElementById('briefingContent');
        const time = document.getElementById('briefingTime');

        if (!briefing) {
            content.innerHTML = '<p class="text-muted">暂无简报，等待下次刷新生成</p>';
            time.textContent = '';
            return;
        }

        time.textContent = briefing.created_at;
        const lines = briefing.content.split('\n').filter(l => l.trim());
        content.innerHTML = lines.map(line => `<p class="mb-2">${line}</p>`).join('');
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
        const status = document.getElementById('newsStatus');
        status.textContent = `${this.items.length} 条快讯`;
    },

    startCountdown() {
        this.countdown = this.REFRESH_INTERVAL;
        if (this.countdownTimer) clearInterval(this.countdownTimer);
        this.countdownTimer = setInterval(() => {
            this.countdown--;
            const status = document.getElementById('newsStatus');
            status.textContent = `${this.items.length} 条快讯 · ${this.countdown}s 后刷新`;
            if (this.countdown <= 0) {
                this.countdown = this.REFRESH_INTERVAL;
                this.refreshItems();
            }
        }, 1000);
    },

    async refreshItems() {
        try {
            const [itemsResp, briefingResp] = await Promise.all([
                fetch(`/news/items?tab=${this.currentTab}&limit=30`),
                fetch('/news/briefing'),
            ]);
            const itemsData = await itemsResp.json();
            const briefingData = await briefingResp.json();
            if (itemsData.success) {
                this.items = itemsData.items;
                this.renderItems();
            }
            this.renderBriefing(briefingData.briefing);
            this.updateStatus();
        } catch (e) {
            console.error('刷新失败:', e);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => News.init());
