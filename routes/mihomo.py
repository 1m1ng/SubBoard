"""Mihomo模板管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from utils.extensions import db, logger
from models import MihomoTemplate
from utils.decorators import admin_required
import yaml

mihomo_bp = Blueprint('mihomo', __name__, url_prefix='/mihomo_template')


@mihomo_bp.route('/')
@admin_required
def mihomo_template():
    """Mihomo 模板管理页面"""
    # 获取所有模板
    templates = MihomoTemplate.query.all()
    active_template = MihomoTemplate.query.filter_by(is_active=True).first()
    
    return render_template('mihomo_template.html', templates=templates, active_template=active_template)


@mihomo_bp.route('/save', methods=['POST'])
@admin_required
def save_mihomo_template():
    """保存 Mihomo 模板"""
    name = request.form.get('name', '默认模板')
    template_content = request.form.get('template_content')
    set_active = request.form.get('set_active') == 'true'
    
    if not template_content:
        flash('模板内容不能为空！', 'error')
        return redirect(url_for('mihomo.mihomo_template'))
    
    # 验证 YAML 格式
    try:
        yaml.safe_load(template_content)
    except yaml.YAMLError as e:
        flash(f'YAML 格式错误: {str(e)}', 'error')
        return redirect(url_for('mihomo.mihomo_template'))
    
    try:
        # 如果设置为活动模板，先取消其他模板的活动状态
        if set_active:
            MihomoTemplate.query.update({MihomoTemplate.is_active: False})
        
        # 检查是否已存在同名模板
        template = MihomoTemplate.query.filter_by(name=name).first()
        if template:
            # 更新现有模板
            template.template_content = template_content
            template.is_active = set_active
            template.updated_at = datetime.utcnow()
        else:
            # 创建新模板
            template = MihomoTemplate(name=name, template_content=template_content, is_active=set_active)  # type: ignore
            db.session.add(template)
        
        db.session.commit()
        logger.info(f'管理员保存了 Mihomo 模板: {name}')
        flash(f'模板 {name} 保存成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存模板失败: {str(e)}")
        flash('保存模板失败！', 'error')
    
    return redirect(url_for('mihomo.mihomo_template'))


@mihomo_bp.route('/delete/<int:template_id>')
@admin_required
def delete_mihomo_template(template_id):
    """删除 Mihomo 模板"""
    template = db.session.get(MihomoTemplate, template_id)
    if not template:
        flash('模板不存在！', 'error')
        return redirect(url_for('mihomo.mihomo_template'))
    
    try:
        db.session.delete(template)
        db.session.commit()
        logger.info(f'管理员删除了 Mihomo 模板: {template.name}')
        flash(f'模板 {template.name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除模板失败: {str(e)}")
        flash('删除模板失败！', 'error')
    
    return redirect(url_for('mihomo.mihomo_template'))


@mihomo_bp.route('/set_active/<int:template_id>')
@admin_required
def set_active_template(template_id):
    """设置活动模板"""
    try:
        # 取消所有模板的活动状态
        MihomoTemplate.query.update({MihomoTemplate.is_active: False})
        
        # 设置指定模板为活动
        template = db.session.get(MihomoTemplate, template_id)
        if template:
            template.is_active = True
            db.session.commit()
            logger.info(f'管理员设置 Mihomo 模板为活动: {template.name}')
            flash(f'已将 {template.name} 设置为活动模板！', 'success')
        else:
            flash('模板不存在！', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"设置活动模板失败: {str(e)}")
        flash('设置活动模板失败！', 'error')
    
    return redirect(url_for('mihomo.mihomo_template'))


@mihomo_bp.route('/validate', methods=['POST'])
@admin_required
def validate_yaml():
    """验证 YAML 格式的 API"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return {'valid': False, 'error': '内容为空'}
        
        # 尝试解析 YAML
        yaml.safe_load(content)
        return {'valid': True}
    except yaml.YAMLError as e:
        return {'valid': False, 'error': str(e)}
    except Exception as e:
        return {'valid': False, 'error': f'验证失败: {str(e)}'}
