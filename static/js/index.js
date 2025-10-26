/**
 * 首页功能模块
 * 处理订阅链接复制等功能
 */

function copySubscription() {
    const url = document.getElementById('subscription_url').value;
    
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
            alert('订阅链接已复制到剪贴板！');
        }).catch(err => {
            fallbackCopy(url);
        });
    } else {
        fallbackCopy(url);
    }
}

function fallbackCopy(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    document.body.appendChild(textArea);
    textArea.select();
    
    try {
        document.execCommand('copy');
        alert('订阅链接已复制到剪贴板！');
    } catch (err) {
        prompt('请手动复制订阅链接：', text);
    }
    
    document.body.removeChild(textArea);
}
