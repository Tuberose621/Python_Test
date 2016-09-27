import datetime
import json

from flask import Blueprint, render_template, request, redirect, session, g, make_response
from flask.ext.login import login_required, login_user
from sqlalchemy import or_

from app.common.access import access_control
from app.common.constants import Gender, VisitorPurpose, CameraStatus, UserRole, ScreenType, SubjectType
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.view_helper import get_pagination, page_format, get_subject_list
from app.foundation import db
from app.models import Company, User, Organization, Screen, Subject
from sqlalchemy.sql.expression import and_
from app.common.db_helper import fast_pagination
from app.common.view_helper import _build_query

org = Blueprint('org', __name__, template_folder='templates')


@org.route('/list', methods=['GET'])
@login_required
@access_control('admin')
def get_organization_list():
    params = request.form or request.get_json() or request.args
    page, size = get_pagination(params)
    search = params.get('search')

    query = Organization.query

    if search:
        users = User.query.filter(User.username.contains(search)).all()
        ids = [user.organization_id for user in users]
        query = query.filter(or_(Organization.name.contains(search),
                                 Organization.id.in_(ids)))

    pagination = query.paginate(page, size)
    orgs = []
    for org in pagination.items:
        data = org.get_json()
        data['company_count'] = org.companies.count()
        user = User.query.filter_by(organization_id=org.id, role_id=UserRole.ROLE_ORGANIZATION).first()
        if user:
            data['username'] = user.username
        orgs.append(data)

    return success_result(orgs, page_format(pagination))


@org.route('/', methods=['POST'])
@login_required
@access_control('admin')
def add_organization():
    params = request.form or request.get_json() or request.args
    name = params.get('name')
    remark = params.get('remark')
    username = params.get('username')
    password = params.get('password')

    if not name or not username or not password:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if Organization.query.filter_by(name=name).first() is not None:
        return error_result(ErrorCode.ERROR_ORGANIZATION_ALREADY_EXIST)
    if User.query.filter_by(username=username).first() is not None:
        return error_result(ErrorCode.ERROR_USERNAME_EXISTED)

    org = Organization(name=name, remark=remark, create_time=g.TIMESTAMP)
    db.session.add(org)
    db.session.commit()

    user = User(organization_id=org.id, role_id=UserRole.ROLE_ORGANIZATION,
                username=username, password=password, password_reseted=True)
    db.session.add(user)
    db.session.commit()

    ret = org.get_json()
    ret['username'] = username
    return success_result(ret)


@org.route('/<int:oid>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@access_control('admin')
def organization_info(oid):
    org = Organization.query.get(oid)
    if org is None:
        return error_result(ErrorCode.ERROR_ORGANIZATION_NOT_EXIST)

    if request.method == 'GET':
        user = User.query.filter_by(organization_id=org.id, role_id=UserRole.ROLE_ORGANIZATION).first()
        data = org.get_json()
        if user:
            data['username'] = user.username
        return success_result(data)

    elif request.method == 'PUT':
        params = request.form or request.get_json() or request.args
        username = params.get('username')
        password = params.get('password')
        name = params.get('name')
        remark = params.get('remark')

        if username is not None or password is not None:
            user = User.query.filter_by(organization_id=org.id, role_id=UserRole.ROLE_ORGANIZATION).first()
            if user.username != username and User.query.filter_by(username=username).first() is not None:
                return error_result(ErrorCode.ERROR_USERNAME_EXISTED)
            if username:
                user.username = username
            if password:
                user.password = password
            db.session.add(user)

        if name:
            org.name = name
        if remark:
            org.remark = remark

        db.session.add(org)
        db.session.commit()
        return success_result({})

    elif request.method == 'DELETE':
        db.session.delete(org)
        db.session.commit()
        return success_result({})


@org.route('/unbind/list', methods=['GET'])
@access_control('admin')
@login_required
def unbind_list():

    data = [dict(username=username, name=name, id=cid, role=role_id) for username, name, cid, role_id in
                 db.session.query(User.username, Company.name, Company.id, User.role_id).filter
                 (and_(User.company_id == Company.id, Company.organization_id == None,
                       User.role_id == UserRole.ROLE_ADMIN))]
    return success_result(data)


@org.route('/bind', methods=['POST'])
@access_control('admin')
@login_required
def bind():
    try:
        params = request.get_json()
        oid = params['organization_id']
        companies = set(params['companies'])
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    old_companies =  set([c.id for c in Organization.query.get(oid).companies])
    for new_id in companies-old_companies:
        company = Company.query.get(new_id)
        company.organization_id = oid
        db.session.add(company)
    for remove_id in old_companies-companies:
        company = Company.query.get(remove_id)
        company.organization_id = None
        db.session.add(company)
    db.session.commit()
    return success_result({})


@org.route('/unbind', methods=['POST'])
@access_control('admin')
@login_required
def unbind():
    try:
        params = request.form or request.get_json() or request.args
        cid = params['company']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    company = Company.query.get(cid)
    company.organization_id = None

    db.session.add(company)
    db.session.commit()
    return success_result({})


@org.route('/changeto/<int:oid>')
@access_control('admin')
@login_required
def organization_change(oid):
    user = User.query.filter_by(organization_id=oid, role_id=UserRole.ROLE_ORGANIZATION).first()
    if user:
        login_user(user)

        url = '/organization/subject/employee?organization=true'
        return redirect(url)
    return redirect('/admin')


@org.route('/company/<int:cid>',  methods=['PUT'])
@access_control('organization')
@login_required
def company_info(cid):
    if cid not in g.user.organization.company_ids:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_IN_ORGANIZATION)

    user = User.query.filter_by(company_id=cid, role_id=UserRole.ROLE_ADMIN).first()

    params = request.form or request.get_json() or request.args
    username = params.get('username')
    password = params.get('password')
    name = params.get('name')
    remark = params.get('remark')



    if username or password:
        if username:
            user.username = username
        if password:
            user.password = password
        db.session.add(user)
    
    if name or remark:
        company = Company.query.get(cid)
        if name:
            company.name = name
        if remark:
            company.remark = remark
        db.session.add(company)
        
    db.session.commit()
    return success_result({})


@org.route('/company_account_list')
@access_control('organization')
@login_required
def company_change():
    params = request.args
    page, size = get_pagination(params)
    query = g.user.organization.companies
    org = g.user.organization
    pagination = query.paginate(page, size)
    ret = []
    for company in pagination.items:
        data=dict(name=company.name)
        user = User.query.filter_by(company_id=company.id, role_id=UserRole.ROLE_ADMIN).first()
        if user:
            data['username'] = user.username
            data['remark'] = company.remark
            data['company_id'] = company.id
        ret.append(data)
    return success_result(ret, page_format(pagination))

@org.route('/subject/employee')
@access_control('organization')
@login_required
def subject_employee():
    gender = Gender.state_mapping
    return render_template('page/subject/index.html', subject_type_options=SubjectType.get_select_options(),
                           gender=gender, category='employee', subject_type=SubjectType.TYPE_EMPLOYEE)


@org.route('/subject/visitor')
@access_control('organization')
@login_required
def subject_visitor():
    gender = Gender.state_mapping
    return render_template('page/subject/index.html', subject_type_options=SubjectType.get_select_options(),
                           gender=gender, category='visitor', subject_type=SubjectType.TYPE_VISITOR,
                           purpose=VisitorPurpose.state_mapping)

@org.route('/subject/list/<int:cid>')
@access_control('organization')
@login_required
def subject_list(cid):
    if cid not in g.user.organization.company_ids:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_IN_ORGANIZATION)
    params = request.args
    company = Company.query.get(cid)
    ret = get_subject_list(company, params, is_company=False)
    if ret[0] is None:
        return error_result(ret[1])
    return success_result(ret[0], ret[1])


@org.route('/system/screens')
@access_control('organization')
@login_required
def setting():
    return render_template('page/system/screen.html', boxes={}, camera_status=CameraStatus.state_mapping)

@org.route('/system/screen/<int:cid>')
@access_control('organization')
@login_required
def get_screen(cid):
    if cid not in g.user.organization.company_ids:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_IN_ORGANIZATION)
    screens = Screen.query.filter(Screen.company_id==cid, Screen.type!=ScreenType.FRONT_PAD)\
                          .options(db.eagerload(Screen.allowed_subjects)).all()

    ret = []
    for screen in screens:
        screen = screen.get_json(with_allowed_subjects=True)
        ret.append(screen)

    ret.sort(key=lambda screen: screen['box_address'])
    return success_result(ret)


# TODO
@org.route('/system/account')
@access_control('organization')
@login_required
def account_index():
    return render_template('page/system/account_organization.html')


@org.route('/event/events/<int:cid>')
@access_control('organization')
def events_list(cid):
    if cid not in g.user.organization.company_ids:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_IN_ORGANIZATION)
    params = request.get_json() or request.form or request.args
    current, size = get_pagination(params)
    no_eager_query, query = _build_query(params, cid)
    pagination = fast_pagination(query, current, size, False, count_query=no_eager_query)
    page = page_format(pagination)
    result = [event.get_json(with_subject=True, with_screen=True, with_subject_photos=True) for event in pagination.items]
    return success_result(result, page)
