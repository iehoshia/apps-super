from PyQt5.QtWidgets import QTableView, QHeaderView, QAbstractItemView
from PyQt5.QtCore import Qt

STRETCH = QHeaderView.Stretch


class TableView(QTableView):

    def __init__(self, name, model, col_sizes=[], method_selected_row=None,
        method_clicked_row=None):
        super(TableView, self).__init__()
        self.setObjectName(name)
        self.verticalHeader().hide()
        self.setGridStyle(Qt.DotLine)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerItem)
        self.model = model
        if method_selected_row:
            self.method_selected_row = method_selected_row
            self.doubleClicked.connect(self.on_selected_row)
        if method_clicked_row:
            self.clicked.connect(method_clicked_row)

        if model:
            self.setModel(model)

        header = self.horizontalHeader()
        if col_sizes:
            for i, size in enumerate(col_sizes):
                if type(size) == int:
                    header.resizeSection(i, size)
                else:
                    header.setSectionResizeMode(i, STRETCH)

    def on_selected_row(self):
        selected_idx = self.currentIndex()
        if selected_idx:
            self.method_selected_row(self.model.get_data(selected_idx))

    def rowsInserted(self, index, start, end):
        # Adjust scroll to last row (bottom)
        self.scrollToBottom()

    def removeElement(self, index):
        if not index:
            return
        if index.row() >= 0 and self.hasFocus():
            item = self.model.get_data(index)
            id_ = self.model.removeId(index.row(), index)
            self.model.deleteRecords([id_])
            self.model.layoutChanged.emit()
            return item

    def movedSelection(self, key):
        selected_idx = self.currentIndex()
        if key == Qt.Key_Down:
            self.selectRow(selected_idx.row() + 1)
        elif key == Qt.Key_Up:
            self.selectRow(selected_idx.row() - 1)
        elif key == Qt.Key_Delete or key == 0:
            item_removed = self.removeElement(selected_idx)
            return item_removed
        else:
            print('missing idx')
