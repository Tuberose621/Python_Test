# encoding=utf-8
from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request
import re
from Subject import Subject



import json


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

	tasks ={
			"avatar": "",
			"verify": "false",
			"password_reseted": "false",
			"company_id": 1,
			"id": 2,
			"company": {
				"door_weekdays": [1,2,3,4,5,6],
				"id": 1,
				"door_range":[[8,35],[21,55]],
				"organization": "旷视科技",
				"data_version": 1474959615,
				"attendance_weekdays": [1,2,3,4,5],
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

	if username == 'admin' and password == '123456':
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
			data=newTasks,page={"size": size, "current": current, "count": count, "total": total})
	return render_template('form.html', message='Bad username or password')
if __name__ == '__main__':
	app.run(host='169.254.215.161')
