#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 22:59:24 2026
@author: olivierbessettemac

Gestion du temps — version fusionnée (BarWidget + ActionBarWidget → UnifiedBarWidget)
"""

import sys
import math
import datetime
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QFrame, QPushButton,
                             QDateEdit, QTimeEdit, QSpinBox, QDialog, QDialogButtonBox)
from PyQt5.QtCore import QTimer, Qt, QDate, QTime
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5 import QtMultimedia
import win32com.client

BAR_HEIGHT    = 30
BASE3_DIGITS  = 3
TEXT_MARGIN   = 20
BLINK_INTERVAL = 500          # clignotement 0.5 s

BLINK_DURATION      = 5 * 60
RED_DURATION        = 5 * 60
JOUR_RED_DURATION   = 2 * 60
JOUR_BLINK_DURATION = 2 * 60

# ─────────────────────────────────────────────
#  Logique base 3
# ─────────────────────────────────────────────

def compute_x012(A, B, D, E, M):
    C = (A + B) / 2
    F = (A + D) / 2
    H = (D + E) / 2
    G = (E + B) / 2
    AB = B - A
    AD = D - A
    DE = E - D
    EB = B - E
    xs = []
    for _ in range(3):
        if A <= M <= D:
            x = 0
            M = C + (M - F) * AB / AD
        elif D < M <= E:
            x = 1
            M = C + (M - H) * AB / DE
        else:
            x = 2
            M = C + (M - G) * AB / EB
        xs.append(x)
    return xs


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
    for i in range(len(base3) - 1, -1, -1):
        phrase += word(base3[i])
        if i > 0:
            phrase += " de la " if base3[i - 1] == "2" else " du "
    return phrase


def value_to_phrase(value, minv, maxv, fd_fraction, df_fraction):
    norm = max(0.0, min(1.0, (value - minv) / (maxv - minv)))
    x0, x1, x2 = compute_x012(0, 1, fd_fraction, df_fraction, norm)
    return build_phrase(f"{x0}{x1}{x2}")


# ─────────────────────────────────────────────
#  Widget unifié
# ─────────────────────────────────────────────

class UnifiedBarWidget(QWidget):
    """
    Barre de progression polyvalente.

    Modes :
      • mode='value'  — valeur poussée de l'extérieur via set_value()
                        (ex. Vie, Journée)
      • mode='timer'  — timer interne démarré / mis en pause / stoppé
                        via start() / pause() / stop()
                        (ex. Action)

    Paramètres communs :
      minv, maxv          — bornes de la plage
      red_duration        — durée (s) d'affichage rouge après changement
      blink_duration      — durée (s) de clignotement avant changement
      fd_fraction         — position initiale du séparateur FD  [0..1]
      df_fraction         — position initiale du séparateur DF  [0..1]

    Paramètres spécifiques mode='timer' :
      duration            — durée totale du timer en secondes
    """

    def __init__(self, minv=0, maxv=1,
                 mode='value',
                 duration=3600,
                 red_duration=RED_DURATION,
                 blink_duration=BLINK_DURATION,
                 fd_fraction=0.33,
                 df_fraction=0.66,
                 label_format='fraction'):
        # label_format :
        #   'fraction'  → affiche les fractions (ancien comportement)
        #   'years'     → affiche la valeur en années (ex. "23.4 ans")
        #   'hhmm'      → affiche en heures:minutes (ex. "9h30")
        #   'timer'     → géré en interne (minutes avant/après)
        self.countdown_text = ""
        
        self.label_format = label_format
        super().__init__()

        self.mode          = mode
        self.minv          = minv
        self.maxv          = maxv
        self.duration      = duration          # timer uniquement
        self.red_duration  = red_duration
        self.blink_duration = blink_duration

        # État
        self.value         = minv
        self.elapsed       = 0                 # timer uniquement
        self.running       = False
        self.paused        = False

        self.phrase        = ""
        self.last_phrase   = ""

        # Visuel
        self.red     = False
        self.blink   = False
        self.visible = True

        self.fd_fraction = fd_fraction
        self.df_fraction = df_fraction

        self.drag_fd = False
        self.drag_df = False

        # Timers Qt
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_visible)

        if self.mode == 'timer':
            self._tick_timer = QTimer()
            self._tick_timer.timeout.connect(self._tick)

        self.setMinimumHeight(BAR_HEIGHT + 2 * TEXT_MARGIN + 20)

    # ── API publique ──────────────────────────

    def set_value(self, value):
        """Mode 'value' : met à jour la valeur affichée."""
        self.value = value
        self._update_phrase(value, self.minv, self.maxv)
        secs = self._seconds_to_next_change(value, self.minv, self.maxv, unit='hours')
        self._refresh_blink(secs)
        self.update()

    def start(self):
        """Mode 'timer' : démarre le timer."""
        if self.mode != 'timer':
            return
        if not self.running:
            self.running = True
            self.paused  = False
            self._tick_timer.start(1000)

    def pause(self):
        """Mode 'timer' : bascule pause / reprise."""
        if self.mode != 'timer' or not self.running:
            return
        if self.paused:
            self._tick_timer.start(1000)
            self.paused = False
        else:
            self._tick_timer.stop()
            self.paused = True

    def stop(self):
        """Mode 'timer' : arrête et remet à zéro."""
        if self.mode != 'timer':
            return
        self.running  = False
        self.paused   = False
        self.elapsed  = 0
        self.phrase   = ""
        self.last_phrase = ""
        self._tick_timer.stop()
        self.stop_blink()
        self.update()

    def set_start_fraction(self, f):
        self.fd_fraction = max(0.0, min(0.5, f))
        self.update()

    # ── Timers internes ───────────────────────

    def _tick(self):
        """Appelé chaque seconde en mode timer."""
        if not (self.running and not self.paused):
            return
        self.elapsed += 1
        minutes     = self.elapsed / 60.0
        max_minutes = self.duration / 60.0
        self._update_phrase(minutes, 0, max_minutes)
        secs = self._seconds_to_next_change(minutes, 0, max_minutes, unit='seconds')
        self._refresh_blink(secs)
        self.update()

    def _update_phrase(self, value, minv, maxv):
        new_phrase = value_to_phrase(value, minv, maxv,
                                     self.fd_fraction, self.df_fraction)
        if new_phrase != self.last_phrase:
            if self.last_phrase:
                QtMultimedia.QSound.play("/System/Library/Sounds/Glass.aiff")
                # arrêter le blink : on vient de franchir la frontière
                self.stop_blink()
                # passer en rouge pour red_duration secondes
                self.red = True
                QTimer.singleShot(self.red_duration * 1000, self._stop_red)
            self.last_phrase = new_phrase
        self.phrase = new_phrase

    def _refresh_blink(self, seconds_to_change):
        """Clignotement UNIQUEMENT si pas en phase rouge."""
        if self.red:
            return  # ne pas démarrer le blink pendant le rouge
        if seconds_to_change < self.blink_duration:
            if not self.blink_timer.isActive():
                self.blink = True
                self.blink_timer.start(BLINK_INTERVAL)
        else:
            self.stop_blink()

    def _seconds_to_next_change(self, value, minv, maxv, unit='seconds'):
        """
        Retourne le temps (en secondes) avant le prochain changement de phrase.
        unit='seconds' si value est en minutes, 'hours' si en heures.
        """
        total   = maxv - minv
        segment = total / (3 ** BASE3_DIGITS)
        pos     = (value - minv) / segment
        next_b  = (math.floor(pos) + 1) * segment + minv
        delta   = next_b - value
        if unit == 'seconds':
            return delta * 60.0   # value en minutes → delta en secondes
        else:
            return delta * 3600.0  # value en heures  → delta en secondes

    def _stop_red(self):
        self.red = False
        # relancer l'évaluation du blink pour la nouvelle phase
        if self.mode == 'timer':
            minutes     = self.elapsed / 60.0
            max_minutes = self.duration / 60.0
            secs = self._seconds_to_next_change(minutes, 0, max_minutes, unit='seconds')
        else:
            secs = self._seconds_to_next_change(self.value, self.minv, self.maxv, unit='hours')
        self._refresh_blink(secs)
        self.update()

    def _toggle_visible(self):
        self.visible = not self.visible
        self.update()

    def stop_blink(self):
        self.blink   = False
        self.visible = True
        self.blink_timer.stop()

    # ── Dessin ───────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)
    
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
    
        width = self.width()
    
        m1 = int(width * self.fd_fraction)
        m2 = int(width * self.df_fraction)
    
        m1 = max(0, min(width, m1))
        m2 = max(0, min(width, m2))
    
        # ── fond ──
        if self.mode in ("timer", "meeting"):
    
            painter.setBrush(QColor(200, 255, 200))
            painter.drawRect(0, TEXT_MARGIN, m1, BAR_HEIGHT)
    
            painter.setBrush(QColor(230, 230, 230))
            painter.drawRect(m1, TEXT_MARGIN, m2 - m1, BAR_HEIGHT)
    
            painter.setBrush(QColor(255, 200, 200))
            painter.drawRect(m2, TEXT_MARGIN, width - m2, BAR_HEIGHT)
    
        else:
            painter.setBrush(QColor(230, 230, 230))
            painter.drawRect(0, TEXT_MARGIN, width, BAR_HEIGHT)
    
        # ── progression ──
        if self.mode == 'timer':
    
            if self.elapsed > 0 and self.duration > 0:
    
                ratio = min(1.0, max(0.0, self.elapsed / self.duration))
                pos = int(ratio * width)
    
                painter.setBrush(QColor(50, 120, 220))
                painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)
    
        else:
    
            if self.maxv != self.minv:
                ratio = (self.value - self.minv) / (self.maxv - self.minv)
            else:
                ratio = 0
    
            ratio = min(1.0, max(0.0, ratio))
            pos = int(ratio * width)
    
            painter.setBrush(QColor(50, 120, 220))
            painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)
    
        # ── étiquettes FD / DF ──
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 10))
    
        fm = painter.fontMetrics()
    
        #lbl_fd, lbl_df = self._fd_df_labels()
        if self.mode == "meeting":
            lbl_fd, lbl_df = self._fd_df_labels_meeting()
        else:
            lbl_fd, lbl_df = self._fd_df_labels()
    
        tw_fd = fm.horizontalAdvance(lbl_fd)
        tw_df = fm.horizontalAdvance(lbl_df)
    
        painter.drawText(max(0, m1 - tw_fd // 2), TEXT_MARGIN - 5, lbl_fd)
        painter.drawText(max(0, m2 - tw_df // 2), TEXT_MARGIN - 5, lbl_df)
    
        # ── compte à rebours réunion ──
        if hasattr(self, "countdown_text") and self.countdown_text:
            painter.setPen(QColor(0, 0, 0))
            painter.setFont(QFont("Arial", 11, QFont.Bold))
            painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT - 4, self.countdown_text)
    
        # ── phrase ──
        if self.visible or self.red:
    
            painter.setPen(QColor(220, 0, 0) if self.red else QColor(0, 0, 0))
            painter.setFont(QFont("Arial", 10))
    
            painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 18, self.phrase)
    
        # ── traits verticaux FD / DF ──
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(3)
        painter.setPen(pen)
    
        painter.drawLine(m1, TEXT_MARGIN, m1, TEXT_MARGIN + BAR_HEIGHT)
        painter.drawLine(m2, TEXT_MARGIN, m2, TEXT_MARGIN + BAR_HEIGHT)
#

    def _fd_df_labels(self):
        """Retourne (label_FD, label_DF) selon label_format."""
        fmt = self.label_format
    
        if fmt == 'years':
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
            return f"{val_fd:.1f} ans", f"{val_df:.1f} ans"
    
        elif fmt == 'hhmm':
    
            def to_hhmm(v):
                h = int(v)
                m = int(round((v - h) * 60))
    
                if m == 60:
                    h += 1
                    m = 0
    
                return f"{h}h{m:02d}"
    
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
    
            return to_hhmm(val_fd), to_hhmm(val_df)
    
        elif fmt == 'timer' or self.mode == 'timer':
    
            if self.duration <= 0:
                return "0 min", "0 min"
    
            # temps depuis le début
            fd_seconds = self.duration * self.fd_fraction
    
            # temps restant avant la fin
            df_seconds = self.duration * (1 - self.df_fraction)
    
            minutes_fd = int(round(fd_seconds / 60))
            minutes_df = int(round(df_seconds / 60))
    
            return f"{minutes_fd} min", f"{minutes_df} min"
    
        else:  # 'fraction' ou autre
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
    
            return f"{val_fd:.2f}", f"{val_df:.2f}"

    def _fd_df_labels_meeting(self):
        """Labels FD / DF pour la barre réunion."""
    
        if self.duration <= 0:
            return "", ""
    
        minutes_fd = int((self.duration * self.fd_fraction) / 60)
        minutes_df = int((self.duration * self.df_fraction) / 60)
    
        return f"{minutes_fd} min", f"{minutes_df} min"

    # ── Souris ───────────────────────────────

    def mousePressEvent(self, event):
        width = self.width()
        m1    = int(width * self.fd_fraction)
        m2    = int(width * self.df_fraction)
        if abs(event.x() - m1) < 10:
            self.drag_fd = True
        elif abs(event.x() - m2) < 10:
            self.drag_df = True

    def mouseMoveEvent(self, event):
        width = self.width()
        x     = event.x() / width
        if self.drag_fd:
            self.fd_fraction = max(0.01, min(self.df_fraction - 0.02, x))
            if self.mode == 'value':
                self.set_value(self.value)
            else:
                self.update()
        elif self.drag_df:
            self.df_fraction = min(0.99, max(self.fd_fraction + 0.02, x))
            if self.mode == 'value':
                self.set_value(self.value)
            else:
                self.update()

    def mouseReleaseEvent(self, event):
        self.drag_fd = False
        self.drag_df = False


# ─────────────────────────────────────────────
#  Fenêtre principale
# ─────────────────────────────────────────────

class Window(QWidget):
    def __init__(self):
        super().__init__()

        self.xml_dict   = {}
        self.vie_dict   = {}
        self.jour_dict  = {}
        self.action_dict = {}
        self.load_xml("phrases.xml")

        # ── Boutons timer ──
        buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶")
        self.pause_btn = QPushButton("⏸")
        self.stop_btn  = QPushButton("■")

        for b in [self.start_btn, self.pause_btn, self.stop_btn]:
            b.setFixedSize(50, 50)

        self.start_btn.setStyleSheet("color:#2ecc71; border:none; font-size:22px;")
        self.pause_btn.setStyleSheet("color:#f39c12; border:none; font-size:22px;")
        self.stop_btn.setStyleSheet( "color:#000000; border:none; font-size:22px;")

        for b in [self.start_btn, self.pause_btn, self.stop_btn]:
            buttons_layout.addWidget(b)

        # ── Layout principal ──
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        title = QLabel("Gestion du temps")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:18px; font-weight:bold; margin:10px;")
        main_layout.addWidget(title)

        layout = QVBoxLayout()
        main_layout.addLayout(layout)

        # ── Dates de vie (persistées dans config_barres.xml) ──
        self.vie_date_naissance = QDate(1970, 1, 1)
        self.vie_date_fin       = QDate(2049, 1, 1)

        def _years_between(d1, d2):
            """Durée fractionnaire en années entre deux QDate."""
            days = d1.daysTo(d2)
            return days / 365.25

        def _age_today(naissance):
            """Âge fractionnaire aujourd'hui."""
            today = QDate.currentDate()
            days  = naissance.daysTo(today)
            return days / 365.25

        self._years_between = _years_between
        self._age_today     = _age_today

        minv_vie = 0.0
        maxv_vie = _years_between(self.vie_date_naissance, self.vie_date_fin)

        # ── Barres (mode value) ──
        self.vie_bar = UnifiedBarWidget(
            minv=minv_vie, maxv=maxv_vie,
            mode='value',
            red_duration=RED_DURATION,
            blink_duration=BLINK_DURATION,
            label_format='years'
        )
        self.vie_bar.set_start_fraction(0.25)

        # ── Heures de journée ──
        self.jour_heure_debut = QTime(6, 0)
        self.jour_heure_fin   = QTime(24, 0)   # stocké comme 0h = minuit via _heure_to_float

        def _heure_to_float(t):
            """QTime → heures fractionnaires (minuit = 24.0 si après midi)."""
            return t.hour() + t.minute() / 60.0

        self._heure_to_float = _heure_to_float

        self.jour_bar = UnifiedBarWidget(
            minv=_heure_to_float(self.jour_heure_debut),
            maxv=24.0,
            mode='value',
            red_duration=JOUR_RED_DURATION,
            blink_duration=JOUR_BLINK_DURATION,
            label_format='hhmm'
        )

        # ── Barre action (mode timer) ──
        self.action_bar = UnifiedBarWidget(
            minv=0, maxv=60,      # en minutes
            mode='timer',
            duration=30 * 60,     # 30 minutes par défaut
            red_duration=2 * 60,
            blink_duration=2 * 60,
            fd_fraction=0.20,
            df_fraction=0.80
        )

        self.start_btn.clicked.connect(self.action_bar.start)
        self.pause_btn.clicked.connect(self.action_bar.pause)
        self.stop_btn.clicked.connect(self.action_bar.stop)

        # ── Ligne Vie ──
        self.vie_titre_lbl = QLabel(self._vie_titre())
        self.vie_titre_lbl.setAlignment(Qt.AlignCenter)
        self.btn_dates_vie = QPushButton("📅")
        self.btn_dates_vie.setFixedSize(28, 28)
        self.btn_dates_vie.setStyleSheet("border:none; font-size:16px;")
        self.btn_dates_vie.clicked.connect(self._choisir_dates_vie)
        vie_titre_row = QHBoxLayout()
        vie_titre_row.addStretch()
        vie_titre_row.addWidget(self.vie_titre_lbl)
        vie_titre_row.addWidget(self.btn_dates_vie)
        vie_titre_row.addStretch()
        vie_col = QVBoxLayout()
        vie_col.addLayout(vie_titre_row)
        vie_col.addWidget(self.vie_bar)
        layout.addLayout(vie_col)

        # ── Ligne Journée ──
        self.jour_titre_lbl = QLabel(self._jour_titre())
        self.jour_titre_lbl.setAlignment(Qt.AlignCenter)
        self.btn_heures_jour = QPushButton("⏰")
        self.btn_heures_jour.setFixedSize(28, 28)
        self.btn_heures_jour.setStyleSheet("border:none; font-size:16px;")
        self.btn_heures_jour.clicked.connect(self._choisir_heures_jour)
        jour_titre_row = QHBoxLayout()
        jour_titre_row.addStretch()
        jour_titre_row.addWidget(self.jour_titre_lbl)
        jour_titre_row.addWidget(self.btn_heures_jour)
        jour_titre_row.addStretch()
        jour_col = QVBoxLayout()
        jour_col.addLayout(jour_titre_row)
        jour_col.addWidget(self.jour_bar)
        layout.addLayout(jour_col)

        # ── Ligne Action ──
        self.action_titre_lbl = QLabel(self._action_titre())
        self.action_titre_lbl.setAlignment(Qt.AlignCenter)
        self.btn_duree_action = QPushButton("⏱")
        self.btn_duree_action.setFixedSize(28, 28)
        self.btn_duree_action.setStyleSheet("border:none; font-size:16px;")
        self.btn_duree_action.clicked.connect(self._choisir_duree_action)
        action_titre_row = QHBoxLayout()
        action_titre_row.addStretch()
        action_titre_row.addWidget(self.action_titre_lbl)
        action_titre_row.addWidget(self.btn_duree_action)
        action_titre_row.addStretch()
        action_col = QVBoxLayout()
        action_col.addLayout(action_titre_row)
        action_col.addWidget(self.action_bar)
        layout.addLayout(action_col)

        # ── Boutons ──
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addLayout(buttons_layout)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        try:
            self.outlook = win32com.client.Dispatch("Outlook.Application")
            self.namespace = self.outlook.GetNamespace("MAPI")
            self.calendar = self.namespace.GetDefaultFolder(9)
        except:
            self.calendar = None
            
        self.namespace = self.outlook.GetNamespace("MAPI")
        self.calendar = self.namespace.GetDefaultFolder(9)

        # ── Barre Réunion Outlook ──
        self.next_meeting = None
        self.meeting_timer = QTimer(self)
        self.meeting_timer.timeout.connect(self.update_meeting)
        self.meeting_timer.start(300000)  # 5 minutes
        self.update_meeting()
        
        self.meeting_bar = UnifiedBarWidget(
            minv=0,
            maxv=24,
            mode='value',
            label_format='hhmm'
        )
        self.meeting_bar.mode = "meeting"
        self.meeting_bar.set_start_fraction(0.33)
        self.meeting_titre_lbl = QLabel("Prochaine réunion Outlook")
        self.meeting_titre_lbl.setAlignment(Qt.AlignCenter)
        
        meeting_col = QVBoxLayout()
        meeting_col.addWidget(self.meeting_titre_lbl)
        meeting_col.addWidget(self.meeting_bar)
        
        layout.addLayout(meeting_col)


        # ── Panneau texte unique en bas ──
        self.texte_vie    = QLabel("")
        self.texte_jour   = QLabel("")
        self.texte_action = QLabel("")
        
        self.texte_meeting = QLabel("")
        self.texte_meeting.setWordWrap(True)

        for lbl in [self.texte_vie, self.texte_jour, self.texte_action]:
            lbl.setWordWrap(True)

        texte_panel = QFrame()
        texte_panel.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        texte_layout = QVBoxLayout(texte_panel)
        texte_layout.setContentsMargins(8, 6, 8, 6)
        texte_layout.setSpacing(4)
        texte_layout.addWidget(self.texte_vie)
        texte_layout.addWidget(self.texte_jour)
        texte_layout.addWidget(self.texte_action)
        texte_layout.addWidget(self.texte_meeting)
        layout.addWidget(texte_panel)

        # ── Init ──
        self.vie_bar.set_value(56)
        self.update_jour()
        self.resize(800, 460)

        timer = QTimer(self)
        timer.timeout.connect(self.update_jour)
        timer.start(1000)

        self.load_bar_config()

    def update_meeting(self):
        subject, start, end = self.get_next_outlook_meeting()
        self.next_meeting = (subject, start, end)
        print("Recherche réunion :", datetime.datetime.now())

    # ── Construction d'une ligne barre seule ──
    def _make_bar_row(self, titre, bar_widget):
        row = QVBoxLayout()
        lbl = QLabel(titre)
        lbl.setAlignment(Qt.AlignCenter)
        row.addWidget(lbl)
        row.addWidget(bar_widget)
        return row

    # ── Mise à jour périodique ──

    def update_jour(self):
        now  = datetime.datetime.now()
        hour = now.hour + now.minute / 60.0
        self.jour_bar.set_value(hour)

        # âge réel en années fractionnaires depuis la date de naissance
        age = self._age_today(self.vie_date_naissance)
        self.vie_bar.set_value(age)

        vie_text    = self.vie_dict.get(self.vie_bar.phrase,       "Pas de texte vie")
        jour_text   = self.jour_dict.get(self.jour_bar.phrase,     "Pas de texte journée")
        action_text = self.action_dict.get(self.action_bar.phrase, "Pas de texte action")

        self.texte_vie.setText(vie_text)
        self.texte_jour.setText(jour_text)
        self.texte_action.setText(action_text)
        
        subject, start, end = self.next_meeting
        
        subject, start, end = self.next_meeting
        
        now = datetime.datetime.now()
        
        if start:
        
            delta_start = (start - now).total_seconds()
            delta_end = (end - now).total_seconds()
        
            if delta_start > 0:
                # réunion pas encore commencée
                minutes = int(delta_start // 60)
                seconds = int(delta_start % 60)
        
                self.meeting_bar.set_value(0)
                self.meeting_bar.countdown_text = f"{minutes:02d}:{seconds:02d}"
        
            elif delta_end > 0:
                # réunion en cours
                total = (end - start).total_seconds()
                elapsed = total - delta_end
        
                progress = elapsed / total * 24
                self.meeting_bar.set_value(progress)
        
                self.meeting_bar.countdown_text = "En réunion"
        
            else:
                self.meeting_bar.set_value(0)
                self.meeting_bar.countdown_text = "Réunion terminée"
        
            txt = f"📅 {subject} — {start.strftime('%H:%M')} → {end.strftime('%H:%M')}"
        
        else:
            txt = "Aucune réunion prévue"
            self.meeting_bar.countdown_text = ""
        
        self.texte_meeting.setText(txt)
        self.meeting_bar.update()
        
        self.texte_meeting.setText(txt)

    # ── Titre dynamique barre vie ──

    def _vie_titre(self):
        duree = self._years_between(self.vie_date_naissance, self.vie_date_fin)
        return (f"Vie  {self.vie_date_naissance.toString('dd/MM/yyyy')}"
                f" → {self.vie_date_fin.toString('dd/MM/yyyy')}"
                f"  ({duree:.1f} ans)")

    def _choisir_dates_vie(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Dates de vie")
        dlg.setMinimumWidth(320)
        form = QVBoxLayout(dlg)

        form.addWidget(QLabel("Date de naissance :"))
        edit_naiss = QDateEdit(self.vie_date_naissance)
        edit_naiss.setCalendarPopup(True)
        edit_naiss.setDisplayFormat("dd/MM/yyyy")
        form.addWidget(edit_naiss)

        form.addWidget(QLabel("Date de fin :"))
        edit_fin = QDateEdit(self.vie_date_fin)
        edit_fin.setCalendarPopup(True)
        edit_fin.setDisplayFormat("dd/MM/yyyy")
        form.addWidget(edit_fin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            self.vie_date_naissance = edit_naiss.date()
            self.vie_date_fin       = edit_fin.date()
            # recalculer les bornes
            maxv = self._years_between(self.vie_date_naissance, self.vie_date_fin)
            self.vie_bar.minv = 0.0
            self.vie_bar.maxv = maxv
            # mettre à jour le titre
            self.vie_titre_lbl.setText(self._vie_titre())
            self.update_jour()

    # ── Titre dynamique barre journée ──

    def _jour_titre(self):
        def fmt(t):
            return f"{t.hour()}h{t.minute():02d}" if t.minute() else f"{t.hour()}h"
        debut = fmt(self.jour_heure_debut)
        # heure de fin : minuit affiché 24h
        fin_h = self.jour_bar.maxv
        fin_str = "24h" if fin_h == 24.0 else f"{int(fin_h)}h{int(round((fin_h % 1)*60)):02d}"
        duree = self.jour_bar.maxv - self.jour_bar.minv
        return f"Journée  {debut} → {fin_str}  ({duree:.1f} h)"

    def _choisir_heures_jour(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Heures de la journée")
        dlg.setMinimumWidth(260)
        form = QVBoxLayout(dlg)

        form.addWidget(QLabel("Heure de début :"))
        edit_debut = QTimeEdit(self.jour_heure_debut)
        edit_debut.setDisplayFormat("HH:mm")
        form.addWidget(edit_debut)

        form.addWidget(QLabel("Heure de fin (max 24h) :"))
        # QTimeEdit ne gère pas 24h nativement — on utilise un QTimeEdit limité à 23:59
        # et on traite 00:00 comme 24h
        fin_qtime = QTime(0, 0) if self.jour_bar.maxv >= 24.0 \
                    else QTime(int(self.jour_bar.maxv),
                               int(round((self.jour_bar.maxv % 1) * 60)))
        edit_fin = QTimeEdit(fin_qtime)
        edit_fin.setDisplayFormat("HH:mm")
        note = QLabel("(00:00 = minuit / 24h)")
        note.setStyleSheet("color: gray; font-size: 10px;")
        form.addWidget(edit_fin)
        form.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            self.jour_heure_debut = edit_debut.time()
            minv = self._heure_to_float(self.jour_heure_debut)
            fin_t = edit_fin.time()
            maxv  = 24.0 if (fin_t.hour() == 0 and fin_t.minute() == 0) \
                         else self._heure_to_float(fin_t)
            # s'assurer que fin > début
            if maxv <= minv:
                maxv = minv + 1.0
            self.jour_bar.minv = minv
            self.jour_bar.maxv = maxv
            self.jour_titre_lbl.setText(self._jour_titre())
            self.update_jour()

    # ── Titre dynamique barre action ──

    def _action_titre(self):
        minutes = self.action_bar.duration // 60
        return f"Action  ({minutes} min)"

    def _choisir_duree_action(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Durée de l'action")
        dlg.setMinimumWidth(220)
        form = QVBoxLayout(dlg)

        form.addWidget(QLabel("Durée (minutes) :"))
        spin = QSpinBox()
        spin.setMinimum(1)
        spin.setMaximum(480)
        spin.setValue(self.action_bar.duration // 60)
        spin.setSuffix(" min")
        form.addWidget(spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            minutes = spin.value()
            self.action_bar.duration = minutes * 60
            # remettre à zéro si le timer tourne
            self.action_bar.stop()
            self.action_titre_lbl.setText(self._action_titre())

    # ── XML ──

    def load_xml(self, filename):
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
        except Exception:
            return

        def _load_section(tag, target_dict):
            section = root.find(tag)
            if section is not None:
                for p in section.findall("phrase"):
                    key  = p.get("key")
                    text = (p.text or "").strip()
                    target_dict[key] = text

        _load_section("vie",    self.vie_dict)
        _load_section("jour",   self.jour_dict)
        _load_section("action", self.action_dict)

    # ── Config barres ──

    def load_bar_config(self):
        try:
            tree = ET.parse("config_barres.xml")
            root = tree.getroot()
            for tag, bar in [("vie", self.vie_bar),
                              ("jour", self.jour_bar),
                              ("action", self.action_bar)]:
                el = root.find(tag)
                if el is not None:
                    bar.fd_fraction = float(el.get("fd", bar.fd_fraction))
                    bar.df_fraction = float(el.get("df", bar.df_fraction))
            # dates de vie
            vie_el = root.find("vie")
            if vie_el is not None:
                naiss_str = vie_el.get("naissance", "")
                fin_str   = vie_el.get("fin", "")
                if naiss_str:
                    self.vie_date_naissance = QDate.fromString(naiss_str, "yyyy-MM-dd")
                if fin_str:
                    self.vie_date_fin = QDate.fromString(fin_str, "yyyy-MM-dd")
                # recalculer bornes et titre
                maxv = self._years_between(self.vie_date_naissance, self.vie_date_fin)
                self.vie_bar.minv = 0.0
                self.vie_bar.maxv = maxv
                self.vie_titre_lbl.setText(self._vie_titre())
            # heures de journée
            jour_el = root.find("jour")
            if jour_el is not None:
                debut_str = jour_el.get("debut", "")
                fin_str2  = jour_el.get("fin",   "")
                if debut_str:
                    self.jour_heure_debut = QTime.fromString(debut_str, "HH:mm")
                    self.jour_bar.minv = self._heure_to_float(self.jour_heure_debut)
                if fin_str2:
                    fin_t = QTime.fromString(fin_str2, "HH:mm")
                    self.jour_bar.maxv = 24.0 if (fin_t.hour() == 0 and fin_t.minute() == 0) \
                                              else self._heure_to_float(fin_t)
                self.jour_titre_lbl.setText(self._jour_titre())
            # durée action
            action_el = root.find("action")
            if action_el is not None:
                duree_str = action_el.get("duree_minutes", "")
                if duree_str:
                    self.action_bar.duration = int(duree_str) * 60
                    self.action_titre_lbl.setText(self._action_titre())
        except Exception:
            pass

    def save_bar_config(self):
        root = ET.Element("config")
        for tag, bar in [("vie", self.vie_bar),
                         ("jour", self.jour_bar),
                         ("action", self.action_bar)]:
            el = ET.SubElement(root, tag)
            el.set("fd", str(bar.fd_fraction))
            el.set("df", str(bar.df_fraction))
        # dates de vie
        vie_el = root.find("vie")
        vie_el.set("naissance", self.vie_date_naissance.toString("yyyy-MM-dd"))
        vie_el.set("fin",       self.vie_date_fin.toString("yyyy-MM-dd"))
        # heures de journée
        jour_el = root.find("jour")
        jour_el.set("debut", self.jour_heure_debut.toString("HH:mm"))
        fin_h = self.jour_bar.maxv
        fin_qtime = QTime(0, 0) if fin_h >= 24.0 \
                    else QTime(int(fin_h), int(round((fin_h % 1) * 60)))
        jour_el.set("fin", fin_qtime.toString("HH:mm"))
        # durée action
        action_el = root.find("action")
        action_el.set("duree_minutes", str(self.action_bar.duration // 60))
        ET.ElementTree(root).write("config_barres.xml")

    def closeEvent(self, event):
        self.save_bar_config()
        event.accept()

    # ── Mise au premier plan ──

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        flags = self.windowFlags()
        self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(500, lambda: (self.setWindowFlags(flags), self.show()))

    def get_next_outlook_meeting(self):
    
        if not self.calendar:
            return None, None, None
    
        try:
            now = datetime.datetime.now()
    
            items = self.calendar.Items
            items.IncludeRecurrences = True
            items.Sort("[Start]")
    
            appt = items.GetFirst()
    
            next_meeting = None
    
            while appt:
    
                start = appt.Start.replace(tzinfo=None)
                end = appt.End.replace(tzinfo=None)
    
                # 1️⃣ réunion en cours
                if start <= now <= end:
                    return appt.Subject, start, end
    
                # 2️⃣ prochaine réunion
                if start > now and next_meeting is None:
                    next_meeting = (appt.Subject, start, end)
    
                appt = items.GetNext()
    
            return next_meeting
    
        except Exception as e:
            print("Erreur Outlook:", e)
    
        return None, None, None
# ─────────────────────────────────────────────
#  Lancement
# ─────────────────────────────────────────────

app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec_())