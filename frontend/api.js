/**
 * 实验室物料库存管理系统 - API服务
 * 连接后端 Flask API
 */

// API基础URL
// 生产环境统一走同源 /api，由 Nginx 反向代理到后端。
// 如需临时改地址，可在 index.html 之前设置 window.LAB_API_BASE_URL。
const API_BASE_URLS = (() => {
    const queryBase = new URLSearchParams(window.location.search).get('api');
    const configuredBase = window.LAB_API_BASE_URL || queryBase;
    const isFileProtocol = window.location.protocol === 'file:';
    const isLocalStaticServer = ['127.0.0.1', 'localhost'].includes(window.location.hostname)
        && window.location.port === '8080';
    const bases = configuredBase
        ? [configuredBase]
        : [(isLocalStaticServer || isFileProtocol) ? 'http://127.0.0.1:5001/api' : '/api'];
    return [...new Set(bases)];
})();

// 存储token
let authToken = localStorage.getItem('labInventory_token') || null;
let sessionExpiryNotified = false;

/**
 * 通用的API请求函数
 */
async function apiRequest(endpoint, options = {}) {
    const endpoints = Array.isArray(endpoint) ? endpoint : [endpoint];

    // 设置默认headers
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    // 如果有token，添加到headers
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    let lastError = null;

    for (const currentEndpoint of endpoints) {
        for (const baseUrl of API_BASE_URLS) {
            const url = `${baseUrl}${currentEndpoint}`;

            try {
                const response = await fetch(url, {
                    ...options,
                    headers
                });

                const contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    lastError = new Error('接口返回格式错误，请检查后端服务或Nginx代理配置');
                    continue;
                }

                const data = await response.json();

                if (!response.ok) {
                    if (response.status === 404 || response.status >= 500) {
                        lastError = new Error(data.message || '请求失败');
                        continue;
                    }

                    // 400/401/403 通常来自真实API，不再继续尝试其它地址
                    if (response.status === 401 && currentEndpoint !== '/auth/login' && currentEndpoint !== '/login') {
                        authToken = null;
                        localStorage.removeItem('labInventory_token');
                        localStorage.removeItem('labInventory_user');
                        localStorage.removeItem('labInventory_role');
                        if (!sessionExpiryNotified) {
                            sessionExpiryNotified = true;
                            showNotification('会话已过期', '请重新登录', 'error');
                            window.dispatchEvent(new CustomEvent('auth:expired'));
                        }
                    }

                    throw new Error(data.message || data.msg || '请求失败');
                }

                return data;
            } catch (error) {
                console.error(`API请求错误 (${url}):`, error);
                lastError = error;
            }
        }
    }

    throw lastError || new Error('无法连接后端API，请检查服务是否启动');
}

/**
 * 认证相关API
 */
const AuthAPI = {
    // 登录
    async login(username, password) {
        const data = await apiRequest(['/auth/login', '/login'], {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        if (data.success) {
            const loginData = data.data || data;
            const accessToken = loginData.access_token || data.access_token || data.token;
            const user = loginData.user || data.user;

            if (!accessToken || !user) {
                throw new Error('登录接口返回数据不完整');
            }

            authToken = accessToken;
            sessionExpiryNotified = false;
            localStorage.setItem('labInventory_token', authToken);
            localStorage.setItem('labInventory_user', JSON.stringify(user));

            return {
                ...data,
                data: {
                    ...loginData,
                    access_token: accessToken,
                    user
                }
            };
        }
        
        return data;
    },
    
    // 退出登录
    async logout() {
        try {
            await apiRequest('/auth/logout', { method: 'POST' });
        } catch (e) {
            console.log('退出登录');
        }
        authToken = null;
        localStorage.removeItem('labInventory_token');
        localStorage.removeItem('labInventory_user');
    },
    
    // 获取用户信息
    async getProfile() {
        return await apiRequest('/auth/profile');
    },
    
    // 修改密码
    async changePassword(oldPassword, newPassword) {
        return await apiRequest('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
    }
};

/**
 * 物料管理API
 */
const MaterialAPI = {
    // 获取物料列表
    async getList(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/materials?${queryString}`);
    },
    
    // 获取物料详情
    async getDetail(id) {
        return await apiRequest(`/materials/${id}`);
    },
    
    // 创建物料
    async create(data) {
        return await apiRequest('/materials', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // 更新物料
    async update(id, data) {
        return await apiRequest(`/materials/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // 删除物料
    async delete(id) {
        return await apiRequest(`/materials/${id}`, { method: 'DELETE' });
    },

    // 批量导入物料
    async import(items) {
        return await apiRequest('/materials/import', {
            method: 'POST',
            body: JSON.stringify({ items })
        });
    },
    
    // 获取分类列表
    async getCategories() {
        return await apiRequest('/materials/categories');
    }
};

/**
 * 出入库管理API
 */
const InventoryAPI = {
    // 入库
    async stockIn(data) {
        return await apiRequest('/inventory/in', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // 出库
    async stockOut(data) {
        return await apiRequest('/inventory/out', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // 出入库记录
    async getRecords(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/inventory/records?${queryString}`);
    }
};

/**
 * 采购申请API
 */
const PurchaseAPI = {
    // 获取采购申请列表
    async getList(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/purchase?${queryString}`);
    },
    
    // 创建采购申请
    async create(data) {
        return await apiRequest('/purchase', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // 审批采购申请
    async approve(id, data) {
        return await apiRequest(`/purchase/${id}/approve`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async complete(id, data) {
        return await apiRequest(`/purchase/${id}/complete`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async summary() {
        return await apiRequest('/purchase/summary');
    },
    
    // 取消采购申请
    async cancel(id) {
        return await apiRequest(`/purchase/${id}/cancel`, { method: 'PUT' });
    }
};

/**
 * 借用管理API
 */
const BorrowAPI = {
    // 获取借用记录列表
    async getList(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/borrow?${queryString}`);
    },
    
    // 创建借用申请
    async create(data) {
        return await apiRequest('/borrow', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // 审批借用申请
    async approve(id, data) {
        return await apiRequest(`/borrow/${id}/approve`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async summary() {
        return await apiRequest('/borrow/summary');
    },
    
    // 归还物料
    async return(id, data) {
        return await apiRequest(`/borrow/${id}/return`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

/**
 * 用户管理API
 */
const UserAPI = {
    // 获取用户列表
    async getList(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/users?${queryString}`);
    },
    
    // 创建用户
    async create(data) {
        return await apiRequest('/users', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // 更新用户
    async update(id, data) {
        return await apiRequest(`/users/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    // 删除用户
    async delete(id) {
        return await apiRequest(`/users/${id}`, { method: 'DELETE' });
    }
};

/**
 * 库存预警API
 */
const AlertAPI = {
    // 获取预警列表
    async getList(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return await apiRequest(`/alerts?${queryString}`);
    },
    
    // 检查库存预警
    async check() {
        return await apiRequest('/alerts/check', { method: 'POST' });
    }
};

/**
 * 历史记录API
 */
const RecordAPI = {
    // 获取历史记录
    async getList(type = 'inventory', params = {}) {
        const queryParams = new URLSearchParams({ type, ...params }).toString();
        return await apiRequest(`/records?${queryParams}`);
    },

    async dashboard() {
        return await apiRequest('/records/dashboard');
    }
};

/**
 * 系统设置API
 */
const SettingsAPI = {
    async get() {
        return await apiRequest('/settings');
    },

    async update(data) {
        return await apiRequest('/settings', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async backup() {
        return await apiRequest('/settings/backup', { method: 'POST' });
    }
};

// 导出API
window.API = {
    Auth: AuthAPI,
    Material: MaterialAPI,
    Inventory: InventoryAPI,
    Purchase: PurchaseAPI,
    Borrow: BorrowAPI,
    User: UserAPI,
    Alert: AlertAPI,
    Record: RecordAPI,
    Settings: SettingsAPI
};
