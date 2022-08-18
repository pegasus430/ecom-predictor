# pip install flask-login
# pip install flask

import os

from flask import (Flask, request, render_template, jsonify)

import flask_login
from auth import user_loader
from compare import adjusted_compare, adjusted_compare_with_trim, exact_compare, exact_compare_with_trim
from videocompare import compare_videos
import urlparse
from os.path import splitext
import urllib
import re

app = Flask(__name__)
CWD = os.path.dirname(os.path.abspath(__file__))

app.secret_key = 'P9;VepcJ}ZgL:Sr3s7B&vAvT{a`E8TJ~t,\&4D_X4&z{*KE;'

CHECK_CREDENTIALS = False

login_manager = flask_login.LoginManager()
login_manager.user_callback = user_loader
login_manager.init_app(app)


def get_ext(url):
    """Return the filename extension from url, or ''."""
    url_parts = urlparse.urlparse(url)
    root, ext = splitext(url_parts.path)

    return ext


def get_video_filename(url, prefix, index):
    return '/tmp/{prefix}_video_{index}{ext}'.format(
        prefix=prefix,
        index=index,
        ext=get_ext(url)
    )


def download_video(url, prefix, index):
    try:
        video = urllib.urlopen(url)
    except:
        return False
    else:
        if video is None\
                or video.getcode() != 200:
            return False

        with open(get_video_filename(url, prefix, index), 'wb') as video_file:
            video_file.write(video.read())

    return True


def get_image_filename(prefix, index):
    return '/tmp/{prefix}_image_{index}.jpg'.format(
        prefix=prefix,
        index=index
    )


def download_image(url, prefix, index):
    allowed_types = ['image/jpeg']

    try:
        image = urllib.urlopen(url)
    except:
        return False
    else:
        if image is None\
                or image.getcode() != 200\
                or image.headers.type not in allowed_types:
            return False

        with open(get_image_filename(prefix, index), 'wb') as image_file:
            image_file.write(image.read())

    return True


class ApiError(Exception):
    def __init__(self, message, code=400):
        super(ApiError, self).__init__(message)

        self.code = code


def get_param(name, multi=False):
    values = request.values.getlist(name)

    if len(values) == 0:
        for param_name, param_value in request.values.items(multi=multi):
            if re.match(r'^{}\[\d*\]$'.format(name), param_name):
                values.append(param_value)

    if multi:
        return values

    return values[0] if len(values) > 0 else None


def validate_url(url):
    url_parts = urlparse.urlparse(url)

    return bool(url_parts.scheme)


@app.route('/compare', methods=['GET', 'POST'])
def compare():
    try:
        missing_params = []

        media_type = get_param('media_type')
        if not media_type:
            missing_params.append('media_type')

        first_url = get_param('first_url')
        if not first_url:
            missing_params.append('first_url')

        second_url = get_param('second_url', multi=True)
        if not second_url:
            missing_params.append('second_url')

        compare_method = get_param('compare_method')
        if media_type == 'image' and not compare_method:
            missing_params.append('compare_method')

        if missing_params:
            raise ApiError('Missing params: {}'.format(', '.join(missing_params)))

        if not validate_url(first_url):
            raise ApiError('The first_url {} field must contain a valid URL'.format(first_url))

        results = []

        if media_type == 'image':
            if compare_method not in ('local', 'base'):
                raise ApiError("The acceptable values for compare_method field are 'local' and 'base'")

            if not download_image(first_url, 1, 0):
                raise ApiError("The media file from first_url {} is no longer available".format(first_url),
                               code=200)

            trim_fuzz = get_param('trim_fuzz')
            if trim_fuzz is not None:
                trim_fuzz = re.sub(r'[^\d.]+', '', trim_fuzz)
                trim_fuzz = float(trim_fuzz) if trim_fuzz else 0

            for index, url in enumerate(second_url):
                result = {
                    'first_url': first_url,
                    'second_url': url,
                    'error': False,
                    'result': None,
                    'message': None,
                }

                if not validate_url(url):
                    result['message'] = 'The second_url {} must contain a valid URL'.format(url)
                    result['error'] = True
                elif not download_image(url, 2, index):
                    result['message'] = 'The media file from second_url {} is no longer available'.format(url)
                    result['error'] = True
                else:
                    try:
                        if compare_method == "local":
                            if trim_fuzz:
                                match_percent = adjusted_compare_with_trim(get_image_filename(1, 0),
                                                                           get_image_filename(2, index),
                                                                           trim_fuzz)
                            else:
                                match_percent = adjusted_compare(get_image_filename(1, 0),
                                                                 get_image_filename(2, index))
                        else:
                            if trim_fuzz:
                                match_percent = exact_compare_with_trim(get_image_filename(1, 0),
                                                                        get_image_filename(2, index),
                                                                        trim_fuzz)
                            else:
                                match_percent = exact_compare(get_image_filename(1, 0),
                                                              get_image_filename(2, index))

                        result['result'] = match_percent
                    except Exception as e:
                        result['message'] = 'ERROR: {}'.format(e)
                        result['error'] = True

                results.append(result)
        elif media_type == 'video':
            if not download_video(first_url, 1, 0):
                raise ApiError("The media file from first_url {} is no longer available".format(first_url),
                               code=200)

            for index, url in enumerate(second_url):
                result = {
                    'first_url': first_url,
                    'second_url': url,
                    'error': False,
                    'result': None,
                    'message': None,
                }

                if not validate_url(url):
                    result['message'] = 'The second_url {} must contain a valid URL'.format(url)
                    result['error'] = True
                elif not download_video(url, 2, index):
                    result['message'] = 'The media file from second_url {} is no longer available'.format(url)
                    result['error'] = True
                else:
                    try:
                        match_percent = compare_videos(get_video_filename(first_url, 1, 0),
                                                       get_video_filename(url, 2, index))
                        result['result'] = match_percent
                    except Exception as e:
                        result['message'] = 'ERROR: {}'.format(e)
                        result['error'] = True

                results.append(result)
        else:
            raise ApiError("The acceptable values for media_type field are 'image' and 'video'")

        if len(results) == 1:
            return jsonify(results[0])
        else:
            return jsonify(results)

    except ApiError as e:
        return jsonify({
            'error': True,
            'result': None,
            'message': e.message
        }), e.code


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(port=8000, host='127.0.0.1')
