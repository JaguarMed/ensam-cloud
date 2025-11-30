/**
 * Cloud Platform Client App - Core JavaScript
 * Handles authentication, API calls, and UI utilities
 */

// ============================================================================
// Token Manager
// ============================================================================

const TokenManager = {
    TOKEN_KEY: 'access_token',
    
    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },
    
    setToken(token) {
        localStorage.setItem(this.TOKEN_KEY, token);
    },
    
    removeToken() {
        localStorage.removeItem(this.TOKEN_KEY);
        localStorage.removeItem('user');
    },
    
    isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            // Check expiration
            if (payload.exp && payload.exp * 1000 < Date.now()) {
                this.removeToken();
                return false;
            }
            return true;
        } catch (e) {
            return false;
        }
    },
    
    getUserInfo() {
        const token = this.getToken();
        if (!token) return null;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return {
                id: payload.sub,
                email: payload.email,
                name: payload.name || 'User'
            };
        } catch (e) {
            return null;
        }
    }
};

// ============================================================================
// Authentication Helpers
// ============================================================================

function requireAuth() {
    if (!TokenManager.isAuthenticated()) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

function logout() {
    TokenManager.removeToken();
    window.location.href = '/login';
}

// ============================================================================
// API Helper
// ============================================================================

const API = {
    async request(url, options = {}) {
        const token = TokenManager.getToken();
        
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        try {
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            // Handle 401 - redirect to login
            if (response.status === 401) {
                TokenManager.removeToken();
                window.location.href = '/login';
                return null;
            }
            
            return response;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },
    
    async get(url) {
        return this.request(url, { method: 'GET' });
    },
    
    async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
};

// ============================================================================
// UI Utilities
// ============================================================================

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="flex items-center gap-2">
            ${getNotificationIcon(type)}
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(20px)';
        notification.style.transition = 'all 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function getNotificationIcon(type) {
    const icons = {
        success: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>',
        error: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>',
        warning: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
        info: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    };
    return icons[type] || icons.info;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ============================================================================
// Page Load Handler
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Add smooth transitions for page loads
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s ease';
    
    requestAnimationFrame(() => {
        document.body.style.opacity = '1';
    });
});








