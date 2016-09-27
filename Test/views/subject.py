# encoding=utf-8
import datetime
import json
import time
import zipfile
import StringIO
import traceback

import xlrd
from flask import Blueprint, render_template, g, request
from flask.ext.login import login_required
from sqlalchemy import or_
import zipstream
from flask import Response, stream_with_context

from app.common.constants import Gender, SubjectType, VisitorPurpose, AccountPermission
from app.common.error_code import ErrorCode
from app.common.json_builder import success_result, error_result
from app.common.permission import permission_required_page
from app.common.view_helper import update_company_data_version, create_user_photo, \
    get_subject_list
from app.foundation import db, storage
from app.models import Photo, Subject, DisplayDevice, PhotoAlternative
from app.common.logger import logger


subject_blueprint = Blueprint('subject', __name__, template_folder='templates')


@subject_blueprint.route('/subject/employee')
@login_required
@permission_required_page(AccountPermission.ADD_EMPLOYEE)
def subject_employee():
    gender = Gender.state_mapping
    return render_template('page/subject/index.html', subject_type_options=SubjectType.get_select_options(),
                           gender=gender, category='employee', subject_type=SubjectType.TYPE_EMPLOYEE)


@subject_blueprint.route('/subject/visitor')
@login_required
@permission_required_page(AccountPermission.ADD_VISITOR)
def subject_visitor():
    gender = Gender.state_mapping
    return render_template('page/subject/index.html', subject_type_options=SubjectType.get_select_options(),
                           gender=gender, category='visitor', subject_type=SubjectType.TYPE_VISITOR,
                           purpose=VisitorPurpose.state_mapping)


@subject_blueprint.route('/subject/list')
@login_required
def subject_list():
    company = g.user.company
    params = request.args
    ret = get_subject_list(company, params)
    if ret[0] is None:
        return error_result(ret[1])
    return success_result(ret[0], ret[1])


@subject_blueprint.route('/subject/all')
@login_required
def subject_all():
    if not g.user.has_permission(AccountPermission.ADD_EMPLOYEE):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)
    subjects = g.user.company.subjects.filter(Subject.subject_type == SubjectType.TYPE_EMPLOYEE).all()
    ret = {}
    for subject in subjects:
        ret[subject.id] = {
            "id": subject.id,
            "name": subject.real_name,
            "department": subject.department,
            "title": subject.title,
            "avatar": subject.avatar
        }
    return success_result(ret)


def _update_photos(subject, photos):
    photos_exist = set([photo.id for photo in subject.photos])
    photos = set(photos)
    if photos_exist - photos != set():
        useless_photos = Photo.query.filter(Photo.id.in_(photos_exist - photos)).all()
        for photo in useless_photos:
            storage.remove(photo.url)
            db.session.delete(photo)
            db.session.query(PhotoAlternative).filter(PhotoAlternative.subject_id == photo.subject_id). \
                filter(PhotoAlternative.url == photo.url).delete()

    if photos - photos_exist != set():
        Photo.query.filter(Photo.id.in_(photos - photos_exist)). \
            update({'subject_id': subject.id}, synchronize_session=False)

    db.session.commit()


@subject_blueprint.route('/subject', methods=['POST'])
@login_required
def subject_new():
    params = request.form or request.get_json()
    try:
        company_id = g.user.company_id
        subject_type = int(params['subject_type'])
        visitor_type = SubjectType.TYPE_VISITOR if params.get('visitor_type') is None else int(params['visitor_type'])
        name = params.get('name', '')
        email = params.get('email', '')
        phone = params.get('phone', '')
        gender = int(params.get('gender', Gender.MALE))
        avatar = params.get('avatar', '')
        department = params.get('department', '')
        title = params.get('title', '')
        description = params.get('description', '')
        start_time = int(params['start_time']) if subject_type != SubjectType.TYPE_EMPLOYEE else 0
        end_time = int(params['end_time']) if subject_type != SubjectType.TYPE_EMPLOYEE else 0
        photo_ids = params['photo_ids'] if 'photo_ids' in params else []
        purpose = int(params.get('purpose', VisitorPurpose.OTHER))
        interviewee = params.get('interviewee', '')
        come_from = params.get('come_from', '')
        job_number = params.get('job_number', '')
        remark = params.get('remark', '')
        birthday = int(params.get('birthday', 0))
        entry_date = int(params.get('entry_date', 0))
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if ((subject_type == SubjectType.TYPE_VISITOR and not g.user.has_permission(AccountPermission.ADD_VISITOR)) or
            (subject_type == SubjectType.TYPE_EMPLOYEE and not g.user.has_permission(AccountPermission.ADD_EMPLOYEE))):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    # VIP type
    if subject_type == SubjectType.TYPE_VISITOR:
        subject_type = visitor_type

    if email and Subject.query.filter_by(email=email).first():
        return error_result(ErrorCode.ERROR_EMAIL_EXISTED)

    subject = Subject(company_id=company_id, subject_type=subject_type, name=name, email=email, department=department,
                      gender=gender, avatar=avatar, title=title, description=description, start_time=start_time,
                      end_time=end_time, password='123456', purpose=purpose, interviewee=interviewee, phone=phone,
                      come_from=come_from, job_number=job_number, remark=remark, create_time=g.TIMESTAMP)
    if birthday:
        subject.birthday = datetime.date.fromtimestamp(birthday)
    if entry_date:
        subject.entry_date = datetime.date.fromtimestamp(entry_date)
    if subject.avatar:
        avatar = storage.save_image_base64(subject.avatar, 'avatar', sync=True)
        if avatar:
            subject.avatar = avatar
        DisplayDevice.query.filter_by(company_id=company_id).update({'user_info_timestamp': g.TIMESTAMP})
    try:
        db.session.add(subject)
        db.session.commit()
        update_company_data_version(subject.company, subject.id)
        _update_photos(subject, photo_ids)
        return success_result(subject.get_json(with_photos=True))
    except:
        db.session.rollback()
        return error_result(ErrorCode.ERROR_UNKNOWN)


@subject_blueprint.route('/subject/<int:sid>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def subject_detail(sid):
    params = request.form or request.get_json() or request.args

    subject = g.user.company.subjects.filter_by(id=sid).first()
    if not subject:
        return error_result(ErrorCode.ERROR_SUBJECT_NOT_EXIST)

    if request.method == 'GET':
        return success_result(subject.get_json(with_photos=True))

    subject_type = subject.subject_type
    if ((subject_type == SubjectType.TYPE_VISITOR and not g.user.has_permission(AccountPermission.ADD_VISITOR)) or
            (subject_type == SubjectType.TYPE_EMPLOYEE and not g.user.has_permission(AccountPermission.ADD_EMPLOYEE))):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    if request.method == 'PUT':
        email = params.get('email')
        avatar = params.get('avatar')
        if email and Subject.query.filter(Subject.id != sid, Subject.email == email).first():
            return error_result(ErrorCode.ERROR_EMAIL_EXISTED)

        if params.get('visitor_type') is not None:
            params['subject_type'] = params['visitor_type']
        fields = (
            'subject_type',
            'description',
            'title',
            'gender',
            'start_time',
            'end_time',
            'department',
            'name',
            'email',
            'phone',
            'purpose',
            'interviewee',
            'come_from',
            'job_number',
            'remark'
        )
        subject.update(fields, params)

        if avatar is None:
            pass
        elif avatar.startswith('http'):
            pass
        elif avatar == '':
            storage.remove(subject.avatar)
            subject.avatar = ''
        elif avatar.startswith('data:image'):
            avatar_url = storage.save_image_base64(avatar, 'avatar', sync=True)
            if avatar_url:
                storage.remove(subject.avatar)
                subject.avatar = avatar_url
            DisplayDevice.query.filter_by(company_id=subject.company.id).update({'user_info_timestamp': g.TIMESTAMP})

        if 'photo_ids' in params:
            _update_photos(subject, params['photo_ids'])
        if 'birthday' in params:
            subject.birthday = datetime.date.fromtimestamp(int(params['birthday'])) if params['birthday'] else None
        if 'entry_date' in params:
            subject.entry_date = datetime.date.fromtimestamp(int(params['entry_date'])) if params[
                'entry_date'] else None
        db.session.add(subject)
        db.session.commit()
        update_company_data_version(subject.company, subject.id)
    elif request.method == 'DELETE':
        for photo in subject.photos:
            storage.remove(photo.url)
        db.session.delete(subject)
        db.session.commit()
        update_company_data_version(subject.company, subject.id)
    return success_result(subject.get_json(with_photos=True))


@subject_blueprint.route('/subject/reset-password/<int:sid>', methods=['PUT'])
@login_required
def subject_reset_password(sid):
    subject = Subject.query.get(sid)
    if subject is None:
        return error_result(ErrorCode.ERROR_SUBJECT_NOT_EXIST)
    subject.password = '123456'
    subject.password_reseted = False
    db.session.add(subject)
    db.session.commit()
    return success_result()


@subject_blueprint.route('/subject/avatar', methods=['POST'])
@login_required
def subject_avatar_create():
    try:
        avatar = request.files['avatar']
        subject_id = int(request.form.get('subject_id', 0))
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    if not avatar:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    image_uri = storage.save_image(avatar.stream, 'avatar', resize=(300, 300), sync=True)
    if not image_uri:
        return error_result(ErrorCode.ERROR_UNKNOWN)

    if subject_id:
        subject = Subject.query.get(subject_id)
        subject.avatar = image_uri
        db.session.add(subject)
        db.session.commit()
        update_company_data_version(g.user.company, subject.id)
    return success_result({'url': storage.get_url(image_uri)})


@subject_blueprint.route('/subject/photo', methods=['POST'])
@login_required
def subject_photo_create():
    try:
        payload = request.files['photo']
        subject_id = int(request.form.get('subject_id', 0))
        old_photo_id = int(request.form.get('old_photo_id', 0))
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not payload:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if subject_id:
        subject = Subject.query.filter_by(id=subject_id).first()
        if subject is None:
            return error_result(ErrorCode.ERROR_INVALID_PARAM)
        subject_type = subject.subject_type
        if ((subject_type == SubjectType.TYPE_VISITOR and not g.user.has_permission(AccountPermission.ADD_VISITOR)) or
                (subject_type == SubjectType.TYPE_EMPLOYEE and not g.user.has_permission(
                        AccountPermission.ADD_EMPLOYEE))):
            return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    photo, error = create_user_photo(payload, g.user.company_id)
    if error:
        return error

    # delete old photo
    if subject_id and old_photo_id:
        old_photo = Photo.query.get(old_photo_id)
        if old_photo and old_photo.subject_id == subject_id:
            storage.remove(old_photo.url)
            db.session.delete(old_photo)
            db.session.query(PhotoAlternative).filter(PhotoAlternative.subject_id == old_photo.subject_id). \
                filter(PhotoAlternative.url == old_photo.url).delete()

    if subject_id:
        photo.subject_id = subject_id
    db.session.add(photo)
    db.session.commit()
    if subject_id:
        update_company_data_version(g.user.company, subject.id)
    return success_result(photo.get_json())


@subject_blueprint.route('/subject/import-photo', methods=['POST'])
@login_required
def subject_import_photo():
    try:
        photo = request.files['photo']
        name = photo.filename.rsplit('.', 1)[0]
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)
    photo, error = create_user_photo(photo, g.user.company_id)
    if error:
        return error
    subject = Subject(company_id=g.user.company_id, subject_type=SubjectType.TYPE_EMPLOYEE,
                      name=name, create_time=g.TIMESTAMP)
    subject.photos.append(photo)
    db.session.add(subject)
    db.session.commit()
    update_company_data_version(g.user.company, subject.id)
    return success_result(subject.get_json(with_photos=True))


@subject_blueprint.route('/subject/import', methods=['POST'])
@login_required
def subject_import():
    try:
        file_ = request.files['file']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not g.user.has_permission(AccountPermission.ADD_EMPLOYEE):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    workbook = xlrd.open_workbook(file_contents=file_.read())
    sheet = workbook.sheet_by_index(0)
    success = 0
    failed = []

    for i in xrange(1, sheet.nrows):
        try:
            row = sheet.row(i)
            name = row[0].value
            email = row[5].value
            if email and Subject.query.filter_by(email=email).first():
                failed.append(dict(name=name, email=email))
                continue
            if not name.strip():
                continue
            db.session.add(Subject(name=name, job_number=row[1].value, department=row[2].value, password='123456',
                                   title=row[3].value, phone=row[4].value, email=email, description=row[6].value,
                                   remark=row[7].value,
                                   subject_type=SubjectType.TYPE_EMPLOYEE, company_id=g.user.company_id))
            db.session.commit()
            success += 1
        except:
            import traceback;

            print traceback.format_exc()
    return success_result({'success': success, 'total': sheet.nrows - 1, 'failed': failed})


@subject_blueprint.route('/subject/import-visitor', methods=['POST'])
@login_required
def subject_import_visitor():
    try:
        file_ = request.files['file']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    if not g.user.has_permission(AccountPermission.ADD_VISITOR):
        return error_result(ErrorCode.ERROR_PERMISSION_DENIED)

    workbook = xlrd.open_workbook(file_contents=file_.read())
    sheet = workbook.sheet_by_index(0)
    success = 0

    state_mapping = VisitorPurpose.state_mapping_reverse

    for i in xrange(1, sheet.nrows):
        try:
            row = sheet.row(i)
            name = row[0].value
            db.session.add(
                Subject(name=name, purpose=state_mapping[row[1].value], come_from=row[2].value, phone=row[3].value,
                        interviewee=row[4].value, remark=row[5].value,
                        subject_type=SubjectType.TYPE_VISITOR, company_id=g.user.company_id))
            db.session.commit()
            success += 1
        except:
            import traceback;

            print traceback.format_exc()
            pass
    return success_result({'success': success, 'total': sheet.nrows - 1, 'failed': []})


@subject_blueprint.route('/subject/export.zip', methods=['GET'])
@login_required
def subject_export():
    def iterable(url):
        try:
            with open(storage.get_path(url)) as f:
                yield f.read()
        except:
            yield ''

    def generator(subjects):
        data = []
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        for subject in subjects:
            subject_json = subject.get_json()
            subject_json['photos'] = []
            for photo in subject.photos:
                short_url = '/'.join(photo.url.split('/')[-2:])
                z.write_iter(short_url, iterable(photo.url))
                subject_json['photos'].append(short_url)
            data.append(subject_json)

        z.writestr('index.json', json.dumps(data, indent=2))
        for zip_data in z:
            yield zip_data

    subjects = g.user.company.subjects.filter(or_(Subject.subject_type == SubjectType.TYPE_EMPLOYEE,
                                                  Subject.end_time > time.time())) \
        .options(db.eagerload_all(Subject.photos))
    response = Response(generator(subjects), mimetype='application/zip')
    response.headers['Content-Disposition'] = 'attachment; filename={}'.format('export.zip')
    return response


@subject_blueprint.route('/subject/import.zip', methods=['POST'])
@login_required
def subject_import_zip():
    try:
        upload = request.files['file']
    except:
        return error_result(ErrorCode.ERROR_INVALID_PARAM)

    def generator(company):
        z = zipfile.ZipFile(upload, 'r')
        data = json.loads(z.read('index.json'))
        total = len(data)
        now = 0
        email_dup = 0
        try:
            for subject_data in data:
                now += 1
                error_code = None
                try:
                    photos = []
                    success_photo = failed_photo = 0

                    for photo in subject_data['photos']:
                        photo, error = create_user_photo(StringIO.StringIO(z.read(photo)), company.id)
                        if not error:
                            photos.append(photo)
                            success_photo += 1
                        else:
                            failed_photo += 1

                    del subject_data['id']
                    del subject_data['photos']
                    subject_data['company_id'] = company.id
                    subject_data['avatar'] = ''

                    date = subject_data['birthday']
                    if type(date) is int:
                        subject_data['birthday'] = datetime.date.fromtimestamp(date)

                    date = subject_data['entry_date']
                    if type(date) is int:
                        subject_data['entry_date'] = datetime.date.fromtimestamp(date)

                    # 判断email是否已经存在
                    email = subject_data['email']
                    if email and Subject.query.filter_by(email=email).first():
                        print email
                        email_dup += 1
                        error_code = ErrorCode.ERROR_EMAIL_EXISTED

                    if error_code is None:
                        subject = Subject(**subject_data)
                        subject.photos = photos
                        db.session.add(subject)
                except:
                    logger.error('/subject/import.zip exception: ' + str(traceback.format_exc()))
                    error_code = ErrorCode.ERROR_UNKNOWN

                    # 建议email字段默认为空字符串，如果有重复，则赋值
                yield json.dumps(
                    dict(now=now, total=total, name=subject_data.get('name'), success=success_photo, fail=failed_photo,
                         email=email if error_code == ErrorCode.ERROR_EMAIL_EXISTED else '')) + '\n'
            print 'email duplicate', email_dup
            update_company_data_version(company, 0)
            z.close()
        except:
            db.session.rollback()
            z.close()

    response = Response(stream_with_context(generator(g.user.company)))
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@subject_blueprint.route('/subject/invite', methods=['GET', 'POST'])
def subject_invite_page():
    subject_id = request.args.get('subject_id')
    token = request.args.get('token')
    if not subject_id or not token:
        return "非法请求"
    try:
        subject_id = int(subject_id)
    except:
        return "非法请求"

    subject = Subject.query.filter(Subject.id == subject_id, Subject.subject_type != SubjectType.TYPE_EMPLOYEE).first()
    if not subject:
        return "链接已失效"

    if g.TIMESTAMP > subject.end_time or subject.job_number != token:
        return "链接已失效"

    if request.method == 'GET':
        return render_template('page/subject/invite.html', subject=subject.get_json(with_photos=True), error='')
    elif request.method == 'POST':
        payload = request.files['photo']
        photo, err = create_user_photo(payload, subject.company_id)
        if err:
            return err
        db.session.add(photo)
        db.session.commit()
        _update_photos(subject, [photo.id])
        update_company_data_version(subject.company, subject.id)
        return success_result(photo.get_json())
