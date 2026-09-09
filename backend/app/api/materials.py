"""
物料管理API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import or_, and_
from datetime import datetime
from difflib import SequenceMatcher
import re
from app import db
from app.models import Material, Category, Supplier, OperationRecord
from app.api.auth import admin_required, get_current_user_id
from app.api.alerts import sync_material_alert
from app.utils.helpers import generate_code, paginate

materials_bp = Blueprint('materials', __name__)


@materials_bp.route('', methods=['GET'])
@jwt_required()
def get_materials():
    """获取物料列表"""
    # 查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', type=int)
    status = request.args.get('status', '')
    
    # 构建查询
    query = Material.query
    
    if keyword:
        query = query.filter(
            or_(
                Material.name.contains(keyword),
                Material.code.contains(keyword),
                Material.spec.contains(keyword)
            )
        )
    
    if category_id:
        query = query.filter(Material.category_id == category_id)
    
    if status:
        query = query.filter(Material.status == status)
    
    # 排序和分页
    query = query.order_by(Material.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'data': {
            'items': [m.to_dict() for m in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'per_page': per_page
        }
    })


@materials_bp.route('/<int:id>', methods=['GET'])
@jwt_required()
def get_material(id):
    """获取物料详情"""
    material = Material.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': material.to_dict()
    })


@materials_bp.route('', methods=['POST'])
@admin_required
def create_material():
    """创建新物料（管理员）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    name = (data.get('name') or '').strip() or '待补充物料'
    category_id = data.get('category_id') or None
    stock = data.get('stock', 0)
    if stock is None or int(stock) < 0:
        return jsonify({'success': False, 'message': '库存不能为负数'}), 400
    
    # 检查物料编号是否已存在
    if data.get('code'):
        existing = Material.query.filter_by(code=data['code']).first()
        if existing:
            return jsonify({'success': False, 'message': '物料编号已存在'}), 400
    else:
        # 自动生成编号
        data['code'] = f"TEMP-{datetime.now().strftime('%m%d%H%M%S')}"
    
    # 创建物料
    material = Material(
        code=data['code'],
        name=name,
        category_id=category_id,
        spec=data.get('spec', ''),
        unit=data.get('unit', '个'),
        stock=int(stock),
        threshold=data.get('threshold', 10),
        location=data.get('location', ''),
        supplier_id=data.get('supplier_id'),
        remark=data.get('remark', '') or ('待补充物料信息' if name == '待补充物料' else '')
    )
    
    material.update_status()
    
    db.session.add(material)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '物料创建成功',
        'data': material.to_dict()
    }), 201


@materials_bp.route('/<int:id>', methods=['PUT'])
@admin_required
def update_material(id):
    """更新物料（管理员）"""
    material = Material.query.get_or_404(id)
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    # 更新字段
    if 'code' in data and data['code'] != material.code:
        existing = Material.query.filter_by(code=data['code']).first()
        if existing:
            return jsonify({'success': False, 'message': '物料编号已存在'}), 400
        material.code = data['code']
    if 'name' in data:
        material.name = data['name']
    if 'category_id' in data:
        material.category_id = data['category_id']
    if 'spec' in data:
        material.spec = data['spec']
    if 'unit' in data:
        material.unit = data['unit']
    if 'stock' in data:
        material.stock = data['stock']
    if 'threshold' in data:
        material.threshold = data['threshold']
    if 'location' in data:
        material.location = data['location']
    if 'supplier_id' in data:
        material.supplier_id = data['supplier_id']
    if 'remark' in data:
        material.remark = data['remark']
    
    # 更新状态
    material.update_status()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '物料更新成功',
        'data': material.to_dict()
    })


@materials_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def delete_material(id):
    """删除物料（管理员）"""
    material = Material.query.get_or_404(id)

    related_records = {
        '采购申请': material.purchase_requests.count(),
        '借用记录': material.borrow_records.count(),
        '出入库记录': material.operation_records.count(),
        '库存预警': material.alerts.count()
    }
    related_summary = [f'{name}{count}条' for name, count in related_records.items() if count]
    if related_summary:
        return jsonify({
            'success': False,
            'message': f"该物料存在{'、'.join(related_summary)}，为保留历史记录无法删除"
        }), 400
    
    db.session.delete(material)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '物料删除成功'
    })


@materials_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_categories():
    """获取物料分类列表"""
    categories = Category.query.all()
    return jsonify({
        'success': True,
        'data': [c.to_dict() for c in categories]
    })


@materials_bp.route('/import', methods=['POST'])
@admin_required
def import_materials():
    """从 Excel 导入并智能匹配库存（管理员）"""
    data = request.get_json() or {}
    rows = data.get('items', [])

    if not isinstance(rows, list) or not rows:
        return jsonify({'success': False, 'message': '导入数据不能为空'}), 400

    imported = []
    skipped = []

    def text(value):
        return str(value or '').strip()

    def normalise(value):
        return re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', text(value).lower())

    def similarity(left, right):
        left, right = normalise(left), normalise(right)
        if not left or not right:
            return 0
        if left == right:
            return 1
        if left in right or right in left:
            return 0.94
        return SequenceMatcher(None, left, right).ratio()

    def parse_date(value):
        value = text(value).replace('/', '.').replace('-', '.')
        if not value or value == '.':
            return None
        for fmt in ('%Y.%m.%d', '%Y.%m.%d %H:%M:%S', '%Y.%m.%d %H:%M'):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def parse_int(value, default=0):
        if value in (None, ''):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            digits = ''.join(ch for ch in str(value) if ch.isdigit())
            return int(digits) if digits else default

    existing_materials = Material.query.all()
    existing_categories = Category.query.all()
    for index, row in enumerate(rows, start=1):
        name = text(row.get('name') or row.get('物料名称') or row.get('物品名称') or row.get('名称') or row.get('物品') or row.get('产品名称'))
        code = text(row.get('code') or row.get('物料编号') or row.get('编号'))
        spec = text(row.get('spec') or row.get('规格') or row.get('规格型号'))
        quantity = parse_int(row.get('stock') or row.get('数量') or row.get('库存数量') or row.get('采购数量'), 0)
        if quantity <= 0:
            skipped.append({'row': index, 'reason': '数量为空或小于等于0'})
            continue

        arrival_date = parse_date(row.get('arrival_date') or row.get('采购到位日期') or row.get('到货日期'))
        purchase_date = parse_date(row.get('purchase_date') or row.get('申购日期') or row.get('采购日期'))
        operation_date = arrival_date or purchase_date
        date_note = ''
        if operation_date:
            date_note = f"入库日期: {operation_date.strftime('%Y-%m-%d')}" + ('（采购到位日期为空，使用申购日期）' if not arrival_date and purchase_date else '')

        matched = None
        match_type = 'unmatched'
        if code:
            matched = Material.query.filter_by(code=code).first()
            if matched:
                match_type = '编号精确匹配'

        if not matched and name:
            target = normalise(name)
            exact = [m for m in existing_materials if normalise(m.name) == target]
            if len(exact) == 1:
                matched, match_type = exact[0], '名称精确匹配'
            elif not exact and target:
                scored = sorted(
                    ((similarity(target, m.name), m) for m in existing_materials if m.name),
                    key=lambda item: item[0], reverse=True
                )
                if scored and scored[0][0] >= 0.78 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.10):
                    matched, match_type = scored[0][1], '名称高置信度模糊匹配'

        category_name = text(row.get('category_name') or row.get('分类') or row.get('物料分类'))
        category = None
        if category_name:
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                target = normalise(category_name)
                exact = [c for c in existing_categories if normalise(c.name) == target]
                if len(exact) == 1:
                    category = exact[0]
                else:
                    scored = sorted(
                        ((similarity(target, c.name), c) for c in existing_categories if c.name),
                        key=lambda item: item[0], reverse=True
                    )
                    if scored and scored[0][0] >= 0.86 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.10):
                        category = scored[0][1]
            if not category:
                category = Category(
                    name=category_name,
                    code=f'cat_{datetime.now().strftime("%y%m%d%H%M%S%f")[-16:]}',
                    description='Excel导入自动创建'
                )
                db.session.add(category)
                db.session.flush()
                existing_categories.append(category)

        raw_remark = text(row.get('remark') or row.get('备注'))
        source_note = f"Excel第{index}行；{date_note}" if date_note else f"Excel第{index}行"
        if matched:
            stock_before = matched.stock
            matched.stock += quantity
            matched.update_status()
            sync_material_alert(matched)
            record = OperationRecord(
                operation_no=generate_code('I'), type='in', user_id=get_current_user_id(),
                material_id=matched.id, material_name=matched.name, quantity=quantity,
                stock_before=stock_before, stock_after=matched.stock,
                related_type='excel_import', remark=f'{source_note}；{match_type}；{raw_remark}'.strip('；'),
                created_at=operation_date
            )
            db.session.add(record)
            imported.append({'row': index, 'action': 'merge', 'match_type': match_type, 'material': matched.to_dict()})
            continue

        incomplete = not name or not code or not category
        material_name = name or f'待补充物料-{index}'
        material_code = code or f'TEMP-{datetime.now().strftime("%m%d%H%M%S")}-{index}'
        if len(material_code) > 20:
            material_code = f'TEMP-{index:04d}'
        material = Material(
            code=material_code,
            name=material_name,
            category_id=category.id if category else row.get('category_id'),
            spec=spec,
            unit=text(row.get('unit') or row.get('单位')) or '个',
            stock=quantity,
            threshold=parse_int(row.get('threshold') or row.get('预警阈值') or row.get('预设阀值') or row.get('预设阈值'), 10),
            location=row.get('location') or row.get('存放位置') or row.get('地区') or '',
            remark=f'{source_note}；{"待补充物料编号；" if not code else ""}{"待补充分类；" if not category else ""}{"待补充物料名称；" if not name else ""}{raw_remark}'.strip('；'),
            created_at=operation_date
        )
        material.update_status()
        db.session.add(material)
        db.session.flush()
        existing_materials.append(material)
        imported.append({'row': index, 'action': 'create_incomplete' if incomplete else 'create', 'match_type': '未匹配，已建立新物料', 'material': material.to_dict()})

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功处理 {len(imported)} 条，跳过 {len(skipped)} 条；已匹配库存会自动叠加',
        'data': {
            'imported': imported,
            'skipped': skipped
        }
    })


@materials_bp.route('/categories', methods=['POST'])
@admin_required
def create_category():
    """创建分类（管理员）"""
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('code'):
        return jsonify({'success': False, 'message': '名称和编码不能为空'}), 400
    
    # 检查编码是否已存在
    existing = Category.query.filter_by(code=data['code']).first()
    if existing:
        return jsonify({'success': False, 'message': '分类编码已存在'}), 400
    
    category = Category(
        name=data['name'],
        code=data['code'],
        description=data.get('description', '')
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '分类创建成功',
        'data': category.to_dict()
    }), 201


@materials_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_material_stats():
    """获取物料统计信息"""
    from sqlalchemy import func
    
    total = Material.query.count()
    normal = Material.query.filter_by(status='normal').count()
    warning = Material.query.filter_by(status='warning').count()
    danger = Material.query.filter_by(status='danger').count()
    
    # 按分类统计
    category_stats = db.session.query(
        Category.name,
        func.count(Material.id)
    ).join(Material).group_by(Category.id).all()
    
    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'normal': normal,
            'warning': warning,
            'danger': danger,
            'category_stats': [{'name': name, 'count': count} for name, count in category_stats]
        }
    })


@materials_bp.route('/low-stock', methods=['GET'])
@jwt_required()
def get_low_stock_materials():
    """获取低库存物料"""
    materials = Material.query.filter(
        Material.stock <= Material.threshold
    ).order_by(Material.stock.asc()).all()
    
    return jsonify({
        'success': True,
        'data': [m.to_dict() for m in materials]
    })
