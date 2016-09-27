# encoding=utf-8
import datetime
import json

from flask import Blueprint, render_template, request, redirect, session, g
from flask.ext.login import login_required, login_user

from app.common.access import access_control
from app.common.constants import UserRole
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.models import Company, User, Box, BoxVersion
from app.foundation import db
from app.common.redis_cache import set_box_bind_cache, clear_sync_local_cache


admin = Blueprint('admin', __name__, template_folder='templates')


@admin.route('/admin')
@login_required
def index():
    if g.user.can_visit('admin') or session.get('admin'):
        admin = User.query.get(1)
        login_user(admin)
    else:
        return redirect('/auth/login')

    companies = Company.query.options(db.joinedload('boxes')).all()
    unused_boxes = Box.query.filter_by(company_id=None).all()

    _companies = []
    for company in companies:
        _company = company.get_json()
        _company['boxes'] = []
        _company['row'] = 0
        for box in company.boxes:
            _box = box.get_json(with_box_version=True)
            _box['screens'] = []
            _box['row'] = 0
            for screen in box.screens.filter_by(type=1):
                _box['screens'].append(screen.get_json())
                _box['row'] += 1
            if not _box['screens']:
                _box['screens'].append({})
                _box['row'] += 1
            _company['boxes'].append(_box)
            _company['row'] += _box['row']
        if not _company['boxes']:
            _company['boxes'] = [{'screens': [{}], 'row': 1, 'box_version': None}]
        _company['row'] = _company['row'] or 1

        _companies.append(_company)

    versions = BoxVersion.query.order_by(BoxVersion.id.desc()).all()

    return render_template('page/admin/index.html', companies=_companies, unused_boxes=unused_boxes, versions=versions)


@admin.route('/admin/company', methods=['POST'])
@access_control('admin')
@login_required
def company_add():
    company = Company(name=request.form['name'])
    company.create_time = g.TIMESTAMP
    db.session.add(company)
    db.session.commit()
    return success_result({})


@admin.route('/admin/company/<int:company_id>', methods=['GET', 'DELETE'])
@access_control('admin')
@login_required
def company(company_id):
    if request.method == 'GET':
        company = Company.query.get(company_id)
        data = {
            "company": company.get_json(),
            "users": [user.get_json() for user in company.users],
            "boxes": [box.get_json() for box in company.boxes]
        }
        return success_result(data)
    elif request.method == 'DELETE':
        return success_result({})


@admin.route('/admin/company/<int:company_id>/user', methods=['POST'])
@access_control('admin')
@login_required
def user_add(company_id):
    params = request.form
    user = User.query.filter_by(username=params['username']).first()
    if user:
        return error_result(ErrorCode.ERROR_USERNAME_EXISTED)

    user = User(company_id=company_id, role_id=UserRole.ROLE_ADMIN,
                username=params['username'], password=params['password'], password_reseted=True)
    db.session.add(user)
    db.session.commit()
    return success_result({})


@admin.route('/admin/company/<int:company_id>/user/<int:user_id>', methods=['DELETE'])
@access_control('admin')
@login_required
def user_delete(company_id, user_id):
    company = Company.query.get(company_id)
    user = User.query.get(user_id)
    if user.role_id == UserRole.ROLE_ROOT:
        return error_result(ErrorCode.ERROR_NOT_ALLOWED)
    company.users.filter_by(id=user_id).delete()
    db.session.commit()
    return success_result({})


@admin.route('/admin/company/<int:company_id>/box', methods=['POST'])
@access_control('admin')
@login_required
def box_add(company_id):
    params = request.form
    box = Box.query.filter_by(box_token=params['box_token']).first()
    if box:
        return error_result(ErrorCode.ERROR_BOX_EXISTED)

    box = Box(company_id=company_id, box_token=params['box_token'])
    db.session.add(box)
    db.session.commit()
    return success_result({})


@admin.route('/admin/company/<int:company_id>/box/bind', methods=['POST'])
@access_control('admin')
@login_required
def box_bind(company_id):
    params = request.form
    box = Box.query.filter_by(box_token=params['box_token']).first()
    box.company_id = company_id
    for screen in box.screens:
        screen.company_id = company_id
    db.session.commit()
    set_box_bind_cache(box.box_token)
    return success_result({})


@admin.route('/admin/company/<int:company_id>/box/<int:box_id>', methods=['DELETE'])
@access_control('admin')
@login_required
def box_unbind(company_id, box_id):
    box = Box.query.filter_by(id=box_id, company_id=company_id).first()
    box.company_id = None
    box.screens.delete()
    db.session.commit()
    clear_sync_local_cache(box.box_token)
    return success_result({})


@admin.route('/admin/changeto/<int:company_id>')
@access_control('admin')
@login_required
def company_change(company_id):
    user = User.query.filter_by(company_id=company_id).first()
    if user:
        login_user(user)
        session['admin'] = 'true'
        return redirect('/')
    return redirect('/admin')


@admin.route('/admin/box-version', methods=['GET', 'POST'])
@access_control('admin')
@login_required
def box_versoin():
    if request.method == 'GET':
        versions = BoxVersion.query.order_by(BoxVersion.id.desc()).all()
        return render_template('page/admin/box_version.html', versions=versions)
    elif request.method == 'POST':
        version = BoxVersion()
        version.version = request.form['name']
        if BoxVersion.query.filter_by(version=version.version).first() is not None:
            return error_result(error=ErrorCode.ERROR_DUPLICATED)
        version.created = datetime.datetime.now()
        db.session.add(version)
        db.session.commit()
        return success_result({})


@admin.route('/admin/box-version/<int:version_id>', methods=['GET', 'PUT'])
@access_control('admin')
@login_required
def box_versoin_detail(version_id):
    if request.method == 'GET':
        version = BoxVersion.query.get(version_id)
        return success_result(version.get_json())
    elif request.method == 'PUT':
        version = BoxVersion.query.get(version_id)
        version.config = request.form['config']
        try:
            json.loads(version.config)
        except:
            return error_result(error=ErrorCode.ERROR_JSON_INVALID)
        db.session.add(version)
        db.session.commit()
        return success_result({})


@admin.route('/admin/box/<int:box_id>/box-version', methods=['PUT'])
@access_control('admin')
@login_required
def box_version_change(box_id):
    box_version_id = request.form['box_version_id']
    Box.query.filter_by(id=box_id).update({'box_version_id': box_version_id})
    db.session.commit()
    return success_result({})
