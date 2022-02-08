
from PyQt5.QtWidgets import QPushButton

__all__ = ['ActionButton']


class ActionButton(QPushButton):

    def __init__(self, action, method):

        super(ActionButton, self).__init__('')
        if action == 'ok':
            name = self.tr("&ACCEPT")
        else:
            name = self.tr("&CANCEL")

        self.setText(name)
        self.clicked.connect(method)
        if action == 'ok':
            self.setAutoDefault(True)
            self.setDefault(True)
        self.setObjectName('button_' + action)
