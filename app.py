#!/usr/bin/python3

from re import compile
from json import dumps
from io import BytesIO
from calendar import isleap
from datetime import date, timedelta

from scipy.integrate import quad
from scipy.optimize import root_scalar

from PIL import Image
from numpy import cos, pi, square
from flask import Flask, Response, redirect, request, send_file, abort

json_number_re = compile(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?')

json_format = r'{"from":%s,"rotation_angle":%s,"rotation_speed":%s}'
rotation_format = r'{"degree":%s,"radius":%s}'

leap_day_step = (1 + 0.2425) / 2
earth_eccentricity = 0.0167086
tropical_year = 365.2425

def get_swept_area_derivative(angle, zero=0):
    return 0.5 / square(1 - earth_eccentricity * cos(angle))

def get_swept_area(angle, zero=0):
    return quad(get_swept_area_derivative, 0, angle)[0] - zero

def iterate_date_ratio():
    year = date.today().year
    while not isleap(year): year -= 1

    ordinal = tropical_year
    date_step = timedelta(1)
    date_aphelion = date(year, 7, 4)

    while ordinal > 0:
        date_aphelion -= date_step
        key = date_aphelion.strftime('%m-%d')
        ordinal -= leap_day_step if key == '02-28' or key == '02-29' else 1

        yield (key, ordinal / tropical_year)

def iterate_rotation_degree():
    max_area = get_swept_area(2 * pi)
    args = {'method': 'newton', 'fprime': get_swept_area_derivative}

    for key, ratio_from_aphelion in iterate_date_ratio():
        args['x0'] = 2 * pi * ratio_from_aphelion
        args['args'] = max_area * ratio_from_aphelion
        result_from_aphelion = root_scalar(get_swept_area, **args)

        angle = result_from_aphelion.root
        speed = max_area / get_swept_area_derivative(angle) / tropical_year

        yield (key, (angle * 180 / pi, speed * 180 / pi))

def format_to_json_number(number, fmt=None):
    json = str(number) if fmt is None else fmt % number
    assert json_number_re.fullmatch(json)
    return json

date_to_rotation = dict(iterate_rotation_degree())

app = Flask(__name__)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/')
def index():
    return redirect('https://github.com/ustc-zzzz/avatar-service')

@app.route('/chrome.png')
def chrome_png():
    try:
        im = request.args.get('im', 'qq')
        key = request.args.get('date', date.today().strftime('%m-%d'))

        if key.index('-') == 4:
            year, key = key.split('-', 1)
            assert key != '02-29' or isleap(int(year))

        assert key in date_to_rotation
        assert im == 'qq' or im == 'tim' or im == 'telegram'
        rotation = date_to_rotation[key][0] - date_to_rotation["09-23"][0] + 60

        image = Image.open('fake_chrome.png')
        image = image.rotate(rotation, resample=Image.CUBIC)

        if im == 'telegram':
            layer = Image.open('fake_chrome_telegram_layer.png')
            image.alpha_composite(layer, dest=(0, 0), source=(0, 0))

        io = BytesIO()
        image.save(io, 'PNG')

        io.seek(0)

        return send_file(io, mimetype='image/png')
    except:
        return abort(404)

@app.route('/chrome.json')
def chrome_json():
    try:
        today = date.today()
        to = today.strftime('%m-%d')
        fmt = request.args.get('format', None)
        key = request.args.get('from', '2017-11-24')

        if key.index('-') == 4:
            year, key = key.split('-', 1)
            assert key in date_to_rotation
            assert key != '02-29' or isleap(int(year))
        else:
            year = None
            assert key in date_to_rotation

        to_angle = date_to_rotation[to][0] - date_to_rotation['01-01'][0]
        from_angle = date_to_rotation[key][0] - date_to_rotation['01-01'][0]

        if year is None:
            day_diff = to_angle % 360 - from_angle % 360
            year = str(today.year - int(day_diff <= 0))
            year_diff = int(day_diff <= 0) * 360
        else:
            day_diff = to_angle % 360 - from_angle % 360
            year_diff = (today.year - int(year)) * 360

        angle_degree = year_diff + day_diff
        angle_radius = angle_degree * pi / 180

        speed_degree = date_to_rotation[to][1]
        speed_radius = speed_degree * pi / 180

        angle_degree = format_to_json_number(angle_degree, fmt=fmt)
        angle_radius = format_to_json_number(angle_radius, fmt=fmt)
        speed_degree = format_to_json_number(speed_degree, fmt=fmt)
        speed_radius = format_to_json_number(speed_radius, fmt=fmt)

        json_from = dumps('%s-%s' % (year, key))
        json_angle = rotation_format % (angle_degree, angle_radius)
        json_speed = rotation_format % (speed_degree, speed_radius)
        json_body = json_format % (json_from, json_angle, json_speed)

        return Response(json_body, status=200, mimetype='application/json')
    except:
        return abort(404)
