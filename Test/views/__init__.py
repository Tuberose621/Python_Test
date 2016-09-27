# encoding=utf-8
from admin import admin
from attendance import attendance_blueprint
from auth import auth
from event import event_blueprint
from mobile import mobile
from mobile_admin import mobile_admin
from overview import overview
from pad import pad
from screen import screen_blueprint
from statistics import statistics
from subject import subject_blueprint
from sync import sync
from system import system
from update import update
from attendance import attendance_blueprint
from admin2 import admin as admin2
from organization import org
from newTest import newTest


MODULES = [
    admin,
    (admin2, '/admin2'),
    attendance_blueprint,
    auth,
    event_blueprint,
    mobile,
    mobile_admin,
    overview,
    pad,
    newTest,
    screen_blueprint,
    statistics,
    subject_blueprint,
    sync,
    system,
    update,
    attendance_blueprint,
    (org, '/organization')
]
