# encoding=utf-8
import datetime
import json

from flask import Blueprint, render_template, request, redirect, session, g, make_response
from flask.ext.login import login_required, login_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

from app.common.access import access_control
from app.common.constants import UserRole, DeploymentVersion
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.redis_cache import clear_updater_cache, set_box_bind_cache, clear_sync_local_cache
from app.common.tasks import switch_feature_version
from app.common.view_helper import get_pagination, page_format
from app.foundation import db
from app.models import Company, User, Box, BoxVersion, Task


admin = Blueprint('admin2', __name__, template_folder='templates')


@admin.route('/')
@login_required
def index():
    if g.user.can_visit('admin') or session.get('admin'):
        _admin = User.query.get(1)
        login_user(_admin)
    else:
        return redirect('/auth/login')
    html = render_template('page/admin2/index.html', deployment_type_options=DeploymentVersion.get_select_options())
    response = make_response(html)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response


@admin.route('/changeto/<int:company_id>')
@access_control('admin')
@login_required
def company_change(company_id):
    user = User.query.filter_by(company_id=company_id, role_id=UserRole.ROLE_ADMIN).first()
    if user:
        login_user(user)
        session['admin'] = 'true'
        return redirect('/')
    return redirect('/admin')


@admin.route('/company/list', methods=['GET'])
@login_required
@access_control('admin')
def get_company_list():
    params = request.args
    page, size = get_pagination(params)
    search = params.get('search')
    deployment = params.get('deployment')
    scenario = params.get('scenario')
    consigner = params.get('consigner')

    query = Company.query

    if consigner:
        query = query.filter_by(consigner=consigner)

    if search:
        users = User.query.filter(User.username.contains(search)).all()
        ids = map(lambda user: getattr(user, 'company_id'), users)
        query = query.filter(or_(Company.name.contains(search),
                                 Company.id.in_(ids)))

    if deployment and deployment != '0':
        query = query.filter(Company.deployment == deployment)

    if scenario:
        query = query.filter(Company.scenario == scenario)

    pagination = query.options(db.joinedload('screens')) \
        .options(db.joinedload('display_devices')) \
        .add_column(Company.subject_count).order_by(Company.id.desc()).paginate(page, size)
    company_list = []
    for company, subject_count in pagination.items:
        company = company.get_json(with_status=True)
        company['subject_count'] = subject_count
        user = User.query.filter_by(company_id=company['id'], role_id=UserRole.ROLE_ADMIN).first()
        if user:
            company['username'] = user.username
        company_list.append(company)

    deployments = Company.get_deployment_count()
    deployments['0'] = sum(deployments.values())

    data = {
        'companies': company_list,
        'scenarios': Company.get_scenario_count(),
        'deployments': deployments
    }
    return success_result(data, page_format(pagination))


@admin.route('/company', methods=['POST'])
@login_required
@access_control('admin')
def add_company():
    params = request.get_json()
    name = params.get('name')
    deployment = params.get('deployment', DeploymentVersion.ONLINE)
    consigner = params.get('consigner')
    scenario = params.get('scenario')
    remark = params.get('remark')
    username = params.get('username')
    password = params.get('password', '123456')
    feature_version = params.get('feature_version', 3)

    if Company.query.filter_by(name=name).first() is not None:
        return error_result(ErrorCode.ERROR_COMPANY_ALREADY_EXIST)
    if User.query.filter_by(username=username).first() is not None:
        return error_result(ErrorCode.ERROR_USERNAME_EXISTED)

    company = Company(name=name, deployment=deployment, consigner=consigner, scenario=scenario, remark=remark,
                      feature_version=feature_version)
    company.create_time = g.TIMESTAMP
    db.session.add(company)
    db.session.commit()

    functions = params.get('functions')
    if functions:
        company.set_function_status(functions)

    if deployment == DeploymentVersion.OFFLINE:
        meta = params.get('meta')
        company.save_meta_data(meta)

    if username:
        user = User(company_id=company.id, role_id=UserRole.ROLE_ADMIN,
                    username=username, password=password, password_reseted=True)
        db.session.add(user)
    db.session.commit()
    ret = company.get_json(with_status=True)
    ret['username'] = username
    return success_result(ret)


@admin.route('/company/<int:cid>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@access_control('admin')
def company_info(cid):
    company = Company.query.filter_by(id=cid).first()
    if company is None:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_EXIST)
    if request.method == 'GET':
        user = User.query.filter_by(company_id=cid, role_id=UserRole.ROLE_ADMIN).first()
        data = company.get_json(with_status=True)
        if user:
            data['username'] = user.username
        return success_result(data)

    elif request.method == 'PUT':
        params = request.get_json()
        username = params.get('username')
        password = params.get('password')
        fields = ('name', 'deployment', 'consigner', 'scenario', 'remark', 'feature_version')
        old_feature_version = company.feature_version
        company.update(fields, params)
        new_feature_version = int(company.feature_version)

        functions = params.get('functions')
        if functions:
            company.set_function_status(functions)

        if company.deployment == DeploymentVersion.OFFLINE:
            meta = params.get('meta')
            company.save_meta_data(meta)

        if username:
            user = User.query.filter_by(company_id=cid, role_id=UserRole.ROLE_ADMIN).first()
            if user is None:
                if not password:
                    password = '123456'
                user = User(company_id=company.id, role_id=UserRole.ROLE_ADMIN,
                            username=username, password_reseted=True)
            else:
                if user.username != username and User.query.filter_by(username=username).first() is not None:
                    return error_result(ErrorCode.ERROR_USERNAME_EXISTED)
                user.username = username
            if password:
                user.password = password
            db.session.add(user)

            #feature版本的设置在task里进行，这里先给改成原来的版本，因为版本切换有可能失败
            if new_feature_version:
                company.feature_version = old_feature_version
        db.session.commit()

        if old_feature_version != new_feature_version:
            task = Task()
            task.name = u'模型版本切换'
            task.content = u'%s: %s -> %s' % (company.name, old_feature_version, new_feature_version)
            db.session.add(task)
            db.session.commit()
            switch_feature_version.delay(task.id, company.id, new_feature_version)

        ret = company.get_json(with_status=True)
        ret['username'] = username
        return success_result(ret)

    elif request.method == 'DELETE':
        if len(company.boxes) > 0:
            return error_result(ErrorCode.ERROR_NOT_ALLOWED)
        db.session.delete(company)
        db.session.commit()
        return success_result({})


@admin.route('/box')
@access_control('admin')
@login_required
def get_box_info():
    params = request.args
    page, size = get_pagination(params)
    query = Box.query
    if params.get('search'):
        query = query.filter()
        query = query.outerjoin(Box.company).filter(or_(Company.name.contains(params.get('search')),
                                                        Box.box_token.contains(params.get('search'))))
    if params.get('company_id'):
        query = query.join(Box.company).filter_by(id=params.get('company_id'))
    if params.get('version'):
        query = query.join(Box.box_version).filter(BoxVersion.version == params.get('version'))

    # 0 全部, 1 挂了, 2 正常
    if params.get('status') == '1':
        query = query.filter(Box.heartbeat <= g.TIMESTAMP - 120)
    elif params.get('status') == '2':
        query = query.filter(or_(Box.heartbeat > g.TIMESTAMP - 120))

    # 0 全部，1，已绑定，2 未绑定
    if params.get('unused') == '1':
        query = query.filter(Box.company_id != None)
    elif params.get('unused') == '2':
        query = query.filter(Box.company_id == None)

    pagination = query.options(db.joinedload('box_version')) \
        .options(db.joinedload('company')) \
        .options(db.joinedload('all_screens')) \
        .order_by(Box.id.desc()).paginate(page, size)
    boxes = []
    for box in pagination.items:
        doc = box.get_json(with_box_version=True, with_company=True, with_all_screens=True)
        boxes.append(doc)

    used = Box.query.filter(Box.company_id != None).count()
    unused = Box.query.filter(Box.company_id == None).count()
    statistics = {'used': used, 'unused': unused, 'all': used + unused}

    data = {'boxes': boxes, 'statistics': statistics}
    return success_result(data, page_format(pagination))


@admin.route('/company/<int:company_id>/box/bind', methods=['POST'])
@access_control('admin')
@login_required
def box_bind(company_id):
    box_token = request.form.get('box_token')
    if box_token is None:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    box = Box.query.filter_by(box_token=box_token).first()
    if box is None:
        return error_result(ErrorCode.ERROR_BOX_NOT_EXIST)
    box.company_id = company_id

    for screen in box.screens:
        db.session.delete(screen)

    try:
        db.session.commit()
    except IntegrityError:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_EXIST)

    #主机的模型用company的模型版本
    company = Company.query.get(company_id)
    box.model = company.feature_version
    db.session.commit()

    clear_updater_cache(box.box_token)
    set_box_bind_cache(box_token)

    return success_result(box.get_json(with_box_version=True, with_company=True, with_all_screens=True))


@admin.route('/company/<int:company_id>/box/<int:box_id>', methods=['DELETE'])
@access_control('admin')
@login_required
def box_unbind(company_id, box_id):
    box = Box.query.filter_by(id=box_id).first()
    box.company_id = None
    box.screens.delete()
    db.session.commit()

    clear_sync_local_cache(box.box_token)
    return success_result({})


@admin.route('/box/<int:box_id>', methods=['DELETE'])
def box_delete(box_id):
    box = Box.query.filter_by(id=box_id).first()
    box.screens.delete()
    db.session.delete(box)
    db.session.commit()
    return success_result({})


@admin.route('/box-version', methods=['GET', 'POST'])
@access_control('admin')
@login_required
def box_version():
    if request.method == 'GET':
        v = request.args.get('version')
        if v:
            versions = BoxVersion.query.filter(BoxVersion.version.contains(v)).all()
        else:
            versions = BoxVersion.query.order_by(BoxVersion.id.desc()).all()
        ret = []
        for version in versions:
            doc = version.get_json()
            doc['count'] = version.boxes.count()
            ret.append(doc)
        return success_result(ret)

    elif request.method == 'POST':
        params = request.form
        version = BoxVersion()

        fields = ('version', 'config', 'remark')
        version.update(fields, params)

        try:
            json.loads(version.config)
        except ValueError:
            return error_result(error=ErrorCode.ERROR_JSON_INVALID)

        if BoxVersion.query.filter_by(version=version.version).first() is not None:
            return error_result(error=ErrorCode.ERROR_DUPLICATED)
        version.created = datetime.datetime.now()
        db.session.add(version)
        db.session.commit()

        v = BoxVersion.query.filter_by(version=version.version).first()

        return success_result(v.get_json())


@admin.route('/box-version/<int:version_id>', methods=['GET', 'PUT'])
@access_control('admin')
@login_required
def box_version_detail(version_id):
    if request.method == 'GET':
        version = BoxVersion.query.get(version_id)
        return success_result(version.get_json())
    elif request.method == 'PUT':
        version = BoxVersion.query.get(version_id)
        version.config = request.form['config']
        version.remark = request.form['remark']
        try:
            json.loads(version.config)
        except ValueError:
            return error_result(error=ErrorCode.ERROR_JSON_INVALID)
        db.session.add(version)
        db.session.commit()
        return success_result(version.get_json())


@admin.route('/box/<int:box_id>/box-version', methods=['PUT'])
@access_control('admin')
@login_required
def box_version_change(box_id):
    box_version_id = request.form['box_version_id']

    box = Box.query.get(box_id)
    box.box_version_id = box_version_id
    db.session.commit()
    clear_updater_cache(box.box_token)

    version = BoxVersion.query.get(box_version_id)
    return success_result(version.get_json())


@admin.route('/box/<int:box_id>/facemin', methods=['PUT'])
@access_control('admin')
@login_required
def box_facemin_change(box_id):
    facemin = request.form['facemin']
    box = Box.query.get(box_id)
    box.facemin = facemin
    db.session.commit()
    clear_updater_cache(box.box_token)
    return success_result()


@admin.route('/box/<int:box_id>/model', methods=['PUT'])
@access_control('admin')
@login_required
def box_model_change(box_id):
    model = request.form['model']
    box = Box.query.get(box_id)
    box.model = model
    db.session.commit()
    clear_updater_cache(box.box_token)
    return success_result()


@admin.route('/task')
@access_control('admin')
@login_required
def task_list():
    params = request.args
    page, size = get_pagination(params)
    pagination = Task.query.order_by(Task.id.desc()).paginate(page, size)
    result = []
    for task in pagination.items:
        result.append(task.get_json())
    return success_result(result, page_format(pagination))


@admin.route('/box/<int:box_id>', methods=['PUT'])
@access_control('admin')
@login_required
def box_leaf_config_change(box_id):
    params = request.get_json()
    box = Box.query.get(box_id)
    leaf_config = params.get('leaf_config')
    if leaf_config:
        for k in ('-video.facemin', '-threshold', '-unthreshold', '-verify'):
            v = leaf_config.get(k)
            if v:
                leaf_config[k] = int(v)
        v = leaf_config.get('-quality')
        leaf_config['-quality'] = float(v)
        box.leaf_config = json.dumps(leaf_config)
    if params.get('box_version_id'):
        box.box_version_id = params.get('box_version_id')
    if params.get('model'):
        box.model = params.get('model')
    db.session.commit()
    clear_updater_cache(box.box_token)
    return success_result()
