# coding=utf-8
__author__ = 'ding'

from flask import Blueprint, request, g
from flask.ext.login import login_user, login_required
from app.common.json_builder import error_result, success_result
from app.common.error_code import ErrorCode
from app.common.constants import ScreenType, SubjectType
from app.common.view_helper import update_company_data_version, create_user_photo
from app.models import User, Screen, Subject, Box
from app.foundation import db


pad = Blueprint('pad', __name__)


@pad.route('/pad/login', methods=['POST'])
def login():
    params = request.form or request.get_json()

    try:
        username = params['username']
        password = params['password']
        pad_id = params['pad_id']
        device_type = int(params['device_type'])
        if device_type not in [ScreenType.DOOR_PAD, ScreenType.FRONT_PAD]:
            raise Exception()
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    user = User.query.filter_by(username=username).first()
    if user:
        if user.check_password(password):
            if not user.password_reseted:
                return error_result(ErrorCode.ERROR_PASSWORD_NEED_CHANGE)

            login_user(user)
            ret = user.get_json()
            if pad_id == 'importer':
                return success_result(ret)
            screen = Screen.query.filter_by(company_id=user.company_id, token=pad_id).first()
            if screen is None:
                screen = Screen(company_id=user.company_id, token=pad_id, name='pad', theme='center',
                                type=device_type, camera_position=ScreenType.get_desc(device_type))
                db.session.add(screen)
                db.session.commit()
                update_company_data_version(user.company)

            ret['position'] = screen.camera_position
            ret['screen_token'] = screen.token
            ret['boxes'] = [box.get_json() for box in user.company.boxes]
            ret['company'] = user.company.get_json()
            return success_result(ret)
        else:
            return error_result(ErrorCode.ERROR_PASSWORD_ERROR)
    else:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)


@pad.route('/pad/add-visitor', methods=['POST'])
@login_required
def add_visitor():
    params = request.form or request.get_json()

    try:
        name = params['name']
        photo = request.files.get('photo')
        purpose = params.get('purpose')
        interviewee = params.get('interviewee')
        come_from = params.get('come_from')
        phone = params.get('phone')
        remark = params.get('remark')
        company_id = g.user.company_id
        start_time = int(params.get('start_time', 0))
        end_time = int(params.get('end_time', 0))
        vip = bool(int(params.get('vip', False)))
        subject_type = int(params.get('subject_type', 1))
        description = params.get('description')
    except:
        import traceback; print traceback.format_exc()
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not start_time or not end_time:
        start_time = g.TIMESTAMP - 5 * 60
        end_time = g.TIMESTAMP + 2 * 3600

    if vip:
        subject_type = SubjectType.TYPE_VIP

    subject = Subject(company_id=company_id, name=name, subject_type=subject_type, description=description, remark=remark,
                      start_time=start_time, end_time=end_time, purpose=purpose, interviewee=interviewee,
                      come_from=come_from, phone=phone, password='123456')
    db.session.add(subject)
    db.session.commit()

    if photo:
        photo, error = create_user_photo(photo, company_id)
        if error:
            return error
        subject.photos.append(photo)
        update_company_data_version(g.user.company, subject.id)

    return success_result(subject.get_json())


@pad.route('/pad/set-info', methods=['PUT'])
@login_required
def set_info():
    params = request.form or request.get_json()

    box_token = params.get('box_token')
    pad_id = params.get('pad_id')
    position = params.get('position')

    screen = Screen.query.filter_by(company_id=g.user.company_id, token=pad_id).first()
    if not screen:
        return error_result(ErrorCode.ERROR_SCREEN_NOT_EXIST)

    if box_token:
        box = Box.query.filter_by(box_token=box_token).first()
        if not box:
            return error_result(ErrorCode.ERROR_BOX_NOT_EXIST)
        screen.box_id = box.id

    if position:
        screen.camera_position = position

    fields = ('network_switcher', 'network_switcher_token')
    screen.update(fields, params)
    db.session.commit()

    if params.get('network_switcher') or params.get('network_switcher_token'):
        update_company_data_version(g.user.company)
    return success_result({})
