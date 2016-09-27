# encoding=utf-8
__author__ = 'wang'

import datetime
import json
from _mysql import IntegrityError

from flask import Blueprint, request, Response, g, session
from flask.ext.login import login_required
from flask.ext.socketio import emit, join_room
from app.common.constants import SubjectType, ScreenType, AccountPermission
from app.common.error_code import ErrorCode
from app.common.json_builder import error_result, success_result
from app.common.redis_cache import cache_etag
from app.common.utility import get_tag_from_request
from app.common.view_helper import record_attendance, push_message, update_company_data_version
from app.common.view_helper import update_event_statistics
from app.foundation import db, socketio, redis, storage
from app.models import Company, Event, Screen, User, Box, AccessCalendar, Subject, VisitorHistory, Photo, SubjectVersion
from config import PUSH_AVAILABLE


sync = Blueprint('sync', __name__)


@sync.route('/sync/event', methods=['POST'])
def sync_event():
    params = request.form or request.get_json()
    screen_token = params.get('screen_token')
    photo = params.get('photo')
    subject_id = params.get('subject_id')
    age = params.get('age')
    gender = params.get('gender')
    group = params.get('group')
    short_group = params.get('short_group')
    quality = params.get('quality')
    confidence = params.get('confidence')

    screen_id = None
    subject = None
    company = None
    camera_position = None

    if not photo or (not screen_token and not subject_id):
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    if screen_token:
        screen = Screen.query.filter_by(token=screen_token).first()
        if screen:
            screen_id = screen.id
            company = screen.company
            camera_position = screen.camera_position
    if subject_id:
        subject = Subject.query.filter_by(id=int(subject_id)).first()
        if subject:
            subject_id = subject.id
            company = subject.company
    if company is None:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    if short_group:
        try:
            short_group = int(short_group)
        except:
            return error_result(ErrorCode.ERROR_INVALID_PARAM)

    # 按照 short_group排重
    if (short_group and
        short_group > 0 and
        Event.query.filter(Event.company_id == company.id, Event.timestamp > g.TIMESTAMP - 60, Event.subject_id != None,
                           Event.short_group == short_group).first() is not None):
        return success_result()

    photo = storage.save_image_base64(photo, 'event', resize=(400, 400))
    event = Event(company_id=company.id, screen_id=screen_id, age=age, gender=gender, group=group,
                  short_group=short_group, photo=photo, subject_id=subject_id, timestamp=g.TIMESTAMP,
                  quality=quality, confidence=confidence)

    try:
        db.session.add(event)
        db.session.commit()

        update_event_statistics(company.id, subject_id)
        if not subject_id and company.warning:
            socketio.emit('message', {'warn_num': company.unread_warning, 'photo': storage.get_url(photo)},
                          namespace='/warn/', room=str(company.id))

        socketio.emit('event', event.get_json(with_screen=True, with_subject=True),
                      namespace='/event/', room=str(company.id) + '_' + str(subject.subject_type if subject else '-1'))
        # employee
        if subject and subject.subject_type == SubjectType.TYPE_EMPLOYEE:
            if company.attendance_on:
                record_attendance(event)
        # visitor
        if subject and subject.subject_type != SubjectType.TYPE_EMPLOYEE:
            if PUSH_AVAILABLE and subject.visit_notify:
                push_message(subject, camera_position)
            # for sms temporally
            info = subject.get_json()
            info['camera_position'] = camera_position
            info = json.dumps(info)
            redis.db.publish('visitor_notify', info)

            subject.visit_notify = False
            subject.visited = True
            db.session.commit()

            today = datetime.date.today()
            if VisitorHistory.query.filter_by(subject_id=subject.id, date=today).first() is None:
                history = VisitorHistory(subject_id=subject.id, date=today, event_id=event.id)
                db.session.add(history)
                db.session.commit()
    except IntegrityError:
        pass
    except:
        import traceback;
        print traceback.format_exc()
        return error_result(ErrorCode.ERROR_UNKNOWN)
    return success_result()


def get_or_create_box(box_token, box_address):
    box = Box.query.filter_by(box_token=box_token).first()
    if not box:
        box = Box(box_token=box_token, box_address=box_address, model=3)
        db.session.add(box)
        db.session.commit()
    elif box.box_address != box_address:
        box.box_address = box_address
        db.session.add(box)
        db.session.commit()
    return box


def get_screens_by_box_company(box, company):
    screens = list()
    for screen in box.screens.options(db.eagerload(Screen.allowed_subjects)).all():
        screens.append(screen.get_json(with_allowed_subjects=True))
    for screen in company.screens:
        if screen.type == ScreenType.CAMERA:
            continue
        screens.append(screen.get_json(with_allowed_subjects=True))
    return screens


def get_features(company):
    people = list()
    now = g.TIMESTAMP
    for subject in company.subjects\
                          .join(Subject.photos)\
                          .options(db.contains_eager(Subject.photos))\
                          .filter(Photo.version==company.feature_version)\
                          .all():
        # filter visitors
        if subject.subject_type != SubjectType.TYPE_EMPLOYEE and now > subject.end_time:
            continue
        item = {
            'id': str(subject.id),
            'features': [photo.feature for photo in subject.photos if photo.feature],
            'tag': json.dumps(subject.get_data())
        }
        if len(item['features']) > 0:
            people.append(item)
    return people


def get_photos(company):
    people = []
    now = g.TIMESTAMP
    for subject in company.subjects\
                          .join(Subject.photos)\
                          .options(db.contains_eager(Subject.photos))\
                          .filter(Photo.version==company.feature_version)\
                          .all():
        if subject.subject_type != SubjectType.TYPE_EMPLOYEE and now > subject.end_time:
            continue
        item = {
            'id': str(subject.id),
            'photos': [photo.url for photo in subject.photos if photo.url],
            'tag': json.dumps(subject.get_data())
        }
        if len(item['photos']) > 0:
            people.append(item)
    return people


@sync.route('/sync/local')
@cache_etag(['box_token'], 60)
def sync_local():
    box_token = request.args.get('box_token')
    box_address = request.args.get('box_address')
    version = request.args.get('version')
    dog_expiration = request.args.get('expiration', 0)

    if not box_token or not box_address:
        return Response(status=404)

    try:
        dog_expiration = int(dog_expiration)
    except:
        dog_expiration = 0

    box = get_or_create_box(box_token, box_address)

    tag = get_tag_from_request(request)
    box.heartbeat = g.TIMESTAMP
    box.current_version = version
    box.dog_expiration = datetime.datetime.fromtimestamp(dog_expiration)
    db.session.commit()

    if not box.company_id:
        return Response(status=404)
    company = Company.query.filter_by(id=box.company_id).first()
    if not company:
        return Response(status=404)

    if company.data_version == tag:
        return Response(status=304)

    screens = get_screens_by_box_company(box, company)
    days = AccessCalendar.get_or_create(company.id, datetime.date.today().year).days
    features = get_features(company)

    resp = Response()
    # force use weak etag
    resp.headers['ETag'] = 'W/%s' % company.data_version
    resp.data = json.dumps({
        'screens': screens,
        'door': {
            'range': json.loads(company.door_range),
            'days': days,
        },
        'features': features
    })
    return resp


@sync.route('/sync/<int:screen_id>/device_status', methods=['POST'])
def save_device_status(screen_id):
    params = request.form or request.get_json()
    try:
        camera_status = params['camera_status']
        network_switcher_status = params['network_switcher_status']
    except KeyError:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    Screen.query.filter_by(id=screen_id).update({
        'camera_status': camera_status,
        'network_switcher_status': network_switcher_status,
    })
    db.session.commit()
    return success_result({})

@sync.route('/sync/photos')
@cache_etag(['box_token'], 60)
def sync_photos():
    box_token = request.args.get('box_token')
    if not box_token:
        return Response(status=404)

    box = Box.query.filter_by(box_token=box_token).first()
    if not box or not box.company:
        return Response(status=404)

    tag = get_tag_from_request(request)
    if box.company.data_version == tag:
        return Response(status=304)

    persons = get_photos(box.company)

    resp = Response()
    resp.headers['ETag'] = 'W/%s' % box.company.data_version
    resp.data = json.dumps({
        'persons': persons
    })
    return resp


@sync.route('/sync/binding', methods=['POST'])
def bind_box():
    params = request.form or request.get_json()
    try:
        email = params['email']
        password = params['password']
        box_token = params['box_token']
        is_binding = params['binding'] == 'true'
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    user = User.query.filter_by(username=email).first()
    if not user:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)
    if not user.check_password(password):
        return error_result(ErrorCode.ERROR_PASSWORD_ERROR)

    box = Box.query.filter_by(box_token=box_token).first()
    if not box:
        return error_result(ErrorCode.ERROR_BOX_NOT_EXIST)
    if is_binding:
        if box.company_id is not None:
            return error_result(ErrorCode.ERROR_BOX_BINDED)
        box.company_id = user.company_id
        db.session.add(box)
        db.session.commit()
        update_company_data_version(box.company)
    else:
        if box.company_id is None:
            return error_result(ErrorCode.ERROR_BOX_NOT_BINDED)
        if box.company_id != user.company_id:
            return error_result(ErrorCode.ERROR_BOX_NOT_MATCH_USER)
        update_company_data_version(box.company)
        box.company_id = None
        db.session.add(box)
        db.session.commit()
    return success_result({})


@socketio.on('connect', namespace='/warn/')
@login_required
def websocket_connect_warn():
    try:
        user_id = int(session['user_id'])
    except:
        emit('join', {'success': False})
        return

    user = User.query.filter_by(id=user_id).first()
    if not user or not user.company or not user.company.warning or not user.has_permission(AccountPermission.REVIEW_STRANGER):
        emit('join', {'success': False})
        return

    company = user.company
    join_room(str(company.id))
    return_num = company.unread_warning if company.warning else 0
    emit('join', {'success': True, 'warn_num': return_num})


@socketio.on('subscribe', namespace='/event/')
@login_required
def websocket_subscribe_event(conf):
    try:
        user_id = int(session['user_id'])
    except:
        emit('join', {'success': False})
        return
    user = User.query.filter_by(id=user_id).first()
    if not user or not user.company:
        emit('join', {'success': False})
        return

    company_id = user.company.id
    for subject_type in conf.keys():
        if conf[subject_type]:
            join_room(str(company_id) + '_' + str(SubjectType.param_mapping.get(subject_type, -1)))
    emit('join', {'success': True})


@sync.route('/sync/local2')
@cache_etag(['box_token'], 60)
def sync_local2(**kwargs):
    box_token = request.args.get('box_token')
    box_address = request.args.get('box_address')
    version = request.args.get('version')
    dog_expiration = request.args.get('expiration', 0)

    if not box_token or not box_address:
        return Response(status=404)

    try:
        dog_expiration = int(dog_expiration)
    except:
        dog_expiration = 0

    box = get_or_create_box(box_token, box_address)
    tag = kwargs.get('tag')
    if tag is None:
        tag = get_tag_from_request(request)

    box.heartbeat = g.TIMESTAMP
    box.current_version = version
    box.dog_expiration = datetime.datetime.fromtimestamp(dog_expiration)
    db.session.commit()

    if not box.company_id:
        return Response(status=404)

    company = Company.query.filter_by(id=box.company_id).first()
    if not company:
        return Response(status=404)

    all_versions = SubjectVersion.query.filter(SubjectVersion.id >= tag).filter(SubjectVersion.company_id==company.id).all()
    if (all_versions and all_versions[-1].id == tag) or (tag == 0 and not all_versions):
        return Response(status=304)

    screens = get_screens_by_box_company(box, company)
    days = AccessCalendar.get_or_create(company.id, datetime.date.today().year).days

    modify, delete = [], []
    features = None
    if (all_versions and all_versions[0].id == tag) or tag == 0:  # tag=0表示上次更新时SubjectVersion数据库为空
        subject_ids = set(v.subject_id for v in all_versions[(0 if tag == 0 else 1):])
        new_version = all_versions[-1].id
        if 0 in subject_ids:
            features = get_features(company)
        else:
            for subject_id in subject_ids:
                if subject_id != -1:
                    subject = Subject.query.get(subject_id)
                    if subject:
                        item = {
                            'id': str(subject_id),
                            'features': [photo.feature for photo in subject.photos if photo.feature],
                            'tag': json.dumps(subject.get_data())
                        }
                        modify.append((subject_id, item))
                    else:
                        # subject is deleted
                        delete.append(subject_id)
                modify.sort(key=lambda x: x[0])
                delete.sort()
    elif not all_versions:
        features = get_features(company)
        new_version = 0
    else:
        features = get_features(company)
        new_version = all_versions[-1].id

    resp = Response()
    # force use weak etag
    resp.headers['ETag'] = 'W/%s' % new_version
    sent = {
        'screens': screens,
        'door': {
            'range': json.loads(company.door_range),
            'days': days,
        },
        'etag': new_version
    }

    #1.底库有修改, 2.重新读入所有底库 3.底库无更新,screen有更新
    if modify or delete:
        sent['modify'] = modify
        sent['delete'] = delete
    elif features:
        sent['features'] = features
    else:
        sent['nothing'] = 1
    resp.data = json.dumps(sent)
    return resp
