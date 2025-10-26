/**
 * 入站节点信息功能模块
 * 处理自动刷新等功能
 */

// 自动刷新功能（可选）
let autoRefreshInterval = null;

function startAutoRefresh() {
    autoRefreshInterval = setInterval(() => {
        location.reload();
    }, 60000); // 每60秒刷新一次
}

// 页面加载完成后启动自动刷新
// startAutoRefresh();

// 页面卸载时清除定时器
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
});
