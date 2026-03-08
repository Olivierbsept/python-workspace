#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 22:59:24 2026

@author: olivierbessettemac
"""

import sys
import math
import datetime
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5 import QtMultimedia

BAR_HEIGHT = 30
BASE3_DIGITS = 3
TEXT_MARGIN = 20

# --- Base 3 ---
def to_base3_fixed(value, digits):
    result = ""
    for _ in range(digits):
        result = str(value % 3) + result
        value //= 3
    return result

def word(c):
    if c == "0": return "début"
    if c == "1": return "milieu"
    return "fin"

def build_phrase(base3):
    phrase = ""
    for i in range(len(base3)-1, -1, -1):
        phrase += word(base3[i])
        if i > 0:
            if base3[i-1] == "2":
                phrase += " de la "
            else:
                phrase += " du "
    return phrase

def value_to_phrase(value, minv, maxv):
    norm = max(0, min(1, (value - minv)/(maxv - minv)))
    intval = round(norm * (3**BASE3_DIGITS - 1))
    base3 = to_base3_fixed(intval, BASE3_DIGITS)
    return build_phrase(base3)

# --- Barre graphique ---
class BarWidget(QWidget):
    def __init__(self, minv, maxv):
        super().__init__()
        self.value = 0
        self.minv = minv
        self.maxv = maxv
        self.phrase = ""
        self.last_phrase = ""
        self.setMinimumHeight(BAR_HEIGHT + 2*TEXT_MARGIN)

    def set_value(self, value):
        self.value = value
        new_phrase = value_to_phrase(value, self.minv, self.maxv)
        if new_phrase != self.last_phrase:
            QtMultimedia.QSound.play("/System/Library/Sounds/Glass.aiff")  # beep
            self.last_phrase = new_phrase
        self.phrase = new_phrase
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        pos = int((self.value - self.minv)/(self.maxv - self.minv) * width)
        m1 = width // 3
        m2 = 2 * width // 3

        # fond barre
        painter.setBrush(QColor(230,230,230))
        painter.drawRect(0, TEXT_MARGIN, width, BAR_HEIGHT)

        # barre remplie
        painter.setBrush(QColor(50,120,220))
        painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)

        painter.setPen(QColor(0,0,0))
        font = QFont("Arial", 10)
        painter.setFont(font)

        # Marques FD / DF
        painter.drawText(m1-10, TEXT_MARGIN-5, "FD")
        painter.drawText(m2-10, TEXT_MARGIN-5, "DF")

        # phrase sous la barre
        painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)

# --- Fenêtre principale ---
class Window(QWidget):
    def __init__(self):
        super().__init__()

        # Charger XML
        self.xml_dict = {}
        self.load_xml("phrases.xml")

        # Layout horizontal
        layout = QHBoxLayout()
        self.setLayout(layout)

        # Panel gauche
        self.left_panel = QVBoxLayout()
        self.vie_bar = BarWidget(0,79)
        self.jour_bar = BarWidget(6,24)
        self.left_panel.addWidget(QLabel("Vie (0 → 79 ans)"))
        self.left_panel.addWidget(self.vie_bar)
        self.left_panel.addWidget(QLabel("Journée (6h → 24h)"))
        self.left_panel.addWidget(self.jour_bar)
        layout.addLayout(self.left_panel, 1)

        # Panel droit
        self.right_panel = QVBoxLayout()
        
        self.vie_text = QLabel("Texte vie")
        self.vie_text.setWordWrap(True)
        self.vie_text.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        self.jour_text = QLabel("Texte journée")
        self.jour_text.setWordWrap(True)
        self.jour_text.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        self.right_panel.addWidget(QLabel("Vie"))
        self.right_panel.addWidget(self.vie_text)
        
        self.right_panel.addWidget(QLabel("Journée"))
        self.right_panel.addWidget(self.jour_text)
        
        layout.addLayout(self.right_panel, 1)

        self.resize(800, 300)

        # Valeurs initiales
        self.vie_bar.set_value(56)
        self.update_jour()

        # Timer
        timer = QTimer(self)
        timer.timeout.connect(self.update_jour)
        timer.start(1000)

    def update_jour(self):
    
        now = datetime.datetime.now()
        hour = now.hour + now.minute/60.0
        self.jour_bar.set_value(hour)
    
        vie_phrase = self.vie_bar.phrase
        jour_phrase = self.jour_bar.phrase
    
        vie_text = self.vie_dict.get(vie_phrase, "Pas de texte vie")
        jour_text = self.jour_dict.get(jour_phrase, "Pas de texte journée")
    
        self.vie_text.setText(vie_text)
        self.jour_text.setText(jour_text)

    def load_xml(self, filename):
    
        tree = ET.parse(filename)
        root = tree.getroot()
    
        self.vie_dict = {}
        self.jour_dict = {}
    
        vie = root.find("vie")
        for p in vie.findall("phrase"):
            key = p.get("key")
            text = p.text.strip()
            self.vie_dict[key] = text
    
        jour = root.find("jour")
        for p in jour.findall("phrase"):
            key = p.get("key")
            text = p.text.strip()
            self.jour_dict[key] = text

# --- Lancement ---
app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec_())