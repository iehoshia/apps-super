from PIL import Image, ImageDraw
from PyQt5.QtGui import QIcon
from io import BytesIO
from slugify import slugify

import os

current_dir = os.path.dirname(__file__)

def get_svg_icon(name):
    file_icon = name if name else 'fork'
    path_icon = os.path.join(current_dir, 'share', file_icon + '.svg')
    _icon = QIcon(path_icon)
    return _icon

def get_png_icon(name):
    name = slugify(name)

    file_icon = name if name else 'fork'
    path_icon = os.path.join(current_dir, 'tmp', file_icon + '.PNG')
    _icon = QIcon(path_icon)
    return _icon

def get_local_png_icon(name):
    name = slugify(name)

    file_icon = name if name else 'fork'
    path_icon = os.path.join(current_dir, 'share', file_icon + '.PNG') or \
        os.path.join(current_dir, 'share', file_icon + '.png') 
    _icon = QIcon(path_icon)
    return _icon

def create_icon_file(name, data):
    try:
        name = slugify(name)
        file_icon = name if name else 'fork'
        path_icon = os.path.join(current_dir, 'tmp', file_icon + '.png')
        image_data = BytesIO(data)
        image = Image.open(image_data)
        image.save(path_icon, 'PNG')
    except:
        pass

