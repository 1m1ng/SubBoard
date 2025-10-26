/**
 * 服务器管理功能模块
 * 处理服务器编辑、模态框等
 */

function editServer(boardName, server, port, path, subPath, username) {
    document.getElementById('edit_server').value = server;
    document.getElementById('edit_port').value = port;
    document.getElementById('edit_path').value = path;
    document.getElementById('edit_sub_path').value = subPath;
    document.getElementById('edit_username').value = username;
    document.getElementById('edit_password').value = '';
    document.getElementById('editServerForm').action = `/servers/edit/${boardName}`;
    document.getElementById('editServerModal').style.display = 'block';
}

function closeEditModal() {
    document.getElementById('editServerModal').style.display = 'none';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('editServerModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
