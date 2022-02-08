
'''
    Electronic Scale measure methods
'''
import time
try:
    import serial
except:
    print('Warning: missing pyserial module!')

from decimal import Decimal
from PyQt5.QtCore import QThread, pyqtSignal

ZERO_VALUES = [b'00.000\n', b'\r00.000\n']
FAKE_WEIGHT = b'01.500\n'
MAX_RANGE_ATTEMPT = 30


class ScaleReader(QThread):
    """
        Electronic Scale Reader Class
    """
    sigSetDevice = pyqtSignal()
    sigSetWeight = pyqtSignal()
    sigCancelAction = pyqtSignal()

    def __init__(self, device_path='/dev/ttyUSB0', fake=False):
        QThread.__init__(self)
        self.fake = fake
        self.device = device_path
        try:
            self.scale = serial.Serial(self.device)
        except:
            print('Error: serial device not found!')

    def run(self):
        values = []
        counter = 0
        self.best_weight = Decimal(0)
        if self.fake:
            self._run_fake()
            return
        try:
            self.scale = serial.Serial(self.device)
        except:
            print('Error: serial device not found!')
            return

        while counter <= MAX_RANGE_ATTEMPT:
            read_value = self.scale.readline()
            if read_value in ZERO_VALUES:
                continue

            counter += 1
            weight = read_value.decode("utf-8")
            weight = weight.replace('\n\r', '')
            weight = weight.encode("ascii").decode()
            try:
                weight = Decimal(weight)
            except:
                continue
            values.append(weight)

        self.scale.close()
        if values:
            self.best_weight = str(max(values))
            self.sigSetWeight.emit()

    def _run_fake(self):
        self.scale = 'Fake Electronic Scale'
        self.sigSetDevice.emit()
        time.sleep(3)
        self.best_weight = FAKE_WEIGHT
        self.sigGetWeight.emit()

    def reset_zero(self):
        self.best_weight = None

    def onClose(self):
        if hasattr(self, 'scale'):
            self.scale.close()
