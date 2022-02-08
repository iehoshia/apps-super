from PyQt5 import QtWidgets, QtCore

__all__ = ['DigitalClock']


class DigitalClock(QtWidgets.QLCDNumber):

    def __init__(self, parent=None):
        super(DigitalClock, self).__init__(parent)
        self.setSegmentStyle(QtWidgets.QLCDNumber.Filled)
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.showTime)
        timer.start(1000)

    def showTime(self):
        time = QtCore.QTime.currentTime()
        text = time.toString('hh:mm')
        if (time.second() % 2) == 0:
            text = text[:2] + ' ' + text[3:]
        self.display(text)
