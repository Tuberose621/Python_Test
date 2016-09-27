# encoding=utf-8
import datetime

from flask import Blueprint, render_template, g, request, redirect
from flask.ext.login import login_required
from app.common.constants import CameraStatus, UserRole
from app.common.json_builder import success_result
from app.models import EventStatistics

overview = Blueprint('overview', __name__, template_folder='templates')


@overview.route('/')
@overview.route('/overview/index')
@login_required
def index():
    if g.user.role_id == UserRole.ROLE_ROOT:
        return redirect('/admin2')
    return render_template('page/overview/index.html', camera_status=CameraStatus.state_mapping)


@overview.route('/overview/statistics')
@login_required
def statistics():
    item = EventStatistics.query.filter_by(company_id=g.user.company_id, date=datetime.datetime.now().date()).first()
    item = EventStatistics(num_employee=0, num_visitor=0, num_warn=0) if item is None else item
    return success_result(item.get_json())
