#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os
import gettext
import logging
from collections import OrderedDict
from pathlib import Path

from PyQt5.QtWidgets import (QDialogButtonBox, QPushButton,
    QLineEdit, QHBoxLayout, QDialog, QFrame, QLabel, QVBoxLayout)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from neox.commons import connection
from neox.commons import common
from neox.commons.config import Params
from neox.commons.dialogs import QuickDialog
from neox.commons.forms import GridForm
from neox.commons.common import get_icon
from neox.commons import bus
import traceback

_ = gettext.gettext

__all__ = ['Login', 'xconnection']

pkg_dir = str(Path(os.path.dirname(__file__)).parents[0])
path_logo = os.path.join(pkg_dir, 'share', 'login.png')
file_base_css = os.path.join(pkg_dir, 'css', 'base.css')
file_tablet_css = os.path.join(pkg_dir, 'css', 'tablet.css')


def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
        total_size = total_size / 5025
        total_size = round(total_size)

    return total_size

class Login(QDialog):

    def __init__(self, parent=None, file_config=''):
        super(Login, self).__init__(parent)
        logging.info(' Start login neox system X...')
        self.connection = None
        params = Params(file_config)
        self.params = params.params
        self.setObjectName('dialog_login')
        if self.params.get('tablet_mode') == 'True':
            self.tablet_mode = eval(self.params['tablet_mode'])
            self.set_style([file_tablet_css])
        else:
            self.set_style([file_base_css])
            self.tablet_mode = None
        self.init_UI()

    def set_style(self, style_files):
        styles = []
        for style in style_files:
            with open(style, 'r') as infile:
                styles.append(infile.read())
        self.setStyleSheet(''.join(styles))

    def init_UI(self):
        hbox_logo = QHBoxLayout()
        label_logo = QLabel()
        label_logo.setObjectName('label_logo')
        hbox_logo.addWidget(label_logo, 0)
        pixmap_logo = QPixmap(path_logo)
        label_logo.setPixmap(pixmap_logo)
        hbox_logo.setAlignment(label_logo, Qt.AlignHCenter)

        values =  OrderedDict([
            ('version', {'name': self.tr('VERSION'), 'readonly': True}),
            ('host', {'name': self.tr('HOST'), 'readonly': True,
                'invisible':True}),
            ('database', {'name': self.tr('DATABASE'), 'readonly': True,
                'invisible':True}),
            ('user', {'name': self.tr('USER')}),
            ('password', {'name': self.tr('PASSWORD')}), #DEACTIVATE
        ])
        formLayout = GridForm(self, values=values, col=1)
        self.field_password.setEchoMode(QLineEdit.Password)
        #self.field_password.setText("ADMIN123")
        self.field_password.textChanged.connect(self.clear_message)

        box_buttons = QDialogButtonBox()
        pushButtonCancel = QPushButton(self.tr("C&ANCEL"))
        pushButtonCancel.setObjectName('button_cancel')
        box_buttons.addButton(pushButtonCancel, QDialogButtonBox.RejectRole)
        pushButtonOk = QPushButton(self.tr("&CONNECT"))
        pushButtonOk.setAutoDefault(True)
        pushButtonOk.setDefault(False)
        pushButtonOk.setObjectName('button_ok')
        box_buttons.addButton(pushButtonOk, QDialogButtonBox.AcceptRole)

        hbox_buttons = QHBoxLayout()
        hbox_buttons.addWidget(box_buttons)

        line = QFrame()
        line.setFrameShape(line.HLine)
        line.setFrameShadow(line.Sunken)
        hbox_line = QHBoxLayout()
        hbox_line.addWidget(line)

        hbox_msg = QHBoxLayout()
        MSG = self.tr('Error: username or password invalid...!')
        self.error_msg = QLabel(MSG)
        self.error_msg.setObjectName('login_msg_error')
        self.error_msg.setAlignment(Qt.AlignCenter);

        hbox_msg.addWidget(self.error_msg)
        vbox_layout = QVBoxLayout()
        vbox_layout.addLayout(hbox_logo)
        vbox_layout.addLayout(formLayout)
        vbox_layout.addLayout(hbox_msg)
        vbox_layout.addLayout(hbox_line)
        vbox_layout.addLayout(hbox_buttons)

        self.setLayout(vbox_layout)
        self.setWindowTitle('Login Effica')
        self.setWindowIcon(get_icon('pos-icon'))
        self.clear_message()

        self.field_password.setFocus()
        box_buttons.accepted.connect(self.accept)
        box_buttons.rejected.connect(self.reject)

    def clear_message(self):
        self.error_msg.hide()

    def run(self, profile=None):
        if self.params['version']:
            version = self.params['version']
            size = get_size()
            version_size = version + ', ' + str(size) + ' MB'
            self.field_version.setText(version_size)
        if self.params['database']:
            self.field_database.setText(self.params['database'])
        if self.params['user']:
            self.field_user.setText(self.params['user'])
        if self.params['server']:
            self.field_host.setText(self.params['server'])

    def accept(self):
        self.validate_access()
        super(Login, self).accept()

    def reject(self):
        sys.exit()

    def validate_access(self):
        user = self.field_user.text()
        password = self.field_password.text()

        self.connection = xconnection(
                user, password, self.params['server'], self.params['port'],
                self.params['database'], self.params['protocol']
        ) # xconnection

        print('  >>> ', self.connection)

        if not self.connection:
            self.field_password.setText('')
            self.field_password.setFocus()
            self.error_message()

        self.params['user'] = user
        self.params['password'] = password

    def error_message(self):
        self.error_msg.show()


def xconnection(user, password, host, port, database, protocol):
    # Get user_id and session
    try:
        url = 'http://%s:%s@%s:%s/%s/' % (
            user, password, host, port, database)
        #try:
        #    if not common.test_server_version(host, int(port)):
        #        print(u'Incompatible version of the server')
        #        return
        #except:
        #    pass

        if protocol == 'json':
            conn = connection.set_jsonrpc(url[:-1])
        elif protocol == 'local':
            conn = connection.set_trytond(
                    database = database,
                    user = user,
            )
        elif protocol == 'xml':
            conn = connection.set_xmlrpc(url)
        else:
            print("Protocol error...!")
            return None

        return conn
    except:
        print('LOG: Data connection invalid!')
        return None

def safe_reconnect(main, attemps=1):

    main.timer.stop()
    if main.conn and main.conn._conn is not None:
        main._global_timer = 0
        CONNECTION = main.conn._conn
        CONNECTION.close()

    if attemps > 5:
        main._global_timer = 0
        main.conn = None
        main.close(from_close=True)
        return

    field_password = QLineEdit()
    field_password.setEchoMode(QLineEdit.Password)
    field_password.cursorPosition()
    field_password.cursor()
    dialog_password = QuickDialog(main, 'warning',
        string=main.tr('Presiona ACEPTAR para reconectar:'),
        #widgets=[field_password],
        #widgets=[],
    )

    #field_password.setFocus()
    dialog_password.exec_()

    #password = field_password.text()
    password = main.password
    if not password or password == '':
        attemps += 1
        main._global_timer = 0
        safe_reconnect(main, attemps)
        return

    main.conn = xconnection(
        main.user,
        str(password),
        main.server,
        main.port,
        main.database,
        main.protocol,
    )
    main._global_timer = 0

    if main.conn:
        #field_password.setText('')
        dialog_password.hide()
        main.timer.start()
        return
    else:
        attemps += 1
        safe_reconnect(main, attemps)