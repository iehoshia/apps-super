
import sys, os
from decimal import Decimal
from pathlib import Path
from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QPushButton

css_small = 'product_button_small.css'
css_high = 'product_button_hd.css'
root_dir = Path(__file__).parent.parent

__all__ = ['ProductButton']


class ProductButton(QPushButton):

    def __init__(self, parent, id, text_up, text_bottom, method, target, size='small'):
        super(ProductButton, self).__init__()

        self.id = id
        styles = []
        if size == 'small':
            css_file_screen = css_small
        else:
            css_file_screen = css_high

        css_file = os.path.join(root_dir, 'css', css_file_screen)

        with open(css_file, 'r') as infile:
            styles.append(infile.read())

        self.setStyleSheet(''.join(styles))
        self.setObjectName('product_button')
        if len(text_up) > 29:
            text_up = text_up[0:29]

        label1 = QLabel(text_up, self)
        label1.setWordWrap(True)
        label1.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        label1.setObjectName('product_label_up')

        label2 = QLabel(text_bottom, self)
        label2.setAlignment(Qt.AlignCenter | Qt.AlignCenter)
        label2.setObjectName('product_label_bottom')

        method = getattr(parent, method)
        if target:
            method = partial(method, target)
        self.clicked.connect(method)
