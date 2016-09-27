# coding=utf-8
__author__ = 'ding'
from cStringIO import StringIO
import os
import time
import uuid
from datetime import datetime, date, timedelta

from flask import Blueprint, request, g, session, abort, url_for
from sqlalchemy import desc
from PIL import Image

from app.common.json_builder import error_result, success_result
from app.common.error_code import ErrorCode
from app.common.constants import SubjectType, weekdays
from app.common.view_helper import subject_login_required, build_status_query,\
    timestamp_to_timestring, update_company_data_version, create_user_photo
from app.models import Event, Subject, VisitorHistory, Attendance, Photo, PhotoAlternative
from app.models.Attendance import is_holiday
from app.foundation import db, storage
from config import DOMAIN

mobile = Blueprint('mobile', __name__)


@mobile.route('/mobile/login', methods=['POST'])
def login():
    params = request.form or request.get_json()
    username = params.get('username')
    password = params.get('password')
    mobile_os = int(params.get('os', 0))
    if not username or not password:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    subject = Subject.query.filter_by(email=username).first()
    if not subject:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)

    if not subject.check_password(password):
        return error_result(ErrorCode.ERROR_PASSWORD_ERROR)

    if not subject.check_mobile_os(mobile_os):
        subject.add_mobile_os(mobile_os)
        db.session.commit()
    session['subject_id'] = subject.id
    ret = subject.get_json()
    ret['company_name'] = subject.company.name
    ret['boxes'] = [box.get_json() for box in subject.company.boxes]
    return success_result(ret)


@mobile.route('/mobile/update-password', methods=['POST'])
@subject_login_required
def update_password():
    params = request.form or request.get_json()
    password = params.get('password')
    password_verification = params.get('password_verification')

    if not password or not password_verification:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if password != password_verification:
        return error_result(ErrorCode.ERROR_PASSWORD_INCONSISTENT)

    subject = g.subject
    subject.password_reseted = True
    subject.password = password
    db.session.add(subject)
    db.session.commit()
    return success_result(subject.get_json())


@mobile.route('/mobile/user-info', defaults={'subject_id': None}, methods=['GET', 'PUT'])
@mobile.route('/mobile/visitor/<int:subject_id>', methods=['GET', 'PUT', 'DELETE'])
@subject_login_required
def user_info(subject_id):
    if subject_id is None:
        subject = g.subject
    else:
        subject = g.subject.visitors.filter_by(id=subject_id).first()
        if subject is None:
            return abort(404)

    if request.method == 'GET':
        attendance = subject.attendances.filter_by(date=date.today()).first()
        ret = subject.get_json(with_photos=True)
        ret['holiday'] = is_holiday(g.subject.company_id, date.today())
        ret['today'] = time.time()
        ret['clock_in'] = u'无'
        ret['clock_out'] = u'无'

        if attendance and attendance.earliest_record:
            ret['clock_in'] = timestamp_to_timestring(attendance.earliest_event.timestamp)
        if attendance and attendance.latest_record:
            ret['clock_out'] = timestamp_to_timestring(attendance.latest_event.timestamp)
        ret['boxes'] = [box.get_json() for box in subject.company.boxes]
        return success_result(ret)
    elif request.method == 'PUT':
        params = request.form or request.get_json()
        fields = (
            'description',
            'avatar',
            'start_time',
            'end_time',
            'title',
            'gender',
            'department',
            'name',
            'email',
            'phone',
            'purpose',
            'interviewee',
            'come_from',
            'job_number',
            'remark',
            'visit_notify',
            'subject_type'
        )
        subject.update(fields, params)
        if params.get('birthday'):
            subject.birthday = date.fromtimestamp(int(params['birthday']))
        db.session.add(subject)
        db.session.commit()
        update_company_data_version(subject.company, subject.id)
        return success_result(subject.get_json())
    elif request.method == 'DELETE':
        subject = Subject.query.get(subject_id)
        if subject is None:
            return abort(404)
        if g.subject.visitors.filter_by(id=subject_id).first() is None:
            return error_result(ErrorCode.ERROR_NOT_ALLOWED)
        for photo in subject.photos:
            storage.remove(photo.url)
        company = subject.company
        db.session.delete(subject)
        db.session.commit()
        update_company_data_version(company, subject.id)
        return success_result()


@mobile.route('/mobile/update-avatar', defaults={'subject_id':None}, methods=['POST'])
@mobile.route('/mobile/visitor/update-avatar/<int:subject_id>', methods=['POST'])
@subject_login_required
def update_avatar(subject_id):
    if subject_id is None:
        subject = g.subject
    else:
        subject = g.subject.visitors.filter_by(id=subject_id).first()
        if subject is None:
            return abort(404)

    avatar_file = request.files.get('avatar')
    if avatar_file is None:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    uri = storage.save_image(avatar_file.stream, 'avatar', resize=(300, 300))
    if not uri:
        return error_result(ErrorCode.ERROR_UNKNOWN)
    subject.avatar = uri
    db.session.add(subject)
    db.session.commit()
    update_company_data_version(subject.company, subject.id)
    return success_result(subject.get_json())


@mobile.route('/mobile/attendance/list')
@subject_login_required
def get_attendance_list():
    params = request.args or request.get_json() or {}
    try:
        start = int(params.get('start'))
        end = int(params.get('end'))
        status = int(params.get('status', -1))

        start_date = date.fromtimestamp(start)
        end_date = date.fromtimestamp(end)
        status = int(status) if status != '' else status
    except:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(10)
        status = -1

    subject = g.subject
    query = Attendance.query.filter(Attendance.subject_id == subject.id,
                                    Attendance.date >= start_date,
                                    Attendance.date <= end_date)
    if status != -1:
        query = build_status_query(query, status)
    attendances = query.order_by(desc(Attendance.date)).all()
    records = [attendance.get_json(with_holiday=True) for attendance in attendances]
    result = {
        'records': records,
    }
    return success_result(result)


seconds_a_day = 24 * 60 * 60
@mobile.route('/mobile/attendance/day')
@subject_login_required
def get_attendance_someday():
    params = request.args or request.get_json() or {}
    try:
        date_ts = int(params['date'])
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    start_ts = date_ts
    end_ts = start_ts + seconds_a_day
    subject = g.subject
    events = subject.company.events.filter(Event.subject_id == subject.id,
                                           Event.timestamp < end_ts,
                                           Event.timestamp >= start_ts).order_by(desc(Event.timestamp)).all()
    weekday = datetime.fromtimestamp(date_ts).weekday()
    result = {
        'date': date_ts,
        'weekday': weekdays[weekday],
        'records': []
    }
    for event in events:
        item = event.get_json()
        item['position'] = event.screen.camera_position if event.screen else u'手机签到'
        result['records'].append(item)
    return success_result(result)


@mobile.route('/mobile/add-visitor', methods=['POST'])
@mobile.route('/mobile/visitor', methods=['POST'])
@subject_login_required
def add_visitor():
    params = request.form

    try:
        name = params['name']
        photo = request.files.get('photo')
        purpose = params.get('purpose')
        interviewee = params.get('interviewee')
        inviter_id = g.subject.id
        come_from = params.get('come_from')
        phone = params.get('phone')
        remark = params.get('remark')
        description = params.get('description')
        company_id = g.subject.company_id
        start_time = int(params.get('start_time', 0))
        end_time = int(params.get('end_time', 0))
        vip = bool(int(params.get('vip', False)))
        subject_type = int(params.get('subject_type', 1))
    except:
        import traceback; print traceback.format_exc()
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not start_time or not end_time:
        start_time = g.TIMESTAMP - 5 * 60
        end_time = g.TIMESTAMP + 2 * 3600

    if vip:
        subject_type = SubjectType.TYPE_VIP

    if interviewee is None:
        interviewee = g.subject.name

    subject = Subject(company_id=company_id, name=name, subject_type=subject_type, remark=remark, description=description,
                      start_time=start_time, end_time=end_time, purpose=purpose, interviewee=interviewee,
                      inviter_id=inviter_id, come_from=come_from, phone=phone, password='123456', create_time=g.TIMESTAMP)
    db.session.add(subject)
    db.session.commit()

    if photo:
        photo, error = create_user_photo(photo, subject.company_id)
        if error:
            return error
        subject.photos.append(photo)
        update_company_data_version(g.subject.company, subject.id)

    return success_result(subject.get_json())


@mobile.route('/mobile/visitors')
@subject_login_required
def visitors():
    ret = []
    visitors = g.subject.visitors.options(db.eagerload_all(Subject.photos)).all()
    for visitor in visitors:
        ret.append(visitor.get_json(with_photos=True))
    return success_result(ret)


@mobile.route('/mobile/visitors/history')
@subject_login_required
def visitors_history():
    try:
        start_id = int(request.args.get('start_id', 0))
        visitor_id = int(request.args.get('visitor_id', 0))
        visitor_name = request.args.get('visitor_name')
        size = int(request.args.get('size', 20))
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    result = []

    # query event for specific visitor
    if visitor_id:
        query = Event.query.filter(Event.subject_id==visitor_id)
        if start_id:
            query = query.filter(Event.id < start_id)
        items = query.order_by(Event.id.desc()).limit(size).all()
        for item in items:
            result.append(item.get_json(with_subject=True, with_screen=False, with_subject_photos=True))

    # query visitor_history for no-specific visitor
    else:
        if visitor_name:
            visitor_name = visitor_name.replace('\\', '\\\\')
            visitor_ids = db.session.query(Subject.id).filter(
                Subject.company_id == g.subject.company_id,
                Subject.subject_type != SubjectType.TYPE_EMPLOYEE,
                Subject.real_name.contains(visitor_name)).all()
        else:
            visitor_ids = db.session.query(Subject.id).filter(Subject.inviter_id == g.subject.id).all()

        visitor_ids = [item[0] for item in visitor_ids]

        if start_id:
            query = VisitorHistory.query.filter(VisitorHistory.id < start_id)
        else:
            query = VisitorHistory.query
        items = query.filter(VisitorHistory.subject_id.in_(visitor_ids)).order_by(VisitorHistory.id.desc()).limit(size).all()
        for item in items:
            event = item.event.get_json(with_subject=True, with_screen=False, with_subject_photos=True)
            event['id'] = item.id # 猥琐的将event.id 改为history.id 为了保持之前的接口一致
            result.append(event)

    return success_result(result)


@mobile.route('/mobile/subject/photo', methods=['POST'])
@subject_login_required
def subject_photo_create():
    try:
        payload = request.files['photo']
        subject_id = int(request.form['subject_id'])
        old_photo_id = int(request.form.get('old_photo_id', 0))
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not payload:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if g.subject.visitors.filter_by(id=subject_id).first() is None:
        return error_result(ErrorCode.ERROR_NOT_ALLOWED)

    photo, error = create_user_photo(payload, g.subject.company_id)
    if error:
        return error
    photo.subject_id = subject_id
    db.session.add(photo)
    db.session.commit()

    #delete old photo
    if old_photo_id:
        old_photo = Photo.query.get(old_photo_id)
        if old_photo.subject.inviter_id != g.subject.id:
            return error_result(ErrorCode.ERROR_NOT_ALLOWED)
        storage.remove(old_photo.url)
        db.session.delete(old_photo)
        db.session.query(PhotoAlternative).filter(PhotoAlternative.subject_id == old_photo.subject_id). \
                                           filter(PhotoAlternative.url == old_photo.url).delete()
        db.session.commit()
    if subject_id:
        update_company_data_version(g.subject.company, subject_id)
    return success_result(photo.get_json())

@mobile.route('/mobile/subject/photo/<int:photo_id>', methods=['DELETE'])
@subject_login_required
def subject_photo_delete(photo_id):
    photo = Photo.query.get(photo_id)
    subject = Subject.query.get(photo.subject_id)

    if photo is None:
        return abort(404)

    if g.subject.visitors.filter_by(id=photo.subject_id).first() is None:
        return error_result(ErrorCode.ERROR_NOT_ALLOWED)

    storage.remove(photo.url)
    db.session.delete(photo)
    db.session.query(PhotoAlternative).filter(PhotoAlternative.subject_id == photo.subject_id).\
                                       filter(PhotoAlternative.url == photo.url).delete()
    db.session.commit()
    update_company_data_version(g.subject.company, subject.id)
    return success_result({})


@mobile.route('/mobile/subject/invite-link', methods=['GET'])
@subject_login_required
def subject_invite_link():
    visitor_id = request.args.get('visitor_id')
    if not visitor_id:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    visitor = g.subject.visitors.filter_by(id=visitor_id).first()
    if visitor is None:
        return error_result(ErrorCode.ERROR_NOT_ALLOWED)
    if not visitor.job_number:
        visitor.job_number = str(uuid.uuid4())
        db.session.commit()
    url = '%s/subject/invite?subject_id=%s&token=%s' % (DOMAIN, visitor_id, visitor.job_number)
    return success_result({'url': url})
