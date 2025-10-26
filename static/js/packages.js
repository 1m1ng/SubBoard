/**
 * 套餐管理功能模块
 * 处理套餐的创建、编辑、节点加载等功能
 */

// 存储已加载的节点数据
const nodesCache = {};
const loadedServers = {};

// 刷新所有节点（清除缓存并重新加载）
async function refreshAllNodes(formType) {
    const refreshBtn = event.target.closest('.btn-refresh');
    const originalHTML = refreshBtn.innerHTML;
    
    // 禁用按钮并显示加载状态
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = `
        <svg class="icon spinning" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        刷新中...
    `;
    
    try {
        // 调用后端刷新接口
        const response = await fetch('/packages/refresh_nodes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 清除本地缓存
            Object.keys(nodesCache).forEach(key => delete nodesCache[key]);
            Object.keys(loadedServers).forEach(key => {
                if (key.startsWith(formType + '_')) {
                    delete loadedServers[key];
                }
            });
            
            // 重新加载所有已展开的节点
            // 从全局变量获取服务器列表
            const servers = window.serversData || [];
            for (const boardName of servers) {
                    await loadNodes(formType, boardName);
                    loadedServers[`${formType}_${boardName}`] = true;
                }
        }
        else {
            alert('刷新失败: ' + (data.message || '未知错误'));
        }
    } 
    catch (error) {
        console.error('刷新节点失败:', error);
        alert('刷新失败: ' + error.message);
    } 
    finally {
        // 恢复按钮状态
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = originalHTML;
    }
}

// 切换服务器节点显示
async function toggleServerNodes(formType, boardName) {
    const nodesList = document.getElementById(`${formType}_nodes_${boardName}`);
    const serverGroup = nodesList.closest('.server-group');
    const toggleIcon = serverGroup.querySelector('.toggle-icon');
    
    if (nodesList.style.display === 'none') {
        nodesList.style.display = 'block';
        toggleIcon.textContent = '▲';
        
        // 如果还没有加载过节点，则加载
        if (!loadedServers[`${formType}_${boardName}`]) {
            await loadNodes(formType, boardName);
            loadedServers[`${formType}_${boardName}`] = true;
        }
    } else {
        nodesList.style.display = 'none';
        toggleIcon.textContent = '▼';
    }
}

// 加载节点列表
async function loadNodes(formType, boardName) {
    const nodesList = document.getElementById(`${formType}_nodes_${boardName}`);
    
    try {
        const response = await fetch(`/packages/get_nodes/${boardName}`);
        const data = await response.json();
        
        if (data.success && data.nodes && data.nodes.length > 0) {
            // 缓存节点数据
            if (!nodesCache[boardName]) {
                nodesCache[boardName] = data.nodes;
            }
            
            let html = '';
            data.nodes.forEach(node => {
                const nodeId = `${boardName}|${node.id}|${node.name}`;
                const rateInputId = `rate_${boardName}_${node.name}`.replace(/[^a-zA-Z0-9_]/g, '_');
                html += `
                    <div class="node-item">
                        <label class="node-checkbox">
                            <input type="checkbox" name="nodes[]" value="${nodeId}">
                            <span class="node-name">${node.name}</span>
                        </label>
                        <div class="rate-input">
                            <label>倍率:</label>
                            <input type="number" name="rate_${boardName}_${node.name}" 
                                   id="${rateInputId}" value="1.0" min="0.1" step="0.1" 
                                   class="rate-field">
                        </div>
                    </div>
                `;
            });
            nodesList.innerHTML = html;
        } else {
            nodesList.innerHTML = '<div class="no-data">该服务器暂无节点</div>';
        }
    } catch (error) {
        console.error('加载节点失败:', error);
        nodesList.innerHTML = '<div class="error-text">加载失败</div>';
    }
}

// 编辑套餐
async function editPackage(packageId, name, totalTraffic, nodes) {
    document.getElementById('edit_name').value = name;
    document.getElementById('edit_total_traffic').value = totalTraffic;
    document.getElementById('editPackageForm').action = `/packages/edit/${packageId}`;
    
    // 重置所有节点选择
    const allCheckboxes = document.querySelectorAll('#editPackageModal input[name="nodes[]"]');
    allCheckboxes.forEach(cb => cb.checked = false);
    
    // 重置所有倍率
    const allRates = document.querySelectorAll('#editPackageModal .rate-field');
    allRates.forEach(rate => rate.value = '1.0');
    
    // 展开并加载所有服务器的节点
    const servers = window.serversData || [];
    for (const boardName of servers) {
        const nodesList = document.getElementById(`edit_nodes_${boardName}`);
        if (!nodesList) continue;
        
        const serverGroup = nodesList.closest('.server-group');
        if (!serverGroup) continue;
        
        const toggleIcon = serverGroup.querySelector('.toggle-icon');
        
        nodesList.style.display = 'block';
        toggleIcon.textContent = '▲';
        
        if (!loadedServers[`edit_${boardName}`]) {
            await loadNodes('edit', boardName);
            loadedServers[`edit_${boardName}`] = true;
        }
    }
    
    // 等待一小段时间确保DOM已更新
    setTimeout(() => {
        // 设置已选择的节点
        nodes.forEach(node => {
            // 遍历所有复选框，通过 board_name 和 inbound_id 来匹配
            const checkboxes = document.querySelectorAll(`#editPackageModal input[name="nodes[]"]`);
            checkboxes.forEach(checkbox => {
                const value = checkbox.value;
                const parts = value.split('|');
                if (parts.length === 3) {
                    const [boardName, inboundId, nodeName] = parts;
                    // 使用 board_name 和 inbound_id 匹配（这两个是稳定的标识）
                    if (boardName === node.board_name && parseInt(inboundId) === node.inbound_id) {
                        checkbox.checked = true;
                        
                        // 设置倍率（使用当前checkbox对应的节点名称）
                        const rateInputName = `rate_${boardName}_${nodeName}`;
                        const rateInput = document.querySelector(`#editPackageModal input[name="${rateInputName}"]`);
                        if (rateInput) {
                            rateInput.value = node.traffic_rate;
                        }
                    }
                }
            });
        });
    }, 100);
    
    document.getElementById('editPackageModal').style.display = 'block';
}

// 关闭编辑模态框
function closeEditModal() {
    document.getElementById('editPackageModal').style.display = 'none';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('editPackageModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
