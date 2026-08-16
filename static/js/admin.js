/**
 * DiariCore Admin Suite - Frontend JavaScript Controller
 * Handles tabs, Chart.js visualizations, user management, services health, settings, and audit logs.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State management
    const state = {
        currentTab: 'dashboard',
        charts: {},
        users: {
            page: 1,
            perPage: 15,
            search: '',
            status: '',
            totalPages: 1,
            total: 0,
        },
        analyticsRange: '30d',
    };

    // DOM Elements Cache
    const navItems = document.querySelectorAll('.nav-item[data-tab]');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const toastContainer = document.getElementById('adminToastContainer');

    // Sidebar & Mobile Elements
    const mobileMenuBtn = document.getElementById('adminMobileMenuBtn');
    const sidebarCloseBtn = document.getElementById('adminSidebarCloseBtn');
    const sidebar = document.getElementById('adminSidebar');
    const sidebarBackdrop = document.getElementById('adminSidebarBackdrop');
    const themeToggleBtn = document.getElementById('adminThemeToggle');
    const themeToggleMobileBtn = document.getElementById('adminThemeToggleMobile');
    const logoutBtn = document.getElementById('logoutBtn');

    // =========================================================================
    // 1. Toast Notifications Utility
    // =========================================================================
    function showToast(message, type = 'info', duration = 3500) {
        if (!toastContainer) return;
        const toast = document.createElement('div');
        toast.className = `admin-toast admin-toast-${type}`;

        const iconMap = {
            success: 'bi-check-circle-fill text-success',
            error: 'bi-exclamation-octagon-fill text-danger',
            info: 'bi-info-circle-fill text-primary',
            warning: 'bi-exclamation-triangle-fill text-warning',
        };
        const iconClass = iconMap[type] || iconMap.info;

        toast.innerHTML = `
            <i class="bi ${iconClass} fs-5"></i>
            <span>${escapeHtml(message)}</span>
        `;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.25s ease';
            setTimeout(() => toast.remove(), 250);
        }, duration);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function getCsrfToken() {
        return window.sessionStorage?.getItem('diari_csrf') || '';
    }

    // =========================================================================
    // 2. Tab Navigation & Mobile Drawer
    // =========================================================================
    function switchTab(tabId) {
        state.currentTab = tabId;

        navItems.forEach((btn) => {
            const isActive = btn.dataset.tab === tabId;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        tabPanes.forEach((pane) => {
            pane.classList.toggle('active', pane.id === `tab-${tabId}`);
        });

        // Close mobile sidebar if open
        closeMobileSidebar();

        // Load specific tab data
        switch (tabId) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'users':
                loadUsers();
                break;
            case 'analytics':
                loadAnalytics();
                break;
            case 'services':
                loadServices();
                break;
            case 'settings':
                loadSettings();
                break;
            case 'audit':
                loadAuditLogs();
                break;
        }
    }

    navItems.forEach((btn) => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    function openMobileSidebar() {
        sidebar?.classList.add('open');
        sidebarBackdrop?.classList.add('open');
    }

    function closeMobileSidebar() {
        sidebar?.classList.remove('open');
        sidebarBackdrop?.classList.remove('open');
    }

    mobileMenuBtn?.addEventListener('click', openMobileSidebar);
    sidebarCloseBtn?.addEventListener('click', closeMobileSidebar);
    sidebarBackdrop?.addEventListener('click', closeMobileSidebar);

    // Dark Mode Toggle
    function toggleTheme() {
        if (window.DiariTheme && typeof window.DiariTheme.toggle === 'function') {
            window.DiariTheme.toggle();
        } else {
            const html = document.documentElement;
            html.classList.toggle('theme-dark');
        }
    }
    themeToggleBtn?.addEventListener('click', toggleTheme);
    themeToggleMobileBtn?.addEventListener('click', toggleTheme);

    // Logout
    logoutBtn?.addEventListener('click', () => {
        fetch('/api/admin/logout', { method: 'POST' })
            .finally(() => {
                if (window.DiariTheme && typeof window.DiariTheme.logout === 'function') {
                    window.DiariTheme.logout('login.html');
                } else {
                    try {
                        localStorage.removeItem('diariCoreUser');
                    } catch (_) {}
                    window.location.href = 'login.html';
                }
            });
    });

    // Modal dismiss delegation
    document.addEventListener('click', (e) => {
        const dismissTarget = e.target.closest('[data-dismiss-modal]');
        if (dismissTarget) {
            const modalId = dismissTarget.dataset.dismissModal;
            const modal = document.getElementById(modalId);
            if (modal) modal.hidden = true;
        }
    });

    // =========================================================================
    // 3. Dashboard Controller
    // =========================================================================
    const refreshDashboardBtn = document.getElementById('refreshDashboardBtn');
    refreshDashboardBtn?.addEventListener('click', () => {
        refreshDashboardBtn.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Refreshing...';
        loadDashboard().finally(() => {
            refreshDashboardBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
        });
    });

    function loadDashboard() {
        return fetch('/api/admin/dashboard')
            .then((res) => res.json())
            .then((data) => {
                if (!data.success) {
                    if (data.error === 'Unauthorized') {
                        window.location.href = 'login.html';
                    }
                    showToast(data.error || 'Failed to load dashboard.', 'error');
                    return;
                }
                renderDashboardMetrics(data.stats);
            })
            .catch((err) => {
                console.error(err);
                showToast('Error connecting to admin API.', 'error');
            });
    }

    function renderDashboardMetrics(stats) {
        if (!stats) return;

        // KPI values
        document.getElementById('kpiTotalUsers').textContent = Number(stats.totalUsers || 0).toLocaleString();
        document.getElementById('kpiActiveUsers').textContent = Number(stats.activeUsers || 0).toLocaleString();
        document.getElementById('kpiTotalEntries').textContent = Number(stats.totalEntries || 0).toLocaleString();
        document.getElementById('kpiTotalAi').textContent = Number(stats.totalAiAnalyses || 0).toLocaleString();

        // Quick service pills
        if (stats.services) {
            updatePillStatus('statusDbDot', 'statusDbDesc', stats.services.database);
            updatePillStatus('statusVoiceDot', 'statusVoiceDesc', stats.services.voiceAi);
            updatePillStatus('statusEmailDot', 'statusEmailDesc', stats.services.emailService);
        }

        // Render Activity Timeline Chart (30 Days)
        renderActivityChart(stats.activityTimeline || []);

        // Render Emotion Distribution Donut Chart
        renderEmotionDonutChart(stats.emotionDistribution || {});

        // Render Recent Activities (Privacy Safe)
        renderRecentActivity(stats.recentActivity || []);
    }

    function updatePillStatus(dotId, descId, serviceInfo) {
        const dot = document.getElementById(dotId);
        const desc = document.getElementById(descId);
        if (!dot || !desc || !serviceInfo) return;

        dot.className = 'status-indicator';
        if (serviceInfo.status === 'operational') {
            dot.classList.add('status-operational');
        } else if (serviceInfo.status === 'warning') {
            dot.classList.add('status-warning');
        } else if (serviceInfo.status === 'disabled') {
            dot.classList.add('status-disabled');
        } else {
            dot.classList.add('status-error');
        }
        desc.textContent = serviceInfo.label || 'Unknown';
    }

    function renderActivityChart(timeline) {
        const ctx = document.getElementById('userActivityChart');
        if (!ctx) return;

        if (state.charts.userActivity) {
            state.charts.userActivity.destroy();
        }

        const labels = timeline.map((t) => {
            const parts = t.date.split('-');
            return `${parts[1]}/${parts[2]}`;
        });
        const entryData = timeline.map((t) => t.entries);
        const signupData = timeline.map((t) => t.signups);

        state.charts.userActivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Journal Entries',
                        data: entryData,
                        borderColor: '#6F8F7F',
                        backgroundColor: 'rgba(111, 143, 127, 0.15)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                    },
                    {
                        label: 'New Registrations',
                        data: signupData,
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.35,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } } },
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    function renderEmotionDonutChart(emotions) {
        const ctx = document.getElementById('emotionDistributionChart');
        if (!ctx) return;

        if (state.charts.emotionDonut) {
            state.charts.emotionDonut.destroy();
        }

        const labels = ['Happy', 'Sad', 'Anxious', 'Angry', 'Neutral'];
        const counts = [
            emotions.happy || 0,
            emotions.sad || 0,
            emotions.anxious || 0,
            emotions.angry || 0,
            emotions.neutral || 0,
        ];
        const colors = ['#22C55E', '#3B82F6', '#F97316', '#EF4444', '#9CA3AF'];

        state.charts.emotionDonut = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [
                    {
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 2,
                        borderColor: document.documentElement.classList.contains('theme-dark') ? '#1B2620' : '#FFFFFF',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } } },
                },
                cutout: '68%',
            },
        });
    }

    function renderRecentActivity(activities) {
        const tbody = document.getElementById('recentActivityTbody');
        if (!tbody) return;

        if (!activities.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center muted py-4">No recent activity found.</td></tr>';
            return;
        }

        tbody.innerHTML = activities
            .map((act) => {
                const emoBadgeClass = `badge-emotion badge-emotion-${escapeHtml(act.emotion || 'neutral')}`;
                return `
                <tr>
                    <td>
                        <div class="fw-bold">${escapeHtml(act.nickname)}</div>
                        <span class="muted small">${escapeHtml(act.maskedEmail)}</span>
                    </td>
                    <td><span class="${emoBadgeClass}">${escapeHtml(act.emotion)}</span></td>
                    <td><span class="text-capitalize small fw-semibold">${escapeHtml(act.sentiment)}</span></td>
                    <td><span class="badge badge-operational">${act.words} words</span></td>
                    <td><span class="muted small">${formatDate(act.createdAt)}</span></td>
                </tr>
            `;
            })
            .join('');
    }

    // =========================================================================
    // 4. User Management Controller
    // =========================================================================
    const userSearchInput = document.getElementById('userSearchInput');
    const userSearchClearBtn = document.getElementById('userSearchClearBtn');
    const userStatusSelect = document.getElementById('userStatusSelect');
    const statPills = document.querySelectorAll('.stat-pill[data-status-filter]');
    const usersPrevBtn = document.getElementById('usersPrevBtn');
    const usersNextBtn = document.getElementById('usersNextBtn');

    let searchDebounceTimer = null;
    userSearchInput?.addEventListener('input', () => {
        const val = userSearchInput.value.trim();
        userSearchClearBtn.hidden = !val;
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            state.users.search = val;
            state.users.page = 1;
            loadUsers();
        }, 300);
    });

    userSearchClearBtn?.addEventListener('click', () => {
        userSearchInput.value = '';
        userSearchClearBtn.hidden = true;
        state.users.search = '';
        state.users.page = 1;
        loadUsers();
    });

    userStatusSelect?.addEventListener('change', () => {
        state.users.status = userStatusSelect.value;
        state.users.page = 1;
        updateStatPillsActive(userStatusSelect.value);
        loadUsers();
    });

    statPills.forEach((pill) => {
        pill.addEventListener('click', () => {
            const filter = pill.dataset.statusFilter;
            state.users.status = filter;
            state.users.page = 1;
            if (userStatusSelect) userStatusSelect.value = filter;
            updateStatPillsActive(filter);
            loadUsers();
        });
    });

    function updateStatPillsActive(status) {
        statPills.forEach((p) => {
            p.classList.toggle('active', p.dataset.statusFilter === status);
        });
    }

    usersPrevBtn?.addEventListener('click', () => {
        if (state.users.page > 1) {
            state.users.page--;
            loadUsers();
        }
    });

    usersNextBtn?.addEventListener('click', () => {
        if (state.users.page < state.users.totalPages) {
            state.users.page++;
            loadUsers();
        }
    });

    function loadUsers() {
        const params = new URLSearchParams({
            q: state.users.search,
            status: state.users.status,
            page: state.users.page,
            perPage: state.users.perPage,
        });

        const tbody = document.getElementById('usersTableTbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center muted py-4"><span class="spinner"></span> Loading users...</td></tr>';
        }

        return fetch(`/api/admin/users?${params.toString()}`)
            .then((res) => res.json())
            .then((data) => {
                if (!data.success) {
                    showToast(data.error || 'Failed to load user records.', 'error');
                    return;
                }
                renderUsersTable(data.data);
            })
            .catch((err) => {
                console.error(err);
                showToast('Error loading users.', 'error');
            });
    }

    function renderUsersTable(userData) {
        const tbody = document.getElementById('usersTableTbody');
        if (!tbody || !userData) return;

        // Update counts
        if (userData.counts) {
            document.getElementById('userCountTotal').textContent = userData.counts.total || 0;
            document.getElementById('userCountActive').textContent = userData.counts.active || 0;
            document.getElementById('userCountDisabled').textContent = userData.counts.disabled || 0;
            document.getElementById('userCount2fa').textContent = userData.counts.twoFactor || 0;
        }

        // Update pagination state
        state.users.totalPages = userData.totalPages || 1;
        state.users.total = userData.total || 0;

        document.getElementById('usersPaginationInfo').textContent = `Showing ${userData.records.length} of ${userData.total} users`;
        document.getElementById('usersPageNum').textContent = `Page ${userData.page} of ${userData.totalPages}`;
        usersPrevBtn.disabled = userData.page <= 1;
        usersNextBtn.disabled = userData.page >= userData.totalPages;

        if (!userData.records.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center muted py-4">No users match your criteria.</td></tr>';
            return;
        }

        tbody.innerHTML = userData.records
            .map((u) => {
                const statusBadge = u.isDisabled
                    ? '<span class="badge badge-disabled"><i class="bi bi-slash-circle me-1"></i>Disabled</span>'
                    : '<span class="badge badge-active"><i class="bi bi-check-circle me-1"></i>Active</span>';

                const twoFaBadge = u.totpEnabled
                    ? '<span class="badge badge-2fa"><i class="bi bi-shield-lock-fill me-1"></i>Enabled</span>'
                    : '<span class="muted small">—</span>';

                const toggleActionText = u.isDisabled ? 'Enable Account' : 'Disable Account';
                const toggleActionIcon = u.isDisabled ? 'bi-check-circle' : 'bi-slash-circle';
                const toggleActionClass = u.isDisabled ? 'text-success' : 'text-warning';

                return `
                <tr>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="avatar-placeholder" style="width: 32px; height: 32px; border-radius: 50%; background: #6F8F7F; color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem;">
                                ${(u.nickname || 'U')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="fw-bold">${escapeHtml(u.fullName)}</div>
                                <span class="muted small">@${escapeHtml(u.nickname)}</span>
                            </div>
                        </div>
                    </td>
                    <td><span class="small">${escapeHtml(u.email)}</span></td>
                    <td>${statusBadge}</td>
                    <td>${twoFaBadge}</td>
                    <td><span class="fw-bold">${u.entryCount}</span> <span class="muted small">entries</span></td>
                    <td><span class="muted small">${formatDate(u.createdAt)}</span></td>
                    <td><span class="muted small">${formatDate(u.lastLogin)}</span></td>
                    <td class="text-end">
                        <div class="d-inline-flex gap-1">
                            <button class="btn btn-sm btn-outline btn-icon view-user-btn" data-user-id="${u.id}" title="View User Details">
                                <i class="bi bi-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-outline btn-icon toggle-user-btn ${toggleActionClass}" data-user-id="${u.id}" data-disabled="${u.isDisabled ? 'false' : 'true'}" title="${toggleActionText}">
                                <i class="bi ${toggleActionIcon}"></i>
                            </button>
                            <button class="btn btn-sm btn-outline btn-icon text-danger delete-user-btn" data-user-id="${u.id}" data-nickname="${escapeHtml(u.nickname)}" data-email="${escapeHtml(u.email)}" title="Delete User Permanently">
                                <i class="bi bi-trash3"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
            })
            .join('');

        // Bind Row Action Buttons
        document.querySelectorAll('.view-user-btn').forEach((btn) => {
            btn.addEventListener('click', () => openUserDetailsModal(btn.dataset.userId));
        });

        document.querySelectorAll('.toggle-user-btn').forEach((btn) => {
            btn.addEventListener('click', () => toggleUserStatus(btn.dataset.userId, btn.dataset.disabled === 'true'));
        });

        document.querySelectorAll('.delete-user-btn').forEach((btn) => {
            btn.addEventListener('click', () => openDeleteUserModal(btn.dataset.userId, btn.dataset.nickname, btn.dataset.email));
        });
    }

    function openUserDetailsModal(userId) {
        const modal = document.getElementById('userDetailsModal');
        const modalBody = document.getElementById('userDetailsModalBody');
        if (!modal || !modalBody) return;

        modal.hidden = false;
        modalBody.innerHTML = '<div class="text-center py-4"><span class="spinner"></span> Loading user details...</div>';

        fetch(`/api/admin/users/${userId}`)
            .then((res) => res.json())
            .then((data) => {
                if (!data.success || !data.user) {
                    modalBody.innerHTML = `<div class="alert alert-danger">${escapeHtml(data.error || 'Failed to load user.')}</div>`;
                    return;
                }
                const u = data.user;
                const stats = u.journalStats || {};
                const emos = stats.emotions || {};

                modalBody.innerHTML = `
                    <div class="user-details-grid">
                        <div class="user-detail-item">
                            <span class="user-detail-label">Full Name</span>
                            <span class="user-detail-val">${escapeHtml(u.fullName)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Nickname / Username</span>
                            <span class="user-detail-val">@${escapeHtml(u.nickname)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Email Address</span>
                            <span class="user-detail-val">${escapeHtml(u.email)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Account Status</span>
                            <span class="user-detail-val">${u.isDisabled ? '<span class="badge badge-disabled">Disabled</span>' : '<span class="badge badge-active">Active</span>'}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Two-Factor Authentication</span>
                            <span class="user-detail-val">${u.totpEnabled ? '<span class="badge badge-2fa">Enabled</span>' : '<span class="muted">Disabled</span>'}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Registration Date</span>
                            <span class="user-detail-val">${formatDate(u.createdAt)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Last Login</span>
                            <span class="user-detail-val">${formatDate(u.lastLogin)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Privacy Notice Consent</span>
                            <span class="user-detail-val">${formatDate(u.privacyAgreedAt)}</span>
                        </div>
                    </div>

                    <hr style="margin: 1.25rem 0; border: 0; border-top: 1px solid var(--border-color);">

                    <h4 style="font-size: 1rem; margin: 0 0 0.75rem;">Journaling Summary &amp; Mood Metadata</h4>
                    <p class="muted" style="margin-bottom: 1rem;">DiariCore preserves user privacy: only aggregated metrics are visible to administrators.</p>

                    <div class="user-details-grid" style="grid-template-columns: repeat(3, 1fr);">
                        <div class="user-detail-item">
                            <span class="user-detail-label">Total Entries</span>
                            <span class="user-detail-val fs-5 fw-bold text-primary">${stats.totalEntries || 0}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">First Entry</span>
                            <span class="user-detail-val">${formatDate(stats.firstEntryDate)}</span>
                        </div>
                        <div class="user-detail-item">
                            <span class="user-detail-label">Latest Entry</span>
                            <span class="user-detail-val">${formatDate(stats.lastEntryDate)}</span>
                        </div>
                    </div>

                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem;">
                        <span class="badge badge-emotion badge-emotion-happy">Happy: ${emos.happy || 0}</span>
                        <span class="badge badge-emotion badge-emotion-sad">Sad: ${emos.sad || 0}</span>
                        <span class="badge badge-emotion badge-emotion-anxious">Anxious: ${emos.anxious || 0}</span>
                        <span class="badge badge-emotion badge-emotion-angry">Angry: ${emos.angry || 0}</span>
                        <span class="badge badge-emotion badge-emotion-neutral">Neutral: ${emos.neutral || 0}</span>
                    </div>
                `;
            })
            .catch(() => {
                modalBody.innerHTML = '<div class="alert alert-danger">Error loading user details.</div>';
            });
    }

    function toggleUserStatus(userId, shouldDisable) {
        const actionLabel = shouldDisable ? 'deactivate' : 'activate';
        if (!confirm(`Are you sure you want to ${actionLabel} this user's account?`)) return;

        fetch(`/api/admin/users/${userId}/toggle-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
            body: JSON.stringify({ disabled: shouldDisable }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(data.message || 'Status updated successfully.', 'success');
                    loadUsers();
                } else {
                    showToast(data.error || 'Failed to update user status.', 'error');
                }
            })
            .catch(() => showToast('Error communicating with server.', 'error'));
    }

    let userToDeleteId = null;
    function openDeleteUserModal(userId, nickname, email) {
        userToDeleteId = userId;
        document.getElementById('deleteUserNickname').textContent = nickname;
        document.getElementById('deleteUserEmail').textContent = email;
        const modal = document.getElementById('deleteUserModal');
        if (modal) modal.hidden = false;
    }

    document.getElementById('confirmDeleteUserBtn')?.addEventListener('click', () => {
        if (!userToDeleteId) return;
        const btn = document.getElementById('confirmDeleteUserBtn');
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-trash3 spin"></i> Deleting...';

        fetch(`/api/admin/users/${userToDeleteId}`, {
            method: 'DELETE',
            headers: { 'X-CSRF-Token': getCsrfToken() },
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(data.message || 'User deleted permanently.', 'success');
                    document.getElementById('deleteUserModal').hidden = true;
                    loadUsers();
                } else {
                    showToast(data.error || 'Failed to delete user.', 'error');
                }
            })
            .catch(() => showToast('Error communicating with server.', 'error'))
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-trash3-fill me-1"></i> Delete Account';
                userToDeleteId = null;
            });
    });

    // =========================================================================
    // 5. Analytics Controller
    // =========================================================================
    const rangeBtns = document.querySelectorAll('#analyticsRangeSelector .range-btn');
    rangeBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            rangeBtns.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');
            state.analyticsRange = btn.dataset.range;
            loadAnalytics();
        });
    });

    function loadAnalytics() {
        return fetch(`/api/admin/analytics?range=${state.analyticsRange}`)
            .then((res) => res.json())
            .then((data) => {
                if (!data.success || !data.analytics) {
                    showToast(data.error || 'Failed to load analytics.', 'error');
                    return;
                }
                renderAnalyticsView(data.analytics);
            })
            .catch(() => showToast('Error connecting to analytics API.', 'error'));
    }

    function renderAnalyticsView(analytics) {
        const timeline = analytics.timeline || [];
        const sentiments = analytics.sentiments || {};
        const dow = analytics.dayOfWeek || [0, 0, 0, 0, 0, 0, 0];

        // Summary values
        document.getElementById('analyticsEntriesCount').textContent = Number(analytics.totalEntriesInRange || 0).toLocaleString();
        document.getElementById('analyticsRangeLabel').textContent = `${analytics.rangeDays} Days Period`;

        const dailyAvg = (analytics.totalEntriesInRange / Math.max(1, analytics.rangeDays)).toFixed(1);
        document.getElementById('analyticsDailyAvg').textContent = dailyAvg;

        // Dominant Emotion
        let topEmo = 'Neutral';
        let topCount = -1;
        const totalEmos = { happy: 0, sad: 0, anxious: 0, angry: 0, neutral: 0 };
        timeline.forEach((t) => {
            totalEmos.happy += t.happy || 0;
            totalEmos.sad += t.sad || 0;
            totalEmos.anxious += t.anxious || 0;
            totalEmos.angry += t.angry || 0;
            totalEmos.neutral += t.neutral || 0;
        });
        Object.entries(totalEmos).forEach(([emo, cnt]) => {
            if (cnt > topCount && cnt > 0) {
                topCount = cnt;
                topEmo = emo.charAt(0).toUpperCase() + emo.slice(1);
            }
        });
        document.getElementById('analyticsTopEmotion').textContent = topEmo;

        // Positive sentiment ratio
        const totalSent = (sentiments.positive || 0) + (sentiments.neutral || 0) + (sentiments.negative || 0);
        const posRatio = totalSent > 0 ? Math.round(((sentiments.positive || 0) / totalSent) * 100) : 0;
        document.getElementById('analyticsPositiveRatio').textContent = `${posRatio}%`;

        // Render Emotion Trends Chart (Stacked Multi-line)
        renderEmotionTrendChart(timeline);

        // Render Sentiment Donut Chart
        renderSentimentChart(sentiments);

        // Render Day of Week Chart
        renderDowChart(dow);
    }

    function renderEmotionTrendChart(timeline) {
        const ctx = document.getElementById('analyticsEmotionTrendChart');
        if (!ctx) return;

        if (state.charts.analyticsEmotion) {
            state.charts.analyticsEmotion.destroy();
        }

        const labels = timeline.map((t) => {
            const parts = t.date.split('-');
            return `${parts[1]}/${parts[2]}`;
        });

        state.charts.analyticsEmotion = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Happy', data: timeline.map((t) => t.happy), borderColor: '#22C55E', backgroundColor: 'rgba(34, 197, 94, 0.1)', tension: 0.35 },
                    { label: 'Sad', data: timeline.map((t) => t.sad), borderColor: '#3B82F6', backgroundColor: 'rgba(59, 130, 246, 0.1)', tension: 0.35 },
                    { label: 'Anxious', data: timeline.map((t) => t.anxious), borderColor: '#F97316', backgroundColor: 'rgba(249, 115, 22, 0.1)', tension: 0.35 },
                    { label: 'Angry', data: timeline.map((t) => t.angry), borderColor: '#EF4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', tension: 0.35 },
                    { label: 'Neutral', data: timeline.map((t) => t.neutral), borderColor: '#9CA3AF', backgroundColor: 'rgba(156, 163, 175, 0.1)', tension: 0.35 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } } },
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    function renderSentimentChart(sentiments) {
        const ctx = document.getElementById('analyticsSentimentChart');
        if (!ctx) return;

        if (state.charts.analyticsSentiment) {
            state.charts.analyticsSentiment.destroy();
        }

        state.charts.analyticsSentiment = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Positive', 'Neutral', 'Negative'],
                datasets: [
                    {
                        data: [sentiments.positive || 0, sentiments.neutral || 0, sentiments.negative || 0],
                        backgroundColor: ['#10B981', '#9CA3AF', '#EF4444'],
                        borderWidth: 2,
                        borderColor: document.documentElement.classList.contains('theme-dark') ? '#1B2620' : '#FFFFFF',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } } },
                },
                cutout: '65%',
            },
        });
    }

    function renderDowChart(dow) {
        const ctx = document.getElementById('analyticsDowChart');
        if (!ctx) return;

        if (state.charts.analyticsDow) {
            state.charts.analyticsDow.destroy();
        }

        const labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

        state.charts.analyticsDow = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Entries',
                        data: dow,
                        backgroundColor: '#6F8F7F',
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    // =========================================================================
    // 6. AI & Services Controller
    // =========================================================================
    const refreshServicesBtn = document.getElementById('refreshServicesBtn');
    refreshServicesBtn?.addEventListener('click', loadServices);

    function loadServices() {
        return fetch('/api/admin/services')
            .then((res) => res.json())
            .then((data) => {
                if (!data.success || !data.services) {
                    showToast('Failed to load services status.', 'error');
                    return;
                }
                renderServicesView(data.services);
            })
            .catch(() => showToast('Error loading services health.', 'error'));
    }

    function renderServicesView(services) {
        // Voice AI Whisper
        const voice = services.voiceAi;
        if (voice) {
            const badge = document.getElementById('svcBadgeVoice');
            if (badge) {
                badge.className = `badge badge-${voice.status}`;
                badge.textContent = voice.status === 'operational' ? 'Operational' : 'Token Missing';
            }
        }

        // Email Service
        const email = services.email;
        if (email) {
            const badge = document.getElementById('svcBadgeEmail');
            if (badge) {
                badge.className = `badge badge-${email.status}`;
                badge.textContent = email.status === 'operational' ? 'Operational' : (email.status === 'disabled' ? 'Disabled' : 'Not Configured');
            }
            document.getElementById('svcSenderEmail').textContent = email.senderEmail || '—';
            document.getElementById('svcSenderName').textContent = email.senderName || '—';
            document.getElementById('svcEmailEnabled').innerHTML = email.enabled
                ? '<span class="text-success fw-bold">Active</span>'
                : '<span class="text-muted">Disabled</span>';
        }

        // Database
        const dbInfo = services.database;
        if (dbInfo) {
            document.getElementById('svcDbEngine').textContent = dbInfo.provider || 'PostgreSQL';
            document.getElementById('svcDbLatency').textContent = `${dbInfo.latencyMs || 0} ms`;
            document.getElementById('svcDbUsers').textContent = dbInfo.details?.split(',')[0] || '—';
            document.getElementById('svcDbEntries').textContent = dbInfo.details?.split(',')[1] || '—';
        }
    }

    // Test Voice AI Connection Ping
    const testAiBtn = document.getElementById('testAiBtn');
    testAiBtn?.addEventListener('click', () => {
        testAiBtn.disabled = true;
        testAiBtn.innerHTML = '<i class="bi bi-lightning-charge-fill spin"></i> Testing Hugging Face Router...';

        fetch('/api/admin/services/test-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(`✅ ${data.message} (${data.latencyMs}ms)`, 'success');
                    const latencyEl = document.getElementById('svcLatencyVoice');
                    if (latencyEl) latencyEl.textContent = `${data.latencyMs} ms`;
                } else {
                    showToast(`❌ ${data.error || 'Connection failed.'}`, 'error', 5000);
                }
            })
            .catch((err) => showToast(`Error: ${err.message}`, 'error'))
            .finally(() => {
                testAiBtn.disabled = false;
                testAiBtn.innerHTML = '<i class="bi bi-lightning-charge-fill"></i> Test Voice AI Connection';
            });
    });

    // Test Email Modal & Submission
    const openTestEmailModalBtn = document.getElementById('openTestEmailModalBtn');
    const testEmailModal = document.getElementById('testEmailModal');
    const sendTestEmailSubmitBtn = document.getElementById('sendTestEmailSubmitBtn');
    const testEmailRecipient = document.getElementById('testEmailRecipient');

    openTestEmailModalBtn?.addEventListener('click', () => {
        if (testEmailModal) testEmailModal.hidden = false;
    });

    sendTestEmailSubmitBtn?.addEventListener('click', () => {
        const emailVal = testEmailRecipient ? testEmailRecipient.value.trim() : '';
        sendTestEmailSubmitBtn.disabled = true;
        sendTestEmailSubmitBtn.innerHTML = '<i class="bi bi-send spin"></i> Sending...';

        fetch('/api/admin/services/test-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
            body: JSON.stringify({ recipientEmail: emailVal }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(data.message || 'Test email sent successfully!', 'success');
                    if (testEmailModal) testEmailModal.hidden = true;
                } else {
                    showToast(data.error || 'Failed to send test email.', 'error', 5000);
                }
            })
            .catch((err) => showToast(`Error: ${err.message}`, 'error'))
            .finally(() => {
                sendTestEmailSubmitBtn.disabled = false;
                sendTestEmailSubmitBtn.innerHTML = '<i class="bi bi-send me-1"></i> Send Test Email';
            });
    });

    // =========================================================================
    // 7. System Settings Controller
    // =========================================================================
    const brevoApiKey = document.getElementById('brevoApiKey');
    const senderEmail = document.getElementById('senderEmail');
    const senderName = document.getElementById('senderName');
    const enableEmailNotifications = document.getElementById('enableEmailNotifications');
    const hfApiToken = document.getElementById('hfApiToken');
    const appNameInput = document.getElementById('appNameInput');
    const allowRegistrationCheck = document.getElementById('allowRegistrationCheck');
    const maintenanceModeCheck = document.getElementById('maintenanceModeCheck');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const apiKeyHint = document.getElementById('apiKeyHint');
    const hfTokenHint = document.getElementById('hfTokenHint');

    // Password visibility toggle buttons
    document.querySelectorAll('.password-toggle-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const input = document.getElementById(targetId);
            if (!input) return;
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            btn.innerHTML = isPassword ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
        });
    });

    function loadSettings() {
        return fetch('/api/admin/settings')
            .then((res) => res.json())
            .then((data) => {
                if (!data.success) {
                    showToast('Unauthorized or unable to load settings.', 'error');
                    return;
                }
                const s = data.settings || {};
                if (senderEmail) senderEmail.value = s.senderEmail || '';
                if (senderName) senderName.value = s.senderName || 'DiariCore';
                if (enableEmailNotifications) enableEmailNotifications.checked = !!s.enableEmailNotifications;
                if (appNameInput) appNameInput.value = s.appName || 'DiariCore';
                if (allowRegistrationCheck) allowRegistrationCheck.checked = s.allowRegistration !== false;
                if (maintenanceModeCheck) maintenanceModeCheck.checked = !!s.maintenanceMode;

                if (apiKeyHint) {
                    apiKeyHint.textContent = s.hasApiKey ? `Configured key: ${s.maskedApiKey}` : 'No API key configured.';
                }
                if (hfTokenHint) {
                    hfTokenHint.textContent = s.hasHfToken ? `Configured token: ${s.maskedHfToken}` : 'No Hugging Face token configured.';
                }
            })
            .catch(() => showToast('Error loading system settings.', 'error'));
    }

    saveSettingsBtn?.addEventListener('click', () => {
        saveSettingsBtn.disabled = true;
        saveSettingsBtn.innerHTML = '<i class="bi bi-floppy spin"></i> Saving...';

        const payload = {
            apiKey: brevoApiKey ? brevoApiKey.value.trim() : '',
            hfToken: hfApiToken ? hfApiToken.value.trim() : '',
            senderEmail: senderEmail ? senderEmail.value.trim() : '',
            senderName: senderName ? senderName.value.trim() : '',
            enableEmailNotifications: enableEmailNotifications?.checked || false,
            appName: appNameInput ? appNameInput.value.trim() : 'DiariCore',
            allowRegistration: allowRegistrationCheck?.checked || false,
            maintenanceMode: maintenanceModeCheck?.checked || false,
        };

        fetch('/api/admin/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(data.message || 'Settings saved successfully!', 'success');
                    if (brevoApiKey) brevoApiKey.value = '';
                    if (hfApiToken) hfApiToken.value = '';
                    loadSettings();
                } else {
                    showToast(data.error || 'Failed to save settings.', 'error');
                }
            })
            .catch((err) => showToast(`Error: ${err.message}`, 'error'))
            .finally(() => {
                saveSettingsBtn.disabled = false;
                saveSettingsBtn.innerHTML = '<i class="bi bi-floppy-fill me-1"></i> Save Settings';
            });
    });

    // =========================================================================
    // 8. Audit Logs Controller
    // =========================================================================
    const refreshAuditBtn = document.getElementById('refreshAuditBtn');
    refreshAuditBtn?.addEventListener('click', loadAuditLogs);

    function loadAuditLogs() {
        const tbody = document.getElementById('auditLogsTbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center muted py-4"><span class="spinner"></span> Loading audit logs...</td></tr>';
        }

        return fetch('/api/admin/audit-logs?limit=50')
            .then((res) => res.json())
            .then((data) => {
                if (!data.success || !data.logs) {
                    showToast('Failed to load audit logs.', 'error');
                    return;
                }
                renderAuditLogsTable(data.logs);
            })
            .catch(() => showToast('Error loading audit logs.', 'error'));
    }

    function renderAuditLogsTable(logs) {
        const tbody = document.getElementById('auditLogsTbody');
        if (!tbody) return;

        if (!logs.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center muted py-4">No audit logs recorded yet.</td></tr>';
            return;
        }

        tbody.innerHTML = logs
            .map((log) => {
                const actionBadgeClass = log.action?.includes('DELETE')
                    ? 'badge-error'
                    : log.action?.includes('DISABLED')
                    ? 'badge-warning'
                    : 'badge-active';

                const detailsSummary = Object.entries(log.details || {})
                    .map(([k, v]) => `<span class="badge badge-operational" style="font-size: 0.7rem;">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`)
                    .join(' ') || '<span class="muted small">—</span>';

                return `
                <tr>
                    <td><span class="muted small">#${log.id}</span></td>
                    <td><span class="badge ${actionBadgeClass}">${escapeHtml(log.action)}</span></td>
                    <td><span class="fw-bold small">${escapeHtml(log.adminEmail)}</span></td>
                    <td>${detailsSummary}</td>
                    <td><span class="muted small">${escapeHtml(log.ipAddress)}</span></td>
                    <td><span class="muted small">${formatDate(log.createdAt)}</span></td>
                </tr>
            `;
            })
            .join('');
    }

    // Helper: Date Formatter
    function formatDate(dateStr) {
        if (!dateStr || dateStr === '—' || dateStr === 'Never') return dateStr || '—';
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch (_) {
            return dateStr;
        }
    }

    // Initial load: Dashboard
    loadDashboard().finally(() => {
        if (window.DiariShell && typeof window.DiariShell.release === 'function') {
            window.DiariShell.release();
        }
    });
});
