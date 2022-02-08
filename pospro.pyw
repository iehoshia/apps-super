#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
import os
import sys
import logging

import qcrash.api as qcrash

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTranslator, QSettings, QTimer
from neox.commons.dblogin import Login
from app import mainwindow

try:
    DIR = os.path.abspath(os.path.normpath(os.path.join(sys.argv[0],
        '..', '..', '..')))
    if os.path.isdir(DIR):
        sys.path.insert(0, os.path.dirname(DIR))
except NameError:
    pass

locale_app = os.path.join(os.path.abspath(
    os.path.dirname(sys.argv[0])), 'app', 'translations', 'i18n_es.qm')
logging.basicConfig()

class Client(object):

    def __init__(self, parent=None):
        self.app = QApplication(sys.argv)
        self.translator = QTranslator()
        self.translator.load(locale_app)
        self.app.installTranslator(self.translator)

    def init_login(self):
        login = Login(file_config='config_pos.ini')

        while not login.connection:
            login.run()
            login.exec_()

        return login.connection, login.params

    def main(self, conn, params):
        mw = mainwindow.MainWindow(conn, params)
        self.app.exec_()


client = Client()
conn, params = client.init_login()

if conn:
    client.main(conn, params)
sys.exit()
