
from PyQt5.QtWidgets import QLabel, QWidget, QDesktopWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

__all__ = ['Image']


class Image(QLabel):

    def __init__(self, obj=None, name='', default_img=None, scaled_rate=None):
        if not obj:
            obj = QWidget()
        super(Image, self).__init__(obj)

        screen = QDesktopWidget().screenGeometry()
        screen_width = screen.width()
        screen_width = 1024


        self.parent = obj
        self.setObjectName('img_' + name)

        if default_img:
            self.pixmap = QPixmap()
            self.pixmap.load(default_img)
            img_width, img_height = self.pixmap.width(), self.pixmap.height()
            #print("img_width and img_height >>", img_width, img_height)
            scaled_rate = False
            if screen_width <= 1024:
                scaled_rate = 1
            elif screen_width <= 1366:
                scaled_rate = 0.75
            if scaled_rate:
                new_width = img_width * scaled_rate
                new_height = img_height * scaled_rate
                self.pixmap = self.pixmap.scaled(new_width, new_height,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(self.pixmap)

    def set_image(self, img):
        self.pixmap = QPixmap()
        if img:
            self.pixmap.loadFromData(img.data)
            self.setPixmap(self.pixmap)

    def load_image(self, pathfile):
        self.pixmap = QPixmap()
        self.pixmap.load(pathfile)
        self.setPixmap(self.pixmap)

    def activate(self):
        self.free_center()
        self.parent.show()

    def free_center(self):
        screen = QDesktopWidget().screenGeometry()
        screen_width = screen.width()
        screen_width = 1024
        screen_height = screen.height()
        size = self.pixmap.size()
        self.parent.setGeometry(
            (screen_width / 2) - (size.width() / 2),
            (screen_height / 2) - (size.height() / 2),
            size.width(),
            size.height()
        )
