#! encoding=utf-8
__author__ = 'ding'
import datetime
import time
from flask import Blueprint, request, Response, g
from flask.ext.login import login_required
from flask_sqlalchemy import Pagination

from app.common.db_helper import fast_pagination
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.view_helper import page_format
from app.models import Event, Screen


statistics = Blueprint('statistics', __name__)


def _parse_start_end_time():
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    if not start_time or not end_time:
        start_time = time.strftime('%Y-%m-%d 00:00:00')
        end_time = time.strftime('%Y-%m-%d 23:59:59')

    start_time = time.mktime(time.strptime(start_time, '%Y-%m-%d %H:%M:%S'))
    end_time = time.mktime(time.strptime(end_time, '%Y-%m-%d %H:%M:%S'))

    # statistics_time = time.mktime(datetime.datetime.now().replace(minute=0, second=0, microsecond=0).timetuple())
    # end_time = min(end_time, statistics_time)
    return start_time, end_time




def _statistics_age_gender(events):
    statistics = {}
    for event in events:
        if event.group not in statistics:
            statistics[event.group] = (0, 0, 0) # 人数, 年龄, 性别

        if event.gender < 0 or event.age < 0:
            continue

        count, age, gender = statistics[event.group]
        count += 1
        age += event.age
        gender += event.gender
        statistics[event.group] = (count, age, gender)
    return statistics


def _filter_events(events, unique=False, update2average=True):
    '''
        算平均值, 把平均值在 0.15 - 0.85之间的过滤掉
    '''
    result = []
    discard_set = set()
    statistics = _statistics_age_gender(events)

    for event in events:
        if event.gender < 0 or event.age < 0:
            continue
        if event.group in discard_set:
            continue

        count, age, gender = statistics[event.group]
        if 0.15 < gender/count < 0.85:
            discard_set.add(event.group)
            continue
        # 更新记录为平均值
        if update2average:
            event.age = age/count
            event.gender = gender/count
        result.append(event)
        if unique:
            discard_set.add(event.group)
    return result


@statistics.route('/statistics/overview')
@login_required
def statistics_overview():
    start_time, end_time = _parse_start_end_time()
    position = request.args.get('position')

    query = Event.query.filter(Event.company_id==g.user.company_id, Event.timestamp>start_time, Event.timestamp<=end_time)
    if position:
        screen = Screen.query.filter_by(camera_position=position).first()
        if screen is None:
            return error_result(ErrorCode.ERROR_SCREEN_NOT_EXIST)
        query = query.filter(Event.screen_id==screen.id)

    events = query.all()

    male, female = 0, 0
    ages = [[0, 0] for i in xrange(100)]

    for event in _filter_events(events, unique=True):
        event.age = int(event.age)
        if event.gender > 0.5:
            male += 1
            ages[event.age][0] += 1
        else:
            female += 1
            ages[event.age][1] += 1

    ret = {
        'gender': {
            'male': male,
            'female': female,
        },
        'ages': ages
    }

    return success_result(ret)

@statistics.route('/statistics/event')
@login_required
def statistics_event():
    position = request.args.get('position')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    unique = int(request.args.get('unique', 0))

    start_time, end_time = _parse_start_end_time()

    query = Event.query.filter(Event.company_id==g.user.company_id, Event.timestamp>start_time, Event.timestamp<=end_time)
    if position:
        screen = Screen.query.filter_by(camera_position=position).first()
        if screen is None:
            return error_result(ErrorCode.ERROR_SCREEN_NOT_EXIST)
        query = query.filter(Event.screen_id==screen.id)

    events = query.order_by(Event.timestamp.desc()).all()

    result = [event.get_json() for event in  _filter_events(events, unique=bool(unique))]
    page_info = page_format(Pagination(None, page, size, len(result), None))
    result = result[(page-1)*size: page*size]

    return success_result(result, page_info)
