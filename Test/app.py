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


# @app.route('/auth/login', methods=['POST'])
# def signin():
#     username = request.form['username']
#     password = request.form['password']
#
#     params = request.args
#     avatar = 'http://img.hb.aicdn.com/e502a0955ff6bd8fa7ec43f6f54d92e5ca0649e310969-I9BeR5_fw658'
#     verify = False
#     password_reseted = True
#     company_id = 1
#     id = 3
#     come_from = '湖南岳阳'
#     company = {"door_weekdays":[1,2,3,4,5,6],"id":1,"door_range":[[8,35],[21,55]],"organization":"旷视科技",
#                              "data_version":"123214455","attendance_weekdays":[1,2,3,4,5],"attendance_on":True,"feature_version":3,
#                              "logo":"https://o7rv4xhdy.qnssl.com/@/static/upload/logo/2016-08-23/5135a156badc8d2a11dafe38cb6b22c7095538b0.jpg",
#                              "scenario":"企业办公","remark":"","deployment":1,"create_time":0,"name":"megvii旷视-Megvii","consigner":"葛聪颖"}
#     permission = '[]'
#     role_id = 2
#     organization_id = null
#
#     if  username=='admin' and password=='123456':
# 	    return success_result(data = {"avatar":avatar,"verify":verify,"password_reseted":password_reseted,
#                                       "company_id":company_id,"id":id,"company":company,"permission":permission,
#                                       "role_id":role_id,"organization_id":organization_id,
#                                       "username":username,"password":password,"come_from":come_from}
#                               ,page={})
#     return render_template('form.html', message='Bad username or password', username=username)

@app.route('/mobile-admin/subjects/list', methods=['GET'])
def subjects():
	print '------>', request

	# return success_result({})
	# params = request.form or request.get_json()
	print request.args

	newTasks = [
		{
			"visit_notify": "null",
			"password_reseted": "true",
			"birthday": "null",
			"title": "",
			"subject_type": 0,
			"job_number": "138",
			"name": "敖翔",
			"come_from": "",
			"purpose": 0,
			"id": 6997,
			"company_id": 1,
			"department": "Cloud Service",
			"email": "aoxiang@megvii.com",
			"gender": 0,
			"phone": "18621736951",
			"pinyin": "aoxiang",
			"interviewee": "",
			"avatar": "https://o7rv4xhdy.qnssl.com/@/static/upload/avatar/2015-12-02/aab9d380766e5d6b5d103f4e81e4f0ab7f63d556.jpg",
			"photos": [
				{
					"version": 3,
					"id": 59343,
					"quality": 0.882629,
					"subject_id": 6997,
					"company_id": 1,
					"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2015-11-10/1aba9ea5da322dca7c66f753b54c6a6795a987cf.jpg"
				}
			],
			"start_time": 0,
			"end_time": 0,
			"entry_date": "null",
			"remark": "",
			"description": ""
		}
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"subject_type": 0,
		# 	"job_number": "",
		# 	"name": "白敬",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 73423,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "baijing",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 84500,
		# 			"quality": 0.9488259999999999,
		# 			"subject_id": 73423,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-06-15/57b1f2c5e7a20041e80824b1abedb4f429ed177d.jpg"
		# 		},
		# 		{
		# 			"version": 3,
		# 			"id": 84501,
		# 			"quality": 0.915075,
		# 			"subject_id": 73423,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-06-15/5b75116e35755d9cf18c59d4d5c76e2ab4ec55d3.jpg"
		# 		}
		# 	],
		# 	"start_time": 0,
		# 	"end_time": 0,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "false",
		# 	"title": "",
		# 	"subject_type": 0,
		# 	"job_number": "",
		# 	"name": "白蒙",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 98826,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "baimeng",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 111296,
		# 			"quality": 0.876607,
		# 			"subject_id": 98826,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-07-21/a5e241d36862e35027ac69633ad6e400b8f41aec.jpg"
		# 		},
		# 		{
		# 			"version": 3,
		# 			"id": 111297,
		# 			"quality": 0.890378,
		# 			"subject_id": 98826,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-07-21/be2b3c76d5a03c6e3357a7ac92ee5cd3aec72b3c.jpg"
		# 		}
		# 	],
		# 	"start_time": 0,
		# 	"end_time": 0,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"subject_type": 0,
		# 	"job_number": "",
		# 	"name": "白校铭",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 105517,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "baixiaoming",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 144729,
		# 			"quality": 0.857142,
		# 			"subject_id": 105517,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-09-02/4426bb5b59b2b0147af6f0da300a284cddf3cddb.jpg"
		# 		}
		# 	],
		# 	"start_time": 0,
		# 	"end_time": 0,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"subject_type": 0,
		# 	"job_number": "",
		# 	"name": "白焱",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 101567,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "baiyan",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 136168,
		# 			"quality": 0.932498,
		# 			"subject_id": 101567,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-08-01/42979367de19e896d550963c9dbaeb49ea52e95c.jpg"
		# 		},
		# 		{
		# 			"version": 3,
		# 			"id": 136169,
		# 			"quality": 0.829299,
		# 			"subject_id": 101567,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-08-01/6be35fe9b9c432499a8e9323b8fbb9fbb0e74983.jpg"
		# 		}
		# 	],
		# 	"start_time": 0,
		# 	"end_time": 0,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"subject_type": 0,
		# 	"job_number": "",
		# 	"name": "蔡皓",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 100807,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "caihao",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 113860,
		# 			"quality": 0.8501840000000001,
		# 			"subject_id": 100807,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-07-27/ce5d45d04913bcf001474c4c19cd8bcc9b19a835.jpg"
		# 		},
		# 		{
		# 			"version": 3,
		# 			"id": 113861,
		# 			"quality": 0.9088039999999999,
		# 			"subject_id": 100807,
		# 			"company_id": 1,
		# 			"url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2016-07-27/6a86253103de084da641cc78a29919f308e9b9dd.jpg"
		# 		}
		# 	],
		# 	"start_time": 0,
		# 	"end_time": 0,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		#
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "王宇晨",
		# 	"come_from": "清华",
		# 	"purpose": 1,
		# 	"id": 108815,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "wangyuchen",
		# 	"interviewee": "杜书洋",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 168237,
		# 			"quality": 0.819011,
		# 			"subject_id": 108815,
		# 			"company_id": 1,
		# 			"url": "https:\/\/o7rv4xhdy.qnssl.com\/@\/static\/upload\/photo\/2016-09-27\/c9955b27b921c8188bfd136050f211ee58c3e88d.jpg"
		# 		}
		# 	],
		# 	"start_time": 1474955639,
		# 	"end_time": 1474962839,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "李晨硕",
		# 	"come_from": "",
		# 	"purpose": 1,
		# 	"id": 108808,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "15201344345",
		# 	"pinyin": "lichenshuo",
		# 	"interviewee": "付英波",
		# 	"avatar": "",
		# 	"photos": [
		#
		# 	],
		# 	"start_time": 1474946997,
		# 	"end_time": 1474954197,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "胡萌洁",
		# 	"come_from": "",
		# 	"purpose": 1,
		# 	"id": 108803,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "13811658660",
		# 	"pinyin": "humengjie",
		# 	"interviewee": "candy",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 168223,
		# 			"quality": 0.923978,
		# 			"subject_id": 108803,
		# 			"company_id": 1,
		# 			"url": "https:\/\/o7rv4xhdy.qnssl.com\/@\/static\/upload\/photo\/2016-09-27\/cae47f1649785f73dc4289c487666e91fd3aecc6.jpg"
		# 		}
		# 	],
		# 	"start_time": 1474945821,
		# 	"end_time": 1474953021,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "郝梦莹",
		# 	"come_from": "",
		# 	"purpose": 2,
		# 	"id": 108801,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "haomengying",
		# 	"interviewee": "胡宝群",
		# 	"avatar": "",
		# 	"photos": [
		#
		# 	],
		# 	"start_time": 1474943983,
		# 	"end_time": 1474951183,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "杜佳",
		# 	"come_from": "",
		# 	"purpose": 2,
		# 	"id": 108799,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "dujia",
		# 	"interviewee": "胡宝群",
		# 	"avatar": "",
		# 	"photos": [
		#
		# 	],
		# 	"start_time": 1474943945,
		# 	"end_time": 1474951145,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "申健",
		# 	"come_from": "",
		# 	"purpose": 1,
		# 	"id": 108797,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "shenjian",
		# 	"interviewee": "吴可茵",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 168217,
		# 			"quality": 0.8964530000000001,
		# 			"subject_id": 108797,
		# 			"company_id": 1,
		# 			"url": "https:\/\/o7rv4xhdy.qnssl.com\/@\/static\/upload\/photo\/2016-09-27\/4aed9146bac4f015ad831f0b45a75f56f0508713.jpg"
		# 		}
		# 	],
		# 	"start_time": 1474942522,
		# 	"end_time": 1474949722,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "孙静",
		# 	"come_from": "北京亿海恒通科技发展有限公司",
		# 	"purpose": 0,
		# 	"id": 108462,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "17710454432",
		# 	"pinyin": "sunjing",
		# 	"interviewee": "詹炳林",
		# 	"avatar": "",
		# 	"photos": [
		#
		# 	],
		# 	"start_time": 1474939495,
		# 	"end_time": 1474946695,
		# 	"entry_date": "null",
		# 	"remark": "设备调试",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "false",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "",
		# 	"name": "曹总",
		# 	"come_from": "",
		# 	"purpose": 2,
		# 	"id": 108258,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 1,
		# 	"phone": "",
		# 	"pinyin": "caozong",
		# 	"interviewee": "刘振宇",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 167657,
		# 			"quality": 0.910882,
		# 			"subject_id": 108258,
		# 			"company_id": 1,
		# 			"url": "https:\/\/o7rv4xhdy.qnssl.com\/@\/static\/upload\/photo\/2016-09-26\/8c60175147a8713bddd91a63268ae6dfd58afc09.jpg"
		# 		}
		# 	],
		# 	"start_time": 1474871152,
		# 	"end_time": 1474878352,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# },
		# {
		# 	"visit_notify": "false",
		# 	"password_reseted": "fasle",
		# 	"birthday": "null",
		# 	"title": "",
		# 	"visitor_type": 1,
		# 	"subject_type": 1,
		# 	"job_number": "0",
		# 	"name": "程衍华",
		# 	"come_from": "",
		# 	"purpose": 0,
		# 	"id": 108132,
		# 	"company_id": 1,
		# 	"department": "",
		# 	"email": "",
		# 	"gender": 0,
		# 	"phone": "",
		# 	"pinyin": "chengyanhua",
		# 	"interviewee": "",
		# 	"avatar": "",
		# 	"photos": [
		# 		{
		# 			"version": 3,
		# 			"id": 167471,
		# 			"quality": 0.945204,
		# 			"subject_id": 108132,
		# 			"company_id": 1,
		# 			"url": "https:\/\/o7rv4xhdy.qnssl.com\/@\/static\/upload\/photo\/2016-09-25\/9d2a3e266b54cd9c23cc1cdf3ef4b0114e698ebb.jpg"
		# 		}
		# 	],
		# 	"start_time": 1474777800,
		# 	"end_time": 1474797600,
		# 	"entry_date": "null",
		# 	"remark": "",
		# 	"description": ""
		# }
	]

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

	# params = request.args
	#
	# visit_notify = null
	# password_reseted = False
	# birthday = null
	# title = null
	# subject_type = 0
	# job_number = '138'
	# name = '聪颖不聪颖'
	# come_from = '湖南岳阳'
	# purpose = 0
	# id = 6992
	# company_id = 1
	# department = 'SSN-PD'
	# email = 'gcy@megvii.com'
	# gender = 0
	# phone = '18600554752'
	# pinyin = 'gecongying'
	# interviewee = ''
	# avatar = 'http://img.hb.aicdn.com/e502a0955ff6bd8fa7ec43f6f54d92e5ca0649e310969-I9BeR5_fw658'
	# photos = [{"version": 3, "id": 3, "quality": 0.8828, "subject_id": 8864, "company_id": 1,
	#            "url": "https://o7rv4xhdy.qnssl.com/@/static/upload/photo/2015-11-10/1aba9ea5da322dca7c66f753b54c6a6795a987cf.jpg"}]
	# start_time = 0
	# end_time = 0
	# entry_date = null
	# remark = ''
	# description = 'iOS开发工程师'
	# interviewee = 'interviewee'
	#
	# category = params.get('', 'employee')
	# order = params.get('', 'name')
	#
	# count = 5
	# total = 5
	# current = 1
	# size = 1
	# if category == 'employee' and order == 'name':
	# 	return success_result(
	# 		data={"visit_notify": visit_notify, "password_reseted": password_reseted, "birthday": birthday,
	# 		      "title": title, "subject_type": subject_type, "job_number": job_number, "name": name,
	# 		      "come_from": come_from, "purpose": purpose, "id": id, "company_id": company_id,
	# 		      "department": department,
	# 		      "email": email, "gender": gender, "phone": phone, "pinyin": pinyin, "interviewee": interviewee,
	# 		      "avatar": avatar, "photos": photos, "start_time": start_time, "end_time": end_time,
	# 		      "entry_date": entry_date, "remark": remark, "description": description,
	#
	# 		      "category": category, "order": order},
	# 		page={"size": size, "current": current, "count": count, "total": total})
	# return render_template('form.html', message='Bad username or password')


if __name__ == '__main__':
	app.run(host='192.168.1.114')
