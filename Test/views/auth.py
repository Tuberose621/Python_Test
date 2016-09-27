# encoding=utf-8
import urllib
import hashlib
import random
from cStringIO import StringIO

from flask import Blueprint, render_template, redirect, request, session, send_file
from flask.ctx import _app_ctx_stack
from flask.ext.login import login_user, logout_user

from app.common.constants import UserRole
from app.common.error_code import ErrorCode
from app.common.mail import send_mail_async
from app.common.json_builder import success_result, error_result
from app.common.view_helper import captcha_image
from app.common.authenticator import TwoFactorAuthenticator
from app.forms import LoginForm
from app.models import User
from app.foundation import db
from config import DOMAIN, DEBUG_CAPTCHA
from app.common.redis_cache import clear_password_incorrect_cache, incr_password_incorrect_cache, \
    get_password_incorrect_cache

auth = Blueprint('auth', __name__, template_folder='templates')


@auth.route('/auth/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if request.method == 'GET':
        return render_template('page/auth/login.html', form=form)
    else:
        params = request.form or request.get_json()

        try:
            username = params['username']
            password = params['password']
            captchas = params.get('captchas')
            remember = params.get('remember_me', False)
        except:
            return error_result(ErrorCode.ERROR_INVALID_PARAM)
        if (request.user_agent.string != 'Koala Admin' and DEBUG_CAPTCHA == False and 
                (not captchas or hashlib.sha1(captchas.upper()).hexdigest() != session.get('captchas'))):
            return error_result(ErrorCode.ERROR_CAPTCHAS_ERROR)

        user = User.query.filter_by(username=username).first()
        if not user:
            return error_result(ErrorCode.ERROR_USER_NOT_EXIST)

        incorrect_times = get_password_incorrect_cache(user.id)
        if incorrect_times is not None and int(incorrect_times) >= 3:
            return error_result(ErrorCode.ERROR_PASSWORD_ERROR_WAITING)

        if user.check_password(password):
            clear_password_incorrect_cache(user.id)
            if not user.password_reseted:
                return error_result(ErrorCode.ERROR_PASSWORD_NEED_CHANGE)
            ret = user.get_json(with_company=True)
            if (user.role_id != UserRole.ROLE_ROOT or
                    TwoFactorAuthenticator.get_google_authenticator_secret() is None):
                login_user(user, remember=remember)
                ret['verify'] = False
            else:
                ret['verify'] = True
            return success_result(ret)
        else:
            if not incr_password_incorrect_cache(user.id):
                return error_result(ErrorCode.ERROR_PASSWORD_ERROR)
            return error_result(ErrorCode.ERROR_PASSWORD_ERROR_TOO_MANY_TIMES)


@auth.route('/auth/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    if 'admin'in session:
        session.pop('admin')
    return redirect('/')


@auth.route('/auth/verify-code.jpg')
def verify_code():
    _chars = 'ABCDEFGHIJKLMNPQRSTUVWXY'
    chars = random.sample(_chars, 4)
    session['captchas'] = hashlib.sha1(''.join(chars).upper()).hexdigest()
    image = captcha_image(chars)
    str_file = StringIO()
    image.save(str_file, 'jpeg', quality=75)
    str_file.seek(0)
    return send_file(str_file, mimetype='image/jpeg')


@auth.route('/auth/reset', methods=['GET', 'POST'])
def reset():
    if request.method == 'GET':
        return render_template('page/auth/reset.html')
    else:
        email = request.form.get('email', '')
        user = User.query.filter_by(username=email).first()
        if user is None:
            return error_result(ErrorCode.ERROR_USER_NOT_EXIST)

        user.reset_token = User.get_token()
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        subject = u'KoalaCam重置密码'
        url = '%s/auth/reset-success?token=%s&uid=%s' % (DOMAIN, urllib.quote(user.reset_token), user.id)
        html = render_template('email/reset-password.html', url=url)
        send_mail_async(_app_ctx_stack.top, subject, [user.username], html)

        return success_result({})


@auth.route('/auth/reset-success', methods=['GET'])
def reset_success():

    uid = request.args['uid']
    token = request.args.get('token')
    user = User.query.get(int(uid))

    if not user.validate_token(token):
        return redirect('/auth/login')
    new_password = '123456'
    user.password = new_password
    user.password_reseted = False
    user.reset_token = ''
    db.session.add(user)
    db.session.commit()
    return render_template('page/auth/resetSuccess.html', new_password=new_password)


@auth.route('/auth/change-password', methods=['POST'])
def change_password():
    params = request.form or request.get_json()
    try:
        username = params['username']
        password = params['password']
        new_password = params['new_password']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    user = User.query.filter_by(username=username).first()
    if not user:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)
    if not user.check_password(password):
        return error_result(ErrorCode.ERROR_PASSWORD_ERROR)
    user.password_reseted = True
    user.password = new_password
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return success_result(user.get_json())


@auth.route('/auth/check-verification', methods=['POST'])
def check_verification():
    params = request.form or request.get_json()
    try:
        username = params['username']
        password = params['password']
        code = params['verify_code']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    user = User.query.filter_by(username=username).first()
    if not user:
        return error_result(ErrorCode.ERROR_USER_NOT_EXIST)
    if not user.check_password(password):
        return error_result(ErrorCode.ERROR_PASSWORD_ERROR)
    if not TwoFactorAuthenticator.check_code(code):
        return error_result(ErrorCode.ERROR_VERIFICATION_CODE)
    login_user(user)
    return success_result(user.get_json())
