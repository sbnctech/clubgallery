// SBNC Photo Admin - JavaScript

// AJAX setup for CSRF protection if needed
// (Add CSRF token handling here if Flask-WTF is used)

// Utility function for fetch with better error handling
async function apiCall(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    };

    if (data) {
        if (data instanceof FormData) {
            options.body = data;
        } else {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 100);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Keyboard shortcut hints
function initKeyboardHints() {
    const hints = document.createElement('div');
    hints.className = 'keyboard-hints';
    hints.innerHTML = `
        <h4>Keyboard Shortcuts</h4>
        <div class="shortcut"><kbd>A</kbd> Approve</div>
        <div class="shortcut"><kbd>R</kbd> Reject</div>
        <div class="shortcut"><kbd>→</kbd> Next</div>
        <div class="shortcut"><kbd>←</kbd> Previous</div>
        <div class="shortcut"><kbd>Esc</kbd> Close panel</div>
    `;

    // Only show on editor page
    if (document.querySelector('.editor-page')) {
        document.body.appendChild(hints);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initKeyboardHints();
});
