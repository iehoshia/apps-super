
import os
from pathlib import Path

from decimal import Decimal
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QScroller, QVBoxLayout,
    QPushButton, QGridLayout, QScrollArea, QLabel)

from .custom_button import CustomButton

pkg_dir = str(Path(os.path.dirname(__file__)).parents[0])
file_back_icon = os.path.join(pkg_dir, 'share', 'back.svg')
file_menu_img = os.path.join(pkg_dir, 'share', 'menu.png')

__all__ = ['GridButtons', 'MenuDash']


def money(v):
    return '${:9,}'.format(int(v))


class GridButtons(QWidget):
    sigItem_selected = pyqtSignal(str)

    def __init__(self, parent, rows, num_cols, action):
        """
            rows: a list of lists
            num_cols: number of columns?
        """
        QWidget.__init__(self)
        self.parent = parent
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.rows = rows
        self.action = action
        self.num_cols = num_cols
        self.layout.setSpacing(15)
        if rows:
            self.set_items(rows)

    def action_selected(self, idx):
        self.action(idx)

    def set_items(self, rows):
        self.rows = rows
        colx = 0
        rowy = 0
        for row in rows:
            if colx >= 2:
                colx = 0
                rowy += 1

            if isinstance(row[3], Decimal):
                row[3] = money(int(row[3]))

            item_button = CustomButton(
                parent=self,
                id=row[0],
                title=row[2],
                desc=str(row[3]),
                method='action_selected',
                target=row[0],
                name_style='product_button'
            )
            item_button.setMaximumHeight(110)
            item_button.setMinimumHeight(100)
            self.layout.addWidget(item_button, rowy, colx)
            colx += 1
            self.layout.setRowMinimumHeight(rowy, 110)
        self.layout.setRowStretch(rowy + 1, 1)


class MenuDash(QVBoxLayout):

    def __init__(self, parent, values, selected_method=None, title=None):
        """
            parent: parent window
            values: is to list of list/tuples values for data model
                [('a' 'b', 'c'), ('d', 'e', 'f')...]
            on_selected: method to call when triggered the selection
            title: title of window
        """
        super(MenuDash, self).__init__()

        self.parent = parent
        self.values = values
        self.current_view = None

        # rec = QDesktopWidget().screenGeometry()
        # _min_width = int(rec.width() * 0.3)
        # self.setMinimumWidth(_min_width)
        self.method_on_selected = getattr(self.parent, selected_method)
        self.create_categories()

        pixmap = QPixmap(file_menu_img)
        new_pixmap = pixmap.scaled(200, 60)
        label_menu = QLabel('')
        label_menu.setPixmap(new_pixmap)

        widget_head = QWidget()
        widget_head.setStyleSheet("background-color: white;")
        self.layout_head = QHBoxLayout()
        widget_head.setLayout(self.layout_head)

        self.addWidget(widget_head, 0)
        self.pushButtonBack = QPushButton()
        self.pushButtonBack.setIcon(QIcon(file_back_icon))
        self.pushButtonBack.setIconSize(QSize(25, 25))
        self.pushButtonBack.setMaximumWidth(35)

        self.layout_head.addWidget(self.pushButtonBack, stretch=0)
        self.layout_head.addWidget(label_menu, stretch=1)
        self.addWidget(self.category_area, 0)
        self.pushButtonBack.clicked.connect(self.action_back)

    def setState(self, args):
        if args.get('layout_invisible'):
            self.category_area.hide()
            self.removeWidget(self.current_view)
        else:
            self.category_area.show()
            self.addWidget(self.category_area)
            if self.current_view:
                self.current_view.hide()

        if args.get('button'):
            view_id = args.get('button')
            if hasattr(self, 'view_' + str(view_id)):
                self.current_view = getattr(self, 'view_' + str(view_id))
                self.addWidget(self.current_view)
                self.current_view.show()

    def create_categories(self):
        # set the list model
        self.category_area = QScrollArea()
        self.category_area.setWidgetResizable(True)
        self.category_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        QScroller.grabGesture(self.category_area, QScroller.LeftMouseButtonGesture)

        category = QWidget()
        self.category_area.setWidget(category)
        self.layout_category = QGridLayout()
        category.setLayout(self.layout_category)
        id_ = 1
        cols = 2
        row = 0
        col = 0
        for value in self.values:
            if not value:
                continue
            if col > cols - 1:
                col = 0
                row += 1
            name_button = 'button_' + str(id_)

            button = CustomButton(
                parent=self,
                id=name_button,
                icon=value['icon'],
                desc=value['name'],
                method='selected_method',
                target=str(id_),
                name_style='category_button'
            )
            button.setMaximumHeight(100)
            self.layout_category.addWidget(button, row, col)
            grid_buttons = GridButtons(self.parent, value['items'], cols,
                action=self.method_on_selected)
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll_area.setWidget(grid_buttons)
            QScroller.grabGesture(scroll_area, QScroller.LeftMouseButtonGesture)
            setattr(self, 'view_' + str(id_), scroll_area)
            col += 1
            id_ += 1

    def action_back(self):
        self.setState({
            'layout_invisible': False
        })

    def selected_method(self, args):
        self.setState({
            'layout_invisible': True,
            'button': args,
        })
