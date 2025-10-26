/**
 * 节点信息页面功能模块
 * 处理节点信息的加载、显示和刷新
 */

let isLoading = false;

// 格式化字节数
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

// 创建节点卡片
function createNodeCard(inbound) {
    const card = document.createElement('div');
    card.className = 'node-card';
    
    // 计算已用流量
    const used = (inbound.up || 0) + (inbound.down || 0);
    const total = inbound.total || 0;
    
    // 状态徽章
    const statusBadge = inbound.enable 
        ? '<span class="status-badge status-active">可用</span>'
        : '<span class="status-badge status-inactive">不可用</span>';
    
    // 流量倍率标签（如果有）
    const trafficRateBadge = inbound.traffic_rate 
        ? `<span class="traffic-rate-badge" title="流量倍率">×${inbound.traffic_rate}</span>`
        : '';
    
    // 流量信息
    let trafficInfo = '';
    trafficInfo = `
        <div class="traffic-info">
            <div class="traffic-label">流量使用情况</div>
            <div class="traffic-stats">
                <span class="traffic-used">${formatBytes(used)}</span>
            </div>
            <div class="traffic-details">
                <div class="traffic-item">
                    <span class="traffic-item-label">上传:</span>
                    <span class="traffic-item-value">${formatBytes(inbound.up || 0)}</span>
                </div>
                <div class="traffic-item">
                    <span class="traffic-item-label">下载:</span>
                    <span class="traffic-item-value">${formatBytes(inbound.down || 0)}</span>
                </div>
            </div>
        </div>
    `;
    
    // 节点名称（后端已保证返回 remark）
    const nodeName = inbound.remark || '未命名节点';
    
    card.innerHTML = `
        <div class="node-header">
            <div class="node-title-section">
                <h3 class="node-name">${nodeName}</h3>
                <div class="node-badges">
                    ${statusBadge}
                    ${trafficRateBadge}
                </div>
            </div>
        </div>
        <div class="node-info">
            <div class="node-info-item">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                    <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                    <line x1="6" y1="6" x2="6.01" y2="6"></line>
                    <line x1="6" y1="18" x2="6.01" y2="18"></line>
                </svg>
                <span>${inbound.board_name || '未知服务器'}</span>
            </div>
            <div class="node-info-item">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="2" y1="12" x2="22" y2="12"></line>
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                </svg>
                <span>${inbound.protocol || 'N/A'}</span>
            </div>
        </div>
        ${trafficInfo}
    `;
    
    return card;
}

// 加载节点信息
async function loadNodes() {
    if (isLoading) return;
    
    isLoading = true;
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const nodesGrid = document.getElementById('nodesGrid');
    const refreshBtn = document.getElementById('refreshBtn');
    
    loadingIndicator.style.display = 'block';
    errorMessage.style.display = 'none';
    nodesGrid.innerHTML = '';
    refreshBtn.disabled = true;
    
    try {
        const response = await fetch('/api/inbounds');
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '加载失败');
        }
        
        loadingIndicator.style.display = 'none';
        
        // 显示套餐信息
        if (data.package_name) {
            const packageInfo = document.getElementById('packageInfo');
            const packageInfoText = document.getElementById('packageInfoText');
            if (packageInfo && packageInfoText) {
                packageInfoText.textContent = `当前套餐: ${data.package_name} | 共 ${data.inbounds.length} 个节点`;
                packageInfo.style.display = 'flex';
            }
        }
        
        if (data.inbounds && data.inbounds.length > 0) {
            // 先清空网格，然后添加新卡片以触发动画
            nodesGrid.style.opacity = '0';
            setTimeout(() => {
                data.inbounds.forEach(inbound => {
                    const card = createNodeCard(inbound);
                    nodesGrid.appendChild(card);
                });
                nodesGrid.style.opacity = '1';
            }, 50);
        } else {
            const message = data.message || '暂无节点信息';
            nodesGrid.innerHTML = `<div class="no-data">${message}</div>`;
        }
    } catch (error) {
        console.error('加载节点失败:', error);
        loadingIndicator.style.display = 'none';
        errorMessage.style.display = 'flex';
        document.getElementById('errorText').textContent = error.message || '加载节点信息失败';
    } finally {
        isLoading = false;
        refreshBtn.disabled = false;
    }
}

// 刷新按钮点击事件
document.getElementById('refreshBtn').addEventListener('click', () => {
    loadNodes();
});

// 页面加载时自动加载节点
document.addEventListener('DOMContentLoaded', () => {
    loadNodes();
});
