/**
 * 管理员页面功能模块
 * 处理用户编辑、模态框等
 */

function editUser(userId, username, email, isAdmin, packageId, packageExpireTime, nextResetTime) {
    document.getElementById('edit_username').value = username;
    document.getElementById('edit_email').value = email;
    document.getElementById('edit_password').value = '';
    document.getElementById('edit_is_admin').checked = isAdmin;
    document.getElementById('edit_package_id').value = packageId || '';
    document.getElementById('edit_package_expire_time').value = packageExpireTime || '';
    document.getElementById('edit_next_reset_time').value = nextResetTime || '';
    document.getElementById('editUserForm').action = `/admin/edit_user/${userId}`;
    document.getElementById('editUserModal').style.display = 'block';
}

function closeEditModal() {
    document.getElementById('editUserModal').style.display = 'none';
}

// 点击模态框外部关闭
window.onclick = function(event) {
    const modal = document.getElementById('editUserModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
