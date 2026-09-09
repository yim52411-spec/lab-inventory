/**
 * 实验室物料库存管理系统 - 前端交互逻辑
 */

// 全局状态
const AppState = {
    currentUser: null,
    currentRole: null,
    currentUserData: null,
    currentPage: 'dashboard',
    sidebarOpen: false,
    editingMaterialId: null,
    editingUserId: null,
    pendingPurchaseMaterialId: null,
    materialPagination: { current_page: 1, per_page: 20, total: 0, pages: 1 },
    purchaseSummary: { pending: 0, approved: 0, total_attention: 0, latest: [] },
    borrowSummary: { pending: 0, active: 0, total_attention: 0, latest: [] },
    reminderTimer: null,
    lastPurchasePending: 0,
    lastBorrowPending: 0,
    activeInoutTab: 'inout-records',
    activeBorrowTab: 'borrow-all'
};

// 模拟数据
const MockData = {
    materials: [
        { id: 'M2024001', name: '乙醇 (分析纯)', category: 'chemical', spec: '500ml/瓶', stock: 2, threshold: 10, location: 'A区-01架', status: 'danger' },
        { id: 'M2024002', name: '离心管 15ml', category: 'consumable', spec: '50个/包', stock: 15, threshold: 20, location: 'B区-03架', status: 'warning' },
        { id: 'M2024003', name: '培养皿', category: 'glassware', spec: '90mm', stock: 20, threshold: 30, location: 'C区-02架', status: 'warning' },
        { id: 'M2024004', name: '电子天平', category: 'equipment', spec: '0.1mg精度', stock: 5, threshold: 2, location: 'D区-仪器室', status: 'normal' },
        { id: 'M2024005', name: '移液器', category: 'equipment', spec: '100-1000μl', stock: 8, threshold: 3, location: 'D区-仪器室', status: 'normal' }
    ],
    users: [
        { id: 'U001', username: 'admin', name: '系统管理员', role: 'admin', department: '实验室管理部', phone: '13800138000', status: 'active' },
        { id: 'U002', username: 'zhangsan', name: '张三', role: 'visitor', department: '化学实验室', phone: '13900139000', status: 'active' },
        { id: 'U003', username: 'lisi', name: '李四', role: 'visitor', department: '生物实验室', phone: '13700137000', status: 'active' }
    ],
    alerts: [
        { id: 1, materialId: 'M2024001', materialName: '乙醇 (分析纯)', current: 2, threshold: 10, level: 'danger', notified: true },
        { id: 2, materialId: 'M2024002', materialName: '离心管 15ml', current: 15, threshold: 20, level: 'warning', notified: true },
        { id: 3, materialId: 'M2024003', materialName: '培养皿', current: 20, threshold: 30, level: 'warning', notified: false }
    ]
};

/**
 * 初始化应用
 */
document.addEventListener('DOMContentLoaded', function() {
    initLoginPage();
    initNavigation();
    initTabs();
    initDateTime();
    initFormHandlers();
});

function isAdmin() {
    return AppState.currentRole === 'admin';
}

function isVisitor() {
    return AppState.currentRole === 'visitor';
}

function requireAdminAction() {
    if (!isAdmin()) {
        showNotification('权限不足', '访问者仅可浏览或提交申请，不能修改数据', 'error');
        return false;
    }
    return true;
}

/**
 * 初始化登录页面
 */
function initLoginPage() {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleLogin();
        });
    }
}

/**
 * 处理登录 - 连接后端API
 */
async function handleLogin() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const selectedRole = document.getElementById('role').value;
    try {
        const result = await API.Auth.login(username, password);
        
        if (result.success) {
            const user = result.data.user;
            if (user.role !== selectedRole) {
                API.Auth.logout();
                localStorage.removeItem('labInventory_role');
                const actualRoleText = user.role === 'admin' ? '管理员' : '访问者';
                const selectedRoleText = selectedRole === 'admin' ? '管理员' : '访问者';
                showNotification('登录角色错误', `该账号权限为${actualRoleText}，不能以${selectedRoleText}登录，请重新选择角色。`, 'error');
                return;
            }

            AppState.currentUser = user.username;
            AppState.currentRole = user.role;
            AppState.currentUserData = user;
            
            // 保存到本地存储
            localStorage.setItem('labInventory_role', user.role);
            
            // 切换到主应用
            showMainApp();
            
            // 显示欢迎消息
            showNotification('登录成功', `欢迎回来，${user.name}！`, 'success');
        } else {
            showNotification('登录失败', result.message || '用户名或密码错误', 'error');
        }
    } catch (error) {
        showNotification('登录失败', error.message || '网络错误，请稍后重试', 'error');
    }
}

/**
 * 显示主应用 - 从API加载数据
 */
async function showMainApp() {
    document.getElementById('login-page').classList.remove('active');
    document.getElementById('main-app').classList.add('active');
    
    // 更新用户信息
    const userDisplay = document.getElementById('current-user');
    const roleDisplay = document.getElementById('current-role');
    
    if (userDisplay && AppState.currentUserData) {
        userDisplay.textContent = AppState.currentUserData.name;
    }
    if (roleDisplay) {
        roleDisplay.textContent = AppState.currentRole === 'admin' ? '管理员' : '访问者';
    }
    
    // 根据角色显示/隐藏管理员功能
    if (AppState.currentRole === 'visitor') {
        document.body.classList.add('visitor-role');
    } else {
        document.body.classList.remove('visitor-role');
    }
    
    // 加载物料数据
    await loadMaterialsData();
    
    // 加载分类数据
    await loadCategoriesData();
    
    // 加载用户数据
    if (AppState.currentRole === 'admin') {
        await loadUsersData();
        await loadAlertsData();
    }

    await loadHistoryData();
    await loadPurchaseData();
    await loadSettingsData();
    await loadPurchaseSummary();
    await loadBorrowSummary();
    
    // 默认显示仪表盘
    navigateToPage('dashboard');
    showAdminTaskReminder();
    startAdminReminderPolling();
}

/**
 * 从API加载物料数据
 */
async function loadMaterialsData(params = {}) {
    try {
        const result = await API.Material.getList(params);
        if (result.success) {
            AppState.materials = result.data.items;
            AppState.materialPagination = {
                current_page: result.data.current_page || 1,
                per_page: result.data.per_page || AppState.materials.length || 20,
                total: result.data.total ?? AppState.materials.length,
                pages: result.data.pages || 1
            };
            updateMaterialsTable();
            updateDashboardStats();
            updateStockMaterialSelects();
            updateBorrowMaterialSelect();
        }
    } catch (error) {
        console.error('加载物料数据失败:', error);
    }
}

/**
 * 从API加载分类数据
 */
async function loadCategoriesData() {
    try {
        const result = await API.Material.getCategories();
        if (result.success) {
            AppState.categories = result.data;
            updateCategorySelects();
            updateMaterialCategoryFilter();
        }
    } catch (error) {
        console.error('加载分类数据失败:', error);
    }
}

/**
 * 从API加载用户数据
 */
async function loadUsersData() {
    try {
        if (!isAdmin()) return;
        const params = {};
        const keyword = document.getElementById('user-search')?.value.trim();
        const role = document.getElementById('user-role-filter')?.value;
        if (keyword) params.keyword = keyword;
        if (role) params.role = role;

        const result = await API.User.getList(params);
        if (result.success) {
            AppState.users = result.data.items;
            updateUsersTable();
        }
    } catch (error) {
        console.error('加载用户数据失败:', error);
    }
}

/**
 * 更新分类下拉框
 */
function updateCategorySelects() {
    const selects = document.querySelectorAll('.category-select');
    selects.forEach(select => {
        // 保留第一个选项
        const firstOption = select.options[0];
        select.innerHTML = '';
        select.appendChild(firstOption);
        
        // 添加分类选项
        if (AppState.categories) {
            AppState.categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.id;
                option.textContent = cat.name;
                select.appendChild(option);
            });
        }
    });
}

function updateMaterialCategoryFilter() {
    const select = document.getElementById('material-category-filter');
    if (!select || !AppState.categories) return;
    const currentValue = select.value;
    select.innerHTML = '<option value="">所有分类</option>';
    AppState.categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = cat.name;
        select.appendChild(option);
    });
    select.value = currentValue;
}

async function applyMaterialFilters() {
    await loadMaterialsPage(1);
}

function getMaterialFilterParams(page = AppState.materialPagination?.current_page || 1) {
    const keyword = document.getElementById('material-search')?.value.trim();
    const categoryId = document.getElementById('material-category-filter')?.value;
    const status = document.getElementById('material-status-filter')?.value;
    const params = { page };
    if (keyword) params.keyword = keyword;
    if (categoryId) params.category_id = categoryId;
    if (status) params.status = status;
    return params;
}

async function loadMaterialsPage(page) {
    await loadMaterialsData(getMaterialFilterParams(page));
}

/**
 * 退出登录 - 连接后端API
 */
async function logout() {
    try {
        await API.Auth.logout();
    } catch (e) {
        console.log('退出登录');
    }

    if (AppState.reminderTimer) {
        clearInterval(AppState.reminderTimer);
        AppState.reminderTimer = null;
    }
    
    AppState.currentUser = null;
    AppState.currentRole = null;
    AppState.currentUserData = null;
    
    localStorage.removeItem('labInventory_token');
    localStorage.removeItem('labInventory_role');
    
    document.getElementById('main-app').classList.remove('active');
    document.getElementById('login-page').classList.add('active');
    
    // 重置表单
    document.getElementById('login-form').reset();
}

function handleSessionExpired() {
    if (AppState.reminderTimer) {
        clearInterval(AppState.reminderTimer);
        AppState.reminderTimer = null;
    }

    AppState.currentUser = null;
    AppState.currentRole = null;
    AppState.currentUserData = null;
    document.getElementById('main-app').classList.remove('active');
    document.getElementById('login-page').classList.add('active');
    document.getElementById('login-form').reset();
}

window.addEventListener('auth:expired', handleSessionExpired);

/**
 * 初始化导航
 */
function initNavigation() {
    // 侧边栏导航
    const navItems = document.querySelectorAll('.sidebar-nav li');
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.dataset.page;
            if (page) {
                navigateToPage(page);
            }
        });
    });
    
    // 退出按钮
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
    
    // 移动端菜单切换
    const menuToggle = document.querySelector('.menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            document.querySelector('.sidebar').classList.toggle('open');
        });
    }
}

/**
 * 页面导航
 */
function navigateToPage(pageName) {
    // 更新侧边栏激活状态
    document.querySelectorAll('.sidebar-nav li').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageName) {
            item.classList.add('active');
        }
    });
    
    // 隐藏所有页面
    document.querySelectorAll('.content-page').forEach(page => {
        page.classList.remove('active');
    });
    
    // 显示目标页面
    const targetPage = document.getElementById(pageName + '-page');
    if (targetPage) {
        targetPage.classList.add('active');
    }
    
    AppState.currentPage = pageName;
    
    // 关闭移动端侧边栏
    document.querySelector('.sidebar').classList.remove('open');
    
    // 页面特定的初始化
    if (pageName === 'dashboard') {
        updateDashboardStats();
    } else if (pageName === 'purchase') {
        loadPurchaseData();
    } else if (pageName === 'borrow') {
        loadBorrowData();
    } else if (pageName === 'history') {
        loadHistoryData();
    } else if (pageName === 'inout') {
        loadPurchaseData();
        loadBorrowData();
        loadInventoryRecords();
    } else if (pageName === 'alerts') {
        loadAlertsData();
    } else if (pageName === 'users') {
        if (isAdmin()) loadUsersData();
    } else if (pageName === 'settings') {
        if (isAdmin()) loadSettingsData();
    }
}

/**
 * 初始化标签页
 */
function initTabs() {
    document.querySelectorAll('.tabs').forEach(tabContainer => {
        const tabBtns = tabContainer.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                // 移除所有激活状态
                tabBtns.forEach(b => b.classList.remove('active'));
                // 激活当前标签
                this.classList.add('active');
                
                // 可以在这里添加切换内容的逻辑
                const tabName = this.dataset.tab;
                handleTabSwitch(tabName);
            });
        });
    });
}

function handleTabSwitch(tabName) {
    if (['inout-records', 'pending-in', 'pending-out'].includes(tabName)) {
        AppState.activeInoutTab = tabName;
        updateInventoryRecordsTable();
        return;
    }

    if (['borrow-all', 'borrow-active', 'borrow-returned', 'borrow-overdue'].includes(tabName)) {
        AppState.activeBorrowTab = tabName;
        updateBorrowTable();
    }
}

/**
 * 初始化日期时间显示
 */
function initDateTime() {
    function updateDateTime() {
        const now = new Date();
        const dateStr = now.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            weekday: 'short'
        });
        const timeStr = now.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const dateEl = document.getElementById('current-date');
        if (dateEl) {
            dateEl.textContent = `${dateStr} ${timeStr}`;
        }
    }
    
    updateDateTime();
    setInterval(updateDateTime, 1000);
}

/**
 * 初始化表单处理
 */
function initFormHandlers() {
    // 采购申请表单
    const purchaseForm = document.getElementById('purchase-form');
    if (purchaseForm) {
        purchaseForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            await handlePurchaseSubmit();
        });
    }
    const purchaseNameInput = document.getElementById('purchase-name');
    if (purchaseNameInput) {
        purchaseNameInput.addEventListener('input', () => {
            AppState.pendingPurchaseMaterialId = null;
        });
    }

    const searchInput = document.getElementById('material-search');
    const categoryFilter = document.getElementById('material-category-filter');
    const statusFilter = document.getElementById('material-status-filter');
    [searchInput, categoryFilter, statusFilter].forEach(el => {
        if (el) {
            el.addEventListener('input', applyMaterialFilters);
            el.addEventListener('change', applyMaterialFilters);
        }
    });

    const importInput = document.getElementById('material-import-file');
    if (importInput) {
        importInput.addEventListener('change', handleMaterialImport);
    }

    const userSearch = document.getElementById('user-search');
    const userRole = document.getElementById('user-role-filter');
    [userSearch, userRole].forEach(el => {
        if (el) {
            el.addEventListener('input', loadUsersData);
            el.addEventListener('change', loadUsersData);
        }
    });

    const alertSettingsForm = document.getElementById('alert-settings-form');
    if (alertSettingsForm) {
        alertSettingsForm.addEventListener('submit', handleSettingsSubmit);
    }

    const dataSettingsForm = document.getElementById('data-settings-form');
    if (dataSettingsForm) {
        dataSettingsForm.addEventListener('submit', handleSettingsSubmit);
    }

    const backupButton = document.getElementById('backup-now-btn');
    if (backupButton) {
        backupButton.addEventListener('click', handleBackupNow);
    }

    const borrowRequiresReturn = document.getElementById('borrow-requires-return');
    if (borrowRequiresReturn) {
        borrowRequiresReturn.addEventListener('change', updateBorrowReturnDateVisibility);
        updateBorrowReturnDateVisibility();
    }
}

function updateBorrowReturnDateVisibility() {
    const requiresReturn = document.getElementById('borrow-requires-return')?.value !== 'false';
    const group = document.getElementById('borrow-return-date-group');
    const input = document.getElementById('borrow-return-date');
    if (!group || !input) return;

    group.style.display = requiresReturn ? '' : 'none';
    input.required = requiresReturn;
    if (!requiresReturn) input.value = '';
}

/**
 * 处理采购申请提交
 */
async function handlePurchaseSubmit() {
    const name = document.getElementById('purchase-name').value;
    const categoryId = document.getElementById('purchase-category').value;
    const spec = document.getElementById('purchase-spec').value;
    const quantity = parseInt(document.getElementById('purchase-quantity').value);
    const supplierUrl = document.getElementById('purchase-url').value;
    const estimatedPrice = parseFloat(document.getElementById('purchase-price').value) || 0;
    const reason = document.getElementById('purchase-reason').value;
    const remark = document.getElementById('purchase-remark').value;

    if (!name || !quantity || !reason) {
        showNotification('错误', '请填写必填项', 'error');
        return;
    }

    try {
        const result = await API.Purchase.create({
            material_id: AppState.pendingPurchaseMaterialId,
            material_name: name,
            category_id: categoryId ? parseInt(categoryId) : null,
            spec: spec,
            quantity: quantity,
            supplier_link: supplierUrl,
            estimated_price: estimatedPrice,
            reason: reason,
            remark: remark
        });

        if (result.success) {
            showNotification('成功', '采购申请已提交，等待管理员审批', 'success');
            document.getElementById('purchase-form').reset();
            AppState.pendingPurchaseMaterialId = null;
            // 刷新采购列表
            await loadPurchaseData();
        } else {
            showNotification('失败', result.message || '提交失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 加载采购数据
 */
async function loadPurchaseData() {
    try {
        const result = await API.Purchase.getList(isVisitor() ? { my: true } : {});
        if (result.success) {
            AppState.purchases = result.data.items;
            updatePurchaseTable();
            updatePurchaseTrend();
            updateAlertList();
        }
    } catch (error) {
        console.error('加载采购数据失败:', error);
    }
}

async function loadPurchaseSummary() {
    if (!isAdmin() || !API.Purchase?.summary) return;
    try {
        const result = await API.Purchase.summary();
        if (result.success) {
            AppState.purchaseSummary = result.data;
            updateAlertBadges();
            updateAlertList();
        }
    } catch (error) {
        console.error('加载采购提醒失败:', error);
    }
}

async function loadBorrowSummary() {
    if (!isAdmin() || !API.Borrow?.summary) return;
    try {
        const result = await API.Borrow.summary();
        if (result.success) {
            AppState.borrowSummary = result.data;
            updateAlertBadges();
            updateAlertList();
        }
    } catch (error) {
        console.error('加载借用提醒失败:', error);
    }
}

function showAdminTaskReminder() {
    if (!isAdmin()) return;
    const purchase = AppState.purchaseSummary || {};
    const borrow = AppState.borrowSummary || {};
    const pendingPurchase = purchase.pending || 0;
    const approvedPurchase = purchase.approved || 0;
    const pendingBorrow = borrow.pending || 0;
    if (pendingPurchase === 0 && approvedPurchase === 0 && pendingBorrow === 0) return;

    const key = `taskReminder:${pendingPurchase}:${approvedPurchase}:${pendingBorrow}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, 'shown');

    const parts = [];
    if (pendingPurchase) parts.push(`${pendingPurchase} 条采购申请待审批`);
    if (approvedPurchase) parts.push(`${approvedPurchase} 条采购申请待入库`);
    if (pendingBorrow) parts.push(`${pendingBorrow} 条借用申请待审批`);
    showNotification('待办提醒', parts.join('，'), 'warning');
}

function startAdminReminderPolling() {
    if (!isAdmin() || AppState.reminderTimer) return;
    AppState.lastPurchasePending = AppState.purchaseSummary?.pending || 0;
    AppState.lastBorrowPending = AppState.borrowSummary?.pending || 0;

    AppState.reminderTimer = setInterval(async () => {
        if (!isAdmin()) return;
        const previousPurchase = AppState.lastPurchasePending;
        const previousBorrow = AppState.lastBorrowPending;
        await loadPurchaseSummary();
        await loadBorrowSummary();

        const currentPurchase = AppState.purchaseSummary?.pending || 0;
        const currentBorrow = AppState.borrowSummary?.pending || 0;
        if (currentPurchase > previousPurchase) {
            showNotification('采购申请提醒', `新增 ${currentPurchase - previousPurchase} 条采购申请待审批`, 'warning');
        }
        if (currentBorrow > previousBorrow) {
            showNotification('借用申请提醒', `新增 ${currentBorrow - previousBorrow} 条借用申请待审批`, 'warning');
        }
        AppState.lastPurchasePending = currentPurchase;
        AppState.lastBorrowPending = currentBorrow;
    }, 30000);
}

/**
 * 更新采购申请表格
 */
function updatePurchaseTable() {
    const tbody = document.querySelector('#purchase-page tbody');
    if (!tbody || !AppState.purchases) return;

    if (AppState.purchases.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">暂无申请记录</td></tr>';
        return;
    }

    tbody.innerHTML = AppState.purchases.map(p => `
        <tr>
            <td>${p.request_no}</td>
            <td>${p.material_name}</td>
            <td>${p.quantity}</td>
            <td>${p.created_at}</td>
            <td><span class="status ${p.status}">${getPurchaseStatusText(p.status)}</span></td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="viewPurchase(${p.id})">查看</button>
                ${p.supplier_link ? `<button class="btn btn-sm btn-primary" onclick="openPurchaseLink(${p.id})">采购链接</button>` : ''}
                ${p.status === 'pending' && p.user_id === AppState.currentUserData?.id ? `<button class="btn btn-sm btn-danger" onclick="cancelPurchase(${p.id})">取消</button>` : ''}
                ${isAdmin() && p.status === 'pending' ? `<button class="btn btn-sm btn-success" onclick="approvePurchase(${p.id}, 'approve')">批准</button><button class="btn btn-sm btn-danger" onclick="approvePurchase(${p.id}, 'reject')">拒绝</button>` : ''}
                ${isAdmin() && p.status === 'approved' ? `<button class="btn btn-sm btn-success" onclick="completePurchase(${p.id})">入库</button>` : ''}
            </td>
        </tr>
    `).join('');
}

/**
 * 获取采购状态文本
 */
function getPurchaseStatusText(status) {
    const statusMap = {
        'pending': '待审批',
        'approved': '待入库',
        'rejected': '已拒绝',
        'cancelled': '已取消',
        'completed': '已完成'
    };
    return statusMap[status] || status;
}

/**
 * 取消采购申请
 */
async function cancelPurchase(id) {
    if (!confirm('确定要取消该采购申请吗？')) return;

    try {
        const result = await API.Purchase.cancel(id);
        if (result.success) {
            showNotification('成功', '采购申请已取消', 'success');
            await loadPurchaseData();
        } else {
            showNotification('失败', result.message || '取消失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

function viewPurchase(id) {
    const item = AppState.purchases?.find(p => p.id === id)
        || AppState.purchaseSummary?.latest?.find(p => p.id === id);
    if (!item) return;
    const category = AppState.categories?.find(c => Number(c.id) === Number(item.category_id));
    const details = [
        `申请单号：${item.request_no}`,
        `状态：${getPurchaseStatusText(item.status)}`,
        `申请人：${item.requester_name || '-'}`,
        `物料名称：${item.material_name || '-'}`,
        `物料分类：${category?.name || item.category_name || '-'}`,
        `规格：${item.spec || '-'}`,
        `数量：${item.quantity || '-'}`,
        `预计单价：${item.estimated_price ?? '-'}`,
        `采购链接：${item.supplier_link || '-'}`,
        `申请理由：${item.reason || '-'}`,
        `备注：${item.remark || '-'}`,
        `审批备注：${item.approval_remark || '-'}`,
        `提交时间：${item.created_at || '-'}`
    ].join('\n');
    alert(details);
}

function openPurchaseLink(id) {
    const item = AppState.purchases?.find(p => p.id === id);
    if (!item?.supplier_link) {
        showNotification('提示', '该申请没有填写采购链接', 'info');
        return;
    }
    const url = /^https?:\/\//i.test(item.supplier_link) ? item.supplier_link : `https://${item.supplier_link}`;
    window.open(url, '_blank', 'noopener');
}

async function approvePurchase(id, action) {
    if (!requireAdminAction()) return;
    try {
        const result = await API.Purchase.approve(id, { action, remark: '' });
        if (result.success) {
            showNotification('成功', '采购申请已处理', 'success');
            await loadPurchaseData();
            await loadPurchaseSummary();
        } else {
            showNotification('失败', result.message || '处理失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

async function completePurchase(id) {
    if (!requireAdminAction()) return;
    const item = AppState.purchases?.find(p => p.id === id);
    const defaultQuantity = item?.quantity || 1;
    const input = prompt('请输入实际入库数量', defaultQuantity);
    if (input === null) return;

    const actualQuantity = parseInt(input, 10);
    if (!actualQuantity || actualQuantity <= 0) {
        showNotification('错误', '入库数量必须大于0', 'error');
        return;
    }

    try {
        const result = await API.Purchase.complete(id, { actual_quantity: actualQuantity });
        if (result.success) {
            showNotification('成功', '采购单已入库，库存和预警已同步', 'success');
            await loadPurchaseData();
            await loadPurchaseSummary();
            await loadMaterialsData();
            await loadInventoryRecords();
            await loadHistoryData();
            await loadAlertsData();
        } else {
            showNotification('失败', result.message || '入库失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 更新仪表盘统计数据
 */
function updateDashboardStats() {
    // 这里可以添加从后端获取数据的逻辑
    // 目前使用模拟数据
    console.log('更新仪表盘数据');
}

/**
 * 显示模态框
 */
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById('modal-overlay');
    
    if (modal && overlay) {
        if (modalId === 'add-material-modal' && !AppState.editingMaterialId) {
            document.getElementById('material-form')?.reset();
        }
        if (modalId === 'add-user-modal' && !AppState.editingUserId) {
            document.getElementById('user-form')?.reset();
            const username = document.getElementById('user-username');
            if (username) username.disabled = false;
        }
        modal.classList.add('active');
        overlay.classList.add('active');
    }
}

/**
 * 关闭所有模态框
 */
function closeAllModals() {
    AppState.editingMaterialId = null;
    AppState.editingUserId = null;
    const username = document.getElementById('user-username');
    if (username) username.disabled = false;
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('active');
    });
    document.getElementById('modal-overlay').classList.remove('active');
}

/**
 * 显示通知
 */
function showNotification(title, message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <strong>${title}</strong>
            <p>${message}</p>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    // 添加样式
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 15px;
        min-width: 300px;
        animation: slideIn 0.3s ease;
    `;
    
    // 添加动画样式
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        .notification-close {
            background: none;
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            opacity: 0.8;
        }
        .notification-close:hover { opacity: 1; }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(notification);
    
    // 3秒后自动消失
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * 搜索物料
 */
function searchMaterials(query) {
    const keyword = (query || '').trim().toLowerCase();
    return (AppState.materials || []).filter(m =>
        String(m.name || '').toLowerCase().includes(keyword) ||
        String(m.code || '').toLowerCase().includes(keyword) ||
        String(m.spec || '').toLowerCase().includes(keyword)
    );
}

/**
 * 添加新物料
 */
function addMaterial(materialData) {
    showNotification('提示', '请通过新增物料表单保存到后端数据库', 'info');
    return materialData;
}

/**
 * 更新物料库存
 */
function updateStock(materialId, quantity, type) {
    const material = (AppState.materials || []).find(m => m.id === materialId);
    if (material) {
        if (type === 'in') {
            material.stock += quantity;
        } else if (type === 'out') {
            material.stock -= quantity;
        }
        
        // 更新状态
        if (material.stock <= 0) {
            material.status = 'danger';
        } else if (material.stock <= material.threshold) {
            material.status = 'warning';
        } else {
            material.status = 'normal';
        }
        
        showNotification('操作成功', `物料 "${material.name}" 库存已更新`, 'success');
        return material;
    }
    return null;
}

/**
 * 检查库存预警
 */
function checkStockAlerts() {
    const alerts = (AppState.materials || []).filter(m => m.stock <= m.threshold);
    if (alerts.length > 0) {
        console.log('发现库存预警:', alerts);
        // 这里可以触发邮件通知
    }
    return alerts;
}

/**
 * 导出 Excel 数据
 */
async function exportData(dataType = 'all') {
    if (typeof XLSX === 'undefined') {
        showNotification('导出失败', 'Excel组件未加载，请刷新页面后重试', 'error');
        return;
    }

    try {
        const [materials, inventory, purchases, borrows] = await Promise.all([
            API.Material.getList({ per_page: 10000 }),
            API.Record.getList('inventory', { per_page: 10000 }),
            API.Record.getList('purchase', { per_page: 10000 }),
            API.Record.getList('borrow', { per_page: 10000 })
        ]);

        const workbook = XLSX.utils.book_new();
        const addSheet = (name, rows) => {
            const sheet = XLSX.utils.json_to_sheet(rows);
            XLSX.utils.book_append_sheet(workbook, sheet, name);
        };

        if (dataType === 'all' || dataType === 'materials') {
            addSheet('库存管理', (materials.data?.items || []).map(m => ({
                物料编号: m.code,
                物料名称: m.name,
                分类: m.category_name || '',
                规格: m.spec || '',
                库存数量: m.stock,
                单位: m.unit,
                预警阈值: m.threshold,
                存放位置: m.location || '',
                状态: getStatusText(m.status),
                备注: m.remark || '',
                创建时间: m.created_at || ''
            })));
        }

        if (dataType === 'all' || dataType === 'history') {
            addSheet('出入库记录', (inventory.data?.items || []).map(r => ({
                操作单号: r.operation_no,
                类型: r.type_name || r.type,
                物料名称: r.material_name || '',
                数量: r.quantity,
                操作前库存: r.stock_before,
                操作后库存: r.stock_after,
                操作人: r.operator_name || '',
                关联类型: r.related_type || '',
                关联ID: r.related_id || '',
                备注: r.remark || '',
                时间: r.created_at || ''
            })));
            addSheet('采购申请', (purchases.data?.items || []).map(p => ({
                申请单号: p.request_no,
                申请人: p.requester_name || '',
                物料名称: p.material_name || '',
                分类ID: p.category_id || '',
                规格: p.spec || '',
                数量: p.quantity,
                预计单价: p.estimated_price ?? '',
                采购链接: p.supplier_link || '',
                申请理由: p.reason || '',
                备注: p.remark || '',
                状态: getPurchaseStatusText(p.status),
                审批人: p.approver_name || '',
                审批备注: p.approval_remark || '',
                审批时间: p.approved_at || '',
                提交时间: p.created_at || ''
            })));
            addSheet('借用记录', (borrows.data?.items || []).map(b => ({
                借用单号: b.borrow_no,
                借用人: b.borrower_name || '',
                物料名称: b.material_name || '',
                数量: b.quantity,
                借用理由: b.reason || '',
                状态: getBorrowStatusText(b.status),
                借用时间: b.borrow_date || '',
                预计归还: b.expected_return_date || '',
                实际归还: b.actual_return_date || ''
            })));
        }

        const timestamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '');
        const filename = dataType === 'materials'
            ? `库存管理_${timestamp}.xlsx`
            : `实验室库存完整记录_${timestamp}.xlsx`;
        XLSX.writeFile(workbook, filename);
        showNotification('导出成功', `已导出 ${filename}`, 'success');
    } catch (error) {
        showNotification('导出失败', error.message || '无法导出Excel', 'error');
    }
}

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    // ESC 关闭模态框
    if (e.key === 'Escape') {
        closeAllModals();
    }
});

// 检查本地存储的登录状态
window.addEventListener('load', function() {
    const savedUser = localStorage.getItem('labInventory_user');
    const savedRole = localStorage.getItem('labInventory_role');
    
    if (savedUser && savedRole) {
        try {
            const user = JSON.parse(savedUser);
            AppState.currentUser = user.username;
            AppState.currentRole = savedRole;
            AppState.currentUserData = user;
            showMainApp();
        } catch (error) {
            localStorage.removeItem('labInventory_user');
            localStorage.removeItem('labInventory_role');
        }
    }
});

// 全局函数暴露（供HTML内联事件使用）
window.showModal = showModal;
window.closeAllModals = closeAllModals;
window.logout = logout;
window.navigateToPage = navigateToPage;
window.applyMaterialFilters = applyMaterialFilters;
window.loadMaterialsPage = loadMaterialsPage;
window.exportData = exportData;
window.handleMaterialSave = handleMaterialSave;
window.handleMaterialImport = handleMaterialImport;
window.deleteMaterial = deleteMaterial;
window.viewMaterial = viewMaterial;
window.handleBorrowSubmit = handleBorrowSubmit;
window.viewBorrow = viewBorrow;
window.handleUserCreate = handleUserCreate;
window.deleteUser = deleteUser;
window.viewPurchase = viewPurchase;
window.openPurchaseLink = openPurchaseLink;
window.approvePurchase = approvePurchase;
window.completePurchase = completePurchase;
window.approveBorrow = approveBorrow;

/**
 * 更新物料表格
 */
function updateMaterialsTable() {
    const tbody = document.querySelector('#inventory-page tbody');
    if (!tbody || !AppState.materials) return;

    updateInventoryStatusBar();
    updateInventoryPagination();

    if (AppState.materials.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center">暂无在库样品/物料</td></tr>';
        return;
    }
    
    tbody.innerHTML = AppState.materials.map(m => `
        <tr>
            <td></td>
            <td>${m.code}</td>
            <td>${m.name}</td>
            <td>${m.category_name || '-'}</td>
            <td>${m.spec || '-'}</td>
            <td>${m.stock} ${m.unit}</td>
            <td>${m.threshold} ${m.unit}</td>
            <td>${m.location || '-'}</td>
            <td><span class="status-badge ${m.status}">${getStatusText(m.status)}</span></td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="viewMaterial(${m.id})">查看</button>
                ${isVisitor() ? `<button class="btn btn-sm btn-primary" onclick="purchaseMaterial(${m.id})">申请采购</button>` : ''}
                ${isAdmin() ? `<button class="btn btn-sm btn-primary" onclick="editMaterial(${m.id})">编辑</button><button class="btn btn-sm btn-success" onclick="stockIn(${m.id})">入库</button><button class="btn btn-sm btn-warning" onclick="stockOut(${m.id})">出库</button><button class="btn btn-sm btn-danger" onclick="deleteMaterial(${m.id})">删除</button>` : ''}
            </td>
        </tr>
    `).join('');
}

function updateInventoryStatusBar() {
    const status = document.querySelector('#inventory-page .pagination > span');
    if (!status) return;
    const pageInfo = AppState.materialPagination || {};
    const total = Number(pageInfo.total ?? AppState.materials?.length ?? 0);
    const page = Math.max(Number(pageInfo.current_page || 1), 1);
    const perPage = Math.max(Number(pageInfo.per_page || AppState.materials?.length || 20), 1);
    const currentCount = AppState.materials?.length || 0;
    const start = total === 0 ? 0 : ((page - 1) * perPage) + 1;
    const end = total === 0 ? 0 : Math.min(start + currentCount - 1, total);
    status.textContent = `显示 ${start}-${end} 条，共 ${total} 条`;
}

function updateInventoryPagination() {
    const nav = document.querySelector('#inventory-page .pagination .page-nav');
    if (!nav) return;

    const pageInfo = AppState.materialPagination || {};
    const total = Number(pageInfo.total || 0);
    const current = Math.max(Number(pageInfo.current_page || 1), 1);
    const pages = Math.max(Number(pageInfo.pages || 1), 1);

    if (total <= 0 || pages <= 1) {
        nav.innerHTML = '';
        return;
    }

    const pageButtons = new Set([1, pages, current, current - 1, current + 1]);
    const visiblePages = [...pageButtons]
        .filter(page => page >= 1 && page <= pages)
        .sort((a, b) => a - b);

    const parts = [
        `<button ${current <= 1 ? 'disabled' : ''} onclick="loadMaterialsPage(${current - 1})"><i class="fas fa-chevron-left"></i></button>`
    ];

    let previous = 0;
    visiblePages.forEach(page => {
        if (previous && page - previous > 1) {
            parts.push('<span>...</span>');
        }
        parts.push(`<button class="${page === current ? 'active' : ''}" onclick="loadMaterialsPage(${page})">${page}</button>`);
        previous = page;
    });

    parts.push(`<button ${current >= pages ? 'disabled' : ''} onclick="loadMaterialsPage(${current + 1})"><i class="fas fa-chevron-right"></i></button>`);
    nav.innerHTML = parts.join('');
}

/**
 * 更新用户表格
 */
function updateUsersTable() {
    const tbody = document.querySelector('#users-page tbody');
    if (!tbody || !AppState.users) return;
    
    tbody.innerHTML = AppState.users.map(u => `
        <tr>
            <td></td>
            <td>U${String(u.id).padStart(3, '0')}</td>
            <td>${u.username}</td>
            <td>${u.name}</td>
            <td><span class="role-badge ${u.role}">${u.role === 'admin' ? '管理员' : '访问者'}</span></td>
            <td>${u.department || '-'}</td>
            <td>${u.phone || '-'}</td>
            <td><span class="status-badge ${u.is_active ? 'normal' : 'danger'}">${u.is_active ? '启用' : '禁用'}</span></td>
            <td>${u.created_at || '-'}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="editUser(${u.id})">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id})">删除</button>
            </td>
        </tr>
    `).join('');
}

/**
 * 获取状态文本
 */
function getStatusText(status) {
    const statusMap = {
        'normal': '正常',
        'warning': '预警',
        'danger': '危险',
        'completed': '已完成',
        'pending': '待处理',
        'cancelled': '已取消'
    };
    return statusMap[status] || status;
}

/**
 * 更新仪表盘统计
 */
function updateDashboardStats() {
    if (!AppState.materials) return;
    
    const totalMaterials = AppState.materials.length;
    const warningCount = AppState.materials.filter(m => m.status === 'warning').length;
    const dangerCount = AppState.materials.filter(m => m.status === 'danger').length;
    const normalCount = AppState.materials.filter(m => m.status === 'normal').length;
    
    // 更新统计卡片
    const statValues = document.querySelectorAll('#dashboard-page .stats-grid .stat-info h3');
    if (statValues.length >= 4) {
        statValues[0].textContent = totalMaterials;
        statValues[1].textContent = normalCount;
        statValues[2].textContent = warningCount;
        statValues[3].textContent = dangerCount;
    }
    
    // 更新预警列表
    updateAlertList();
    updateRecentActivityTable();
    updateInventoryTrend();
    updatePurchaseTrend();
    updateAlertBadges();
}

/**
 * 更新预警列表
 */
function updateAlertList() {
    const alertList = document.querySelector('.alert-list');
    if (!alertList || !AppState.materials) return;
    
    const alerts = AppState.materials.filter(m => m.status === 'warning' || m.status === 'danger');
    const purchaseTasks = isAdmin() ? (AppState.purchaseSummary?.latest || []) : [];
    const borrowTasks = isAdmin() ? (AppState.borrowSummary?.latest || []) : [];
    
    if (alerts.length === 0 && purchaseTasks.length === 0 && borrowTasks.length === 0) {
        alertList.innerHTML = '<p class="no-data">暂无库存预警</p>';
        return;
    }

    const alertHtml = alerts.map(m => `
        <div class="alert-item ${m.status}">
            <div class="alert-info">
                <strong>${m.name}</strong>
                <span>当前库存: ${m.stock} ${m.unit} / 预警阈值: ${m.threshold} ${m.unit}</span>
            </div>
            <button class="btn btn-sm btn-primary" onclick="purchaseMaterial(${m.id})">申请采购</button>
        </div>
    `).join('');

    const purchaseHtml = purchaseTasks.map(p => `
        <div class="alert-item warning">
            <div class="alert-info">
                <strong>${p.material_name}</strong>
                <span>${p.request_no}：${getPurchaseStatusText(p.status)}，数量 ${p.quantity}</span>
            </div>
            <button class="btn btn-sm btn-primary" onclick="navigateToPage('purchase')">${p.status === 'approved' ? '去入库' : '去审批'}</button>
        </div>
    `).join('');

    const borrowHtml = borrowTasks.map(b => `
        <div class="alert-item warning">
            <div class="alert-info">
                <strong>${b.material_name}</strong>
                <span>${b.borrow_no}：借用申请待审批，数量 ${b.quantity}</span>
            </div>
            <button class="btn btn-sm btn-primary" onclick="navigateToPage('borrow')">去审批</button>
        </div>
    `).join('');

    alertList.innerHTML = borrowHtml + purchaseHtml + alertHtml;
}

function updateAlertBadges() {
    const alertCount = AppState.alerts || [];
    const purchaseCount = AppState.purchaseSummary?.total_attention || 0;
    const borrowCount = AppState.borrowSummary?.total_attention || 0;
    const stockAlertCount = isAdmin() ? alertCount.length : 0;
    const totalTaskCount = isAdmin() ? stockAlertCount + purchaseCount + borrowCount : 0;

    const navBadge = document.getElementById('nav-alert-badge');
    if (navBadge) {
        navBadge.textContent = stockAlertCount;
        navBadge.style.display = stockAlertCount > 0 ? '' : 'none';
    }

    const headerBadge = document.getElementById('header-alert-badge');
    if (headerBadge) {
        headerBadge.textContent = totalTaskCount;
        headerBadge.style.display = totalTaskCount > 0 ? '' : 'none';
    }
}

function updateInventoryTrend() {
    const container = document.getElementById('inventory-trend-chart');
    if (!container) return;

    const currentStock = (AppState.materials || []).reduce((sum, m) => sum + Number(m.stock || 0), 0);
    const sourceRecords = (AppState.records || AppState.inventoryRecords || [])
        .slice()
        .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
        .filter(r => typeof r.quantity !== 'undefined')
        .slice(0, 8);

    let runningTotal = currentStock;
    const records = sourceRecords.map(r => {
        const point = {
            label: formatTrendLabel(r.created_at),
            value: runningTotal,
            detail: `${r.material_name || '-'} / ${r.type_name || r.type || ''}`
        };
        runningTotal -= Number(r.quantity || 0);
        return point;
    }).reverse();

    if (records.length === 0) {
        renderTrendChart(container, {
            title: '系统总库存',
            series: [{
                name: '总库存',
                color: '#2563eb',
                values: [{ label: '当前', value: currentStock, detail: '当前库存总量' }]
            }],
            footer: 'X：时间 / Y：系统总库存'
        });
        return;
    }

    renderTrendChart(container, {
        title: '系统总库存',
        series: [{
            name: '总库存',
            color: '#2563eb',
            values: records
        }],
        footer: 'X：出入库时间 / Y：系统总库存'
    });
}

function updatePurchaseTrend() {
    const container = document.getElementById('purchase-trend-chart');
    if (!container) return;

    const purchases = (AppState.purchases || []).slice().reverse().slice(-8);
    if (purchases.length === 0) {
        renderTrendEmpty(container, '暂无采购趋势数据', '提交采购申请后自动生成趋势');
        return;
    }

    const quantitySeries = purchases.map(p => ({
        label: formatTrendLabel(p.created_at),
        value: Number(p.quantity || 0),
        detail: p.material_name || '-'
    }));
    const amountSeries = purchases.map(p => {
        const amount = Number(p.quantity || 0) * Number(p.estimated_price || 0);
        return {
            label: formatTrendLabel(p.created_at),
            value: amount,
            displayValue: `¥${formatMoney(amount)}`,
            detail: p.material_name || '-'
        };
    });

    renderTrendChart(container, {
        title: '采购数量 / 预计金额',
        series: [
            { name: '数量', color: '#16a34a', values: quantitySeries },
            { name: '金额', color: '#f59e0b', values: amountSeries }
        ],
        footer: `合计数量：${quantitySeries.reduce((sum, p) => sum + p.value, 0)} / 合计金额：¥${formatMoney(amountSeries.reduce((sum, p) => sum + p.value, 0))}`
    });
}

function renderTrendEmpty(container, message, meta) {
    container.innerHTML = `
        <div class="trend-empty">
            <i class="fas fa-chart-line"></i>
            <span>${message}</span>
            <small>${meta}</small>
        </div>
    `;
}

function renderTrendChart(container, config) {
    const allValues = config.series.flatMap(series => series.values.map(point => Number(point.value || 0)));
    const maxValue = Math.max(...allValues, 1);
    const minValue = Math.min(...allValues, 0);
    const range = Math.max(maxValue - minValue, 1);
    const width = 520;
    const height = 210;
    const padding = { top: 28, right: 24, bottom: 46, left: 48 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const labels = config.series[0]?.values.map(point => point.label) || [];
    const xFor = index => padding.left + (labels.length <= 1 ? chartWidth / 2 : (index / (labels.length - 1)) * chartWidth);
    const yFor = value => padding.top + chartHeight - ((Number(value || 0) - minValue) / range) * chartHeight;
    const ticks = [maxValue, Math.round((maxValue + minValue) / 2), minValue];

    const seriesSvg = config.series.map(series => {
        const points = series.values.map((point, index) => `${xFor(index)},${yFor(point.value)}`).join(' ');
        const markers = series.values.map((point, index) => {
            const x = xFor(index);
            const y = yFor(point.value);
            const label = point.displayValue || point.value;
            return `
                <g class="trend-marker">
                    <circle cx="${x}" cy="${y}" r="4" fill="${series.color}"></circle>
                    <text x="${x}" y="${Math.max(14, y - 9)}" text-anchor="middle">${label}</text>
                </g>
            `;
        }).join('');
        return `
            <polyline class="trend-line" points="${points}" fill="none" stroke="${series.color}" />
            ${markers}
        `;
    }).join('');

    container.innerHTML = `
        <div class="trend-chart-heading">
            <span>${config.title}</span>
            <div class="trend-legend">
                ${config.series.map(series => `<span><i style="background:${series.color}"></i>${series.name}</span>`).join('')}
            </div>
        </div>
        <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img">
            <line class="trend-axis" x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}"></line>
            <line class="trend-axis" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
            ${ticks.map(tick => `
                <line class="trend-grid-line" x1="${padding.left}" y1="${yFor(tick)}" x2="${width - padding.right}" y2="${yFor(tick)}"></line>
                <text class="trend-y-label" x="${padding.left - 8}" y="${yFor(tick) + 4}" text-anchor="end">${tick}</text>
            `).join('')}
            ${seriesSvg}
            ${labels.map((label, index) => `<text class="trend-x-label" x="${xFor(index)}" y="${height - 18}" text-anchor="middle">${label}</text>`).join('')}
        </svg>
        <div class="chart-axis-labels">
            <span>${config.footer}</span>
        </div>
    `;
}

function formatMoney(value) {
    return Number(value || 0).toLocaleString('zh-CN', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    });
}

function formatTrendLabel(value) {
    if (!value) return '-';
    const parts = String(value).split(' ');
    return parts.length > 1 ? parts[1].slice(0, 5) : parts[0].slice(5);
}

function viewMaterial(id) {
    const material = AppState.materials?.find(m => m.id === id);
    if (!material) return;
    showNotification('物料详情', `${material.name}，库存 ${material.stock}${material.unit}，预警阈值 ${material.threshold}${material.unit}`, 'info');
}

async function handleMaterialSave() {
    if (typeof event !== 'undefined') event.preventDefault();
    if (!requireAdminAction()) return;

    const payload = {
        code: document.getElementById('material-code').value.trim() || undefined,
        name: document.getElementById('material-name').value.trim(),
        category_id: parseInt(document.getElementById('material-category').value),
        spec: document.getElementById('material-spec').value.trim(),
        stock: parseInt(document.getElementById('material-stock').value || '0'),
        threshold: parseInt(document.getElementById('material-threshold').value || '10'),
        unit: document.getElementById('material-unit').value.trim() || '个',
        location: document.getElementById('material-location').value.trim(),
        remark: document.getElementById('material-remark').value.trim()
    };

    if (payload.stock < 0) {
        showNotification('错误', '库存不能为负数', 'error');
        return;
    }

    try {
        const result = AppState.editingMaterialId
            ? await API.Material.update(AppState.editingMaterialId, payload)
            : await API.Material.create(payload);
        if (result.success) {
            showNotification('成功', AppState.editingMaterialId ? '物料已更新' : '物料已新增', 'success');
            AppState.editingMaterialId = null;
            document.getElementById('material-form').reset();
            closeAllModals();
            await loadMaterialsData();
            await loadAlertsData();
        } else {
            showNotification('失败', result.message || '新增失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

async function deleteMaterial(id) {
    if (!requireAdminAction()) return;
    if (!confirm('确定要删除该物料吗？有关联记录的物料将无法删除。')) return;

    try {
        const result = await API.Material.delete(id);
        if (result.success) {
            showNotification('成功', result.message || '物料已删除', 'success');
            await loadMaterialsData();
            await loadAlertsData();
        } else {
            showNotification('失败', result.message || '删除失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

async function handleMaterialImport(event) {
    if (!requireAdminAction()) return;
    const file = event.target.files?.[0];
    if (!file) return;

    try {
        if (!window.XLSX) {
            throw new Error('Excel解析库加载失败，请检查网络后重试');
        }

        const buffer = await file.arrayBuffer();
        const workbook = XLSX.read(buffer, { type: 'array' });
        const sheet = workbook.Sheets[workbook.SheetNames[0]];
        const rawRows = XLSX.utils.sheet_to_json(sheet, { defval: '' });
        const rows = rawRows.map(row => Object.fromEntries(
            Object.entries(row).map(([key, value]) => [
                String(key).replace(/[\s\uFEFF]/g, ''),
                value
            ])
        ));

        const valueOf = (row, aliases, fallback = '') => {
            for (const alias of aliases) {
                const value = row[alias.replace(/[\s\uFEFF]/g, '')];
                if (value !== undefined && value !== null && String(value).trim() !== '') return value;
            }
            return fallback;
        };

        const items = rows.map(row => ({
            code: valueOf(row, ['物料编号', '编号', 'code']),
            name: valueOf(row, ['物料名称', '物品名称', '名称', '物品', '产品名称', 'name']),
            category_name: valueOf(row, ['分类', '物料分类', 'category_name']),
            spec: valueOf(row, ['规格', '规格型号', 'spec']),
            stock: valueOf(row, ['数量', '库存数量', '采购数量', 'stock'], 0),
            threshold: valueOf(row, ['预警阈值', '预设阀值', '预设阈值', 'threshold'], 10),
            unit: valueOf(row, ['单位', 'unit'], '个'),
            location: valueOf(row, ['存放位置', '地区', 'location']),
            remark: valueOf(row, ['备注', 'remark']),
            purchase_date: valueOf(row, ['申购日期', '采购日期', 'purchase_date']),
            arrival_date: valueOf(row, ['采购到位日期', '到货日期', 'arrival_date'])
        }));

        const result = await API.Material.import(items);
        if (result.success) {
            showNotification('导入完成', result.message, 'success');
            await loadCategoriesData();
            await loadMaterialsData();
        } else {
            showNotification('导入失败', result.message || '导入失败', 'error');
        }
    } catch (error) {
        showNotification('导入失败', error.message || '文件解析失败', 'error');
    } finally {
        event.target.value = '';
    }
}

/**
 * 编辑物料
 */
function editMaterial(id) {
    if (!requireAdminAction()) return;
    const material = AppState.materials.find(m => m.id === id);
    if (material) {
        AppState.editingMaterialId = id;
        document.getElementById('material-code').value = material.code || '';
        document.getElementById('material-name').value = material.name || '';
        document.getElementById('material-category').value = material.category_id || '';
        document.getElementById('material-spec').value = material.spec || '';
        document.getElementById('material-stock').value = material.stock || 0;
        document.getElementById('material-threshold').value = material.threshold || 10;
        document.getElementById('material-unit').value = material.unit || '个';
        document.getElementById('material-location').value = material.location || '';
        document.getElementById('material-remark').value = material.remark || '';
        showModal('add-material-modal');
    }
}

/**
 * 入库操作 - 打开入库模态框
 */
function stockIn(id) {
    if (!requireAdminAction()) return;
    const material = AppState.materials.find(m => m.id === id);
    if (material) {
        // 更新物料选择下拉框
        updateStockMaterialSelects();
        // 设置选中的物料
        document.getElementById('stock-in-material').value = id;
        showModal('in-modal');
    }
}

/**
 * 出库操作 - 打开出库模态框
 */
function stockOut(id) {
    if (!requireAdminAction()) return;
    const material = AppState.materials.find(m => m.id === id);
    if (material) {
        // 更新物料选择下拉框
        updateStockMaterialSelects();
        // 设置选中的物料
        document.getElementById('stock-out-material').value = id;
        showModal('out-modal');
    }
}

/**
 * 更新出入库物料选择下拉框
 */
function updateStockMaterialSelects() {
    const inSelect = document.getElementById('stock-in-material');
    const outSelect = document.getElementById('stock-out-material');
    
    if (inSelect && AppState.materials) {
        const firstOption = inSelect.options[0];
        inSelect.innerHTML = '';
        inSelect.appendChild(firstOption);
        
        AppState.materials.forEach(m => {
            const option = document.createElement('option');
            option.value = m.id;
            option.textContent = `${m.name} (${m.code})`;
            inSelect.appendChild(option);
        });
    }
    
    if (outSelect && AppState.materials) {
        const firstOption = outSelect.options[0];
        outSelect.innerHTML = '';
        outSelect.appendChild(firstOption);
        
        AppState.materials.forEach(m => {
            const option = document.createElement('option');
            option.value = m.id;
            option.textContent = `${m.name} (${m.code}) - 库存: ${m.stock}${m.unit}`;
            outSelect.appendChild(option);
        });
    }
}

function updateBorrowMaterialSelect() {
    const select = document.getElementById('borrow-material');
    if (!select || !AppState.materials) return;
    const firstOption = select.options[0] || new Option('请选择设备', '');
    select.innerHTML = '';
    select.appendChild(firstOption);

    AppState.materials
        .filter(m => m.stock > 0)
        .forEach(m => {
            const option = document.createElement('option');
            option.value = m.id;
            option.textContent = `${m.name} (${m.code}) - 可借: ${m.stock}${m.unit}`;
            select.appendChild(option);
        });
}

async function handleBorrowSubmit() {
    if (typeof event !== 'undefined') event.preventDefault();
    const materialId = document.getElementById('borrow-material').value;
    const quantity = parseInt(document.getElementById('borrow-quantity').value || '1');
    const requiresReturn = document.getElementById('borrow-requires-return')?.value !== 'false';
    const expectedReturnDate = document.getElementById('borrow-return-date').value;
    const reason = document.getElementById('borrow-reason').value.trim();

    if (!materialId || !quantity || !reason || (requiresReturn && !expectedReturnDate)) {
        showNotification('错误', '请填写完整的借用申请', 'error');
        return;
    }

    try {
        const result = await API.Borrow.create({
            material_id: parseInt(materialId),
            quantity,
            requires_return: requiresReturn,
            expected_return_date: requiresReturn ? expectedReturnDate : null,
            reason
        });

        if (result.success) {
            showNotification('成功', '借用申请已提交，等待管理员审批', 'success');
            document.getElementById('borrow-form').reset();
            closeAllModals();
            await loadBorrowData();
            await loadBorrowSummary();
        } else {
            showNotification('失败', result.message || '提交失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 处理入库提交
 */
async function handleStockIn() {
    const materialId = document.getElementById('stock-in-material').value;
    const quantity = parseInt(document.getElementById('stock-in-quantity').value);
    const type = document.getElementById('stock-in-type').value;
    const remark = document.getElementById('stock-in-remark').value;
    
    if (!materialId || !quantity || quantity <= 0) {
        showNotification('错误', '请填写完整的入库信息', 'error');
        return;
    }
    
    try {
        const result = await API.Inventory.stockIn({
            material_id: parseInt(materialId),
            quantity: quantity,
            related_type: type,
            remark: remark
        });
        
        if (result.success) {
            const matched = result.data?.matched_purchase;
            showNotification('成功', matched ? `入库成功，已自动关联采购单 ${matched.request_no}` : '入库操作成功', 'success');
            closeAllModals();
            // 重置表单
            document.getElementById('stock-in-form').reset();
            // 刷新数据
            await loadMaterialsData();
            await loadInventoryRecords();
            await loadHistoryData();
            await loadAlertsData();
            await loadPurchaseData();
            await loadPurchaseSummary();
        } else {
            showNotification('失败', result.message || '入库失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 处理出库提交
 */
async function handleStockOut() {
    const materialId = document.getElementById('stock-out-material').value;
    const quantity = parseInt(document.getElementById('stock-out-quantity').value);
    const recipient = document.getElementById('stock-out-recipient').value;
    const purpose = document.getElementById('stock-out-purpose').value;
    
    if (!materialId || !quantity || quantity <= 0 || !recipient) {
        showNotification('错误', '请填写完整的出库信息', 'error');
        return;
    }
    
    try {
        const result = await API.Inventory.stockOut({
            material_id: parseInt(materialId),
            quantity: quantity,
            recipient: recipient,
            purpose: purpose,
            remark: purpose
        });
        
        if (result.success) {
            showNotification('成功', '出库操作成功', 'success');
            closeAllModals();
            // 重置表单
            document.getElementById('stock-out-form').reset();
            // 刷新数据
            await loadMaterialsData();
            await loadInventoryRecords();
            await loadHistoryData();
            await loadAlertsData();
        } else {
            showNotification('失败', result.message || '出库失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 编辑用户
 */
function editUser(id) {
    if (!requireAdminAction()) return;
    const user = AppState.users.find(u => u.id === id);
    if (user) {
        AppState.editingUserId = id;
        document.getElementById('user-username').value = user.username || '';
        document.getElementById('user-username').disabled = true;
        document.getElementById('user-name').value = user.name || '';
        document.getElementById('user-password').value = '';
        document.getElementById('user-role').value = user.role || 'visitor';
        document.getElementById('user-department').value = user.department || '';
        document.getElementById('user-phone').value = user.phone || '';
        document.getElementById('user-email').value = user.email || '';
        showModal('add-user-modal');
    }
}

/**
 * 删除用户
 */
async function deleteUser(id) {
    if (!requireAdminAction()) return;
    if (confirm('确定要删除该用户吗？')) {
        try {
            const result = await API.User.delete(id);
            if (result.success) {
                showNotification('成功', result.message || '用户已删除/禁用', 'success');
                await loadUsersData();
            } else {
                showNotification('失败', result.message || '删除失败', 'error');
            }
        } catch (error) {
            showNotification('错误', error.message || '网络错误', 'error');
        }
    }
}

async function handleUserCreate() {
    if (typeof event !== 'undefined') event.preventDefault();
    if (!requireAdminAction()) return;

    const payload = {
        username: document.getElementById('user-username').value.trim(),
        name: document.getElementById('user-name').value.trim(),
        password: document.getElementById('user-password').value,
        role: document.getElementById('user-role').value,
        department: document.getElementById('user-department').value.trim(),
        phone: document.getElementById('user-phone').value.trim(),
        email: document.getElementById('user-email').value.trim()
    };

    if (!payload.username || !payload.name || (!AppState.editingUserId && !payload.password)) {
        showNotification('错误', '请填写用户名、姓名和初始密码', 'error');
        return;
    }

    try {
        const result = AppState.editingUserId
            ? await API.User.update(AppState.editingUserId, {
                name: payload.name,
                role: payload.role,
                department: payload.department,
                phone: payload.phone,
                email: payload.email
            })
            : await API.User.create(payload);
        if (result.success) {
            showNotification('成功', AppState.editingUserId ? '用户已更新' : '用户已添加', 'success');
            AppState.editingUserId = null;
            document.getElementById('user-username').disabled = false;
            document.getElementById('user-form').reset();
            closeAllModals();
            await loadUsersData();
        } else {
            showNotification('失败', result.message || '添加失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

/**
 * 采购物料 - 从预警列表直接申请
 */
function purchaseMaterial(id) {
    const material = AppState.materials.find(m => m.id === id);
    if (material) {
        // 跳转到采购申请页面并填充物料信息
        navigateToPage('purchase');
        AppState.pendingPurchaseMaterialId = material.id;
        document.getElementById('purchase-name').value = material.name;
        document.getElementById('purchase-category').value = material.category_id || '';
        document.getElementById('purchase-spec').value = material.spec || '';
        document.getElementById('purchase-reason').value = `库存不足，当前库存${material.stock}${material.unit}，需要补充`;
    }
}

/**
 * 加载借用数据
 */
async function loadBorrowData() {
    try {
        const result = await API.Borrow.getList(isVisitor() ? { my: true } : {});
        if (result.success) {
            AppState.borrows = result.data.items;
            updateBorrowTable();
        }
    } catch (error) {
        console.error('加载借用数据失败:', error);
    }
}

/**
 * 更新借用记录表格
 */
function updateBorrowTable() {
    const tbody = document.querySelector('#borrow-page tbody');
    if (!tbody || !AppState.borrows) return;

    const statusByTab = {
        'borrow-active': ['active'],
        'borrow-returned': ['returned'],
        'borrow-overdue': ['overdue']
    };
    const allowedStatuses = statusByTab[AppState.activeBorrowTab];
    const rows = allowedStatuses
        ? AppState.borrows.filter(b => allowedStatuses.includes(b.status))
        : AppState.borrows;

    if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">暂无借用记录</td></tr>';
        return;
    }

    tbody.innerHTML = rows.map(b => `
        <tr>
            <td>${b.borrow_no}</td>
            <td>${b.material_name}</td>
            <td>${b.borrower_name || '-'}</td>
            <td>${b.borrow_date}</td>
            <td>${b.expected_return_date || '-'}</td>
            <td>${b.actual_return_date || '-'}</td>
            <td><span class="status ${b.status}">${getBorrowStatusText(b.status)}</span></td>
            <td>
                <button class="btn btn-sm btn-outline" onclick="viewBorrow(${b.id})">查看</button>
                ${isAdmin() && b.status === 'pending' ? `<button class="btn btn-sm btn-success" onclick="approveBorrow(${b.id}, 'approve')">同意</button><button class="btn btn-sm btn-danger" onclick="approveBorrow(${b.id}, 'reject')">拒绝</button>` : ''}
                ${isAdmin() && b.status === 'active' ? `<button class="btn btn-sm btn-primary" onclick="returnBorrow(${b.id})">归还</button>` : ''}
            </td>
        </tr>
    `).join('');
}

/**
 * 获取借用状态文本
 */
function getBorrowStatusText(status) {
    const statusMap = {
        'pending': '待审批',
        'approved': '已批准',
        'rejected': '已拒绝',
        'borrowed': '借用中',
        'active': '借用中',
        'returned': '已归还',
        'overdue': '已逾期'
    };
    return statusMap[status] || status;
}

/**
 * 归还借用物品
 */
async function returnBorrow(id) {
    if (!requireAdminAction()) return;
    try {
        const result = await API.Borrow.return(id, {});
        if (result.success) {
            showNotification('成功', '归还成功', 'success');
            await loadBorrowData();
            await loadBorrowSummary();
            await loadMaterialsData();
            await loadInventoryRecords();
            await loadHistoryData();
            await loadAlertsData();
            updateDashboardStats();
        } else {
            showNotification('失败', result.message || '归还失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

async function approveBorrow(id, action) {
    if (!requireAdminAction()) return;
    try {
        const result = await API.Borrow.approve(id, { action });
        if (result.success) {
            showNotification('成功', action === 'approve' ? '借用申请已同意，库存已同步出库' : '借用申请已拒绝', 'success');
            await loadBorrowData();
            await loadBorrowSummary();
            await loadMaterialsData();
            await loadInventoryRecords();
            await loadHistoryData();
            await loadAlertsData();
        } else {
            showNotification('失败', result.message || '处理失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

function viewBorrow(id) {
    const item = AppState.borrows?.find(b => b.id === id)
        || AppState.borrowSummary?.latest?.find(b => b.id === id);
    if (!item) return;
    const details = [
        `借用单号：${item.borrow_no}`,
        `状态：${getBorrowStatusText(item.status)}`,
        `物料名称：${item.material_name || '-'}`,
        `借用人：${item.borrower_name || '-'}`,
        `数量：${item.quantity || '-'}`,
        `预计归还：${item.expected_return_date || '-'}`,
        `实际归还：${item.actual_return_date || '-'}`,
        `借用理由：${item.reason || '-'}`
    ].join('\n');
    alert(details);
}

/**
 * 加载历史记录数据
 */
async function loadHistoryData() {
    try {
        const result = await API.Record.getList('inventory');
        if (result.success) {
            AppState.records = result.data.items;
            updateHistoryTable();
            updateInventoryTrend();
        }
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

async function loadInventoryRecords() {
    try {
        const result = await API.Inventory.getRecords();
        if (result.success) {
            AppState.inventoryRecords = result.data.items;
            updateInventoryRecordsTable();
            updateInventoryTrend();
        }
    } catch (error) {
        console.error('加载出入库记录失败:', error);
    }
}

function updateInventoryRecordsTable() {
    const tbody = document.querySelector('#inout-page tbody');
    if (!tbody || !AppState.inventoryRecords) return;

    if (AppState.activeInoutTab === 'pending-in') {
        const rows = (AppState.purchases || []).filter(p => p.status === 'approved');
        tbody.innerHTML = rows.length === 0
            ? '<tr><td colspan="8" style="text-align:center">暂无待入库采购单</td></tr>'
            : rows.map(p => `
                <tr>
                    <td>${p.request_no}</td>
                    <td><span class="badge-type in">待入库</span></td>
                    <td>${p.material_name || '-'}</td>
                    <td>${p.quantity}</td>
                    <td>${p.requester_name || '-'}</td>
                    <td>${p.created_at || '-'}</td>
                    <td><span class="status pending">待入库</span></td>
                    <td><button class="btn btn-sm btn-outline" onclick="viewPurchase(${p.id})">查看</button><button class="btn btn-sm btn-success" onclick="completePurchase(${p.id})">入库</button></td>
                </tr>
            `).join('');
        return;
    }

    if (AppState.activeInoutTab === 'pending-out') {
        const rows = (AppState.borrows || []).filter(b => b.status === 'pending');
        tbody.innerHTML = rows.length === 0
            ? '<tr><td colspan="8" style="text-align:center">暂无待出库借用申请</td></tr>'
            : rows.map(b => `
                <tr>
                    <td>${b.borrow_no}</td>
                    <td><span class="badge-type out">待出库</span></td>
                    <td>${b.material_name || '-'}</td>
                    <td>-${b.quantity}</td>
                    <td>${b.borrower_name || '-'}</td>
                    <td>${b.borrow_date || '-'}</td>
                    <td><span class="status pending">待审批</span></td>
                    <td><button class="btn btn-sm btn-outline" onclick="viewBorrow(${b.id})">查看</button><button class="btn btn-sm btn-success" onclick="approveBorrow(${b.id}, 'approve')">同意出库</button></td>
                </tr>
            `).join('');
        return;
    }

    if (AppState.inventoryRecords.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">暂无出入库记录</td></tr>';
        return;
    }

    tbody.innerHTML = AppState.inventoryRecords.map(r => `
        <tr>
            <td>${r.operation_no}</td>
            <td><span class="badge-type ${r.type}">${r.type_name || r.type}</span></td>
            <td>${r.material_name || '-'}</td>
            <td>${r.quantity > 0 ? '+' : ''}${r.quantity}</td>
            <td>${r.operator_name || '-'}</td>
            <td>${r.created_at || '-'}</td>
            <td><span class="status completed">已完成</span></td>
            <td><button class="btn btn-sm btn-outline" onclick="showNotification('记录详情', '${r.operation_no}', 'info')">查看</button></td>
        </tr>
    `).join('');
}

async function loadAlertsData() {
    if (!isAdmin()) return;
    try {
        await API.Alert.check().catch(() => null);
        const result = await API.Alert.getList({ is_resolved: false });
        if (result.success) {
            AppState.alerts = result.data.items;
            await loadPurchaseSummary();
            await loadBorrowSummary();
            updateAlertsTable();
            updateAlertStats();
            updateAlertPageReminders();
            updateAlertBadges();
        }
    } catch (error) {
        console.error('加载库存预警失败:', error);
        AppState.alerts = [];
        updateAlertBadges();
    }
}

function updateAlertPageReminders() {
    const page = document.getElementById('alerts-page');
    const statsGrid = page?.querySelector('.stats-grid');
    if (!page || !statsGrid) return;

    let panel = document.getElementById('alert-task-reminder-panel');
    const purchaseTasks = AppState.purchaseSummary?.latest || [];
    const borrowTasks = AppState.borrowSummary?.latest || [];
    const tasks = [
        ...purchaseTasks.map(item => ({ type: 'purchase', item })),
        ...borrowTasks.map(item => ({ type: 'borrow', item }))
    ];

    if (tasks.length === 0) {
        if (panel) panel.remove();
        return;
    }

    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'alert-task-reminder-panel';
        panel.className = 'card';
        statsGrid.insertAdjacentElement('afterend', panel);
    }

    panel.innerHTML = `
        <div class="card-header">
            <h3>申请待办提醒</h3>
            <a href="#" class="view-all" onclick="navigateToPage('purchase'); return false;">处理采购</a>
        </div>
        <div class="card-body">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>类型</th>
                        <th>单号</th>
                        <th>物料名称</th>
                        <th>数量</th>
                        <th>状态</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    ${tasks.map(({ type, item }) => type === 'purchase' ? `
                        <tr>
                            <td>采购申请</td>
                            <td>${item.request_no}</td>
                            <td>${item.material_name}</td>
                            <td>${item.quantity}</td>
                            <td>${getPurchaseStatusText(item.status)}</td>
                            <td>
                                <button class="btn btn-sm btn-outline" onclick="viewPurchase(${item.id})">查看</button>
                                <button class="btn btn-sm btn-primary" onclick="navigateToPage('purchase')">处理</button>
                            </td>
                        </tr>
                    ` : `
                        <tr>
                            <td>借用申请</td>
                            <td>${item.borrow_no}</td>
                            <td>${item.material_name}</td>
                            <td>${item.quantity}</td>
                            <td>${getBorrowStatusText(item.status)}</td>
                            <td>
                                <button class="btn btn-sm btn-outline" onclick="viewBorrow(${item.id})">查看</button>
                                <button class="btn btn-sm btn-primary" onclick="navigateToPage('borrow')">处理</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function updateAlertsTable() {
    const tbody = document.querySelector('#alerts-page tbody');
    if (!tbody || !AppState.alerts) return;

    if (AppState.alerts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">暂无库存预警</td></tr>';
        updateAlertBadges();
        return;
    }

    tbody.innerHTML = AppState.alerts.map(a => `
        <tr>
            <td>${a.material_code || '-'}</td>
            <td>${a.material_name || '-'}</td>
            <td>${a.current_stock}</td>
            <td>${a.threshold}</td>
            <td class="${a.level === 'danger' ? 'text-danger' : 'text-warning'}">${Number(a.current_stock || 0) - Number(a.threshold || 0)}</td>
            <td><span class="status-badge ${a.level}">${a.level === 'danger' ? '严重不足' : '库存预警'}</span></td>
            <td>${a.is_sent ? '已发送' : '未发送'}</td>
            <td><button class="btn btn-sm btn-primary" onclick="purchaseMaterial(${a.material_id})">申请采购</button></td>
        </tr>
    `).join('');
    updateAlertBadges();
}

function updateAlertStats() {
    const alerts = AppState.alerts || [];
    const danger = alerts.filter(a => a.level === 'danger').length;
    const warning = alerts.filter(a => a.level === 'warning').length;
    const sentToday = alerts.filter(a => a.is_sent).length;

    const dangerEl = document.getElementById('alert-danger-count');
    const warningEl = document.getElementById('alert-warning-count');
    const mailEl = document.getElementById('alert-mail-count');
    if (dangerEl) dangerEl.textContent = danger;
    if (warningEl) warningEl.textContent = warning;
    if (mailEl) mailEl.textContent = sentToday;
    updateAlertBadges();
}

async function loadSettingsData() {
    if (!isAdmin() || !API.Settings) return;
    try {
        const result = await API.Settings.get();
        if (!result.success) return;
        const data = result.data;
        const alertEmail = document.getElementById('setting-alert-email');
        const alertInterval = document.getElementById('setting-alert-interval');
        const alertEmailEnabled = document.getElementById('setting-alert-email-enabled');
        const warningEmailEnabled = document.getElementById('setting-warning-email-enabled');
        const overdueEmailEnabled = document.getElementById('setting-overdue-email-enabled');
        const storageLocation = document.getElementById('setting-storage-location');
        const backupFrequency = document.getElementById('setting-backup-frequency');

        if (alertEmail) alertEmail.value = data.alert_email || '';
        if (alertInterval) alertInterval.value = data.alert_check_interval || '30';
        if (alertEmailEnabled) alertEmailEnabled.checked = data.alert_email_enabled !== 'false';
        if (warningEmailEnabled) warningEmailEnabled.checked = data.alert_email_enabled !== 'false';
        if (overdueEmailEnabled) overdueEmailEnabled.checked = data.overdue_email_enabled === 'true';
        if (storageLocation) storageLocation.value = data.storage_location || 'cloud';
        if (backupFrequency) backupFrequency.value = data.backup_frequency || 'daily';
    } catch (error) {
        console.error('加载系统设置失败:', error);
    }
}

async function handleSettingsSubmit(e) {
    e.preventDefault();
    if (!requireAdminAction()) return;

    const payload = {
        alert_email: document.getElementById('setting-alert-email')?.value || '',
        alert_check_interval: document.getElementById('setting-alert-interval')?.value || '30',
        alert_email_enabled: String(Boolean(document.getElementById('setting-alert-email-enabled')?.checked || document.getElementById('setting-warning-email-enabled')?.checked)),
        overdue_email_enabled: String(Boolean(document.getElementById('setting-overdue-email-enabled')?.checked)),
        storage_location: document.getElementById('setting-storage-location')?.value || 'cloud',
        backup_frequency: document.getElementById('setting-backup-frequency')?.value || 'daily'
    };

    try {
        const result = await API.Settings.update(payload);
        if (result.success) {
            showNotification('成功', '系统设置已保存', 'success');
        } else {
            showNotification('失败', result.message || '保存失败', 'error');
        }
    } catch (error) {
        showNotification('错误', error.message || '网络错误', 'error');
    }
}

async function handleBackupNow() {
    if (!requireAdminAction()) return;

    const storageLocation = document.getElementById('setting-storage-location')?.value || 'cloud';
    if (storageLocation === 'local') {
        await exportData('all');
        return;
    }

    try {
        const result = await API.Settings.backup();
        if (result.success) {
            const path = result.data?.backup_path || '';
            showNotification('备份成功', path ? `已保存到 ${path}` : '数据库已备份到本地服务器', 'success');
            await loadSettingsData();
        } else {
            showNotification('备份失败', result.message || '无法创建备份', 'error');
        }
    } catch (error) {
        showNotification('备份失败', error.message || '网络错误', 'error');
    }
}

/**
 * 更新历史记录表格
 */
function updateHistoryTable() {
    const tbody = document.querySelector('#history-page tbody');
    if (!tbody || !AppState.records) return;

    if (AppState.records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">暂无记录</td></tr>';
        updateRecentActivityTable();
        updateInventoryTrend();
        return;
    }

    tbody.innerHTML = AppState.records.map(r => `
        <tr>
            <td>${r.created_at}</td>
            <td><span class="badge-type ${r.type}">${r.type === 'in' ? '入库' : '出库'}</span></td>
            <td>${r.material_name}</td>
            <td>${r.type === 'in' ? '+' : '-'}${r.quantity}</td>
            <td>${r.operator_name || '-'}</td>
            <td><span class="status completed">已完成</span></td>
        </tr>
    `).join('');
    updateRecentActivityTable();
    updateInventoryTrend();
}

function updateRecentActivityTable() {
    const tbody = document.querySelector('#dashboard-page .data-table tbody');
    if (!tbody) return;
    const records = AppState.records || [];

    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">暂无最近活动</td></tr>';
        return;
    }

    tbody.innerHTML = records.slice(0, 5).map(r => `
        <tr>
            <td>${r.created_at || '-'}</td>
            <td><span class="badge-type ${r.type}">${r.type_name || r.type}</span></td>
            <td>${r.material_name || '-'}</td>
            <td>${r.quantity > 0 ? '+' : ''}${r.quantity}</td>
            <td>${r.operator_name || '-'}</td>
            <td><span class="status completed">已完成</span></td>
        </tr>
    `).join('');
}
