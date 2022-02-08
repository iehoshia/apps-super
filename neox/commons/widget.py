
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from PyQt5.QtWidgets import (QLabel, QTextEdit, QHBoxLayout, QVBoxLayout,
    QWidget, QGridLayout, QLineEdit, QDoubleSpinBox, QTreeView,
    QListView, QAbstractItemView, QCalendarWidget, QApplication,
    QDateEdit)

class CustomQLineEdit(QLineEdit):

    def __init__(self, contents='', parent=None):
        super(CustomQLineEdit, self).__init__(contents, parent)
        print("contents", contents)
        self.editingFinished.connect(self.__handleEditingFinished)
        self.textChanged.connect(self.__handleTextChanged)
        #self._before = contents

    def __handleTextChanged(self, text):
        if not self.hasFocus():
            self._before = text

    def __handleEditingFinished(self):
        before, after = self._before, self.text()
        if before != after:
            self._before = after
            self.textModified.emit(before, after)