from PyQt5 import QtCore
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QIcon
import PyQt5
import sys
import os
import os
from operator import itemgetter
from datetime import datetime, timedelta, date
from decimal import Decimal

from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel, \
    pyqtSignal, QModelIndex, QSize
from PyQt5.QtWidgets import QTableView, QVBoxLayout,  \
    QAbstractItemView, QLineEdit, QDialog, QLabel, QScroller, \
    QHBoxLayout, QScrollArea, QItemDelegate
from PyQt5.QtGui import QPixmap, QIcon

from neox.commons.buttons import ActionButton

__all__ = ['PdfReport', 'PdfWindow']

class PdfReport(QWebEngineView):

    def load_pdf(self, filename):
        q = QtCore.QUrl(filename)
        self.webSettings = self.settings()
        self.webSettings.setAttribute(QWebEngineSettings.PluginsEnabled,True)
        self.webSettings.setAttribute(QWebEngineSettings.JavascriptEnabled,True)
        self.webSettings.setAttribute(QWebEngineSettings.PdfViewerEnabled,True)
        self.setUrl(QUrl(q))

    def sizeHint(self):
        return QtCore.QSize(640, 480)

    @QtCore.pyqtSlot(int)
    def index_load(self, index):
        path = pdfpath(index)
        print(path)
        self.load_pdf(path)


class Main(QDialog):

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Hola Mundo')
        vbox = QVBoxLayout()
        grid = QGridLayout()
        web = PdfReport()
        web.load_pdf("c:/backups/lascumbres.pdf")
        grid.addWidget(web)
        vbox.addLayout(grid)
        self.setLayout(vbox)
        self.show()

class PdfWindow(QDialog):

    def __init__(self, parent, current_row,
            url="", methods, title=None):
        """
            parent: parent window
            on_accepted_method: method to call when triggered the selection
            filter_column: list of column to search values, eg: [0,2]
            title: title of window
        """
        super(PdfWindow, self).__init__(parent)

        self.parent = parent
        self.url = url
        self.methods = methods
        self.on_accepted_method = methods.get('on_accepted_method')
        self.model = model
        self.current_row = current_row
        self.optionals = optionals
        self.context = context

        self.ok_button = ActionButton('ok', self.dialog_accepted)
        self.ok_button.setFocus()
        self.cancel_button = ActionButton('cancel', self.action_close)
        self.print_button = ActionButton('print', self.action_print)

        if not title:
            title = self.tr('VIEWFINDER...')
            self.setWindowTitle(title)
        WIDTH = 550

        self.resize(QSize(WIDTH, 400))
        self.create_layout()

    def get_id(self):
        if self.current_row:
            return self.current_row['id']

    def dialog_accepted(self):
        #args = ([], self.current_row['id'], *optionals, context)
        #getattr(self.parent, self.model,
        #    self.on_accepted_method)(*args)
        parent._current_pdf_document = self.get_id()
        if self.parent:
            getattr(self.parent, self.on_accepted_method)()
        self.parent.setFocus()
        self.hide()

    def action_print(self):
        '''
        def print_odt_statement(self, statement_id=None, direct_print=False):
            if not statement_id:
                return
            model = u'account.statement'
            data = {
                'model': model,
                'action_id': self._action_report_statement['id'],
                'id': statement_id,
                'ids': [statement_id],
            }
            ctx = {'date_format': u'%d/%m/%Y'}
            ctx.update(self._context)
            Action.exec_report(self.conn, u'account.statement',
                data, direct_print=direct_print, context=ctx)
        '''
        return

    def create_layout(self):
        vbox = QVBoxLayout()
        grid = QGridLayout()
        web = PdfReport()
        web.load_pdf(self.url)
        grid.addWidget(web)
        vbox.addLayout(grid)
        self.setLayout(vbox)
        self.show()

    def show(self):
        self.parent.releaseKeyboard()
        super(SearchWindow, self).show()

    def hide(self):
        self.parent.grabKeyboard()
        self.parent.setFocus()
        super(SearchWindow, self).hide()

    def action_close(self):
        self.close()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Return:
            self.dialog_accepted()
        elif key == Qt.Key_Escape:
            self.hide()
        else:
            pass
        super(SearchWindow, self).keyPressEvent(event)