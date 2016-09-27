# encoding=utf-8
# __author__ = 'wang'

import random

from flask import Blueprint, render_template, g, request, Response

from app.common.constants import SubjectType, ScreenType, BackgroundLayout
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.redis_cache import clear_display_config_cache, cache_etag
from app.common.view_helper import update_company_data_version, get_theme_config, get_ordered_theme_list,\
                                   create_user_photo
from app.common.weather import WeatherManager
from app.foundation import db, storage
from app.models import *
from config import SCREEN_LIB_DIR, THEME_DIR

screen_blueprint = Blueprint('screen', __name__, template_folder='templates')


@screen_blueprint.route('/screen/')
def get_screen_blanket():
    return render_template('screen/blanket.html')


# Step: 1, 获取所有可以相机列表
@screen_blueprint.route('/screen/get-screen-list')
def get_screen_list():
    box_token = request.args.get('box_token')
    if not box_token:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    box = Box.query.filter_by(box_token=box_token).first()
    if not box:
        return error_result(ErrorCode.ERROR_BOX_NOT_EXIST)
    if not box.company:
        return error_result(ErrorCode.ERROR_BOX_NOT_BINDED)
    screens = filter(lambda screen: screen.type == ScreenType.CAMERA, box.company.screens)
    screens = [screen.get_json() for screen in screens]
    return success_result({"screens": screens})


# Step: 2, 设置显示设备需要弹窗和显示的相机
@screen_blueprint.route('/screen/set-display-config', methods=['POST'])
def set_display_config():
    box_token = request.form.get('box_token')
    device_token = request.form.get('device_token')
    screen_ids = request.form.getlist('screens')
    video_screen = request.form.get('video_screen', 0)

    if not box_token or not device_token:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    box = Box.query.filter_by(box_token=box_token).first()
    if not box:
        return error_result(ErrorCode.ERROR_BOX_NOT_EXIST)

    device = DisplayDevice.query.filter_by(token=device_token).first()
    if not device:
        device = DisplayDevice(company_id=box.company_id, token=device_token)
        db.session.add(device)
        db.session.commit()

    device.set_screen_ids(map(int, screen_ids))
    device.video_screen_id = int(video_screen)
    device.company_id = box.company_id
    db.session.commit()
    return success_result({})


@screen_blueprint.route("/screen/set-device-info", methods=['POST'])
def set_device_city():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err:
        return err
    city = params.get('city', '北京')
    device.city = city
    db.session.commit()
    return success_result()


# Step: 3, 获取最新的显示设备设置
@screen_blueprint.route('/screen/get-display-config')
@cache_etag(['device_token'], 60)
def get_display_device_info():
    params = request.args or request.get_json() or request.form
    token = params.get('device_token')
    if not token:
        resp = error_result(ErrorCode.ERROR_INVALID_PARAM)
    else:
        device = DisplayDevice.query.filter_by(token=token).first()
        if not device:
            resp = error_result(ErrorCode.ERROR_DISPLAY_DEVICE_NOT_EXIST)
        else:
            # prevent db from being updated too frequently
            if g.TIMESTAMP > device.heartbeat + 60:
                device.heartbeat = g.TIMESTAMP
                db.session.commit()

            screens = []
            for screen in device.screens:
                screens.append(screen.get_json())
            result = {
                'screens': screens,
                'device': device.get_json()
            }
            resp = success_result(result)
    resp.headers['Access-Control-Expose-Headers'] = 'Etag'
    if device:
        resp.headers['ETag'] = 'W/%s' % (device.reload_timestamp + device.display_info_timestamp + device.user_info_timestamp)
    else:
        resp.headers['ETag'] = 'W/0'
    return resp


@screen_blueprint.route('/screen/get')
def get_single_screen():
    resp = success_result()
    resp.headers['Access-Control-Expose-Headers'] = 'Etag'
    resp.headers['ETag'] = 'W/%s' % (g.TIMESTAMP)
    return resp


def get_device_from_params(params):
    token = params.get('device_token')
    if token is None:
        return None, ErrorCode.ERROR_INVALID_PARAM

    device = DisplayDevice.query.filter_by(token=str(token)).first()
    if not device:
        return None, ErrorCode.ERROR_DISPLAY_DEVICE_NOT_EXIST
    if not device.company:
        return None, ErrorCode.ERROR_COMPANY_NOT_EXIST
    return device, None


# Origin APIs
@screen_blueprint.route("/screen/set-theme", methods=['POST'])
def set_screen_theme():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)
    theme = params.get('theme')
    device.theme = theme
    device.reload_timestamp = g.TIMESTAMP
    db.session.add(device)
    db.session.commit()
    clear_display_config_cache(device.token)
    return success_result()


@screen_blueprint.route("/screen/get_theme_config")
def get_all_themes():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    theme_configs = get_ordered_theme_list(THEME_DIR, device)
    return success_result({
        "theme_config": theme_configs
    })


# for screenlib.js
@screen_blueprint.route('/screen/theme', methods=['GET', 'POST'])
def get_one_theme():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    theme = device.theme
    theme_config = get_theme_config(THEME_DIR, device)
    if theme not in theme_config:
        return error_result(ErrorCode.ERROR_INVALID_THEME)
    result = dict(config=theme_config[theme], card_duration=device.card_duration)
    return success_result(data=result)


surname = u"李王张刘陈杨黄赵周吴徐孙朱马胡郭林何高梁郑罗宋谢唐韩曹许邓萧冯曾程蔡彭潘袁董余苏叶吕魏蒋田杜丁姜范江傅钟卢戴崔任陆姚方金邱夏谭贾邹石孟秦段郝孔邵史常顾"
first_name = u"世中仁佩佳俊信伦伟杰仪元冠凯君哲嘉国士如娟婷宇安宏宗宜家建弘强彦彬德心志忠怡惠慧庆成政敏文昌明智晓柏荣欣正民永淑玉玲珊珍珮琪玮瑜瑞莹盈真祥秀秋颖立维美翰圣育良芬芳英菁华萍蓉裕豪贞贤郁铃铭雅雯霖青静韵鸿丽"
def generate_name():
    res = random.choice(surname) + random.choice(first_name)
    if random.randrange(3) != 0:
        res += random.choice(first_name)
    return res


#TODO 修改
@screen_blueprint.route("/screen/add-visitor", methods=['POST'])
def add_visitor():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    name = params.get('name')
    vip = params.get('vip', False)
    photo = request.files.get('photo')
    company = device.company

    if not photo:
        error_result(ErrorCode.ERROR_INVALID_PARAM)
    if not name:
        name = generate_name() + u'(临时名)'

    user_photo, error = create_user_photo(photo, company.id)
    if error:
        return error

    subject_type = SubjectType.TYPE_VIP if vip else SubjectType.TYPE_VISITOR
    start_time = g.TIMESTAMP - 5 * 60
    end_time = g.TIMESTAMP + 2 * 3600
    subject = Subject(company_id=company.id,
                      name=name,
                      subject_type=subject_type,
                      start_time=start_time,
                      end_time=end_time)
    db.session.add(subject)
    db.session.commit()

    user_photo.subject_id = subject.id
    db.session.add(user_photo)
    db.session.commit()

    update_company_data_version(company, subject.id)
    return success_result(subject.get_data())


@screen_blueprint.route('/screen/weather', methods=['GET'])
def get_weather():
    params = request.args or request.get_json() or request.form
    try:
        city_name = str(params['city'])
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    weather = WeatherManager.get_weather_by_city(city_name)
    if weather is None:
        return error_result(ErrorCode.ERROR_WEATHER_ERROR)
    return success_result(weather)


@screen_blueprint.route('/screen/avatars', methods=['GET'])
def get_user_info():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    avatars = list()
    for subject in device.company.subjects:
        if subject.avatar:
            avatars.append(storage.get_url(subject.avatar))
    return success_result({
        'avatars': avatars
    })


@screen_blueprint.route('/screen/custom.css')
def custom_css():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    card = device.card_theme or 'card16'
    try:
        theme_file = open(SCREEN_LIB_DIR + '/cards/css/' + card + '.css', 'r')
    except:
        return error_result(ErrorCode.ERROR_FILE_NOT_EXIST)
    content = theme_file.read()
    theme_file.close()
    return Response(content, mimetype='text/css')


@screen_blueprint.route('/screen/vip-cards.css')
def vip_cards_css():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    card = device.card_theme_vip or 'vip-card1'
    try:
        theme_file = open(SCREEN_LIB_DIR + '/vipcards/css/' + card + '.css', 'r')
    except:
        return error_result(ErrorCode.ERROR_FILE_NOT_EXIST)
    content = theme_file.read()
    theme_file.close()
    return Response(content, mimetype='text/css')


@screen_blueprint.route('/screen/custom.html')
def custom_html():
    params = request.args or request.get_json() or request.form
    device, err = get_device_from_params(params)
    if err is not None:
        return error_result(err)

    layout = BackgroundLayout.file_mapping[device.background_layout or BackgroundLayout.CENTER]
    try:
        layout_file = open(SCREEN_LIB_DIR + '/layouts/' + layout + '/template.html', 'r')
    except:
        return error_result(ErrorCode.ERROR_FILE_NOT_EXIST)
    content = layout_file.read()
    layout_file.close()
    return Response(content, mimetype='text/html')
