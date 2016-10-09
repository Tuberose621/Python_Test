# encoding=utf-8

from flask.ext.sqlalchemy import SQLAlchemy


from config import QINIU_AVAILABLE, REDIS_URI

class Redis(object):

    def __init__(self):
        self._db = None

    @property
    def db(self):
        return self._db

db = SQLAlchemy()