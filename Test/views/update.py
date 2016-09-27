#! encoding=utf-8
__author__ = 'ding'
import json

from flask import Blueprint, request, Response

from app.common.json_builder import success_result
from app.common.redis_cache import cache
from app.models import Box, BoxVersion
from config import DEFAULT_BOX_VERSION, CORE_MODELS
from app.common.logger import logger


update = Blueprint('update', __name__)

@update.route('/update/updater')
@cache(['token'], 60)
def update_updater():
    token = request.args.get('token')
    model = 3

    box = Box.query.filter_by(box_token=token).first()
    if box is None or box.box_version is None:
        box_version = BoxVersion.query.filter_by(version=DEFAULT_BOX_VERSION).first()
    else:
        box_version = box.box_version
    if box_version is None:
        return Response(status=404)
    if box is not None:
        model = box.model

    config_text = box_version.config.replace('{{token}}', token)
    config_text = config_text.replace('{{facemin}}', '50')

    config = json.loads(config_text)

    leaf = None
    for package in config['packages']:
        if package['name'] == 'leaf':
            leaf = package
            break
    if leaf is None:
        return Response(status=500)


    if config_text.find('-fpp.model') == -1:
        if model in CORE_MODELS:
            model = CORE_MODELS[model]
            config['packages'] = model['packages'] + config['packages']
            leaf['args'].extend(model['leaf-params'])

    if box:
        leaf_config = box.get_leaf_config()
        if leaf_config.get('-video.facemin') == 50:
            del leaf_config['-video.facemin']

        if leaf_config:
            d = {}
            try:
                for arg in leaf['args'][1:]:
                    k, v = arg.split('=')
                    d[k] = v
                d.update(leaf_config)
                leaf['args'][1:] = [str(k) + '=' + str(v) for k, v in d.items()]
            except Exception, e:
                logger.error(e)

    config_text = json.dumps(config)
    return Response(config_text, content_type='application/json')


@update.route('/update/app')
def update_tv():
    client = request.args.get('client')
    version = request.args.get('version')

    latest_version = ''
    url = ''
    force = False
    description = ''

    if client == 'ios_mobile':
        latest_version = '1.2'

    elif client == 'ios_admin':
        latest_version = '1.2'

    elif client == 'android_mobile':
        latest_version = '1.2'
        url = 'http://7xqae9.com1.z0.glb.clouddn.com/megvii-%E5%91%98%E5%B7%A5-1.2-release.apk'

    elif client == 'android_admin':
        latest_version = '1.2'
        url = 'http://7xqae9.com1.z0.glb.clouddn.com/megvii-%E7%AE%A1%E7%90%86-1.1-release.apk'

    elif client == 'android_pad':
        latest_version = '1.2'
        url = 'http://7xqae9.com1.z0.glb.clouddn.com/megvii-pad-1.2-release.apk'

    elif client == 'android_tv':
        latest_version = '1.2'
        url = 'http://7xqae9.com1.z0.glb.clouddn.com/megvii-tv-1.2-release.apk'


    data = {
        'version': latest_version,
        'url': url,
        'force': force,
        'description': description
    }
    return success_result(data)


@update.route('/update/mobile/android')
def update_mobile_android():
    return '0'
