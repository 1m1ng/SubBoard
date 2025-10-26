/**
 * 侧边栏功能模块
 * 处理侧边栏的展开/收起、移动端菜单等
 */

// 侧边栏功能
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const mobileMenuToggle = document.getElementById('mobileMenuToggle');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const mainContent = document.getElementById('mainContent');

// 从 localStorage 读取侧边栏状态（仅桌面端）
const sidebarState = localStorage.getItem('sidebarCollapsed');
if (sidebarState === 'true' && window.innerWidth > 768) {
    sidebar.classList.add('collapsed');
    mainContent.classList.add('sidebar-collapsed');
}

// 桌面端切换侧边栏
if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        mainContent.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
}

// 移动端打开侧边栏
if (mobileMenuToggle) {
    mobileMenuToggle.addEventListener('click', () => {
        sidebar.classList.add('mobile-open');
        sidebarOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    });
}

// 移动端关闭侧边栏
if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        sidebarOverlay.classList.remove('active');
        document.body.style.overflow = '';
    });
}

// 移动端点击菜单项后关闭侧边栏
if (window.innerWidth <= 768) {
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('active');
            document.body.style.overflow = '';
        });
    });
}

// 窗口大小改变时处理
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
        sidebar.classList.remove('mobile-open');
        sidebarOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// 高亮当前页面
const currentPath = window.location.pathname;
document.querySelectorAll('.sidebar-item').forEach(item => {
    if (item.getAttribute('href') === currentPath) {
        item.classList.add('active');
    }
});
