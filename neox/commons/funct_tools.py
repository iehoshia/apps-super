# -*- coding: UTF-8 -*-
import time
import locale
from datetime import datetime

try:
    # FIXME
    # Set locale from config
    #from neo.commons.config import LOCALE
    locale.setlocale(locale.LC_ALL, str('es_CO.UTF-8'))
except:
    print("Warning: Error setting locale")

starttime = datetime.now()

def time_record(x):
    now = datetime.now()
    print(x, (now - starttime).total_seconds())


def time_dec(func):
    def time_mes(self, *arg):
        t1 = time.clock()
        res = func(self, *arg)
        t2 =  time.clock()
        delta = (t2 - t1) * 1000.0
        print('%s take %0.5f ms' % (func.__name__, delta))
        return res
    return time_mes
