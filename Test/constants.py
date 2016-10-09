# encoding=utf-8

class ConstransBase(object):

    @classmethod
    def get_desc(cls, key):
        if cls.state_mapping.has_key(key):
            return cls.state_mapping.get(key)
        return 'unknown'

    @classmethod
    def get_select_options(cls):
        options = cls.state_mapping.items()
        return options

    @classmethod
    def parse_param(cls, param):
        return cls.param_mapping.get(param, None)

class UserRole(ConstransBase):
    # warning you can not set zero value, this is db primary key
    ROLE_ROOT = 1
    ROLE_ADMIN = 2
    ROLE_NORMAL = 3
    ROLE_ORGANIZATION = 4

    state_mapping = {
        ROLE_ROOT: u'root',
        ROLE_ADMIN: u'管理员',
        ROLE_NORMAL: u'普通用户',
        ROLE_ORGANIZATION: u'组织账号'
    }


class Gender(ConstransBase):
    UNKNOW = 0
    MALE = 1
    FEMALE = 2

    state_mapping = {
        UNKNOW: u'未选择',
        MALE: u'男',
        FEMALE: u'女',
    }

    _name_mapping = dict(map(lambda a: (a[1], a[0]), state_mapping.items()))

    @classmethod
    def parse(cls, name):
        return cls._name_mapping.get(name, cls.UNKNOW)


class SubjectType(ConstransBase):
    TYPE_EMPLOYEE = 0
    TYPE_VISITOR = 1
    TYPE_VIP = 2

    state_mapping = {
        TYPE_EMPLOYEE: u'员工',
        TYPE_VISITOR: u'访客',
        TYPE_VIP: u'VIP'
    }

    param_mapping = {
        'employee': TYPE_EMPLOYEE,
        'visitor': TYPE_VISITOR,
        'vip': TYPE_VIP
    }


class MobileOS(ConstransBase):
    TYPE_ANDROID = 1
    TYPE_IOS = 2

    state_mapping = {
        TYPE_ANDROID: u'安卓',
        TYPE_IOS: u'IOS'
    }

    param_mapping = {
        'android': TYPE_ANDROID,
        'ios': TYPE_IOS
    }


class ScreenType(ConstransBase):
    CAMERA = 1
    DOOR_PAD = 2
    FRONT_PAD = 3

    state_mapping = {
        CAMERA: u'摄像头',
        DOOR_PAD: u'门禁Pad',
        FRONT_PAD: u'前台Pad'
    }

class CameraStatus(ConstransBase):
    OK = 0
    ERROR = 1

    state_mapping = {
        OK: u'正常',
        ERROR: u'异常'
    }


class VisitorPurpose(ConstransBase):
    OTHER = 0
    INTERVIEW = 1
    BUSINESS = 2
    FRIENDS = 3
    EXPRESS = 4

    state_mapping = {
        OTHER: u"其他",
        INTERVIEW: u"面试",
        BUSINESS: u"商务",
        FRIENDS: u"亲友",
        EXPRESS: u"快递送货",
    }

    state_mapping_reverse = {
        u"其他": OTHER,
        u"面试": INTERVIEW,
        u"商务洽谈": BUSINESS,
        u"员工亲友": FRIENDS,
        u"快递送货": EXPRESS,
    }


class AttendanceStatus(ConstransBase):
    UNCHECKED = 0
    NORMAL = 1
    LATE = 2
    LEAVE_EARLY = 3
    ABSENTEEISM = 4

    state_mapping = {
        UNCHECKED: u'漏打卡',
        NORMAL: u'正常',
        LATE: u'迟到',
        LEAVE_EARLY: u'早退',
        ABSENTEEISM: u'缺勤'
    }


class BackgroundLayout(ConstransBase):
    CENTER = 1
    FULL = 2
    RIGHT = 3

    state_mapping = {
        CENTER: u'居中',
        FULL: u'全屏',
        RIGHT: u'居右'
    }

    file_mapping = {
        CENTER: 'center',
        FULL: 'full',
        RIGHT: 'right'
    }


class DeploymentVersion(ConstransBase):
    ONLINE = 1
    OFFLINE = 2

    state_mapping = {
        ONLINE: u'在线版',
        OFFLINE: u'离线版'
    }


class CompanyFunction(ConstransBase):
    ACCOUNTS = 1
    ATTENDANCE = 2
    VISITOR = 4
    USHER = 8
    STRANGER = 16
    ACCESS = 32

    state_mapping = {
        ACCOUNTS: u'多账户',
        ATTENDANCE: u'考勤',
        VISITOR: u'访客',
        USHER: u'迎宾',
        STRANGER: u'陌生人',
        ACCESS: u'门禁'

    }

class FeatureVersion(ConstransBase):
    T1 = 1
    SV4 = 2
    SV6 = 3

    state_mapping = {
        T1: u'T1',
        SV4: u'SV4',
        SV6: u'SV6'
    }


weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


class AccountPermission(ConstransBase):
    ADD_EMPLOYEE = 1
    ADD_VISITOR = 2
    REVIEW_ATTENDANCE = 3
    REVIEW_STRANGER = 4

    state_mapping = {
        ADD_EMPLOYEE: u'添加员工',
        ADD_VISITOR: u'添加访客',
        REVIEW_ATTENDANCE: u'查看考勤',
        REVIEW_STRANGER: u'查看陌生人'
    }
