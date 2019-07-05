# /usr/bin/python3

from io import BytesIO
from calendar import isleap
from datetime import date, timedelta

from scipy.integrate import quad
from scipy.optimize import root_scalar

from PIL import Image
from numpy import cos, pi, square
from flask import Flask, request, send_file, abort

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

        yield (key, result_from_aphelion.root * 180 / pi)

date_to_rotation = dict(iterate_rotation_degree())

app = Flask(__name__)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/chrome.png')
def chrome():
    try:
        im = request.args.get('im', 'qq')
        key = request.args.get('date', date.today().strftime('%m-%d'))

        assert im == 'qq' or im == 'tim' or im == 'telegram'
        rotation = date_to_rotation[key] - date_to_rotation["09-23"] + 60

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
