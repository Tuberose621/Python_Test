# coding=utf-8
import os
import logging

DEBUG = True
DEBUG_CAPTCHA = True
LOGGING_LEVEL = logging.INFO
BASEDIR = os.path.abspath(os.path.dirname(__file__))

# flask
WTF_CSRF_ENABLED = False
SECRET_KEY = 'koala_secret_key_!@#%!fasdgnjwehtwTT#$DF43ys_v1'

# db
SQLALCHEMY_POOL_RECYCLE = 10
#SQLALCHEMY_ECHO = True
SQLALCHEMY_POOL_SIZE = 30
SQLALCHEMY_TRACK_MODIFICATIONS = True
MYSQL_USER = 'root'
MYSQL_PASS = ''
MYSQL_HOST = 'localhost'
MYSQL_PORT = '3306'
MYSQL_DB = 'koala_online'

SQLALCHEMY_DATABASE_URI = 'mysql://%s:%s@%s:%s/%s?charset=utf8' % (MYSQL_USER, MYSQL_PASS, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
# SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, 'security.db')


# data
STATIC_DIR = BASEDIR + \
             '/app/static'
TMP_DIR = '/tmp/koala-online/static'

THEME_DIR = BASEDIR + "/app/static/screen/theme"
THEME_URL = '/static/screen/theme'
SCREEN_LIB_URL = '/static/screen/lib'
SCREEN_LIB_DIR = BASEDIR + '/app' + SCREEN_LIB_URL



# face core

CORE_MODELS = {
    1: {
        'name': 'T1',
        'service': '10.101.3.48:6379',
        'packages': [
            {
                'name': 'gpumodel',
                'url': 'http://7vigzf.com1.z0.glb.clouddn.com/gpumodel_t1.tgz.enc',
                'sha256': '2f42a2533161d7a80df80b37c36ad8f18224221d7e07b2c10dc629635f411701',
                'key': 'IwFxDrQ823i+etsWwvhYDvHia3TDHBQWdxGR/1bhaOQ=',
                'command': 'true',
                'args': []
            }
        ],
        'leaf-params': [
            '-fpp.model=../gpumodel/gpumodel',
            '-fpp.modeltype=t1',
        ]
    },
    2: {
        'name': 'SV4',
        'service': '10.101.3.48:6379',
        'packages': [
                {
                    'name': 'model_sv4',
                    'url': 'http://7xng0a.com1.z0.glb.clouddn.com/model_sv4.tgz.enc',
                    'sha256': '2589d217faad57647c4fc2ed440c49a4ab4fb7c98e8ffcae4cb291436a2254c7',
                    'key': '2HLXLstj+X3XGeSPQR90qxETAOgcaQOiz62Iz8orsn8=',
                    'command': 'true',
                    'args': []
                }
        ],
        'leaf-params': [
            '-fpp.model=../model_sv4/model_sv4',
            '-fpp.modeltype=sv4',
        ]
    },
    3: {
        'name': 'SV6',
        'service': '10.101.3.48:6379',
        #'service': '10.101.6.220:8080',

        'packages': [
                {
                    'name': 'model_sv6_2',
                    'url': 'http://7xng0a.com1.z0.glb.clouddn.com/model_sv6_2.tgz.enc',
                    'sha256': '540ceaf73b3128af3f854366c554c9b810136950e0f234d09bf8f5a43c0375ce',
                    'key': 'jR3Tw7oV4WmyC5dsfOQfZ3hKsFdruc4eIzQM2zte7cs=',
                    'command': 'true',
                    'args': []
                }
        ],
        'leaf-params': [
            '-fpp.model=../model_sv6_2/model_sv6_2',
            '-fpp.modeltype=sv6_2',
        ]
    }
}

SECRET_FILE_PATH = '/home/koala/.google_authenticator'


# image
VERIFY_CODE_FONTS = [
    BASEDIR + '/app/static/css/fonts/aller-bold.ttf'
]


# Domain
DOMAIN = ''

# custom theme
SCREEN_BG_STATIC = {
    'size': (1920, 1080),
    'video_position': (1398, 743),
    'logo_position': (161, 114),
    'time_position': (1586, 115)
}



# email
MAIL_SERVER = 'smtp.126.com'
MAIL_PORT = 994
MAIL_USE_TLS = False
MAIL_USE_SSL = True
MAIL_USERNAME = 'megviitest'
MAIL_PASSWORD = 'legjasinpdxywhyv'
MAIL_DEFAULT_SENDER = 'megviitest@126.com'
MAIL_FAIL_SILENTLY = False
MAIL_DEBUG = True


# Weather
WEATHER_API_KEY = 'ac58ae4c287f5e9cde112a75c82bebb2'
UPDATE_WEATHER_INTERVAL = 30 * 60

# qiniu
QINIU_ACCESS_KEY = ''
QINIU_SECRET_KEY = ''
QINIU_BUCKET_NAME = ''
QINIU_IMAGE_HOSTNAME = 'http://.../'
QINIU_AVAILABLE = False

#redis
REDIS_URI = 'redis://127.0.0.1:6379/0'
RQ_DEFAULT_URL = REDIS_URI


# Push
JPUSH_APP_KEY = ''
JPUSH_SECRET = ''
APNS_PRODUCTION = True
PUSH_AVAILABLE = False

# BOX-VERSION
DEFAULT_BOX_VERSION = 'v1.3-v2.6.1'

# FOR SMS
ALIDAYU_APP_KEY = ''
ALIDAYU_SECRET = ''

# 人脸最低质量
FACE_QUALITY_LIMIT = 0.7

# 前端版本控制
PRODUCT_RELEASE = {
    'RELEASE': False,
    'DEBUG': True,
    'VERSION': '1.3.4'
}
