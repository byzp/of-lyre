// 工具函数模块
const utils = (() => {
    // 防抖函数
    function debounce(fn, wait) {
        let timeout = null;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    // XSS防护
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // 格式化文件大小
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // 格式化时长
    function formatDuration(ms) {
        if (!ms) return '-';
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    // 格式化上传时间
    function formatUploadTime(timeStr) {
        if (!timeStr) return '-';
        try {
            const date = new Date(timeStr);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return timeStr;
        }
    }

    // 通用提示函数
    function showMessage(message, type = 'info') {
        // 如果消息是翻译键，则翻译它
        let displayMessage = message;
        if (message.startsWith('t-')) {
            const key = message.substring(2);
            displayMessage = language.t(key);
        }

        const msg = document.createElement('div');
        msg.textContent = displayMessage;

        // 根据类型设置不同颜色
        const colors = {
            info: '#2196F3',
            success: '#4CAF50',
            error: '#f44336',
            warning: '#ff9800'
        };

        msg.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 10px 15px;
            border-radius: 4px;
            z-index: 1000;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        `;

        document.body.appendChild(msg);

        // 3秒后自动移除提示
        setTimeout(() => msg.remove(), 3000);
    }

    // 获取或生成设备唯一标识符
    function getDeviceId() {
        // 尝试从localStorage获取设备ID
        let deviceId = localStorage.getItem('midi_app_device_id');

        // 如果不存在，生成新的设备ID
        if (!deviceId) {
            // 使用时间戳和随机数生成唯一ID
            deviceId = 'dev_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
            // 存储到localStorage
            localStorage.setItem('midi_app_device_id', deviceId);
        }

        return deviceId;
    }

    return {
        debounce,
        escapeHtml,
        formatFileSize,
        formatDuration,
        formatUploadTime,
        showMessage,
        getDeviceId
    };
})();
