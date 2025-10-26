/**
 * Mihomo 模板管理功能模块
 * 处理模板加载、YAML验证、格式化等
 */

// 加载模板到编辑器
function loadTemplate(id, name, content) {
    document.getElementById('name').value = name;
    document.getElementById('template_content').value = content;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 验证 YAML
function validateYAML() {
    const content = document.getElementById('template_content').value;
    
    fetch('/mihomo_template/validate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: content })
    })
    .then(response => response.json())
    .then(data => {
        if (data.valid) {
            alert('✓ YAML 格式正确！');
        } else {
            alert('✗ YAML 格式错误:\n' + data.error);
        }
    })
    .catch(error => {
        alert('验证失败: ' + error);
    });
}

// 格式化 YAML（简单的缩进处理）
function formatYAML() {
    const textarea = document.getElementById('template_content');
    const content = textarea.value;
    
    // 这里可以添加更复杂的格式化逻辑
    // 目前只是简单的提示
    alert('YAML 格式化功能提示：\n\n1. 确保使用空格缩进（通常是2个空格）\n2. 列表项使用 "- " 开头\n3. 键值对使用 ": " 分隔\n4. 多行内容使用 | 或 >');
}

// 表单提交前的额外验证
document.getElementById('templateForm').addEventListener('submit', function(e) {
    const content = document.getElementById('template_content').value.trim();
    
    if (!content) {
        e.preventDefault();
        alert('模板内容不能为空！');
        return false;
    }
    
    // 简单的 YAML 语法检查
    const lines = content.split('\n');
    let hasError = false;
    let errorMessage = '';
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // 检查是否使用了 tab（YAML 不允许 tab）
        if (line.includes('\t')) {
            hasError = true;
            errorMessage = `第 ${i + 1} 行包含 Tab 字符，YAML 不允许使用 Tab 缩进，请使用空格`;
            break;
        }
    }
    
    if (hasError) {
        e.preventDefault();
        alert('YAML 格式错误:\n' + errorMessage);
        return false;
    }
});
