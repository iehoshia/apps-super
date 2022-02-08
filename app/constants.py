import os
from datetime import datetime
from decimal import Decimal

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHeaderView

EMAIL = 'jepgez@gmail.com'

PATH_PRINTERS = '/dev/usb'

UTC_OFFSET_TIMEDELTA = datetime.now() - datetime.utcnow()
DELTA_LOCALE = round(UTC_OFFSET_TIMEDELTA.total_seconds() / 60 / 60)
RATE_CREDIT_LIMIT = 0.8

STRETCH = QHeaderView.Stretch
alignRight = Qt.AlignRight
alignLeft = Qt.AlignLeft
alignCenter = Qt.AlignCenter
alignVCenter = Qt.AlignVCenter
alignHCenter = Qt.AlignHCenter

DIALOG_REPLY_NO = 0
DIALOG_REPLY_YES = 1
ZERO = Decimal('0')

FRACTIONS = [
    ('', ''),
    ('1', '1'),
    ('0.5', '1/2'),
    ('0.25', '1/4'),
    ('0.125', '1/8'),
    ('0.0625', '1/16'),
    ('0.0313', '1/32')
]

current_dir = os.path.dirname(__file__)

SCREENS = {
    'large': os.path.join(current_dir, 'large_screen.css'),
    'medium': os.path.join(current_dir, 'medium_screen.css'),
    'small': os.path.join(current_dir, 'small_screen.css')
}

FILE_BANNER = os.path.join(current_dir, 'share', 'pos_banner.png')

_YEAR = datetime.now().year
_MONTH = datetime.now().month

MONTHS = [{'id':'A','name':"Enero",},
          {'id':'B','name':"Febrero",},
          {'id':'C','name':"Marzo",},
          {'id':'D','name':"Abril",},
          {'id':'E','name':"Mayo",},
          {'id':'F','name':"Junio",},
          {'id':'G','name':"Julio",},
          {'id':'H','name':"Agosto",},
          {'id':'I','name':"Septiembre",},
          {'id':'J','name':"Octubre",},
          {'id':'K','name':"Noviembre",},
          {'id':'L','name':"Diciembre",},
          ]