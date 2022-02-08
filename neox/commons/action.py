import subprocess
import os
import sys
import tempfile
import time
import win32api#win32print,win32api


from neox.commons.common import slugify, file_open
import neox.commons.rpc as rpc

from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import pyqtSignal


class Action(object):

    @staticmethod
    def exec_report(conn, name, data, direct_print=False,
        context=None, printer=None):
        if context is None:
            context = {}

        data = data.copy()
        ctx = {}
        ctx.update(context)
        ctx['direct_print'] = direct_print
        args = ('report', name, 'execute', data.get('ids', []), data, ctx)
        try:
            rpc_progress = rpc.RPCProgress(conn, 'execute', args)
            res = rpc_progress.run()
        except:
            return False
        if not res:
            return False

        (type, content, print_p, name) = res

        name = slugify(name)

        dtemp = tempfile.mkdtemp(prefix='tryton_')

        path = os.path.join(dtemp,
            name + os.extsep + type)

        if os.name == 'nt':
            with open(path, 'wb') as fp:
                #fp.write(content.data)
                fp.write(content)
            if direct_print:
                try:
                    operation = 'print'
                    os.startfile(path, operation)
                except win32api.error as exception:
                    print(str(exception))
                finally:
                    pass
            else:
                    file_open(path,type,direct_print=False)
        else:
            with open(fp_name, 'wb') as file_d:
                file_d.write(content.data)
            file_open(fp_name, type, direct_print=direct_print)
        return True