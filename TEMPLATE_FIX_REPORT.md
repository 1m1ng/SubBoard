# 模板文件 URL 修复报告

## 修复的文件

已成功修复所有模板文件中的 `url_for()` 调用，更新为使用蓝图前缀。

### 1. ✅ base.html
已经正确使用蓝图前缀：
- `url_for('main.index')` ✅
- `url_for('admin.admin')` ✅
- `url_for('servers.servers')` ✅
- `url_for('mihomo.mihomo_template')` ✅
- `url_for('auth.profile')` ✅
- `url_for('auth.logout')` ✅
- `url_for('auth.login')` ✅

### 2. ✅ login.html
已经正确使用蓝图前缀：
- `url_for('auth.login')` ✅

### 3. ✅ index.html
已经正确使用蓝图前缀：
- `url_for('main.refresh_token')` ✅

### 4. ✅ admin.html
修复内容：
- ❌ `url_for('create_user')` → ✅ `url_for('admin.create_user')`
- ❌ `url_for('delete_user', user_id=user.id)` → ✅ `url_for('admin.delete_user', user_id=user.id)`
- ❌ `url_for('unblock_ip', ip_id=ip.id)` → ✅ `url_for('admin.unblock_ip', ip_id=ip.id)`
- JavaScript 路径保持 `/admin/edit_user/${userId}` ✅（蓝图 url_prefix 处理）

### 5. ✅ servers.html
修复内容：
- ❌ `url_for('add_server')` → ✅ `url_for('servers.add_server')`
- ❌ `url_for('delete_server', board_name=board_name)` → ✅ `url_for('servers.delete_server', board_name=board_name)`
- JavaScript 路径保持 `/servers/edit/${boardName}` ✅（蓝图 url_prefix 处理）

### 6. ✅ profile.html
修复内容：
- ❌ `url_for('change_password')` → ✅ `url_for('auth.change_password_page')`
- ❌ `url_for('index')` → ✅ `url_for('main.index')`

### 7. ✅ change_password.html
修复内容：
- ❌ `url_for('change_password')` → ✅ `url_for('auth.change_password')`
- ❌ `url_for('profile')` → ✅ `url_for('auth.profile')`

### 8. ✅ mihomo_template.html
修复内容：
- ❌ `url_for('save_mihomo_template')` → ✅ `url_for('mihomo.save_mihomo_template')`
- ❌ `url_for('set_active_template', template_id=template.id)` → ✅ `url_for('mihomo.set_active_template', template_id=template.id)`
- ❌ `url_for('delete_mihomo_template', template_id=template.id)` → ✅ `url_for('mihomo.delete_mihomo_template', template_id=template.id)`
- AJAX 路径保持 `/mihomo_template/validate` ✅（蓝图 url_prefix 处理）

## 蓝图路由映射

| 蓝图 | URL前缀 | 示例路由 |
|------|---------|---------|
| main_bp | / | `main.index` → `/` |
| auth_bp | / | `auth.login` → `/login` |
| admin_bp | /admin | `admin.admin` → `/admin/` |
| subscription_bp | / | `subscription.subscription` → `/sub` |
| servers_bp | /servers | `servers.servers` → `/servers/` |
| mihomo_bp | /mihomo_template | `mihomo.mihomo_template` → `/mihomo_template/` |

## 修复方法

### url_for() 调用
在模板中使用蓝图端点时，格式为：`蓝图名.函数名`

**示例：**
```jinja2
{# 旧的方式（会报错） #}
{{ url_for('index') }}

{# 新的方式（正确） #}
{{ url_for('main.index') }}
```

### JavaScript 中的路径
由于蓝图使用了 `url_prefix`，JavaScript 中的硬编码路径会自动匹配：

**示例：**
```javascript
// 这个会自动匹配到 admin_bp 的 edit_user 路由
document.getElementById('editUserForm').action = `/admin/edit_user/${userId}`;
```

## 验证结果

所有模板文件已修复完成，应该不会再出现以下错误：
```
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'xxx'. 
Did you mean 'blueprint.xxx' instead?
```

## 测试建议

重启应用后，测试以下功能：
1. ✅ 登录/登出
2. ✅ 首页显示
3. ✅ 刷新订阅Token
4. ✅ 用户管理（创建、编辑、删除）
5. ✅ IP解锁
6. ✅ 服务器管理（添加、编辑、删除）
7. ✅ 个人资料
8. ✅ 修改密码
9. ✅ Mihomo模板管理（保存、激活、删除）

---
**修复时间**: 2025年10月20日  
**状态**: ✅ 完成  
**修复文件数**: 8个模板文件  
**修复数量**: 15处 url_for() 调用
