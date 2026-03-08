import sys
import math
import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QColor, QFont

BAR_WIDTH = 600
BAR_HEIGHT = 30
BASE3_DIGITS = 3
TEXT_MARGIN = 20  # marge pour afficher le texte

def to_base3_fixed(value, digits):
    result = ""
    for _ in range(digits):
        result = str(value % 3) + result
        value //= 3
    return result

def word(c):
    if c == "0":
        return "début"
    if c == "1":
        return "milieu"
    return "fin"

def build_phrase(base3):
    phrase = ""
    for i in range(len(base3) - 1, -1, -1):
        phrase += word(base3[i])
        if i > 0:
            if base3[i - 1] == "2":
                phrase += " de la "
            else:
                phrase += " du "
    return phrase

def value_to_phrase(value, minv, maxv):
    norm = (value - minv) / (maxv - minv)
    norm = max(0, min(1, norm))
    intval = round(norm * (3 ** BASE3_DIGITS - 1))
    base3 = to_base3_fixed(intval, BASE3_DIGITS)
    return build_phrase(base3)

class BarWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.value = 0
        self.minv = 0
        self.maxv = 1
        self.phrase = ""
        self.last_phrase = ""
        self.setMinimumHeight(BAR_HEIGHT + 2*TEXT_MARGIN)  # assez grand pour texte

    def set_value(self, value, minv, maxv):
        self.value = value
        self.minv = minv
        self.maxv = maxv
        new_phrase = value_to_phrase(value, minv, maxv)
        if new_phrase != self.last_phrase:
            QApplication.beep()
            self.last_phrase = new_phrase
        self.phrase = new_phrase
        self.update()  # redessine le widget

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        pos = int((self.value - self.minv) / (self.maxv - self.minv) * width)
        m1 = width // 3
        m2 = 2 * width // 3

        # fond barre
        painter.setBrush(QColor(230, 230, 230))
        painter.drawRect(0, TEXT_MARGIN, width, BAR_HEIGHT)

        # barre remplie
        painter.setBrush(QColor(50, 120, 220))
        painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)

        # marques FD et DF
        painter.setPen(QColor(0, 0, 0))
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(m1 - 10, TEXT_MARGIN - 5, "FD")
        painter.drawText(m2 - 10, TEXT_MARGIN - 5, "DF")

        # phrase sous la barre
        painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)

class Window(QWidget):

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.vie_bar = BarWidget()
        self.jour_bar = BarWidget()
        layout.addWidget(self.vie_bar)
        layout.addWidget(self.jour_bar)
        self.setLayout(layout)
        self.resize(BAR_WIDTH, 150)

        # valeur fixe pour la vie
        self.vie_bar.set_value(56, 0, 79)

        # timer pour la journée
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)

    def update_time(self):
        now = datetime.datetime.now()
        hour = now.hour + now.minute / 60
        self.jour_bar.set_value(hour, 6, 24)

app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec_())