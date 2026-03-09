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
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,  QPushButton
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5 import QtMultimedia
#from PyQt5 import Qt
from PyQt5.QtCore import Qt

BAR_HEIGHT = 30
BASE3_DIGITS = 3
TEXT_MARGIN = 20
#
BLINK_DURATION = 5 * 60       # 5 minutes
RED_DURATION = 5 * 60         # 5 minutes
BLINK_INTERVAL = 500          # clignotement 0.5 s

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
        
        self.blink = False
        self.red = False
        self.visible = True
        
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_visible)

    def stop_blink(self):
        self.blink = False
        self.visible = True
        self.blink_timer.stop()
    
    def stop_red(self):
        self.red = False
        self.update()
        
    def set_value(self, value):
        self.value = value
        new_phrase = value_to_phrase(value, self.minv, self.maxv)
    
        if new_phrase != self.last_phrase and self.last_phrase:
            QtMultimedia.QSound.play("/System/Library/Sounds/Glass.aiff")
            self.last_phrase = new_phrase
            self.red = True
            QTimer.singleShot(RED_DURATION * 1000, self.stop_red)
    
        seconds_to_change = self.compute_phase()
    
        if seconds_to_change < BLINK_DURATION:
            if not self.blink_timer.isActive():
                self.blink = True
                self.blink_timer.start(BLINK_INTERVAL)
        else:
            self.stop_blink()
    
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
        #painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)
        # phrase sous la barre
        if self.visible:
            if self.red:
                painter.setPen(QColor(220,0,0))
            else:
                painter.setPen(QColor(0,0,0))
        
            painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)

#
    def toggle_visible(self):
        self.visible = not self.visible
        self.update()
        
    def compute_phase(self):
        total = self.maxv - self.minv
        segment = total / (3**BASE3_DIGITS)
    
        pos = (self.value - self.minv) / segment
        next_boundary = (math.floor(pos) + 1) * segment + self.minv
    
        seconds_to_change = (next_boundary - self.value) * 3600  # approx
        return seconds_to_change
#

class ActionBarWidget(QWidget):
    def __init__(self, duration=30*60):
        super().__init__()

        self.duration = duration
        self.elapsed = 0

        self.running = False
        self.paused = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)

        self.setMinimumHeight(BAR_HEIGHT + 2*TEXT_MARGIN)

        self.phrase = ""
        self.last_phrase = ""
    def start(self):

        if not self.running:
            self.running = True
            self.paused = False
            self.timer.start(1000)

    def pause(self):

        if not self.running:
            return

        if self.paused:
            self.timer.start(1000)
            self.paused = False
        else:
            self.timer.stop()
            self.paused = True

    def stop(self):

        self.running = False
        self.paused = False
        self.timer.stop()

        self.elapsed = 0
        self.update()

    def update_time(self):
    
        if self.running and not self.paused:
    
            self.elapsed += 1
    
            minutes = self.elapsed / 60
            max_minutes = self.duration / 60
    
            self.phrase = value_to_phrase(minutes, 0, max_minutes)
    
            if self.elapsed >= self.duration:
                self.stop()
    
            self.update()

    def stop(self):
    
        self.running = False
        self.paused = False
        self.timer.stop()
    
        self.elapsed = 0
        self.phrase = ""
    
        self.update()


    def paintEvent(self, event):

        painter = QPainter(self)

        width = self.width()

        zone = int(width * (6*60) / self.duration)

        # fond
        painter.setBrush(QColor(230,230,230))
        painter.drawRect(0, TEXT_MARGIN, width, BAR_HEIGHT)

        # zone début
        painter.setBrush(QColor(200,255,200))
        painter.drawRect(0, TEXT_MARGIN, zone, BAR_HEIGHT)

        # zone fin
        painter.setBrush(QColor(255,200,200))
        painter.drawRect(width-zone, TEXT_MARGIN, zone, BAR_HEIGHT)

        # progression bleue
        if self.elapsed > 0:

            pos = int(self.elapsed/self.duration * width)

            painter.setBrush(QColor(50,120,220))
            painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)

        painter.setPen(QColor(0,0,0))
        painter.drawText(5, TEXT_MARGIN-5, "6 min")
        painter.drawText(width-50, TEXT_MARGIN-5, "6 min")
        
        painter.setPen(QColor(0,0,0))
        painter.setFont(QFont("Arial",10))
        
        if self.phrase:
            painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)

# --- Fenêtre principale ---
class Window(QWidget):
    def __init__(self):
        super().__init__()

        # Charger XML
        self.xml_dict = {}
        self.load_xml("phrases.xml")

        #
        self.action_bar = ActionBarWidget()
        titre_action = QLabel("Action (1 h)")
        titre_action.setAlignment(Qt.AlignCenter)
       
        buttons_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶")
        self.pause_btn = QPushButton("⏸")
        self.stop_btn = QPushButton("■")
        
        for b in [self.start_btn, self.pause_btn, self.stop_btn]:
            b.setFixedSize(50,50)
            b.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size:22px;
                }
            """)
        
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size:22px;
                color:#2ecc71;
            }
        """)
        self.start_btn.setStyleSheet("color:#2ecc71; border:none; font-size:22px;")
        self.pause_btn.setStyleSheet("color:#f39c12; border:none; font-size:22px;")
        self.stop_btn.setStyleSheet("color:#000000; border:none; font-size:22px;")
        buttons_layout.addWidget(self.start_btn)
        buttons_layout.addWidget(self.pause_btn)
        buttons_layout.addWidget(self.stop_btn)
        
        self.start_btn.clicked.connect(self.action_bar.start)
        self.pause_btn.clicked.connect(self.action_bar.pause)
        self.stop_btn.clicked.connect(self.action_bar.stop)
        
        # Layout vertical principal
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Titre global
        title = QLabel("Gestion du temps")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title)
        
        layout = QVBoxLayout()
        main_layout.addLayout(layout)

        ##
        self.left_panel = QVBoxLayout()
        self.vie_bar = BarWidget(0,79)
        self.jour_bar = BarWidget(6,24)
        row_vie = QHBoxLayout()
        
        left_vie = QVBoxLayout()
        titre_vie = QLabel("Vie (0 → 79 ans)")
        titre_vie.setAlignment(Qt.AlignCenter)
        left_vie.addWidget(titre_vie)
        left_vie.addWidget(self.vie_bar)
        
        right_vie = QVBoxLayout()
        titre_vie_text = QLabel("Vie")
        titre_vie_text.setAlignment(Qt.AlignCenter)
        
        self.vie_text = QLabel("Texte vie")
        self.vie_text.setWordWrap(True)
        self.vie_text.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        right_vie.addWidget(titre_vie_text)
        right_vie.addWidget(self.vie_text)
        
        row_vie.addLayout(left_vie,1)
        row_vie.addLayout(right_vie,1)
        
        layout.addLayout(row_vie)
        
        row_jour = QHBoxLayout()

        left_jour = QVBoxLayout()
        titre_jour = QLabel("Journée (6h → 24h)")
        titre_jour.setAlignment(Qt.AlignCenter)
        left_jour.addWidget(titre_jour)
        left_jour.addWidget(self.jour_bar)
        
        right_jour = QVBoxLayout()
        titre_jour_text = QLabel("Journée")
        titre_jour_text.setAlignment(Qt.AlignCenter)
        
        self.jour_text = QLabel("Texte journée")
        self.jour_text.setWordWrap(True)
        self.jour_text.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        right_jour.addWidget(titre_jour_text)
        right_jour.addWidget(self.jour_text)
        
        row_jour.addLayout(left_jour,1)
        row_jour.addLayout(right_jour,1)
        
        layout.addLayout(row_jour)
        
        # ----- Ligne Action : barre + texte -----
        
        row_action = QHBoxLayout()
        
        left_action_bar = QVBoxLayout()
        titre_action = QLabel("Action (1 h)")
        titre_action.setAlignment(Qt.AlignCenter)
        
        left_action_bar.addWidget(titre_action)
        left_action_bar.addWidget(self.action_bar)
        
        right_action = QVBoxLayout()
        titre_action_text = QLabel("Action")
        titre_action_text.setAlignment(Qt.AlignCenter)
        
        self.action_text = QLabel("Texte action")
        self.action_text.setWordWrap(True)
        self.action_text.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        
        right_action.addWidget(titre_action_text)
        right_action.addWidget(self.action_text)
        
        row_action.addLayout(left_action_bar,1)
        row_action.addLayout(right_action,1)
        
        layout.addLayout(row_action)
        
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addLayout(buttons_layout)
        buttons_row.addStretch()
        
        layout.addLayout(buttons_row)
        
        # Valeurs initiales
        self.vie_bar.set_value(56)
        self.update_jour()
        self.resize(800, 300)
        
        # Timer
        timer = QTimer(self)
        timer.timeout.connect(self.update_jour)
        timer.start(1000)
         
    def update_jour(self):
        
        now = datetime.datetime.now()
        hour = now.hour + now.minute/60.0
        self.jour_bar.set_value(hour)
    
        # Vie
        vie_phrase = self.vie_bar.phrase
        vie_text = self.vie_dict.get(vie_phrase, "Pas de texte vie")
        self.vie_text.setText(vie_text)
    
        # Journée
        jour_phrase = self.jour_bar.phrase
        jour_text = self.jour_dict.get(jour_phrase, "Pas de texte journée")
        self.jour_text.setText(jour_text)
    
        # Action
        action_phrase = self.action_bar.phrase
        action_text = self.action_dict.get(action_phrase, "Pas de texte action")
        self.action_text.setText(action_text)

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
            
        action = root.find("action")
        self.action_dict = {}
        
        for p in action.findall("phrase"):
            key = p.get("key")
            text = p.text.strip()
            self.action_dict[key] = text

# --- Lancement ---
app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec_())