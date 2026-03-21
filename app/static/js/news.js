const NEWS_SOURCE_LABELS = {
    wallstreetcn: { label: '华尔街', color: 'secondary' },
    smolai: { label: 'SmolAI', color: 'info' },
    cls: { label: '财联社', color: 'primary' },
    '36kr': { label: '36kr', color: 'warning' },
    google_news: { label: 'Google', color: 'danger' },
    xueqiu: { label: '雪球', color: 'success' },
};

const News = {
    CHECK_SECONDS: 30,
    currentTab: 'all',
    items: [],
    checkTimer: null,
    keywordModal: null,

    async init() {
        this.keywordModal = new bootstrap.Modal(document.getElementById('keywordModal'));
        this.bindEvents();
        await this.loadData();
        this.startCheck();
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
        document.getElementById('newKeywordInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addKeyword();
        });
        document.getElementById('newCompanyInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addCompany();
        });
    },

    async loadData() {
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30`);
            const data = await resp.json();
            if (data.success) this.items = data.items;
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
        if (unique.length) this.items = [...unique, ...this.items];
    },

    async loadItems() {
        try {
            const resp = await fetch(`/news/items?tab=${this.currentTab}&limit=30`);
            const data = await resp.json();
            if (data.success) this.items = data.items;
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

    startCheck() {
        if (this.checkTimer) clearInterval(this.checkTimer);
        this.checkTimer = setInterval(() => this.check(), this.CHECK_SECONDS * 1000);
    },

    async check() {
        const maxId = this.items.length ? Math.max(...this.items.map(i => parseInt(i.id))) : 0;
        try {
            const resp = await fetch(`/news/latest?since_id=${maxId}`);
            const data = await resp.json();
            if (!data.success || data.new_count === 0) {
                if (this.currentTab === 'interest') await this.loadItems();
                return;
            }
            if (this.currentTab === 'interest' || this.currentTab === 'company') {
                await this.loadItems();
            } else if (data.new_count <= 3) {
                this.insertNewItems(data.new_items);
            } else {
                await this.insertSummaryCard(data.new_items);
            }
            this.updateStatus();
        } catch (e) {
            console.error('检查新闻失败:', e);
        }
    },

    insertNewItems(newItems) {
        // 兴趣 tab 下只插入兴趣条目
        const visible = this.currentTab === 'interest'
            ? newItems.filter(i => i.is_interest)
            : newItems;
        this.mergeNewItems(visible);
        if (!visible.length) return;
        const container = document.getElementById('newsList');
        const fragment = document.createDocumentFragment();
        for (const item of visible) {
            const el = this.createItemElement(item);
            el.classList.add('news-item-new');
            fragment.appendChild(el);
        }
        container.insertBefore(fragment, container.firstChild);
        setTimeout(() => {
            container.querySelectorAll('.news-item-new').forEach(el => el.classList.remove('news-item-new'));
        }, 3000);
    },

    async insertSummaryCard(newItems) {
        const visible = this.currentTab === 'interest'
            ? newItems.filter(i => i.is_interest)
            : newItems;
        this.mergeNewItems(visible);
        if (!visible.length) return;
        const ids = visible.map(i => i.id);
        let summary = null;
        try {
            const resp = await fetch('/news/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_ids: ids }),
            });
            const data = await resp.json();
            if (data.success) summary = data.summary;
        } catch (e) {
            console.error('AI摘要失败:', e);
        }
        if (!summary) { this.insertNewItems(visible); return; }

        const container = document.getElementById('newsList');
        const card = document.createElement('div');
        card.className = 'news-summary-card mb-2 p-3 border rounded bg-light news-item-new';
        card.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <span class="fw-bold text-primary">
                    <i class="bi bi-clipboard-data"></i> ${visible.length}条新快讯整理
                </span>
                <button class="btn btn-sm btn-link text-muted p-0" onclick="News.toggleDetail(this)">展开 ▼</button>
            </div>
            <div class="summary-text">${summary}</div>
            <div class="summary-detail" style="display:none">
                ${visible.map(i => `
                    <div class="small text-muted border-top pt-1 mt-1">
                        <span class="me-1">${i.display_time}</span> ${i.content}
                    </div>
                `).join('')}
            </div>
        `;
        container.insertBefore(card, container.firstChild);
        setTimeout(() => card.classList.remove('news-item-new'), 3000);
    },

    toggleDetail(btn) {
        const card = btn.closest('.news-summary-card, .news-item');
        const detail = card.querySelector('.summary-detail, .derivation-wrap');
        if (!detail) return;
        const isHidden = detail.style.display === 'none';
        detail.style.display = isHidden ? '' : 'none';
        btn.textContent = isHidden ? '收起 ▲' : '展开 ▼';
    },

    createItemElement(item) {
        const src = NEWS_SOURCE_LABELS[item.source_name] || { label: '', color: 'secondary' };
        const scoreIcon = item.score >= 2
            ? '<span class="text-danger me-1">●</span>'
            : '<span class="text-muted me-1">○</span>';
        const srcBadge = src.label
            ? `<span class="badge bg-${src.color} keyword-tag">${src.label}</span>`
            : '';
        const stars = item.importance > 0
            ? `<span class="importance-stars">${'★'.repeat(item.importance)}${'☆'.repeat(5 - item.importance)}</span>`
            : '';
        const kwTags = item.matched_keywords
            ? item.matched_keywords.split(',').map(k => `<span class="badge bg-success keyword-tag">${k.trim()}</span>`).join('')
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
                <div>
                    <span>${item.content}</span>${srcBadge}${stars}${kwTags}
                </div>
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
        container.innerHTML = '';
        let lastDate = '';
        for (const item of this.items) {
            if (item.display_date && item.display_date !== lastDate) {
                lastDate = item.display_date;
                const dateDiv = document.createElement('div');
                dateDiv.className = 'text-muted small fw-bold mt-3 mb-2 border-bottom pb-1';
                dateDiv.textContent = lastDate;
                container.appendChild(dateDiv);
            }
            container.appendChild(this.createItemElement(item));
        }
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

    async showKeywordModal() {
        this.keywordModal.show();
        await this.loadKeywords();
    },

    async loadKeywords() {
        try {
            const [kwResp, compResp] = await Promise.all([
                fetch('/news/keywords'),
                fetch('/news/companies'),
            ]);
            const kwData = await kwResp.json();
            const compData = await compResp.json();

            if (kwData.success) {
                const userKws = kwData.keywords.filter(k => k.source === 'user' || k.is_active);
                const aiKws = kwData.keywords.filter(k => k.source === 'ai' && !k.is_active);

                document.getElementById('userKeywords').innerHTML = userKws.length
                    ? userKws.map(k => `
                        <span class="kw-manage-tag kw-user">
                            ${k.keyword}
                            <button class="kw-delete" onclick="News.deleteKeyword('${k.id}')">-</button>
                        </span>
                    `).join('')
                    : '<span class="text-muted">暂无关键词</span>';

                const aiSection = document.getElementById('aiRecommendSection');
                if (aiKws.length) {
                    aiSection.style.display = '';
                    document.getElementById('aiKeywords').innerHTML = aiKws.map(k => `
                        <span class="kw-manage-tag kw-ai">
                            ${k.keyword}
                            <button class="btn btn-sm btn-outline-success py-0 px-1 ms-1" onclick="News.acceptKeyword('${k.id}')" title="接受">✓</button>
                            <button class="btn btn-sm btn-outline-danger py-0 px-1 ms-1" onclick="News.deleteKeyword('${k.id}')" title="拒绝">✕</button>
                        </span>
                    `).join('');
                } else {
                    aiSection.style.display = 'none';
                }
            }

            if (compData.success) {
                document.getElementById('companyKeywords').innerHTML = compData.companies.length
                    ? compData.companies.map(c => `
                        <span class="kw-manage-tag kw-company">
                            ${c.name}
                            <button class="kw-delete" onclick="News.deleteCompany('${c.id}')">-</button>
                        </span>
                    `).join('')
                    : '<span class="text-muted">暂无公司</span>';
            }
        } catch (e) {
            console.error('加载关键词失败:', e);
        }
    },

    async addKeyword() {
        const input = document.getElementById('newKeywordInput');
        const keyword = input.value.trim();
        if (!keyword) return;
        try {
            await fetch('/news/keywords', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword }),
            });
            input.value = '';
            await this.loadKeywords();
        } catch (e) {
            console.error('添加关键词失败:', e);
        }
    },

    async deleteKeyword(id) {
        try {
            const resp = await fetch(`/news/keywords/${id}`, { method: 'DELETE' });
            const data = await resp.json();
            if (!data.success) console.error('删除关键词失败:', data.error);
            await this.loadKeywords();
        } catch (e) {
            console.error('删除关键词失败:', e);
        }
    },

    async acceptKeyword(id) {
        try {
            await fetch(`/news/keywords/${id}/accept`, { method: 'POST' });
            await this.loadKeywords();
        } catch (e) {
            console.error('接受关键词失败:', e);
        }
    },

    async addCompany() {
        const input = document.getElementById('newCompanyInput');
        const name = input.value.trim();
        if (!name) return;
        try {
            await fetch('/news/companies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            input.value = '';
            await this.loadKeywords();
        } catch (e) {
            console.error('添加公司失败:', e);
        }
    },

    async deleteCompany(id) {
        try {
            const resp = await fetch(`/news/companies/${id}`, { method: 'DELETE' });
            const data = await resp.json();
            if (!data.success) console.error('删除公司失败:', data.error);
            await this.loadKeywords();
        } catch (e) {
            console.error('删除公司失败:', e);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => News.init());
