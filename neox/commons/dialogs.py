# -*- coding: UTF-8 -*-
import os
from collections import OrderedDict

from PyQt5.QtWidgets import (QDialog, QAbstractItemView, QVBoxLayout,
    QHBoxLayout, QLabel, QWidget, QTreeView, QLineEdit, QTableView, QCompleter)
from PyQt5.QtGui import QStandardItem, QStandardItemModel, QPixmap
from PyQt5.QtCore import Qt, pyqtSlot, QModelIndex

from neox.commons.qt_models import get_simple_model
from neox.commons.forms import GridForm
from neox.commons.buttons import ActionButton

__all__ = ['QuickDialog', 'SearchDialog', 'HelpDialog',
    'CategoryDialog',
    'ProductDialog','FactoryIcons']

current_dir = os.path.dirname(__file__)
par_dir = os.path.dirname(current_dir) 

_SIZE = (500, 200)
_TSIZE = (800,200)


class QuickDialog(QDialog):

    def __init__(self, parent, kind, string=None, data=None, widgets=None,
        icon=None, size=None, readonly=False, disable_cancel=False,
        active_widget=None, cancel_message=None, message_bar=None):
        super(QuickDialog, self).__init__(parent)
        # Size arg is in deprecation
        
        if not size:
            size = _SIZE
        self.factory = None
        self.readonly = readonly
        self.parent = parent
        self.active_widget = active_widget
        self.parent_model = None
        titles = {
            'warning': self.tr('Warning...'),
            'info': self.tr('Information...'),
            'action': self.tr('Action...'),
            'help': self.tr('Help...'),
            'error': self.tr('Error...'),
            'question': self.tr('Question...'),
            'selection': self.tr('Selection...'),
            None: self.tr('Dialog...')
        }
        self.setWindowTitle(titles[kind])
        self.setModal(True)
        self.setParent(parent)
        self.factory = FactoryIcons()
        self.default_widget_focus = None
        self.kind = kind
        self.widgets = widgets
        self.data = data
        self.disable_cancel = disable_cancel
        self.cancel_message = cancel_message
        self.message_bar = message_bar
        string_widget = None
        data_widget = None
        _buttons = None
        row_stretch = 1
        main_vbox = QVBoxLayout()

        self.sub_hbox = QHBoxLayout()

        # Add main message
        if string:
            # For simple dialog
            string_widget = QLabel(string)

        if kind == 'help':
            data_widget = widgets[0]
        elif kind == 'action':
            if widgets:
                data_widget = widgets[0]
            else:
                data_widget = GridForm(parent, OrderedDict(data))
        elif kind == 'selection':
            self.name = data['name']
            data_widget = self.set_selection(parent, data)
        elif widgets:
            data_widget = GridForm(parent, OrderedDict(widgets))

        if string_widget:
            main_vbox.addWidget(string_widget, 0)

        if data_widget:
            if isinstance(data_widget, QWidget):
                row_stretch += 1
                size = (size[0], size[1] + 200)
                self.sub_hbox.addWidget(data_widget, 0)
            else:
                self.sub_hbox.addLayout(data_widget, 0)

        self.ok_button = ActionButton('ok', self.dialog_accepted)
        self.ok_button.setFocus()
        self.cancel_button = ActionButton('cancel', self.dialog_rejected)

        _buttons = []
        if kind in ('info', 'help', 'warning', 'question', 'error'):
            if kind in ('warning', 'question'):
                _buttons.append(self.cancel_button)
            _buttons.append(self.ok_button)
        elif kind in ('action', 'selection'):
            _buttons.extend([self.cancel_button, self.ok_button])

        self.buttonbox = QHBoxLayout()
        for b in _buttons:
            self.buttonbox.addWidget(b, 1)

        main_vbox.addLayout(self.sub_hbox, 0)
        main_vbox.addLayout(self.buttonbox, 1)
        main_vbox.insertStretch(row_stretch, 0)

        self.setLayout(main_vbox)
        self.setMinimumSize(*size)

        if kind in ('info', 'error'):
            self.show()

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(QuickDialog, self).exec()
        if self.kind == 'action':
            pass
        return res

    def show(self):
        super(QuickDialog, self).show()
        self.parent.releaseKeyboard()
        self.ok_button.setFocus()
        if self.default_widget_focus:
            self.default_widget_focus.setFocus()
            if hasattr(self.default_widget_focus, 'setText'):
                self.default_widget_focus.setText('')
        else:
            self.setFocus()

    def hide(self):
        super(QuickDialog, self).hide()
        self.parent.setFocus()

    def set_info(self, info):
        if hasattr(self, 'label_info'):
            self.label_info.setText(info)

    def set_widgets(self, widgets):
        if widgets:
            # Set default focus to first widget created
            self.default_widget_focus = widgets[0]

    def closeEvent(self, event):
        super(QuickDialog, self).closeEvent(event)
        if self.message_bar and self.cancel_message:
            self.message_bar.set(self.cancel_message)
        if self.active_widget:
            self.active_widget.setFocus()

    def dialog_rejected(self):
        self.parent.setFocus()
        if self.active_widget:
            self.active_widget.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        if self.kind in ('action', 'selection', 'warning', 'question'):
            self.setResult(1)
            self.done(1)
        self.hide()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if self.disable_cancel==False:
                if self.message_bar and self.cancel_message:
                    self.message_bar.set(self.cancel_message)
                if self.active_widget:
                    self.active_widget.setFocus()
                self.dialog_rejected()
            return
        else:
            super(QuickDialog, self).keyPressEvent(event)

    def set_selection(self, obj, data):
        self.set_simple_model()
        setattr(obj, data['name'] + '_model', self.data_model)
        self.parent_model = data.get('parent_model')
        self.treeview = QTreeView()
        self.treeview.setRootIsDecorated(False)
        self.treeview.setColumnHidden(0, True)
        self.treeview.setItemsExpandable(False)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.treeview.setModel(self.data_model)
        self.treeview.clicked.connect(self.field_selection_changed)
        self.treeview.activated.connect(self.field_selection_changed)

        self.update_values(self.data['values'])

        # By default first row must be selected
        item = self.data_model.item(0, 0)
        idx = self.data_model.indexFromItem(item)
        self.treeview.setCurrentIndex(idx)
        return self.treeview

    def update_values(self, values):
        self.data_model.removeRows(0, self.data_model.rowCount())
        self._insert_items(self.data_model, values)
        self.treeview.resizeColumnToContents(0)

    def set_simple_model(self):
        self.data_model = QStandardItemModel(0, len(self.data['heads']), self)
        _horizontal = Qt.Horizontal
        for i, h in enumerate(self.data['heads'], 0):
            self.data_model.setHeaderData(i, _horizontal, h)

    def _insert_items(self, model, values):
        for value in values:
            row = []
            for v in value:
                itemx = QStandardItem(v)
                itemx.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                row.append(itemx)
            self.data_model.insertRow(0, row)
        self.data_model.sort(0, Qt.AscendingOrder)

    @pyqtSlot(QModelIndex)
    def field_selection_changed(self, qm_index):
        if not self.readonly:
            item_id = self.data_model.item(qm_index.row(), 0).text()
            item_name = self.data_model.item(qm_index.row(), 1).text()

            if self.parent_model is not None:
                self.parent_model[self.name] = item_id
            if hasattr(self.parent, 'field_' + self.name):
                field = getattr(self.parent, 'field_' + self.name)
                if hasattr(field, 'setText'):
                    field.setText(item_name)
            else:
                setattr(self.parent, 'field_' + self.name + '_name', item_name)
            setattr(self.parent, 'field_' + self.name + '_id', int(item_id))
            action = getattr(self.parent, 'action_' + self.name + '_selection_changed')
            action()
        self.dialog_accepted()


class SearchDialog(QDialog):

    def __init__(self, parent, headers, values, on_activated,
            hide_headers=False, completion_column=None, title=None):
        super(SearchDialog, self).__init__(parent)
        self.parent = parent
        self.headers = headers
        self.values = values
        if not title:
            title = self.tr('Search Products...')
        self.setWindowTitle(title)

        self._product_line = QLineEdit()
        self.table_view = QTableView()

        button_cancel = ActionButton('cancel', self.on_reject)
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        hbox.addWidget(button_cancel)
        vbox.addWidget(self._product_line)
        vbox.addLayout(hbox)
        self.setLayout(vbox)
        self.completer = QCompleter()
        self.treeview_search_product = QTreeView()
        if hide_headers:
            col_headers = self.treeview_search_product.header()
            col_headers.hide()
        self.completer.setPopup(self.treeview_search_product)
        self._product_line.setCompleter(self.completer)
        self.set_model()

        self.completer.activated.connect(self.on_accept)
        self.completer.setFilterMode(Qt.MatchStartsWith)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setCompletionColumn(2)
        self.completer.activated.connect(on_activated)

    def set_model(self):
        headers_name = [h[1] for h in self.headers]
        self.model = get_simple_model(self.parent, self.values, headers_name)
        self.completer.setModel(self.model)

    def get_selected_index(self):
        model_index = self._get_model_index()
        idx = self.model.index(model_index.row(), 0)
        return idx.data()

    def get_selected_data(self):
        model_index = self._get_model_index()
        data = {}
        i = 0
        for h, _ in self.headers:
            data[h] = self.model.index(model_index.row(), i).data()
            i += 1
        return data

    def _get_model_index(self):
        item_view = self.completer.popup()
        index = item_view.currentIndex()
        proxy_model = self.completer.completionModel()
        model_index = proxy_model.mapToSource(index)
        return model_index

    def on_accept(self):
        self.accept()

    def on_reject(self):
        self.reject()


class HelpDialog(QuickDialog):

    def __init__(self, parent):
        self.treeview = QTreeView()
        self.treeview.setRootIsDecorated(False)
        self.treeview.setAlternatingRowColors(True)
        self.treeview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.treeview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        super(HelpDialog, self).__init__(parent, 'help', widgets=[self.treeview],
            size=(400, 500))
        self.set_info(self.tr('Keys Shortcuts...'))
        self.hide()

    def set_shortcuts(self, shortcuts):
        model = self._help_model(shortcuts)
        self.treeview.setModel(model)
        header = self.treeview.header()
        header.resizeSection(0, 250)

    def _help_model(self, shortcuts):
        model = QStandardItemModel(0, 2, self)
        model.setHeaderData(0, Qt.Horizontal, self.tr('Action'))
        model.setHeaderData(1, Qt.Horizontal, self.tr('Shortcut'))

        for short in shortcuts:
            model.insertRow(0)
            model.setData(model.index(0, 0), short[0])
            model.setData(model.index(0, 1), short[1])
        return model

class ProductDialog(QDialog):
    def __init__(self, parent, methods=None, widget=None, title=None):
        super(ProductDialog, self).__init__(parent)
        vbox = QVBoxLayout()
        self.parent = parent
        width = 1000
        height = 300
        if widget:
            vbox.addLayout(widget.products, 0)

            count = len(widget.products)

            #width = count * 250
            if count > 4:
                #width = 1000
                height = 600

        self.setWindowTitle(title)
        self.setLayout(vbox)
        self.resize(width, height)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.dialog_rejected()
            return
        else:
            super(ProductDialog, self).keyPressEvent(event)

    def on_accept(self):
        self.accept()

    def on_reject(self):
        self.reject()

    def dialog_rejected(self):
        self.parent.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        self.setResult(1)
        self.done(1)
        self.parent.setFocus()
        self.hide()

    def closeEvent(self, event):
        super(ProductDialog, self).closeEvent(event)

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(ProductDialog, self).exec_()
        return res

    def show(self):
        super(ProductDialog, self).show()
        self.parent.releaseKeyboard()
        self.cancel_button.setFocus()
        self.setFocus()

    def hide(self):
        super(ProductDialog, self).hide()
        self.parent.setFocus()

class CategoryDialog(QDialog):
    def __init__(self, parent, methods=None, widget=None, title=None):
        super(CategoryDialog, self).__init__(parent)
        vbox = QVBoxLayout()
        self.parent = parent
        width = 500
        height = 300
        if widget:
            vbox.addLayout(widget.categories, 0)
            count = len(widget.categories)
            if count > 4:
                width = 1000
                height = 600
        self.setWindowTitle(title)
        self.setLayout(vbox)
        self.resize(width, height)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.dialog_rejected()
            return
        else:
            super(CategoryDialog, self).keyPressEvent(event)

    def on_accept(self):
        self.accept()

    def on_reject(self):
        self.reject()

    def dialog_rejected(self):
        self.parent.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        self.setResult(1)
        self.done(1)
        self.parent.setFocus()
        self.hide()

    def closeEvent(self, event):
        super(CategoryDialog, self).closeEvent(event)

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(CategoryDialog, self).exec_()
        return res

    def show(self):
        super(CategoryDialog, self).show()
        self.parent.releaseKeyboard()
        self.cancel_button.setFocus()
        self.setFocus()

    def hide(self):
        super(CategoryDialog, self).hide()
        self.parent.setFocus()

class AgentDialog(QDialog):
    def __init__(self, parent, methods=None,widget=None,title=None):
        super(AgentDialog, self).__init__(parent)
        vbox = QVBoxLayout()
        self.parent = parent
        if widget:
            vbox.addLayout(widget.agents,0)
        self.setWindowTitle(title)
        self.setLayout(vbox)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.dialog_rejected()
            return
        else:
            super(AgentDialog, self).keyPressEvent(event)

    def on_accept(self):
        self.accept()

    def on_reject(self):
        self.reject()

    def dialog_rejected(self):
        self.parent.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        self.setResult(1)
        self.done(1)
        self.parent.setFocus()
        self.hide()

    def closeEvent(self, event):
        super(AgentDialog, self).closeEvent(event)

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(AgentDialog, self).exec_()
        return res

    def show(self):
        super(AgentDialog, self).show()
        self.parent.releaseKeyboard()
        self.cancel_button.setFocus()
        self.setFocus()

    def hide(self):
        super(AgentDialog, self).hide()
        self.parent.setFocus()

class DeliveryDialog(QDialog):
    def __init__(self, parent, methods=None, widget=None, title=None):
        super(DeliveryDialog, self).__init__(parent)
        vbox = QVBoxLayout()
        self.parent = parent
        width = 800
        height = 300
        if widget:
            vbox.addLayout(widget.functions,0)
        self.setWindowTitle(title)
        self.setLayout(vbox)
        self.resize(width, height)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.dialog_rejected()
            return
        else:
            super(DeliveryDialog, self).keyPressEvent(event)

    def on_accept(self):
        self.accept()

    def on_reject(self):
        self.reject()

    def dialog_rejected(self):
        self.parent.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        self.setResult(1)
        self.done(1)
        self.parent.setFocus()
        self.hide()

    def closeEvent(self, event):
        super(DeliveryDialog, self).closeEvent(event)

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(DeliveryDialog, self).exec_()
        return res

    def show(self):
        super(DeliveryDialog, self).show()
        self.parent.releaseKeyboard()
        self.cancel_button.setFocus()
        self.setFocus()

    def hide(self):
        super(DeliveryDialog, self).hide()
        self.parent.setFocus()


class FactoryIcons(object):

    def __init__(self):
        name_icons = ['print', 'warning', 'info', 'error', 'question']
        self.icons = {}
        for name in name_icons:
            path_icon = os.path.join(par_dir, 'share', 'icon-' + name + '.png')
            if not os.path.exists(path_icon):
                continue
            _qpixmap_icon = QPixmap()
            _qpixmap_icon.load(path_icon)
            _icon_label = QLabel()
            _icon_label.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
            _icon_label.setPixmap(_qpixmap_icon.scaledToHeight(48))
            self.icons[name] = _icon_label

class TableDialog(QDialog):
    def __init__(self, parent, methods=None, widgets=[],
            table=None, title=None, cols_width=[]):
        super(TableDialog, self).__init__(parent)

        self.on_accepted_method = methods.get('on_accepted_method')

        vbox = QVBoxLayout()
        self.parent = parent
        self.ok_button = ActionButton('ok', self.dialog_accepted)
        self.cancel_button = ActionButton('cancel', self.dialog_canceled)
        self.cancel_button.setFocus()

        _buttons = []
        _buttons.extend([self.cancel_button, self.ok_button])

        buttonbox = QHBoxLayout()
        for b in _buttons:
            buttonbox.addWidget(b, 1)
        vbox.addLayout(buttonbox, 1)

        if widgets:
            vbox.addLayout(widgets, 2)

        if table:
            self.table = table
            vbox.addWidget(table, 3)

        self.setWindowTitle(title)
        self.setLayout(vbox)
        if cols_width:
            #print("cols_width >>", cols_width)
            WIDTH = sum(cols_width) + 75
        else:
            WIDTH = _TSIZE[0]
        size = (WIDTH+30, _TSIZE[1])
        self.setMinimumSize(*size)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.dialog_canceled()
            return
        else:
            super(TableDialog, self).keyPressEvent(event)

    def dialog_canceled(self):
        self.parent.setFocus()
        self.setResult(0)
        self.hide()

    def dialog_accepted(self):
        if self.parent and self.on_accepted_method:
            getattr(self.parent, self.on_accepted_method)()
        self.parent.setFocus()
        self.setResult(1)
        self.done(1)
        self.hide()

    def exec_(self, args=None):
        res = None
        self.parent.releaseKeyboard()
        res = super(TableDialog, self).exec_()
        return res

    def show(self):
        super(TableDialog, self).show()
        self.parent.releaseKeyboard()
        self.cancel_button.setFocus()
        self.setFocus()

    def hide(self):
        super(TableDialog, self).hide()
        self.parent.setFocus()