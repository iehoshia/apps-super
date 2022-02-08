#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from decimal import Decimal
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QFrame, QScroller,\
    QVBoxLayout, QPushButton, QLabel, QGridLayout, QDialog, QScrollArea


def money(v):
    return '${:20,}'.format(int(v))


class Separator(QFrame):

    def __init__(self):
        QFrame.__init__(self)
        self.setLineWidth(1)
        self.setFrameShape(QFrame.HLine)


class TLabel(QLabel):
    # Category Label

    def __init__(self, key, id_, parent):
        QLabel.__init__(self, key)
        self.parent = parent
        self.setAlignment(Qt.AlignCenter)
        self.id = id_

    def mouseDoubleClickEvent(self, qmouse_event):
        self.parent.setState({
            'layout_invisible': True,
            'view': self.id,
        })
        super(TLabel, self).mouseDoubleClickEvent(qmouse_event)


class RLabel(QLabel):
    #Item Label

    def __init__(self, name, idx):
        super(RLabel, self).__init__(name)
        self.idx = idx

    def mouseDoubleClickEvent(self, qmouse_event):
        self.parent().action_selected(self.idx)
        super(RLabel, self).mouseDoubleClickEvent(qmouse_event)


class List(QWidget):
    sigItem_selected = pyqtSignal(str)

    def __init__(self, rows, num_cols, show_code, action):
        """
            rows: a list of lists
            num_cols: number of columns?
        """
        QWidget.__init__(self)
        self.layout_list = QGridLayout()
        self.setLayout(self.layout_list)
        self.rows = rows
        self.show_code = show_code
        self.action = action
        self.num_cols = num_cols
        self.layout_list.setVerticalSpacing(5)
        self.layout_list.setColumnStretch(1, 1)
        if rows:
            self.set_items(rows)

    def action_selected(self, idx):
        self.action(idx) #.selected_method(idx)

    def set_items(self, rows):
        self.rows = rows
        idx = 0
        self.layout_list.addWidget(Separator(), 0, 0, 1, self.num_cols)

        for row in rows:
            idx += 1
            separator = Separator()
            for col in range(self.num_cols):
                val = row[col]
                if isinstance(val, Decimal):
                    val = money(int(val))
                if not self.show_code:
                    if col == 0:
                        val = ''
                item = RLabel(val, idx=row[0])
                self.layout_list.addWidget(item, idx, col)
            idx += 1
            self.layout_list.addWidget(separator, idx, 0, 1, self.num_cols)
        self.layout_list.setRowStretch(idx + 1, 1)


class MenuWindow(QDialog):

    def __init__(self, parent, values, selected_method=None, title=None):
        """
            parent: parent window
            values: is to list of list/tuples values for data model
                [('a' 'b', 'c'), ('d', 'e', 'f')...]
            on_selected: method to call when triggered the selection
            title: title of window
        """
        super(MenuWindow, self).__init__(parent)

        self.parent = parent
        self.values = values
        self.current_view = None
        if not title:
            title = self.tr('Menu...')
            self.setWindowTitle(title)
        self.resize(QSize(200, 400))
        self.show_code = False
        self.create_categories()
        self.create_widgets()

        # ---------------------------------------------------------------
        self.layout = QVBoxLayout()
        self.layout_buttons = QHBoxLayout()
        self.layout.addLayout(self.layout_buttons, 0)
        self.layout_buttons.addWidget(self.pushButtonOk)
        self.layout_buttons.addWidget(self.pushButtonBack)
        self.layout.addWidget(self.category, 0)
        self.setLayout(self.layout)

        # ---------------------------------------------------------------

        self.create_connections()
        self.method_on_selected = getattr(self.parent, selected_method)

    def setState(self, args):
        if args.get('layout_invisible'):
            self.category.hide()
        else:
            self.category.show()
            self.layout.addWidget(self.category)
            if self.current_view:
                self.current_view.hide()

        if args.get('view'):
            view_id = args.get('view')
            if hasattr(self, 'view_' + str(view_id)):
                self.current_view = getattr(self, 'view_' + str(view_id))
                self.layout.addWidget(self.current_view)
                self.current_view.show()

    def create_categories(self):
        # set the list model
        self.category = QWidget()
        self.layout_category = QVBoxLayout()
        self.category.setLayout(self.layout_category)
        id_ = 1
        self.layout_category.addWidget(Separator())
        for k, values in self.values.items():
            separator = Separator()
            label = TLabel(k, id_, self)
            self.layout_category.addWidget(label)
            self.layout_category.addWidget(separator)
            list_item = List(values, 3, self.show_code, self.selected_method)
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll_area.setWidget(list_item)
            QScroller.grabGesture(scroll_area, QScroller.LeftMouseButtonGesture)
            setattr(self, 'view_'+ str(id_), scroll_area)
            id_ += 1

    def create_widgets(self):
        self.pushButtonOk = QPushButton(self.tr("&ACCEPT"))
        self.pushButtonOk.setAutoDefault(True)
        self.pushButtonOk.setDefault(False)
        self.pushButtonBack = QPushButton(self.tr("&BACK"))

    def create_layout(self):
        pass

    def create_connections(self):
        self.pushButtonOk.clicked.connect(self.action_close)
        self.pushButtonBack.clicked.connect(self.action_back)

    def action_back(self):
        self.setState({
            'layout_invisible': False,
        })

    def action_close(self):
        self.close()

    def selected_method(self, args):
        if self.parent and self.selected_method:
            self.method_on_selected(args)
