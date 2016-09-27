# encoding=utf-8
__author__ = 'wangyihan'

import datetime
import json
import os
import time
import tempfile
from cStringIO import StringIO
from datetime import date, timedelta

import xlsxwriter
from flask import Blueprint, render_template, g, request, send_file
from flask.ext.login import login_required
from sqlalchemy import desc, func

from app.common.constants import AttendanceStatus, weekdays, SubjectType, AccountPermission
from app.common.db_helper import fast_pagination
from app.common.error_code import ErrorCode
from app.common.view_helper import get_pagination, page_format, build_status_query
from app.common.json_builder import success_result, error_result
from app.common.permission import permission_required, permission_required_page
from app.foundation import db, storage
from app.models import Attendance, Event, AttendanceCalendar, Subject


attendance_blueprint = Blueprint('attendance', __name__, template_folder='templates')

#------------- viewhelper ----------------

def _build_query(params, ori_query):
    start_time = params.get('start_time')
    end_time = params.get('end_time')
    user_name = params.get('user_name')
    department = params.get('department')
    status = params.get('status')
    subject_id = int(params.get('subject_id', 0))

    query = ori_query.filter(Attendance.company_id == g.user.company_id)
    if end_time:
        end_date = date.fromtimestamp(int(end_time))
    else:
        end_date = date.today() - timedelta(1)
    query = query.filter(Attendance.date <= end_date)
    if start_time:
        start_date = date.fromtimestamp(int(start_time))
        query = query.filter(Attendance.date >= start_date)

    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if department:
        department = department.replace('\\', '\\\\')
        subjects = Subject.query.filter(Subject.department.contains(department)).all()
        subject_ids = map(lambda subject: getattr(subject, 'id'), subjects)
        query = query.filter(Attendance.subject_id.in_(subject_ids))
    if status:
        query = build_status_query(query, int(status))
    if user_name:
        user_name = user_name.replace('\\', '\\\\')
        subjects = Subject.query.filter(Subject.real_name.contains(user_name) | Subject.pinyin.contains(user_name)).all()
        subject_ids = map(lambda subject: getattr(subject, 'id'), subjects)
        query = query.filter(Attendance.subject_id.in_(subject_ids))
    query = query.order_by(desc(Attendance.date))
    return query


def month_range(month):
    '''
    :param month: format like "201601"
    :return: date(2016-01-01), date(2016-02-01)
    '''
    start_date = datetime.datetime.strptime(month, "%Y%m").date()
    end_date = start_date.replace(month=start_date.month + 1 if start_date.month != 12 else 1)
    if end_date.month == 1:
        end_date = end_date.replace(year=end_date.year+1)
    return start_date, end_date


class AttendanceStats(object):
    properties = {
        AttendanceStatus.NORMAL: 'normal',
        AttendanceStatus.LATE: 'late',
        AttendanceStatus.LEAVE_EARLY: 'leave_early',
        AttendanceStatus.UNCHECKED: 'unchecked',
        AttendanceStatus.ABSENTEEISM: 'absenteeism',
    }

    def __init__(self):
        self.normal = 0
        self.late = 0
        self.leave_early = 0
        self.unchecked = 0
        self.absenteeism = 0

    @staticmethod
    def calc_statuses(clock_in, clock_out):
        if clock_in == AttendanceStatus.NORMAL and clock_out == AttendanceStatus.NORMAL:
            return [AttendanceStatus.NORMAL]
        if clock_in == AttendanceStatus.UNCHECKED and clock_out == AttendanceStatus.UNCHECKED:
            return [AttendanceStatus.ABSENTEEISM]

        result = list(set([clock_in, clock_out]) - set([AttendanceStatus.NORMAL]))
        return result

    def add_attendance(self, clock_in, clock_out, count):
        statuses = self.calc_statuses(clock_in, clock_out)
        for status in statuses:
            self[self.properties[status]] += count

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def to_dict(self):
        return {item: self[item] for item in self.properties.values()}
            

# ------------- template ----------------

@attendance_blueprint.route('/attendance/search')
@login_required
@permission_required_page(AccountPermission.REVIEW_ATTENDANCE)
def search():
    return render_template('page/attendance/search.html',
                           attendance_status=AttendanceStatus.get_select_options(),
                           subject_type=SubjectType.get_select_options())


@attendance_blueprint.route('/attendance/total')
@login_required
@permission_required_page(AccountPermission.REVIEW_ATTENDANCE)
def total():
    return render_template('page/attendance/total.html', attendance_status=AttendanceStatus.get_select_options())


@attendance_blueprint.route('/attendance/config')
@login_required
@permission_required_page(AccountPermission.REVIEW_ATTENDANCE)
def config():
    return render_template('page/attendance/config.html', attendance_status=AttendanceStatus.get_select_options())


@attendance_blueprint.route('/attendance/advance')
@login_required
@permission_required_page(AccountPermission.REVIEW_ATTENDANCE)
def advance():
    return render_template('page/attendance/advance.html', attendance_status=AttendanceStatus.get_select_options())


def _check_photo_file(filename):
    if os.path.exists(filename) and os.path.getsize(filename):
        return True
    else:
        return False


# ----------- API -----------

@attendance_blueprint.route('/attendance/records')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def get_attendance_record():
    params = request.get_json() or request.form or request.args
    current, size = get_pagination(params)
    event_alias1 = db.aliased(Event)
    event_alias2 = db.aliased(Event)
    query = _build_query(params, Attendance.query.outerjoin(event_alias1, Attendance.earliest_event)
                                                 .outerjoin(event_alias2, Attendance.latest_event)
                                                 .join(Attendance.subject))
    query = query.options(db.contains_eager(Attendance.earliest_event, alias=event_alias1),
                          db.contains_eager(Attendance.latest_event, alias=event_alias2),
                          db.contains_eager(Attendance.subject),
                          )
    pagination = query.paginate(current, size, False)
    page = page_format(pagination)
    result = [attendance.get_json(with_subject=True) for attendance in pagination.items]
    return success_result(result, page)


@attendance_blueprint.route('/attendance/records/monthly')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def get_attendance_record_monthly():
    params = request.get_json() or request.form or request.args
    date = params.get('date')
    subject_id = params.get('subject_id')
    try:
        start_date, end_date = month_range(date)
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    event_alias1 = db.aliased(Event)
    event_alias2 = db.aliased(Event)
    attendances = Attendance.query.outerjoin(event_alias1, Attendance.earliest_event)\
                                  .outerjoin(event_alias2, Attendance.latest_event)\
                                  .filter(Attendance.subject_id == subject_id,
                                          Attendance.date >= start_date,
                                          Attendance.date < end_date)\
                                  .options(db.contains_eager(Attendance.earliest_event, alias=event_alias1),
                                           db.contains_eager(Attendance.latest_event, alias=event_alias2))\
                                  .all()

    calendar = AttendanceCalendar.get_or_create(g.user.company_id, datetime.date.today().year)
    stats = AttendanceStats()
    for attendance in attendances:
        if calendar.check_day(attendance.date):
            stats.add_attendance(attendance.clock_in, attendance.clock_out, 1)

    records_dict = {attendance.date:attendance.get_json() for attendance in attendances}
    records = []

    date = start_date
    while date < end_date:
        records.append(records_dict.get(date, None))
        date = date + timedelta(days=1)

    result = {
        'records': records,
        'stats': stats.to_dict()
    }
    return success_result(result)


@attendance_blueprint.route('/attendance/count')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def get_attendance_count():
    params = request.get_json() or request.form or request.args

    query = db.session.query(Attendance.date, Attendance.clock_in, Attendance.clock_out, func.count(Attendance.id))
    query = _build_query(params, query).group_by(Attendance.date, Attendance.clock_in, Attendance.clock_out)

    query_result = query.all()
    result = list()
    stats = None
    last_date = None

    # 添加尾标记
    query_result.append([0, 0, 0, 0])
    for count in query_result:
        print count
        if not count[0] == last_date:
            if stats is not None:
                doc = stats.to_dict()
                doc.update({
                    'date': int(time.mktime(last_date.timetuple())),
                    'weekday': weekdays[last_date.weekday()],
                })
                result.append(doc)
            stats = AttendanceStats()
            last_date = count[0]
        stats.add_attendance(count[1], count[2], count[3])
    return success_result(result)


@attendance_blueprint.route('/attendance/stats')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def get_attendance_stats():
    params = request.get_json() or request.args
    current, size = get_pagination(params)
    date = params.get('date')
    search = params.get('search')
    try:
        start_date, end_date = month_range(date)
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if search:
        search = search.replace('\\', '\\\\')
        query = db.session.query(Subject.id).filter(Subject.company_id == g.user.company_id,
                                                    Subject.subject_type == SubjectType.TYPE_EMPLOYEE,
                                                    db.or_(Subject.real_name.contains(search),
                                                           Subject.pinyin.contains(search),
                                                           ))
        pagination = fast_pagination(query, current, size)
        if not pagination.items:
            query = db.session.query(Subject.id).filter(Subject.company_id == g.user.company_id,
                                                        Subject.subject_type == SubjectType.TYPE_EMPLOYEE,
                                                        Subject.department.contains(search))
            pagination = fast_pagination(query, current, size)
    else:
        query = db.session.query(Subject.id).filter(Subject.company_id == g.user.company_id,
                                                    Subject.subject_type == SubjectType.TYPE_EMPLOYEE)
        pagination = fast_pagination(query, current, size)

    subjects = pagination.items
    subject_ids = [id for id, in subjects]
    subjects = Subject.query.outerjoin(Attendance, db.and_(Attendance.subject_id == Subject.id,
                                                           Attendance.date < end_date,
                                                           Attendance.date >= start_date))\
                            .options(db.contains_eager(Subject.all_attendances))\
                            .filter(Subject.id.in_(subject_ids)).all()

    calendar = AttendanceCalendar.get_or_create(g.user.company_id, datetime.date.today().year)
    result = []
    for subject in subjects:
        subject_json = subject.get_json()
        stats = AttendanceStats()
        for _attendance in subject.all_attendances:
            if calendar.check_day(_attendance.date):
                stats.add_attendance(_attendance.clock_in, _attendance.clock_out, 1)
        subject_json['attendance'] = stats.to_dict()
        result.append(subject_json)
    return success_result(result, page_format(pagination))


@attendance_blueprint.route('/attendance/calendar/<int:year>', methods=['GET', 'PUT'])
@login_required
@permission_required(5)
def attendance_calendar(year):
    company = g.user.company

    if request.method == 'GET':
        calendar = AttendanceCalendar.get_or_create(company.id, year)
    elif request.method == 'PUT':
        params = request.get_json() or request.form
        calendar = AttendanceCalendar.get_or_create(company.id, year)
        calendar.days = params['days']
        db.session.add(calendar)
        db.session.commit()
    return success_result(calendar.get_json())


@attendance_blueprint.route('/attendance/export/<path:export_name>')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def export(export_name):
    params = request.get_json() or request.form or request.args
    query = _build_query(params, Attendance.query)
    attendances = query.all()[:1000]
    temp = tempfile.TemporaryFile()
    workbook = xlsxwriter.Workbook(temp)
    worksheet = workbook.add_worksheet("attendances")
    worksheet.set_column('A:K', 15)
    worksheet.set_column(5, 5, 30)
    worksheet.set_column(9, 9, 30)
    worksheet.write(0, 0, u'因为导出文件大小限制，最多只导出1000条（请选择日期用来导出不同时段记录）')

    worksheet.write(1, 0, u'员工工号')
    worksheet.write(1, 1, u'员工姓名')
    worksheet.write(1, 2, u'打卡日期')
    worksheet.write(1, 3, u'最早打卡时间')
    worksheet.write(1, 4, u'和应打卡时间比')
    worksheet.write(1, 5, u'抓拍头像')
    worksheet.write(1, 6, u'打卡位置')
    worksheet.write(1, 7, u'最晚打卡时间')
    worksheet.write(1, 8, u'和应打卡时间比')
    worksheet.write(1, 9, u'抓拍头像')
    worksheet.write(1, 10, u'打卡位置')
    worksheet.write(1, 11, u'工作时长')

    for i, attendance in enumerate(attendances):
        row_index = i + 2
        worksheet.write(row_index, 0, attendance.subject and attendance.subject.job_number)
        worksheet.write(row_index, 1, attendance.subject and attendance.subject.name)
        worksheet.write(row_index, 2, attendance.date.strftime('%Y-%m-%d'))
        if attendance.earliest_record is not None:
            event = attendance.earliest_event
            worksheet.write(row_index, 3, time.strftime('%H:%M:%S', time.localtime(event.timestamp)))
            worksheet.write(row_index, 4, AttendanceStatus.state_mapping[attendance.clock_in])
            filename = storage.get_path(event.photo)
            if _check_photo_file(filename):
                worksheet.insert_image(row_index, 5, filename)
            worksheet.write(row_index, 6, event.screen and event.screen.camera_position)
        if attendance.latest_record is not None:
            event = attendance.latest_event
            worksheet.write(row_index, 7, time.strftime('%H:%M:%S', time.localtime(event.timestamp)))
            worksheet.write(row_index, 8, AttendanceStatus.state_mapping[attendance.clock_out])
            filename = storage.get_path(event.photo)
            if _check_photo_file(filename):
                worksheet.insert_image(row_index, 9, filename)
            worksheet.write(row_index, 10, event.screen and event.screen.camera_position)
        if attendance.worktime is not None:
            worksheet.write(row_index, 11, attendance.format_worktime())
        worksheet.set_row(row_index, 160)

    workbook.close()

    temp.seek(0)
    sio = StringIO(temp.read())
    temp.close()

    return send_file(sio, mimetype='application/octet-stream', attachment_filename=export_name)


@attendance_blueprint.route('/attendance/export/monthly/<path:export_name>')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def export_monthly(export_name):
    params = request.get_json() or request.args
    date = params.get('date')
    search = params.get('search')
    try:
        start_date, end_date = month_range(date)
        begin_weekday = start_date.weekday()
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    days = (end_date - start_date).days

    query = Subject.query.outerjoin(Attendance, db.and_(Attendance.subject_id == Subject.id,
                                                        Attendance.date < end_date,
                                                        Attendance.date >= start_date))\
                         .options(db.contains_eager(Subject.all_attendances))\
                         .filter(Subject.company_id == g.user.company_id,
                                 Subject.subject_type == SubjectType.TYPE_EMPLOYEE)

    if search:
        search = search.replace('\\', '\\\\')
        subjects = db.session.query(Subject.id).filter(Subject.company_id == g.user.company_id,
                                                       db.or_(Subject.real_name.contains(search),
                                                              Subject.pinyin.contains(search),
                                                            )).all()
        if not subjects:
            subjects = db.session.query(Subject.id).filter(Subject.company_id == g.user.company_id,
                                                           Subject.department.contains(search)).all()
        subject_ids = [id for id, in subjects]
        query = query.filter(Subject.id.in_(subject_ids))

    subjects = query.all()

    temp = tempfile.TemporaryFile()
    workbook = xlsxwriter.Workbook(temp)
    worksheet = workbook.add_worksheet("attendances")
    worksheet.freeze_panes(3, 9)
    worksheet.set_column('A:AN', 15)

    DAILY_START = 9

    xlsx_common = {
        'font_color'    : '#000000',
        'font_size'     : 14,
        'font_name'     : '微软雅黑',
        'border'        : 1,
        'border_color'  : '#cccccc',
        'align'         : 'right',
        'valign'        : 'bottom'
    }
    def f(d):
        xlsx_common = {
            'font_color': '#000000',
            'font_size': 14,
            'font_name': '微软雅黑',
            'border': 1,
            'border_color': '#cccccc',
            'align': 'right',
            'valign': 'bottom'
        }
        xlsx_common.update(d)
        return xlsx_common

    xlsx_blue = workbook.add_format(f({ 'bg_color' : 'b8dee7', 'bold' : True }))
    xlsx_blue_left = workbook.add_format(f({ 'bg_color' : 'b8dee7', 'bold' : True, 'align' : 'left' }))
    xlsx_blue2 = workbook.add_format(f({ 'bg_color' : 'b9cce3', 'bold' : True }))
    xlsx_green = workbook.add_format(f({ 'bg_color' : 'd8efa9', 'bold' : True }))
    xlsx_red = workbook.add_format(f({ 'bg_color' : 'fbd5b6', 'font_color' : 'red', 'bold' : True }))

    xlsx_content = workbook.add_format(xlsx_common)
    xlsx_content_red = workbook.add_format(f({ 'font_color' : 'red' }))

    worksheet.merge_range(0, 0, 0, 1, u'%d年%d月考勤详细表' % (start_date.year, start_date.month), workbook.add_format(f({ 'align' : 'left' })))

    WEEKDAYS = u"一二三四五六天"
    for i in xrange(0, days):
        worksheet.write(1, DAILY_START + i, u'%d月%s日' % (start_date.month, i + 1), xlsx_green)
        worksheet.write(2, DAILY_START + i, u'星期' + WEEKDAYS[(begin_weekday + i) % 7], xlsx_blue)

    TITLES = [ u'姓名', u'部门', u'工号', u'正常天数', u'迟到次数', u'早退次数', u'漏打卡次数', u'缺勤天数', u'时间']
    for i in xrange(0, DAILY_START):
        if i==0:
            worksheet.merge_range(1, i, 2, i, TITLES[i], xlsx_blue_left)
        elif i < 4 or i == DAILY_START - 1:
            worksheet.merge_range(1, i, 2, i, TITLES[i], xlsx_blue)
        else:
            worksheet.merge_range(1, i, 2, i, TITLES[i], xlsx_red)

    calendar = AttendanceCalendar.get_or_create(g.user.company_id, datetime.date.today().year)
    for i, subject in enumerate(subjects):
        row_index = i * 2 + 3
        stats = AttendanceStats()

        worksheet.write(row_index, DAILY_START - 1, u'上班', xlsx_content)
        worksheet.write(row_index + 1, DAILY_START - 1, u'下班', xlsx_content)

        for _attendance in subject.all_attendances:
            if calendar.check_day(_attendance.date):
                stats.add_attendance(_attendance.clock_in, _attendance.clock_out, 1)
                day = (_attendance.date - start_date).days

                clock_in_status = AttendanceStatus.get_desc(_attendance.clock_in)
                clock_out_status = AttendanceStatus.get_desc(_attendance.clock_out)
                if clock_in_status == u'正常':
                    clock_in_status = u'√'
                if clock_out_status == u'正常':
                    clock_out_status = u'√'

                worksheet.write(row_index, DAILY_START + day, clock_in_status, xlsx_content)
                worksheet.write(row_index + 1, DAILY_START + day, clock_out_status, xlsx_content)

        # 合并单元格
        for i in xrange(DAILY_START - 1):
            worksheet.merge_range(row_index, i, row_index + 1, i, '')

        col = 0
        worksheet.write(row_index, col, subject.real_name,  workbook.add_format(f({ 'align' : 'left' }))); col += 1
        worksheet.write(row_index, col, subject.department, xlsx_content); col += 1
        worksheet.write(row_index, col, subject.job_number, xlsx_content); col += 1
        worksheet.write(row_index, col, stats.normal,       xlsx_content); col += 1
        worksheet.write(row_index, col, stats.late,         xlsx_content_red); col += 1
        worksheet.write(row_index, col, stats.leave_early,  xlsx_content_red); col += 1
        worksheet.write(row_index, col, stats.unchecked,    xlsx_content_red); col += 1
        worksheet.write(row_index, col, stats.absenteeism,  xlsx_content_red); col += 1

    workbook.close()
    temp.seek(0)
    sio = StringIO(temp.read())
    temp.close()
    return send_file(sio, mimetype='application/octet-stream', attachment_filename=export_name)


@attendance_blueprint.route('/attendance/export/single/<path:export_name>')
@login_required
@permission_required(AccountPermission.REVIEW_ATTENDANCE)
def export_single(export_name):
    params = request.get_json() or request.form or request.args
    date = params.get('date')
    subject_id = params.get('subject_id')
    try:
        start_date, end_date = month_range(date)
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    event_alias1 = db.aliased(Event)
    event_alias2 = db.aliased(Event)
    attendances = Attendance.query.outerjoin(event_alias1, Attendance.earliest_event)\
                                  .outerjoin(event_alias2, Attendance.latest_event)\
                                  .filter(Attendance.subject_id == subject_id,
                                          Attendance.date >= start_date,
                                          Attendance.date < end_date)\
                                  .options(db.contains_eager(Attendance.earliest_event, alias=event_alias1),
                                           db.contains_eager(Attendance.latest_event, alias=event_alias2))\
                                  .all()

    calendar = AttendanceCalendar.get_or_create(g.user.company_id, datetime.date.today().year)

    stats = AttendanceStats()
    for attendance in attendances:
        if calendar.check_day(attendance.date):
            stats.add_attendance(attendance.clock_in, attendance.clock_out, 1)

    temp = tempfile.TemporaryFile()
    workbook = xlsxwriter.Workbook(temp)
    worksheet = workbook.add_worksheet("attendances")
    worksheet.set_column('A:K', 15)
    worksheet.freeze_panes(4, 0)

    xlsx_common = { 
        'font_color'    : '#000000', 
        'font_size'     : 14, 
        'font_name'     : '微软雅黑', 
        'border'        : 1,
        'border_color'  : '#cccccc',
        'align'         : 'right',
        'valign'        : 'bottom'
    }
    def f(d,xlsx_common=xlsx_common):
        xlsx_common_copy = xlsx_common.copy()
        xlsx_common_copy.update(d)
        return xlsx_common_copy

    xlsx_blue = workbook.add_format(f({ 'bg_color' : 'b8dee7', 'bold' : True }))
    xlsx_blue2 = workbook.add_format(f({ 'bg_color' : 'b9cce3', 'bold' : True }))
    xlsx_green = workbook.add_format(f({ 'bg_color' : 'd8efa9', 'bold' : True }))
    xlsx_red = workbook.add_format(f({ 'bg_color' : 'fbd5b6', 'font_color' : 'red', 'bold' : True }))

    xlsx_content = workbook.add_format(f(xlsx_common))
    xlsx_content_red = workbook.add_format(f({ 'font_color' : 'red' }))


    worksheet.write(0, 0, u'%d年%d月个人考勤明细表' % (start_date.year, start_date.month), workbook.add_format(f({ 'align' : 'left' }, xlsx_common)))

    col = 0
    worksheet.write(1, col, u'正常（天）', xlsx_blue); col += 1
    worksheet.write(1, col, u'迟到（次）', xlsx_red); col += 1
    worksheet.write(1, col, u'早退（次）', xlsx_red); col += 1
    worksheet.write(1, col, u'漏打卡（次）', xlsx_red); col += 1
    worksheet.write(1, col, u'缺勤（天）', xlsx_red); col += 1

    col = 0
    worksheet.write(2, col, stats.normal, xlsx_content); col += 1
    worksheet.write(2, col, stats.late, xlsx_content_red); col += 1
    worksheet.write(2, col, stats.leave_early, xlsx_content_red); col += 1
    worksheet.write(2, col, stats.unchecked, xlsx_content_red); col += 1
    worksheet.write(2, col, stats.absenteeism, xlsx_content_red); col += 1

    col = 0
    worksheet.write(3, col, u'日期', workbook.add_format(f({ 'align' : 'left', 'bg_color' : 'b8dee7', 'bold' : True }, xlsx_common))); col += 1
    worksheet.write(3, col, u'最早打卡时间', xlsx_blue); col += 1
    worksheet.write(3, col, u'迟到分钟数', xlsx_blue); col += 1
    worksheet.write(3, col, u'最晚打卡时间', xlsx_blue); col += 1
    worksheet.write(3, col, u'早退分钟数', xlsx_blue); col += 1
    worksheet.write(3, col, u'工作时长', xlsx_blue); col += 1
    worksheet.write(3, col, u'考勤状态', xlsx_blue); col += 1

    attendances = {attendance.date: attendance for attendance in attendances}
    normal_work_time = json.loads(g.user.company.normal_time)

    row = 4
    date = start_date
    while date < end_date:
        col = 0
        worksheet.write(row, col, date.strftime('%m/%d'), workbook.add_format(f({ 'align' : 'left' }, xlsx_common))); col += 1
        if date in attendances:
            attendance = attendances[date]
            if attendance.earliest_record is not None:
                event = attendance.earliest_event
                worksheet.write(row, col, time.strftime('%H:%M', time.localtime(event.timestamp)), xlsx_content); col += 1
                dt = datetime.datetime.fromtimestamp(event.timestamp)
                standard_time = dt.replace(hour=normal_work_time[0][0], minute=normal_work_time[0][1], second=0)
                diff_time = max((dt - standard_time).total_seconds(), 0)
                if diff_time:
                    worksheet.write(row, col, u'%d' % (diff_time/60), xlsx_content)
                col += 1
            else:
                col += 2

            if attendance.latest_record is not None:
                event = attendance.latest_event
                worksheet.write(row, col, time.strftime('%H:%M', time.localtime(event.timestamp)), xlsx_content); col += 1
                dt = datetime.datetime.fromtimestamp(event.timestamp)
                standard_time = dt.replace(hour=normal_work_time[1][0], minute=normal_work_time[1][1], second=0)
                diff_time = max((standard_time - dt).total_seconds(), 0)
                if diff_time:
                    worksheet.write(row, col, u'%d' % (diff_time/60), xlsx_content)
                col += 1
            else:
                col += 2

            #工作时长
            worktime = datetime.datetime.utcfromtimestamp(attendance.worktime if attendance.worktime is not None else 0)
            worksheet.write(row, col, worktime.strftime(u'%H小时%M分'), xlsx_content); col += 1
            # 考勤状态
            statuses = AttendanceStats.calc_statuses(attendance.clock_in, attendance.clock_out)
            statuses_text = ','.join([AttendanceStatus.get_desc(status) for status in statuses])
            worksheet.write(row, col, statuses_text, xlsx_content); col += 1
        if not calendar.check_day(date):
            worksheet.write(row, 6, u'休息日', xlsx_content)

        date = date + timedelta(days=1)
        row += 1

    workbook.close()
    temp.seek(0)
    sio = StringIO(temp.read())
    temp.close()
    return send_file(sio, mimetype='application/octet-stream', attachment_filename=export_name)
