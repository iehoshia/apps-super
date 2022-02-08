
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem


def get_simple_model(obj, data, header=[]):
    model = QStandardItemModel(0, len(header), obj)
    if header:
        i = 0
        for head_name in header:
            model.setHeaderData(i, Qt.Horizontal, head_name)
            i += 1
    _insert_items(model, data)
    return model


def _insert_items(model, data):
    for d in data:
        row = []
        for val in d:
            itemx = QStandardItem(str(val))
            itemx.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            row.append(itemx)
        model.appendRow(row)
    model.sort(0, Qt.AscendingOrder)


def set_selection_model(tryton_model, args):
    pass
