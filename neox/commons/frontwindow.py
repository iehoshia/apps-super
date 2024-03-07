# -*- coding: UTF-8 -*-
import os
import gc


import time
import logging
from pathlib import Path

from PyQt5.QtWidgets import QMainWindow, QDesktopWidget, QLabel
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QTimer

from neox.commons.dialogs import QuickDialog
import neox.commons.dblogin as dblogin
#from neox.commons.idle_queue_dispatcher import ThreadDispatcher
import neox.commons.rpc as rpc

__all__ = ['FrontWindow', 'ClearUi']

parent = Path(__file__).parent.parent
parent = str(parent)
file_base_css = os.path.join(parent, 'css', 'base.css')
_DEFAULT_TIMEOUT = 30  # on segs
path_trans = os.path.join(os.path.abspath(
    os.path.dirname(__file__)), 'locale', 'i18n_es.qm')


class FrontWindow(QMainWindow):

    def __init__(self, connection, params, title=None,
            show_mode=None, icon=None, debug=False):
        super(FrontWindow, self).__init__()

        if not title:
            title = self.tr('APPLICATION')

        self._state = None
        self._keyStates = {}
        self.window().setWindowTitle(title)
        if icon is not None:
            self.window().setWindowIcon(icon)
        self.setObjectName('WinMain')
        self.conn = connection
        self._context = connection.context # to work with xmlrpc

        self.set_params(params)
        self.logger = logging.getLogger('neox_logger')

        """
        We need get the size of screen (display)
            ---------------  -------------------
                  name           width (px)
            ---------------  -------------------
            small screen     =< 1024
            medium screen    > 1024 and =< 1366
            large screen     > 1366
        """

        screen = QDesktopWidget().screenGeometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        screen_width = screen.width()
        #print("screen_width >> ", screen_width)
        screen_width = 1024

        self.screen_size = 'large'
        if screen_width <= 1024:
            self.screen_size = 'small'
        elif screen_width <= 1366:
            self.screen_size = 'medium'
        #print('Screen width : ', self.screen_size)

        self.timeout = _DEFAULT_TIMEOUT
        self.set_stack_messages()

        if show_mode == 'fullscreen':
            self.window().showFullScreen()
        else:
            self.window().show()
        self.setFocus()
        self._global_timer = 0
        self.set_timeout()

    def set_stack_messages(self):
        self.stack_msg = {}

    def get_geometry(self):
        screen = QDesktopWidget().screenGeometry()
        return screen.width(), screen.height()

    def set_statusbar(self, values):
        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)

        for k, v in values.items():
            _label = QLabel(v['name'] + ':')
            _label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            status_bar.addWidget(_label, 1)
            setattr(self, k, QLabel(str(v['value'])))
            _label_info = getattr(self, k)
            _label_info.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            status_bar.addWidget(_label_info)

    def set_style(self, file_css):
        styles = []
        for style in [file_base_css, file_css]:
            with open(style, 'r') as infile:
                styles.append(infile.read())
        self.setStyleSheet(''.join(styles))

    def set_timeout(self):
        if not self.timeout:
            self.timeout = _DEFAULT_TIMEOUT
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.count_time)
        self.timer.start(1000)

    def check(self):
        #return self.debug_cycles() # uncomment to just debug cycles
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print ('gc_check called:', l0, l1, l2)
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print ('collecting gen 0, found:', num, 'unreachable')
            if l1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    print ('collecting gen 1, found:', num, 'unreachable')
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print ('collecting gen 2, found:', num, 'unreachable')

    def debug_cycles(self):
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))

    def count_time(self):
        self._global_timer += 1
        if self._global_timer > self.timeout:
            self._global_timer = 0
            self.action_print_pending_sales()

    def dialog(self, name, response=False):
        res = QuickDialog(
            parent=self,
            kind=self.stack_msg[name][0],
            string=self.stack_msg[name][1],
        )
        return res

    def set_params(self, values):
        for k, v in values.items():
            if v in ('False', 'True'):
                v = eval(v)
            setattr(self, k, v)

    def action_block(self):
        dblogin.safe_reconnect(self)

    def keyReleaseEvent(self, event):
        self._keyStates[event.key()] = False
        #event.callback()

    def closeEvent(self, event):
        self.close(from_close=True)

    def on_quit(self, *args):
        #if TrytonServerUnavailable:
        #    pass
        rpc.logout()
        self.close(from_close=True)

    def get_active_window(self):
        return self


class ClearUi(QThread):
    sigActionClear = pyqtSignal()
    state = None

    def __init__(self, wait_time):
        QThread.__init__(self)
        self.wait_time = wait_time

    def run(self):
        time.sleep(self.wait_time)
        self.sigActionClear.emit()

'''
class DoReconnect(QThread):

    sigDoReconnect = pyqtSignal()

    def __init__(self, main, context):
        print("__init__ DoReconnect")
        QThread.__init__(self)

    def run(self):
        self.sigDoReconnect.emit()

        timer = QTimer(self)
        timer.timeout.connect(safe_reconnect(MainWi))
        timer.start(15)
'''