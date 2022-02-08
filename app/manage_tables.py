import os

from PyQt5.QtWidgets import QGridLayout, QPushButton

DIR_SHARE = os.path.abspath(
    os.path.normpath(os.path.join(__file__, '..', '..', 'share')))

__all__ = ['ManageTables']

STATES = {
    'available': 'rgb(180, 180, 180)',
    'occupied': 'rgb(255, 210, 30)',
    'reserved': 'rgb(150, 30, 0)'
}


class CallButton(QPushButton):

    def __init__(self, value, method):
        super(CallButton, self).__init__(value['name'])
        self.setAutoFillBackground(True)
        self.name = value['name']
        self.id = value['id']
        self.state = value['state']
        self.method = method
        self.set_state(value['state'])
        self.clicked.connect(self.handle_click)

    def handle_click(self):
        if self.state == 'available':
            state = 'occupied'
        else:
            state = 'available'

        res = self.method(self.id, self.name, self.state, state)
        if not res:
            return

        self.set_state(state)

    def set_state(self, state):
        self.state = state
        color = STATES[self.state]
        self.setStyleSheet('background-color: {}; border:none;'.format(color))


class ManageTables(QGridLayout):

    def __init__(self, parent, tables, method):
        super(ManageTables, self).__init__()
        self.setHorizontalSpacing(1)
        self.setVerticalSpacing(1)
        columns = 6
        rows = int(len(tables) / columns) + 1
        self.buttons = {}
        positions = [(i, j) for i in range(rows) for j in range(columns)]
        for position, value in zip(positions, tables):
            button = CallButton(value, method)
            self.buttons[button.id] = button
            self.addWidget(button, *position)

    def update_table(self, button_id, state):
        button = self.buttons[button_id]
        button.set_state(state)
