# encoding=utf-8
import os
import tempfile
from cStringIO import StringIO

import xlsxwriter
from flask import Blueprint, render_template, g, request, send_file
from flask.ext.login import login_required
from PIL import Image
from app.common.constants import SubjectType, Gender, VisitorPurpose, AccountPermission
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.db_helper import fast_pagination
from app.common.view_helper import get_pagination, page_format, format_timestamp, _build_query
from app.common.permission import permission_required_page
from app.foundation import db, socketio, storage
from app.models import Event, Subject, Screen
from app.models.Company import Company

event_blueprint = Blueprint('event', __name__, template_folder='templates')


@event_blueprint.route('/event/user')
@login_required
def index():
    screens = Screen.get_all(g.user.company_id)
    return render_template('page/event/index.html', category="user", screens=screens,
                           purpose=VisitorPurpose.state_mapping,
                           subject_type=SubjectType.get_select_options())


@event_blueprint.route('/event/warning')
@login_required
@permission_required_page(AccountPermission.REVIEW_STRANGER)
def warning():
    screens = Screen.get_all(g.user.company_id)
    return render_template('page/event/index.html', category="warning", screens=screens,
                           subject_type=SubjectType.get_select_options())


def clear_unread_warnings(params):
    category = params.get('category', 'user')
    if not category == 'warning':
        return
    Company.query.filter_by(id=g.user.company_id).update({'unread_warning': 0})
    socketio.emit('message', {'warn_num': 0}, namespace='/warn/', room=str(g.user.company_id))
    db.session.commit()


@event_blueprint.route('/event/events')
@login_required
def events_list():
    params = request.get_json() or request.form or request.args
    category = params.get('category', 'user')
    if category == 'warning' and not g.user.has_permission(AccountPermission.REVIEW_STRANGER):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    current, size = get_pagination(params)
    no_eager_query, query = _build_query(params, g.user.company_id)
    clear_unread_warnings(params)
    pagination = fast_pagination(query, current, size, False, count_query=no_eager_query)
    page = page_format(pagination)
    result = [event.get_json(with_subject=True, with_screen=True, with_subject_photos=True) for event in pagination.items]
    return success_result(result, page)


@event_blueprint.route('/event/events/<int:eid>', methods=['DELETE'])
@login_required
def events_delete(eid):
    event = Event.query.get(eid)
    if not event:
        return error_result(ErrorCode.ERROR_EVENT_NOT_EXIST)
    else:
        db.session.delete(event)
        db.session.commit()
    return success_result(event.get_json())


def _check_photo_file(filename):
    if os.path.exists(filename) and os.path.getsize(filename):
        return True
    else:
        return False


@event_blueprint.route('/event/export/<path:export_name>')
@login_required
def exports(export_name):
    params = request.get_json() or request.form or request.args
    _, query = _build_query(params, g.user.company_id)
    events = query.all()[:1000]
    temp = tempfile.TemporaryFile()
    workbook = xlsxwriter.Workbook(temp)
    worksheet = workbook.add_worksheet("events")
    worksheet.set_column(0, 0, 30)

    worksheet.write(0, 0, u'因为导出文件大小限制，最多只导出1000条（请选择日期用来导出不同时段记录）')

    if params.get('category', 'user') == 'user':
        worksheet.write(1, 0, u'头像')
        worksheet.write(1, 1, u'工号')
        worksheet.write(1, 2, u'姓名')
        worksheet.write(1, 3, u'性别')
        worksheet.write(1, 4, u'部门')
        worksheet.write(1, 5, u'职位')
        worksheet.write(1, 6, u'识别位置')
        worksheet.write(1, 7, u'用户类型')
        worksheet.write(1, 8, u'识别时间')

        for i, event in enumerate(events):
            row_index = i + 2
            if event.photo:
                filename = storage.get_path(event.photo)
                if _check_photo_file(filename):
                    image = Image.open(filename)
                    width, height = image.size
                    x_scale = 200.0 / width
                    y_scale = 200.0 / height
                    worksheet.insert_image(row_index, 0, filename, {'x_scale': x_scale, 'y_scale': y_scale})
            worksheet.write(row_index, 1, event.subject and event.subject.job_number)
            worksheet.write(row_index, 2, event.subject and event.subject.name)
            worksheet.write(row_index, 3, event.subject and Gender.get_desc(event.subject.gender))
            worksheet.write(row_index, 4, event.subject and event.subject.department)
            worksheet.write(row_index, 5, event.subject and event.subject.title)
            worksheet.write(row_index, 6, event.screen and event.screen.camera_position)
            worksheet.write(row_index, 7, event.subject and SubjectType.get_desc(event.subject.subject_type))
            worksheet.write(row_index, 8, format_timestamp(event.timestamp))
            worksheet.set_row(row_index, 160)

    else:
        worksheet.write(0, 0, u'头像')
        worksheet.write(0, 1, u'摄像头')
        worksheet.write(0, 2, u'识别位置')
        worksheet.write(0, 3, u'识别时间')

        for i, event in enumerate(events):
            row_index = i + 1
            if event.photo:
                filename = storage.get_path(event.photo)
                if _check_photo_file(filename):
                    image = Image.open(filename)
                    width, height = image.size
                    x_scale = 200.0 / width
                    y_scale = 200.0 / height
                    worksheet.insert_image(row_index, 0, filename, {'x_scale': x_scale, 'y_scale': y_scale})
            worksheet.write(row_index, 1, event.screen and event.screen.camera_name)
            worksheet.write(row_index, 2, event.screen and event.screen.camera_position)
            worksheet.write(row_index, 3, format_timestamp(event.timestamp))
            worksheet.set_row(row_index, 160)

    workbook.close()

    temp.seek(0)
    sio = StringIO(temp.read())
    temp.close()

    return send_file(sio, mimetype='application/octet-stream', attachment_filename=export_name)
