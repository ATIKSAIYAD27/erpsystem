/* Nexus ERP - Efficiency & Multitasking Engine */

(function() {
    'use strict';

    // ============ AJAX HELPER ============
    window.NexusAjax = {
        csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || '',
        
        async request(url, options = {}) {
            const defaults = {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.csrfToken,
                },
            };
            if (options.body && !(options.body instanceof FormData) && typeof options.body === 'object') {
                defaults.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(options.body);
            }
            const response = await fetch(url, { ...defaults, ...options });
            return response.json();
        },

        async get(url) { return this.request(url); },
        async post(url, data) { return this.request(url, { method: 'POST', body: data }); },
        async delete(url, data) { return this.request(url, { method: 'DELETE', body: data }); },
    };

    // ============ PAGINATION ENGINE ============
    window.NexusPagination = {
        containers: new Map(),

        init(containerId, options = {}) {
            const container = document.getElementById(containerId);
            if (!container) return;

            const state = {
                page: options.page || 1,
                perPage: options.perPage || 25,
                total: options.total || 0,
                totalPages: options.totalPages || 1,
                baseUrl: options.baseUrl || window.location.pathname,
                callback: options.callback || null,
                loading: false,
            };

            this.containers.set(containerId, state);
            this.render(containerId);
        },

        render(containerId) {
            const container = document.getElementById(containerId);
            const state = this.containers.get(containerId);
            if (!container || !state) return;

            if (state.totalPages <= 1) { container.innerHTML = ''; return; }

            let html = '<div class="pagination-wrapper d-flex align-items-center justify-content-between flex-wrap gap-3">';

            html += `<div class="pagination-info text-secondary small">`;
            html += `Showing ${(state.page - 1) * state.perPage + 1} - ${Math.min(state.page * state.perPage, state.total)} of ${state.total}`;
            html += `</div>`;

            html += '<div class="pagination-controls d-flex align-items-center gap-1">';

            html += `<button class="btn btn-sm btn-outline-light border-0 pagination-btn" data-page="1" ${state.page === 1 ? 'disabled' : ''}>`;
            html += '<i class="bi bi-chevron-double-left"></i></button>';

            html += `<button class="btn btn-sm btn-outline-light border-0 pagination-btn" data-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>`;
            html += '<i class="bi bi-chevron-left"></i></button>';

            const startPage = Math.max(1, state.page - 2);
            const endPage = Math.min(state.totalPages, state.page + 2);

            for (let i = startPage; i <= endPage; i++) {
                html += `<button class="btn btn-sm ${i === state.page ? 'btn-primary' : 'btn-outline-light border-0'} pagination-btn" data-page="${i}">${i}</button>`;
            }

            html += `<button class="btn btn-sm btn-outline-light border-0 pagination-btn" data-page="${state.page + 1}" ${state.page === state.totalPages ? 'disabled' : ''}>`;
            html += '<i class="bi bi-chevron-right"></i></button>';

            html += `<button class="btn btn-sm btn-outline-light border-0 pagination-btn" data-page="${state.totalPages}" ${state.page === state.totalPages ? 'disabled' : ''}>`;
            html += '<i class="bi bi-chevron-double-right"></i></button>';

            html += '</div></div>';
            container.innerHTML = html;

            container.querySelectorAll('.pagination-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const page = parseInt(btn.dataset.page);
                    if (page && page !== state.page && !state.loading) {
                        this.goTo(containerId, page);
                    }
                });
            });
        },

        async goTo(containerId, page) {
            const state = this.containers.get(containerId);
            if (!state || state.loading) return;

            state.loading = true;
            state.page = page;
            this.render(containerId);

            const url = new URL(state.baseUrl, window.location.origin);
            url.searchParams.set('page', page);
            url.searchParams.set('per_page', state.perPage);

            try {
                const data = await NexusAjax.get(url.toString());
                if (data.total !== undefined) {
                    state.total = data.total;
                    state.totalPages = data.total_pages;
                }
                this.render(containerId);

                if (state.callback) state.callback(data);
                else window.location.href = url.toString();
            } catch (e) {
                console.error('Pagination error:', e);
            } finally {
                state.loading = false;
            }
        }
    };

    // ============ BULK OPERATIONS ============
    window.NexusBulk = {
        selected: new Set(),
        onSelectAll: null,

        toggle(id) {
            if (this.selected.has(id)) this.selected.delete(id);
            else this.selected.add(id);
            this.updateUI();
        },

        toggleAll(checkbox) {
            const checkboxes = document.querySelectorAll('.bulk-select');
            checkboxes.forEach(cb => {
                cb.checked = checkbox.checked;
                const id = cb.dataset.id;
                if (checkbox.checked) this.selected.add(id);
                else this.selected.delete(id);
            });
            this.updateUI();
        },

        clear() {
            this.selected.clear();
            document.querySelectorAll('.bulk-select').forEach(cb => cb.checked = false);
            const selectAll = document.getElementById('selectAll');
            if (selectAll) selectAll.checked = false;
            this.updateUI();
        },

        updateUI() {
            const toolbar = document.getElementById('bulkToolbar');
            const countEl = document.getElementById('bulkCount');
            if (toolbar) {
                toolbar.style.display = this.selected.size > 0 ? 'flex' : 'none';
            }
            if (countEl) countEl.textContent = this.selected.size;
        },

        async bulkDelete(url, confirmMsg) {
            if (this.selected.size === 0) return;
            if (confirmMsg && !confirm(confirmMsg)) return;

            try {
                const data = await NexusAjax.post(url, { ids: Array.from(this.selected) });
                if (data.success) {
                    NexusToast.show(data.message, 'success');
                    this.clear();
                    setTimeout(() => window.location.reload(), 800);
                } else {
                    NexusToast.show(data.message || 'Operation failed', 'danger');
                }
            } catch (e) {
                NexusToast.show('Bulk operation failed', 'danger');
            }
        },

        async bulkUpdate(url, field, value) {
            if (this.selected.size === 0) return;
            try {
                const data = await NexusAjax.post(url, { ids: Array.from(this.selected), field, value });
                if (data.success) {
                    NexusToast.show(data.message, 'success');
                    this.clear();
                    setTimeout(() => window.location.reload(), 800);
                }
            } catch (e) {
                NexusToast.show('Bulk update failed', 'danger');
            }
        }
    };

    // ============ TOAST NOTIFICATIONS ============
    window.NexusToast = {
        show(message, type = 'info', duration = 4000) {
            const container = document.getElementById('toastContainer');
            if (!container) return;

            const iconMap = {
                'info': 'bi-info-circle-fill',
                'success': 'bi-check-circle-fill',
                'warning': 'bi-exclamation-triangle-fill',
                'danger': 'bi-x-circle-fill'
            };

            const toast = document.createElement('div');
            toast.className = 'realtime-toast';
            toast.innerHTML = `
                <div class="toast-icon ${type}"><i class="bi ${iconMap[type] || iconMap['info']}"></i></div>
                <div class="toast-body">
                    <div class="toast-msg">${message}</div>
                    <div class="toast-time">Just now</div>
                </div>
            `;
            toast.addEventListener('click', () => toast.remove());
            container.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100px)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    };

    // ============ KEYBOARD SHORTCUTS ============
    window.NexusShortcuts = {
        shortcuts: [],

        register(key, ctrl, shift, alt, callback, description) {
            this.shortcuts.push({ key, ctrl, shift, alt, callback, description });
        },

        init() {
            document.addEventListener('keydown', (e) => {
                for (const s of this.shortcuts) {
                    const ctrlMatch = s.ctrl ? (e.ctrlKey || e.metaKey) : !(e.ctrlKey || e.metaKey);
                    const shiftMatch = s.shift ? e.shiftKey : !e.shiftKey;
                    const altMatch = s.alt ? e.altKey : !e.altKey;

                    if (e.key.toLowerCase() === s.key.toLowerCase() && ctrlMatch && shiftMatch && altMatch) {
                        e.preventDefault();
                        s.callback(e);
                        return;
                    }
                }
            });
        },

        showHelp() {
            let html = '<div class="shortcut-help"><h5 class="text-white mb-3 fw-bold">Keyboard Shortcuts</h5>';
            html += '<div class="list-group list-group-flush">';
            for (const s of this.shortcuts) {
                let keyStr = '';
                if (s.ctrl) keyStr += 'Ctrl+';
                if (s.shift) keyStr += 'Shift+';
                if (s.alt) keyStr += 'Alt+';
                keyStr += s.key.toUpperCase();
                html += `<div class="list-group-item bg-transparent text-white d-flex justify-content-between border-secondary">
                    <span>${s.description}</span>
                    <kbd class="text-secondary">${keyStr}</kbd>
                </div>`;
            }
            html += '</div></div>';

            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `<div class="modal-dialog modal-dialog-centered"><div class="modal-content bg-dark border-secondary rounded-4">
                <div class="modal-header border-secondary"><h5 class="modal-title text-white">Keyboard Shortcuts</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">${html}</div></div></div>`;
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
        }
    };

    // ============ MULTITASKING PANEL ============
    window.NexusMultitask = {
        tabs: [],
        maxTabs: 8,

        init() {
            this.render();
            this.registerShortcuts();
        },

        registerShortcuts() {
            NexusShortcuts.register('b', true, false, false, () => this.toggle(), 'Toggle multitasking panel');
            NexusShortcuts.register('w', true, false, false, () => this.addTab(window.location.href, document.title), 'Pin current page');
            for (let i = 1; i <= 8; i++) {
                NexusShortcuts.register(String(i), true, false, false, () => this.switchTo(i - 1));
            }
        },

        addTab(url, title) {
            if (this.tabs.find(t => t.url === url)) return;
            if (this.tabs.length >= this.maxTabs) this.tabs.shift();
            this.tabs.push({ url, title: title.substring(0, 30), active: false });
            this.render();
            NexusToast.show(`Pinned: ${title.substring(0, 30)}`, 'info', 2000);
        },

        switchTo(index) {
            if (index >= 0 && index < this.tabs.length) {
                window.location.href = this.tabs[index].url;
            }
        },

        removeTab(index) {
            this.tabs.splice(index, 1);
            this.render();
        },

        toggle() {
            const panel = document.getElementById('multitaskPanel');
            if (panel) panel.classList.toggle('open');
        },

        render() {
            let panel = document.getElementById('multitaskPanel');
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'multitaskPanel';
                panel.className = 'multitask-panel';
                document.body.appendChild(panel);
            }

            let html = '<div class="multitask-header"><span class="fw-bold text-white"><i class="bi bi-layers me-2"></i>Quick Tabs</span>';
            html += '<button class="btn btn-sm btn-outline-light border-0" onclick="NexusMultitask.tabs=[];NexusMultitask.render();"><i class="bi bi-x-lg"></i></button></div>';
            html += '<div class="multitask-tabs">';

            if (this.tabs.length === 0) {
                html += '<div class="text-secondary small p-3 text-center">Press Ctrl+W to pin current page<br>or Ctrl+B to toggle this panel</div>';
            }

            this.tabs.forEach((tab, i) => {
                const isActive = window.location.href === tab.url;
                html += `<div class="multitask-tab ${isActive ? 'active' : ''}">
                    <a href="${tab.url}" class="text-decoration-none">${tab.title}</a>
                    <button class="btn btn-sm p-0 text-secondary ms-2" onclick="event.preventDefault();NexusMultitask.removeTab(${i});"><i class="bi bi-x"></i></button>
                </div>`;
            });

            html += '</div>';
            panel.innerHTML = html;
        }
    };

    // ============ TABLE SORTING ============
    window.NexusSort = {
        init(tableId) {
            const table = document.getElementById(tableId);
            if (!table) return;

            table.querySelectorAll('th[data-sort]').forEach(th => {
                th.style.cursor = 'pointer';
                th.addEventListener('click', () => {
                    const key = th.dataset.sort;
                    const url = new URL(window.location);
                    const current = url.searchParams.get('sort');
                    const dir = url.searchParams.get('dir') || 'ASC';
                    url.searchParams.set('sort', key);
                    url.searchParams.set('dir', current === key && dir === 'ASC' ? 'DESC' : 'ASC');
                    window.location.href = url.toString();
                });

                const url = new URL(window.location);
                if (url.searchParams.get('sort') === th.dataset.sort) {
                    const dir = url.searchParams.get('dir') || 'ASC';
                    th.innerHTML += ` <i class="bi bi-chevron-${dir === 'ASC' ? 'up' : 'down'} text-primary"></i>`;
                }
            });
        }
    };

    // ============ LAZY LOADING ============
    window.NexusLazy = {
        init() {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const el = entry.target;
                        if (el.dataset.src) {
                            el.src = el.dataset.src;
                            el.removeAttribute('data-src');
                        }
                        if (el.dataset.content) {
                            el.innerHTML = el.dataset.content;
                            el.removeAttribute('data-content');
                        }
                        observer.unobserve(el);
                    }
                });
            }, { rootMargin: '100px' });

            document.querySelectorAll('[data-src], [data-content]').forEach(el => observer.observe(el));
        }
    };

    // ============ SEARCH DEBOUNCE ============
    window.NexusSearch = {
        debounceTimer: null,

        init(inputId, callback, delay = 300) {
            const input = document.getElementById(inputId);
            if (!input) return;

            input.addEventListener('input', () => {
                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => callback(input.value), delay);
            });
        }
    };

    // ============ FORM AJAX SUBMIT ============
    window.NexusForm = {
        init(formId, options = {}) {
            const form = document.getElementById(formId);
            if (!form) return;

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const data = {};
                formData.forEach((v, k) => data[k] = v);

                try {
                    const result = await NexusAjax.post(form.action, data);
                    if (result.success) {
                        NexusToast.show(result.message || 'Operation successful', 'success');
                        if (options.onSuccess) options.onSuccess(result);
                        else setTimeout(() => window.location.reload(), 800);
                    } else {
                        NexusToast.show(result.message || 'Operation failed', 'danger');
                    }
                } catch (err) {
                    NexusToast.show('Request failed', 'danger');
                }
            });
        }
    };

    // ============ INITIALIZATION ============
    document.addEventListener('DOMContentLoaded', () => {
        NexusShortcuts.init();
        NexusMultitask.init();
        NexusLazy.init();

        NexusShortcuts.register('?', false, false, false, () => NexusShortcuts.showHelp(), 'Show keyboard shortcuts');
        NexusShortcuts.register('Escape', false, false, false, () => {
            document.getElementById('multitaskPanel')?.classList.remove('open');
            document.getElementById('searchOverlay')?.classList.remove('active');
        });

        document.querySelectorAll('.sortable-table').forEach(table => {
            NexusSort.init(table.id);
        });

        document.querySelectorAll('.pagination-container').forEach(container => {
            const state = {
                page: parseInt(container.dataset.page) || 1,
                perPage: parseInt(container.dataset.perPage) || 25,
                total: parseInt(container.dataset.total) || 0,
                totalPages: parseInt(container.dataset.totalPages) || 1,
                baseUrl: container.dataset.baseUrl || window.location.pathname,
            };
            NexusPagination.init(container.id, state);
        });

        document.querySelectorAll('.bulk-select').forEach(cb => {
            cb.addEventListener('change', () => NexusBulk.toggle(cb.dataset.id));
        });

        const selectAll = document.getElementById('selectAll');
        if (selectAll) {
            selectAll.addEventListener('change', () => NexusBulk.toggleAll(selectAll));
        }
    });

})();
