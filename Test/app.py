# encoding=utf-8
import os

from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request
import re
from Subject import Subject
from constants import SubjectType, Gender, VisitorPurpose

from flask.ext.sqlalchemy import SQLAlchemy
from flask_script import Shell, Manager


basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = \
	'sqlite:///' + os.path.join(basedir, 'data.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

db = SQLAlchemy(app)
manage = Manager(app)



class Subjects(db.Model):
	__tablename__ = 'subjects'
	id = db.Column(db.Integer, primary_key=True)
	subject_type = db.Column(db.SmallInteger, nullable=False, default=SubjectType.TYPE_EMPLOYEE)
	create_time = db.Column(db.Integer, server_default='0')
	
	email = db.Column(db.String(64), default='')
	password_hash = db.Column(db.String(256), nullable=False)
	password_reseted = db.Column(db.Boolean, default=False)
	
	real_name = db.Column(db.String(64), nullable=False, index=True)
	pinyin = db.Column(db.String(128), nullable=False)
	gender = db.Column(db.SmallInteger, default=Gender.MALE)
	phone = db.Column(db.String(20), default='')
	avatar = db.Column(db.String(256), default='')
	department = db.Column(db.String(256), default='')
	department_pinyin = db.Column(db.String(512), default='')
	title = db.Column(db.String(64), default='')
	description = db.Column(db.String(128), default='')
	mobile_os = db.Column(db.Integer)
	birthday = db.Column(db.Date)
	entry_date = db.Column(db.Date)
	
	job_number = db.Column(db.String(64), default='')
	remark = db.Column(db.String(128), default='')
	
	# visitor info
	purpose = db.Column(db.Integer, default=VisitorPurpose.OTHER)
	interviewee = db.Column(db.String(20), default='')
	interviewee_pinyin = db.Column(db.String(128), default='')
	come_from = db.Column(db.String(128), default='')
	visited = db.Column(db.Boolean, default=False)
	visit_notify = db.Column(db.Boolean, default=False)
	
	start_time = db.Column(db.Integer)
	end_time = db.Column(db.Integer)
	
	# events = db.relationship('Event', backref='subject', lazy='dynamic', cascade='all')
	# photos = db.relationship('Photo', backref='subject', lazy='select', cascade='all')
	# attendances = db.relationship('Attendance', backref='subject', lazy='dynamic', cascade='all')
	# all_attendances = db.relationship('Attendance', lazy='select', cascade='all')
	# visitors = db.relationship('Subject', backref=db.backref('inviter', remote_side=id),
	#                            lazy='dynamic', cascade='all')
	
	def __repr__(self):
		return '<Role %r>' % self.name


class User(db.Model):
	__tablename__ = 'users'
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(64), nullable=False, index=True, unique=True)
	password_hash = db.Column(db.String(256), nullable=False)
	password_reseted = db.Column(db.Boolean, default=False)
	reset_token = db.Column(db.String(64), default='')
	
	permission = db.Column(db.String(32), server_default='[]')
	
	avatar = db.Column(db.String(256))
	remark = db.Column(db.String(256))
	
	
	def __repr__(self):
		return '<User %r>' % self.username


def success_result(data={}, page={}):
	ret = {
		'code': 0,
		'data': data,
		'page': page
	}
	return jsonify(ret)


app = Flask(__name__)


def get(self, url, **kwargs):
	"""Sends a GET request. Returns :class:`Response` object.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    """
	
	kwargs.setdefault('allow_redirects', True)
	return self.request('GET', url, **kwargs)


def json(self):
	"""If the mimetype is `application/json` this will contain the
    parsed JSON data.  Otherwise this will be `None`.

    The :meth:`get_json` method should be used instead.
    """
	# XXX: deprecate property
	return self.get_json()


def ProcessMail(inputMail):
	isMatch = bool(
		re.match(r"^[a-zA-Z](([a-zA-Z0-9]*\.[a-zA-Z0-9]*)|[a-zA-Z0-9]*)[a-zA-Z]@([a-z0-9A-Z]+\.)+[a-zA-Z]{2,}$",
		         inputMail, re.VERBOSE))
	if isMatch:
		print ("邮箱注册成功。")
	else:
		print ("邮箱注册失败。")
	return isMatch


@app.route('/', methods=['GET', 'POST'])
def home():
	return render_template('home.html')


@app.route('/auth/login', methods=['GET'])
def signin_form():
	return render_template('form.html')


@app.route('/auth/login', methods=['POST'])
def signin():
	username = request.form['username']
	password = request.form['password']
	
	tasks = {
		"avatar": "",
		"verify": "false",
		"password_reseted": "false",
		"company_id": 1,
		"id": 2,
		"company": {
			"door_weekdays": [1, 2, 3, 4, 5, 6],
			"id": 1,
			"door_range": [[8, 35], [21, 55]],
			"organization": "旷视科技",
			"data_version": 1474959615,
			"attendance_weekdays": [1, 2, 3, 4, 5],
			"attendance_on": "true",
			"feature_version": 3,
			"logo": "https://o7rv4xhdy.qnssl.com/@/static/upload/logo/2016-08-23/5135a156badc8d2a11dafe38cb6b22c7095538b0.jpg",
			"scenario": "企业办公",
			"remark": "",
			"deployment": 1,
			"create_time": 0,
			"name": "megvii旷视-Megvii",
			"consigner": "葛聪颖"
		},
		"permission": [
		
		],
		"role_id": 2,
		"username": "megvii@megvii.com",
		"organization_id": "null"
	}
	
	if username == 'admin@megvii.com' and password == '123456':
		return success_result(data=tasks, page={})
	return render_template('form.html', message='Bad username or password', username=username)


@app.route('/mobile-admin/subjects/list', methods=['GET'])
def subjects():
	print '------>', request
	
	print request.args
	
	newTasks = Subject.get_json()
	
	params = request.args
	category = params.get('', 'employee')
	order = params.get('', 'name')
	count = 6
	total = 6
	current = 1
	size = 6
	if category == 'employee' and order == 'name':
		return success_result(
			data=newTasks, page={"size": size, "current": current, "count": count, "total": total})
	return render_template('form.html', message='Bad username or password')


if __name__ == '__main__':
	app.run(host='169.254.215.161')
	manage.run()
	
	
	db.init_app(app)
	db.create_all()
	
	db.session.commit()
	print app.config['SQLALCHEMY_DATABASE_URI']
	

def _make_context():
	return dict(db=db)

manage.add_command("shell", Shell(make_context=_make_context))