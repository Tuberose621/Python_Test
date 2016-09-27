# coding=utf-8
__author__ = 'ding'

from flask import Blueprint, g, request
from flask.ext.login import login_required
from sqlalchemy import desc, or_
from sqlalchemy.orm import eagerload_all

from app.common.json_builder import error_result, success_result
from app.models import Subject
from app.common.constants import SubjectType, AccountPermission
from app.common.error_code import ErrorCode
from app.foundation import db
from app.common.view_helper import get_pagination, page_format


mobile_admin = Blueprint('mobile_admin', __name__)


@mobile_admin.route('/mobile-admin/subjects', methods=['GET'])
@login_required
def subjects():
    subjects = g.user.company.subjects.options(eagerload_all(Subject.photos)).order_by(desc(Subject.id)).all()
    ret = []
    for subject in subjects:
        item = subject.get_json(with_photos=True)
        ret.append(item)
        item['photo_ids'] = []
        for photo in item['photos']:
            item['photo_ids'].append(photo['id'])
    return success_result(ret)


@mobile_admin.route('/mobile-admin/subjects/list', methods=['GET', 'POST'])
@login_required
def subjects_list():
    ORDER_TYPE_TIME = 'time'
    ORDER_TYPE_NAME = 'name'
    params = request.args
    name = params.get('name')
    category = params.get('category')
    order = params.get('order')
    subject_type = SubjectType.parse_param(category)
    if subject_type is None:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    if ((subject_type == SubjectType.TYPE_VISITOR and not g.user.has_permission(AccountPermission.ADD_VISITOR)) or
            (subject_type == SubjectType.TYPE_EMPLOYEE and not g.user.has_permission(AccountPermission.ADD_EMPLOYEE))):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    query = g.user.company.subjects.options(db.eagerload_all(Subject.photos))
    if name:
        name = name.replace('\\', '\\\\')
        query = query.filter(Subject.real_name.contains(name) | Subject.pinyin.contains(name))
    if subject_type is not None:
        if subject_type == SubjectType.TYPE_VISITOR:
            # VIP is visitor, too
            query = query.filter(or_(Subject.subject_type == SubjectType.TYPE_VISITOR,
                                     Subject.subject_type == SubjectType.TYPE_VIP))
        else:
            query = query.filter_by(subject_type=subject_type)

    #TODO add index to start_time and pinyin ...
    if order == ORDER_TYPE_TIME:
        query = query.order_by(Subject.start_time.desc())
    elif order == ORDER_TYPE_NAME:
        query = query.order_by(Subject.pinyin.asc())
    else:
        query = query.order_by(Subject.start_time.desc())

    current, size = get_pagination(params)
    pagination = query.paginate(current, size, False)
    page = page_format(pagination)
    ret = [subject.get_json(with_photos=True, with_visitor_type=True) for subject in pagination.items]
    return success_result(ret, page)
