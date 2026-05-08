// app/static/js/main.js
// Управление токеном
function setAuthToken(token) {
    localStorage.setItem('access_token', token);
}

function getAuthToken() {
    return localStorage.getItem('access_token');
}

// Форматирование чисел
function formatCurrency(value, currency = 'USD') {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: currency
    }).format(value);
}

// Уведомления
function showNotification(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.container').firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

// Проверка авторизации
async function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/auth/login';
        return false;
    }
    return true;
}