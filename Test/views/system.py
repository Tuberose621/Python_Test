# encoding=utf-8
import datetime
import json
import os
import re
import time

from flask import Blueprint, render_template, g, request
from flask.ext.login import login_required

from app.common.constants import CameraStatus, ScreenType, AccountPermission, UserRole
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.redis_cache import clear_display_config_cache
from app.common.view_helper import save_screen_background,\
    update_company_data_version, get_ordered_theme_list
from app.foundation import db, storage
from app.models import Screen, AccessCalendar, AttendanceCalendar, User, DisplayDevice, Task
from app.common.permission import permission_required, permission_required_page
from config import THEME_DIR
from app.common.tasks import delete_screen


system = Blueprint('system', __name__, template_folder='templates')


@system.route('/system/alert')
@login_required
def system_alert():
    return success_result({'id': '3', 'message': '通知：迎宾主题新增“圣诞节”主题。'});


# -------------------  设备 -------------------
@system.route('/system/screens')
@login_required
@permission_required_page(5)
def setting():
    boxes = {}
    for box in g.user.company.boxes:
        boxes[box.id] = str(box.box_address) + '  ' + box.box_token
    return render_template('page/system/screen.html', boxes=boxes, camera_status=CameraStatus.state_mapping)


@system.route('/system/boxes')
@login_required
@permission_required_page(5)
def boxes():
    boxes = []
    for box in g.user.company.boxes:
        boxes.append(box.get_json(with_all_screens=True))
    return success_result(boxes)

@system.route('/system/screen')
@login_required
@permission_required(5)
def screen_list():
    company = g.user.company
    if company is None:
        return error_result(ErrorCode.ERROR_COMPANY_NOT_EXIST)
    cur_time = time.time()
    screens = Screen.query.filter(Screen.company_id==company.id, Screen.type!=ScreenType.FRONT_PAD)\
                          .options(db.eagerload(Screen.allowed_subjects)).all()

    ret = []
    task_content = TASK_SCRREN_DELETE_PREFIX + str(company.id) + '%'
    task_screen_delete = db.session.query(Task.content).filter(Task.content.like(task_content)).filter(Task.status != 2).all()
    screen_deleting_ids = [int(x[0].split(':')[-1]) for x in task_screen_delete]
    for screen in screens:
        screen = screen.get_json(with_allowed_subjects=True)
        screen['server_time'] = cur_time
        if screen['id'] in screen_deleting_ids:
            screen['deleting'] = 1
        ret.append(screen)

    ret.sort(key=lambda screen: screen['box_address'])
    return success_result(ret)


@system.route('/system/screen', methods=['POST'])
@login_required
@permission_required(5)
def screen_create():
    company = g.user.company
    params = request.get_json() or request.form
    screen = Screen(company_id=company.id, theme='center', type=ScreenType.CAMERA)
    fields = (
        'name',
        'camera_name',
        'camera_address',
        'camera_position',
        'network_switcher',
        'network_switcher_token'
        'description',
        # 'screen_id'
    )
    screen.update(fields, params)
    try:
        screen.box_id = int(params.get('box_id'))
    except:
        pass
    screen.token = Screen.create_unique_token()
    db.session.add(screen)
    update_company_data_version(company)
    return success_result(screen.get_json())

TASK_SCRREN_DELETE_PREFIX = 'delete screen '


def generate_delete_screen_task_content(company_id, screen_id):
    return TASK_SCRREN_DELETE_PREFIX + str(company_id) + ' : ' + str(screen_id)

@system.route('/system/screen/<int:sid>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@permission_required(5)
def screen_detail(sid):
    company = g.user.company
    screen = Screen.query.filter(Screen.company_id==company.id, Screen.id==sid).first()
    if screen is None:
        return error_result(ErrorCode.ERROR_SCREEN_NOT_EXIST)

    if request.method == 'GET':
        return success_result(screen.get_json())
    elif request.method == 'PUT':
        params = request.get_json()
        fields = (
            'box_id',
            'name',
            'camera_name',
            'camera_address',
            'camera_position',
            'network_switcher',
            'network_switcher_token'
            'description',
            'allow_all_subjects',
            'allow_visitor',
            'allowed_subject_ids'
        )
        screen.update(fields, params)
        screen.display_devices.update({'reload_timestamp': g.TIMESTAMP})
        db.session.add(screen)
        update_company_data_version(company)
        return success_result(screen.get_json())
    elif request.method == 'DELETE':
        content = generate_delete_screen_task_content(company.id, sid)
        task = Task()
        task.name = u'删除相机'
        task.content = content
        db.session.add(task)
        db.session.commit()
        delete_screen.delay(task.id, company.id, sid)
        return success_result()


@system.route('/system/encryption')
@login_required
@permission_required(5)
def encryption():
    try:
        cmu_id = os.popen('cmu -x|grep PC=|tail -1').read()
        cmu_id = re.search('PC=(\d+)', cmu_id).groups()[0]
        expiration = os.popen('cmu -x|grep "Expiration Date:"|tail -1').read()
        expiration = expiration.split(':', 1)[1]
        name = os.popen('cmu -x|grep "Name:"|tail -1').read()
        name = name.split(':', 1)[1]
        ret = {
            "name": name,
            "expiration": expiration,
            "cmu_id": cmu_id
        }
    except:
        ret = {}
    return success_result(ret)

# -------------------  门禁 & 考勤 -------------------
@system.route('/system/attendance')
@login_required
@permission_required_page(5)
def attendance_index():
    return render_template('page/system/attendance.html')


@system.route('/system/attendance/setting', methods=['GET', 'PUT'])
@login_required
@permission_required(5)
def attendance_setting():
    company = g.user.company

    if request.method == 'GET':
        ret = {
            'door_range': json.loads(company.door_range),
            'attendance_on': company.attendance_on,
            'attendance_range': json.loads(company.normal_time),
            'tolerance': json.loads(company.tolerance),
            'weekdays': json.loads(company.door_weekdays),
            'attendance_weekdays': json.loads(company.attendance_weekdays),
            'warning': company.warning
        }
        return success_result(ret)
    elif request.method == 'PUT':
        params = request.get_json()
        company.door_range = json.dumps(params['door_range'])
        company.normal_time = json.dumps(params['attendance_range'])
        company.tolerance = json.dumps(params['tolerance'])
        company.attendance_on = params['attendance_on']
        weekdays = json.dumps(params['weekdays'])
        attendance_weekdays = json.dumps(params.get('attendance_weekdays', []))
        # 更新门禁控制
        if company.door_weekdays != weekdays:
            access_calendar = AccessCalendar.get_or_create(company.id, datetime.date.today().year)
            access_calendar.set_weekdays(params['weekdays'])
            db.session.add(access_calendar)
            company.door_weekdays = weekdays
        # 更新考勤日期
        if company.attendance_weekdays != attendance_weekdays:
            attendance_calendar = AttendanceCalendar.get_or_create(company.id, datetime.date.today().year)
            attendance_calendar.set_weekdays(params.get('attendance_weekdays', []))
            db.session.add(attendance_calendar)
            company.attendance_weekdays = attendance_weekdays

        company.warning = params['warning']
        db.session.add(company)
        update_company_data_version(company)
    return success_result({})


@system.route('/system/attendance/calendar/setting', methods=['GET', 'PUT'])
@login_required
@permission_required_page(5)
def calendar_index():
    return render_template('page/system/calendar.html')


@system.route('/system/attendance/calendar/<int:year>', methods=['GET', 'PUT'])
@login_required
@permission_required(5)
def calendar(year):
    company = g.user.company

    if request.method == 'GET':
        access_calendar = AccessCalendar.get_or_create(company.id, year)
    elif request.method == 'PUT':
        params = request.get_json() or request.form
        access_calendar = AccessCalendar.get_or_create(company.id, year)
        access_calendar.days = params['days']
        db.session.add(access_calendar)
        update_company_data_version(company)
    return success_result(access_calendar.get_json())


# -------------------  主题 -------------------
@system.route('/system/display-device')
@login_required
@permission_required(5)
def display_devices():
    result = []
    devices = DisplayDevice.query.filter_by(company_id=g.user.company_id).all()
    for device in devices:
        result.append(device.get_json(with_screens=True, with_logo=True))
    return success_result(result)


@system.route('/system/theme')
@login_required
@permission_required_page(5)
def theme():
    themes = get_ordered_theme_list(THEME_DIR)
    theme_data = g.user.company.get_custom_theme(themes)
    return render_template('page/system/theme.html', theme_data=theme_data)


@system.route('/system/display-device/<int:device_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@permission_required(5)
def theme_setting(device_id):
    company = g.user.company
    device = DisplayDevice.query.filter_by(id=device_id).first()
    if not device:
        return error_result(ErrorCode.ERROR_DISPLAY_DEVICE_NOT_EXIST)

    if request.method == 'GET':
        return success_result(device.get_json(with_logo=True))

    elif request.method == 'PUT':
        card_theme = request.form.get('card_theme')
        card_theme_vip = request.form.get('card_theme_vip')
        photo = request.files.get('photo')
        logo = request.files.get('logo')
        theme = request.form.get('theme') # current
        duration = request.form.get('duration') # stay
        reset_background = request.form.get('reset_background', 'false') # stay

        if logo is not None:
            company.logo = storage.save_image(logo.stream, 'logo')

        if photo is not None:
            device.background = save_screen_background(photo)

        if card_theme is not None:
            device.card_theme = card_theme

        if card_theme_vip is not None:
            device.card_theme_vip = card_theme_vip

        if theme is not None:
            device.theme = theme

        if duration is not None:
            device.card_duration = int(duration)

        if reset_background == 'true':
            device.background = '/static/screen/images/background_blue.png'

        device.reload_timestamp = g.TIMESTAMP
        db.session.commit()

        clear_display_config_cache(device.token)
        return success_result(device.get_json())

    elif request.method == 'DELETE':
        db.session.delete(device)
        db.session.commit()
        return success_result({})

    return error_result(ErrorCode.ERROR_NOT_ALLOWED)



# ------------------- 帐号管理 -------------------
@system.route('/system/account')
@login_required
@permission_required_page(5)
def account_index():
    return render_template('page/system/account.html', account_permission=AccountPermission.state_mapping)


@system.route('/system/account/list', methods=['GET', 'POST'])
@login_required
@permission_required(5)
def account_lists():
    if not g.user.can_visit('system'):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)
    company = g.user.company
    if request.method == 'GET':
        users = User.query.filter_by(company_id=company.id, role_id=UserRole.ROLE_NORMAL).all()
        data = [{
            'id': user.id,
            'account': user.username,
            'permission': json.loads(user.permission),
            'remark': user.remark
        } for user in users]
        return success_result(data)

    elif request.method == 'POST':
        params = request.get_json() or request.form
        if params.get('account') is None:
            return error_result(ErrorCode.ERROR_INVALID_PARAM)
        user = User.query.filter_by(username=params.get('account')).first()
        if user:
            return error_result(ErrorCode.ERROR_USERNAME_EXISTED)
        try:
            user = User(company_id=company.id, role_id=UserRole.ROLE_NORMAL, permission=json.dumps(params['permission']),
                        remark=params['remark'], password_reseted=False, username=params['account'], password='123456')
        except:
            return error_result(ErrorCode.ERROR_INVALID_PARAM)
        db.session.add(user)
        db.session.commit()
        return success_result({})


@system.route('/system/account/list/<int:aid>', methods=['PUT', 'DELETE'])
@login_required
@permission_required(5)
def account_edit(aid):
    if not g.user.can_visit('system'):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)
    user = User.query.filter_by(id=aid).first()
    if user is None:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)

    if request.method == 'PUT':
        params = request.args or request.get_json() or request.form
        if params.get('account'):
            user.username = params['account']
        if params.get('permission'):
            user.permission = json.dumps(params['permission'])
        if params.get('remark'):
            user.remark = params['remark']
        db.session.add(user)
        db.session.commit()
        return success_result({})
    elif request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return success_result({})


# -------------------  about -------------------
@system.route('/system/about')
@login_required
def about():
    return render_template('page/system/about.html', hidden="hidden")
