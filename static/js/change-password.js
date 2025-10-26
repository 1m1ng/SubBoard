/**
 * 修改密码功能模块
 * 处理密码可见性切换、强度检测、匹配验证等
 */

// 密码可见性切换
document.querySelectorAll('.toggle-password').forEach(button => {
    button.addEventListener('click', function() {
        const targetId = this.getAttribute('data-target');
        const input = document.getElementById(targetId);
        const eyeIcon = this.querySelector('.eye-icon');
        const eyeOffIcon = this.querySelector('.eye-off-icon');
        
        if (input.type === 'password') {
            input.type = 'text';
            eyeIcon.style.display = 'none';
            eyeOffIcon.style.display = 'block';
        } else {
            input.type = 'password';
            eyeIcon.style.display = 'block';
            eyeOffIcon.style.display = 'none';
        }
    });
});

// 密码强度检测
const newPassword = document.getElementById('new_password');
const strengthBarFill = document.getElementById('strengthBarFill');
const strengthText = document.getElementById('strengthText');
const reqLength = document.getElementById('req-length');
const reqLetter = document.getElementById('req-letter');
const reqNumber = document.getElementById('req-number');

newPassword.addEventListener('input', function() {
    const password = this.value;
    let strength = 0;
    
    // 检查长度
    if (password.length >= 6) {
        strength += 1;
        reqLength.classList.add('met');
    } else {
        reqLength.classList.remove('met');
    }
    
    // 检查是否包含字母
    if (/[a-zA-Z]/.test(password)) {
        strength += 1;
        reqLetter.classList.add('met');
    } else {
        reqLetter.classList.remove('met');
    }
    
    // 检查是否包含数字
    if (/[0-9]/.test(password)) {
        strength += 1;
        reqNumber.classList.add('met');
    } else {
        reqNumber.classList.remove('met');
    }
    
    // 额外强度检查
    if (password.length >= 10) strength += 1;
    if (/[!@#$%^&*]/.test(password)) strength += 1;
    
    // 更新强度条
    const percentage = (strength / 5) * 100;
    strengthBarFill.style.width = percentage + '%';
    
    if (strength <= 1) {
        strengthBarFill.style.background = '#dc3545';
        strengthText.textContent = '弱';
        strengthText.style.color = '#dc3545';
    } else if (strength <= 3) {
        strengthBarFill.style.background = '#ffc107';
        strengthText.textContent = '中等';
        strengthText.style.color = '#ffc107';
    } else {
        strengthBarFill.style.background = '#28a745';
        strengthText.textContent = '强';
        strengthText.style.color = '#28a745';
    }
});

// 确认密码匹配检测
const confirmPassword = document.getElementById('confirm_password');
const matchText = document.getElementById('matchText');

confirmPassword.addEventListener('input', function() {
    if (this.value === '') {
        matchText.textContent = '';
        return;
    }
    
    if (this.value === newPassword.value) {
        matchText.textContent = '✓ 密码匹配';
        matchText.style.color = '#28a745';
    } else {
        matchText.textContent = '✗ 密码不匹配';
        matchText.style.color = '#dc3545';
    }
});

// 表单提交验证
document.getElementById('passwordForm').addEventListener('submit', function(e) {
    if (newPassword.value !== confirmPassword.value) {
        e.preventDefault();
        alert('新密码和确认密码不匹配！');
        confirmPassword.focus();
    }
});
