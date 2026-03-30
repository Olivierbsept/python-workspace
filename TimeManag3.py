#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 22:59:24 2026
@author: olivierbessettemac

Gestion du temps — version fusionnée (BarWidget + ActionBarWidget → UnifiedBarWidget)
"""

import sys
import datetime
import xml.etree.ElementTree as ET
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton,
                             QDateEdit, QTimeEdit, QSpinBox, QDialog, QDialogButtonBox, QCalendarWidget)
from PyQt5.QtCore import QTimer, Qt, QDate, QTime
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5 import QtMultimedia
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPolygon


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
    def __init__(self, minv=0, maxv=1,
                 mode='value',
                 duration=3600,
                 red_duration=RED_DURATION,
                 blink_duration=BLINK_INTERVAL,
                 fd_fraction=0.33,
                 df_fraction=0.66,
                 label_format='fraction',
                 show_triangle=True):

        super().__init__()

        # ── Paramètres ──
        self.mode = mode
        self.minv = minv
        self.maxv = maxv
        self.duration = duration
        self.red_duration = red_duration
        self.blink_duration = blink_duration
        self.label_format = label_format

        self.fd_fraction = fd_fraction
        self.df_fraction = df_fraction

        # ── Triangles ──
        self.triangle_fraction = 0.5
        self.triangle_clicked = False
        self.triangle_moved = False
        self.triangle_press_x = 0
        self.triangle_black_value = None
        self.triangle_reference_value = None
        self.triangle_red_value = None
        self.show_triangle = (show_triangle and self.mode == 'value')
        self.show_second_triangle = False

        # ── État barre ──
        self.value = minv
        self.elapsed = 0
        self.running = False
        self.paused = False
        self.target_value = None

        self.phrase = ""
        self.last_phrase = ""

        # ── Visuel ──
        self.red = False
        self.blink = False
        self.visible = True

        self.drag_fd = False
        self.drag_df = False
        self.drag_triangle = False

        # ── Timers Qt ──
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
        if not (self.running and not self.paused):
            return
    
        if self.target_value is not None:
            # calcul du delta vers target_value
            delta = self.target_value - self.value
    
            # incrémenter value progressivement (ajustable selon granularité)
            step = delta / 60  # ici 1/60ème du chemin vers la cible par tick
            self.value += step
    
            # arrêter exactement à target_value
            if abs(self.value - self.target_value) < 0.01:
                self.value = self.target_value
                self.stop()
    
        else:
            # comportement normal timer si pas de target_value
            self.elapsed += 1
            if self.duration > 0:
                #self.value = self.elapsed / 60.0
                self.value = self.minv + (self.elapsed / self.duration) * (self.maxv - self.minv)
    
        # mise à jour phrase et clignotement
        self._update_phrase(self.value, self.minv, self.maxv)
        #secs = self._seconds_to_next_change(minutes, 0, max_minutes, unit='seconds')
        #self._refresh_blink(secs)
        self.update()

    def _update_phrase(self, value, minv, maxv):
        new_phrase = value_to_phrase(value, minv, maxv,
                                     self.fd_fraction, self.df_fraction)
        if new_phrase != self.last_phrase:
            if self.last_phrase:
                #try:
                #   QtMultimedia.QSound.play("/System/Library/Sounds/Glass.aiff")
                #except Exception:
                #    pass
                # arrêter le blink : on vient de franchir la frontière
                self.stop_blink()
                # passer en rouge pour red_duration secondes
                self.red = True
                QTimer.singleShot(self.red_duration * 1000, self._stop_red)
            self.last_phrase = new_phrase
        self.phrase = new_phrase
        #print(value, minv, maxv)

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
        Temps (secondes) avant le prochain changement de phrase.
        Compatible avec compute_x012().
        """
    
        current_phrase = value_to_phrase(value, minv, maxv,
                                         self.fd_fraction, self.df_fraction)
        low = value
        high = maxv
    
        # recherche grossière
        step = (maxv - minv) / 200
        v = value
    
        while v <= maxv:
            v += step
            p = value_to_phrase(v, minv, maxv,
                                self.fd_fraction, self.df_fraction)
            if p != current_phrase:
                high = v
                break
    
        # recherche dichotomique précise
        for _ in range(20):
            mid = (low + high) / 2
            p = value_to_phrase(mid, minv, maxv,
                                self.fd_fraction, self.df_fraction)
    
            if p == current_phrase:
                low = mid
            else:
                high = mid
    
        delta = high - value
    
        if unit == "seconds":
            return delta * 60
        else:
            return delta * 3600

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
        painter = QPainter(self)
        width   = self.width()

        m1 = int(width * self.fd_fraction)
        m2 = int(width * self.df_fraction)

        # ── fond ──
        if self.mode == 'timer':
            # zones colorées FD / milieu / DF
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
                pos = int(self.elapsed / self.duration * width)
                painter.setBrush(QColor(50, 120, 220))
                painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)
        else:
            if self.maxv != self.minv:
                pos = int((self.value - self.minv) / (self.maxv - self.minv) * width)
            else:
                pos = 0
            painter.setBrush(QColor(50, 120, 220))
            painter.drawRect(0, TEXT_MARGIN, pos, BAR_HEIGHT)

        # ── étiquettes FD / DF ──
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 10))
        fm = painter.fontMetrics()

        lbl_fd, lbl_df = self._fd_df_labels()

        # étiquette gauche (FD) centrée sur m1, étiquette droite (DF) centrée sur m2
        tw_fd = fm.horizontalAdvance(lbl_fd)
        tw_df = fm.horizontalAdvance(lbl_df)
        painter.drawText(max(0, m1 - tw_fd // 2), TEXT_MARGIN - 5, lbl_fd)
        painter.drawText(max(0, m2 - tw_df // 2), TEXT_MARGIN - 5, lbl_df)

        # ── phrase ──
        if self.visible or self.red:
            painter.setPen(QColor(220, 0, 0) if self.red else QColor(0, 0, 0))
            painter.drawText(5, TEXT_MARGIN + BAR_HEIGHT + 15, self.phrase)

        # ── traits verticaux FD / DF ──
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(m1, TEXT_MARGIN, m1, TEXT_MARGIN + BAR_HEIGHT)
        painter.drawLine(m2, TEXT_MARGIN, m2, TEXT_MARGIN + BAR_HEIGHT)
        
        # ── triangle au-dessus du centre ──
        center_x = int(self.triangle_fraction * width)
        top_y = TEXT_MARGIN - 10   # position verticale au-dessus de la barre
        size = 10                  # taille du triangle
        
        # Triangle (pointe vers le bas)
        if self.show_triangle:
            center_x = int(self.triangle_fraction * width)
            top_y = TEXT_MARGIN - 15
            size = 10
        
            # ── triangle principal (NOIR) ──
            pen = QPen(QColor(0, 0, 0))
            pen.setWidth(2)
            painter.setPen(pen)
        
            if self.triangle_clicked:
                painter.setBrush(QColor(0, 0, 0))  # noir
            else:
                painter.setBrush(Qt.NoBrush)
        
            painter.drawPolygon(
                QPoint(center_x, top_y + size),
                QPoint(center_x - size, top_y),
                QPoint(center_x + size, top_y)
            )
        
            # ── "1" au-dessus du triangle principal (TOUJOURS visible) ──
            font = QFont("Arial")
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 0))
            
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance("1")
            
            painter.drawText(center_x - text_width // 2, top_y + 3, "1")
            
            # ── deuxième triangle (+1h) ──
        if self.show_second_triangle and self.triangle_reference_value is not None:
        
            value_plus_1h = self.triangle_reference_value + 1.0
        
            if self.maxv != self.minv:
                ratio = (value_plus_1h - self.minv) / (self.maxv - self.minv)
                x2 = int(ratio * width)
            else:
                x2 = center_x
        
            # triangle rouge
            pen = QPen(QColor(200, 0, 0))
            #pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(QColor(200, 0, 0))
        
            painter.drawPolygon(
                QPoint(x2, top_y + size),
                QPoint(x2 - size, top_y),
                QPoint(x2 + size, top_y)
            )
        
            # ── "1" au-dessus du triangle rouge ──
            #painter.setFont(QFont("Arial", 10))
            painter.setPen(QColor(200, 0, 0))
            painter.drawText(x2 - 4, top_y - 2, "1")
            
            # ── heure correspondant à la position du triangle ──
            
            if self.label_format == 'hhmm':
                # position du triangle (normalisée)
                if self.maxv != self.minv:
                    ratio = center_x / width
                    value_at_pos = self.minv + ratio * (self.maxv - self.minv)
                else:
                    value_at_pos = self.value
            
                # conversion en hh:mm
                h = int(value_at_pos)
                m = int((value_at_pos - h) * 60)
            
                if m == 60:
                    h += 1
                    m = 0
            
                time_str = f"{h:02d}:{m:02d}"
            
                # position texte
                text_x = center_x + size + 5
                text_y = top_y + size + 5
            
                color = QColor(220, 0, 0) if self.red else QColor(0, 0, 0)
                painter.setPen(color)
                #painter.setFont(QFont("Arial", 10))
            
                painter.drawText(text_x, text_y, time_str)

    def _fd_df_labels(self):
        """Retourne (label_FD, label_DF) selon label_format."""
        fmt = self.label_format

        if fmt == 'years':
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
            return f"{val_fd:.1f} ans", f"{val_df:.1f} ans"

        elif fmt == 'hhmm':
            def to_hhmm(v):
                h  = int(v)
                m  = int(round((v - h) * 60))
                if m == 60:
                    h += 1; m = 0
                return f"{h}h{m:02d}"
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
            return to_hhmm(val_fd), to_hhmm(val_df)

        elif fmt == 'timer' or self.mode == 'timer':
            # étiquette gauche : durée FD en minutes depuis le début
            # étiquette droite : durée restante DF en minutes avant la fin
            minutes_fd = int(self.duration * self.fd_fraction / 60)
            minutes_df = int(self.duration * (1 - self.df_fraction) / 60)
            return f"{minutes_fd} min", f"{minutes_df} min"

        else:  # 'fraction' ou autre
            val_fd = self.minv + self.fd_fraction * (self.maxv - self.minv)
            val_df = self.minv + self.df_fraction * (self.maxv - self.minv)
            return f"{val_fd:.2f}", f"{val_df:.2f}"

    # ── Souris ───────────────────────────────

    def mousePressEvent(self, event):
        width = self.width()
        m1    = int(width * self.fd_fraction)
        m2    = int(width * self.df_fraction)
        if abs(event.x() - m1) < 10:
            self.drag_fd = True
        elif abs(event.x() - m2) < 10:
            self.drag_df = True
            
        # détection clic sur triangle
        triangle_x = int(self.triangle_fraction * self.width())
        
        if abs(event.x() - triangle_x) < 10:
            self.drag_triangle = True
            
        if self.show_triangle:
            triangle_x = int(self.triangle_fraction * self.width())
            if abs(event.x() - triangle_x) < 10:
                self.drag_triangle = True
                self.triangle_moved = False
                self.triangle_press_x = event.x()  # mémorise position initiale
                
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
        #
        main_widget = self.parent().parent()
        action_prog_bar = getattr(main_widget, "action_prog_bar", None)
        if self.drag_fd or self.drag_df:
            main_widget = self.parent().parent()
            action_prog_bar = getattr(main_widget, "action_prog_bar", None)
            if action_prog_bar:
                # On met à jour uniquement l'affichage de la fraction (peinture + labels)
                self.update()  # ça suffit pour que FD/DF se déplacent et que les heures s'affichent correctement
        #        
        if self.drag_triangle:
            dx = abs(event.x() - self.triangle_press_x)
        
            if dx > 5:  # ← seuil anti micro-mouvement
                self.triangle_moved = True
        
            x = event.x() / self.width()
            self.triangle_fraction = max(0.0, min(1.0, x))
        
            if self.triangle_moved:
                self.triangle_clicked = False  # déplacement → évidé
        
            self.update()

    def mouseReleaseEvent(self, event):
        print("NEW start =", self.minv)
        print("NEW end   =", self.maxv)
    
        self.drag_fd = False
        self.drag_df = False
        
        parent_widget = self.parent()
        main_widget = self.parent().parent()
        action_prog_bar = getattr(main_widget, "action_prog_bar", None)

        if action_prog_bar:
            action_prog_bar._update_phrase(
                action_prog_bar.value,
                action_prog_bar.minv,
                action_prog_bar.maxv
            )
            action_prog_bar.update()
            #    
        if self.drag_triangle:
            value_at_triangle = self.minv + self.triangle_fraction * (self.maxv - self.minv)
            # ==============================
            # 🖱️ CAS 1 : CLICK (pas bougé)
            # ==============================
            if not self.triangle_moved:
                self.triangle_clicked = True
                self.triangle_reference_value = value_at_triangle
    
                # Initialisation du premier triangle
                if not hasattr(self, 'triangle_black_value') or self.triangle_black_value is None:
                    self.triangle_black_value = value_at_triangle
                    self.triangle_red_value = value_at_triangle + 1
                    self.show_second_triangle = True
    
                print("CLICK ONLY → aucune modification de la barre")
    
            # ==============================
            # 🖱️ CAS 2 : DRAG (déplacé)
            # ==============================
            else:
                self.triangle_clicked = False
    
                # Mise à jour des valeurs
                if hasattr(self, 'triangle_black_value'):
                    self.triangle_black_value = value_at_triangle
                    self.triangle_red_value = self.triangle_black_value + 1
    
                start = self.triangle_black_value
                end   = self.triangle_red_value
    
                print(f"DRAG → start={start}, end={end}")
    
                # Mise à jour de la barre UNIQUEMENT ici
                if action_prog_bar:
                    action_prog_bar.minv = start
                    action_prog_bar.maxv = end

                    # recalage immédiat de la value
                    now = datetime.datetime.now()
                    current_hour = now.hour + now.minute / 60 + now.second / 3600
                    action_prog_bar.value = current_hour
    
                    if end > start:
                        if current_hour < start:
                            action_prog_bar.elapsed = 0
                            remaining_seconds = int((start - current_hour) * 3600)
    
                        elif start <= current_hour <= end:
                            ratio = (current_hour - start) / (end - start)
                            ratio = max(0.0, min(1.0, ratio))
                            action_prog_bar.elapsed = ratio * action_prog_bar.duration
                            remaining_seconds = int((end - current_hour) * 3600)
    
                        else:
                            action_prog_bar.elapsed = action_prog_bar.duration
                            remaining_seconds = 0
    
                    now = datetime.datetime.now()
                    current_hour = now.hour + now.minute / 60 + now.second / 3600    
                    action_prog_bar.value = current_hour
                    
                    action_prog_bar._update_phrase(
                        action_prog_bar.value,
                        action_prog_bar.minv,
                        action_prog_bar.maxv
                    )
                    
                    action_prog_bar.running = True
                    action_prog_bar.show()
                    action_prog_bar.raise_()
                    action_prog_bar.update()
                    action_prog_bar.start()                    
                    #
                    print(f"Barre mise à jour → elapsed={action_prog_bar.elapsed}")
    
            # ==============================
            # ⏱️ MAJ COUNTDOWN (toujours ok)
            # ==============================
            if parent_widget and hasattr(parent_widget, 'countdown_lbl'):
                secs = self._seconds_to_next_change(
                    value_at_triangle,
                    self.minv,
                    self.maxv,
                    unit='hours'
                )
                parent_widget.countdown_lbl.setText(
                    parent_widget.seconds_to_text(secs)
                )
    
        # reset état
        self.drag_triangle = False
        self.triangle_moved = False
    
        self.update()

#
class JourCompactWidget(QWidget):
    def __init__(self, bar_widget, stack=None, kind="jour",
                 vie_dict=None, jour_dict=None, action_dict=None, action_prog_dict=None,
                 controls_mode="full"):
        super().__init__()
        self.controls_mode = controls_mode  # "full" ou "pause_only"
        self.bar = bar_widget
        self.stack = stack
        self.kind = kind

        # stocker les dictionnaires
        self.vie_dict = vie_dict or {}
        self.jour_dict = jour_dict or {}
        self.action_dict = action_dict or {}
        self.action_prog_dict = action_prog_dict or {}

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)
        self.line_layout = QHBoxLayout()

        # ── Labels ──
        self.title_lbl = QLabel("")
        self.symbol_lbl = QLabel("")
        self.countdown_lbl = QLabel("")
        self.symbol_lbl.setStyleSheet("font-size:16px;")
        
        self.symbol_text_lbl = QLabel("")
        self.symbol_text_lbl.setWordWrap(True)
        self.symbol_text_lbl.setStyleSheet("color: darkblue; font-size:12px;")
        self.symbol_text_lbl.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.symbol_text_lbl)

        # ── Boutons haut/bas/plus ──
        self.up_btn = QPushButton("⇧")
        self.down_btn = QPushButton("⇩")
        self.plus_btn = QPushButton("+")
        for b in [self.up_btn, self.down_btn, self.plus_btn]:
            b.setFixedSize(30, 30)

        if stack is None:
            self.up_btn.hide()
            self.down_btn.hide()

        # ── Icône de la barre ──
        self.icon_btn = QPushButton()
        self.icon_btn.setFixedSize(32, 32)
        self.icon_btn.setStyleSheet("border:none;font-size:18px")
        if self.kind == "vie":
            self.icon_btn.setText("📅")
            self.icon_btn.clicked.connect(self.show_calendar)
        elif self.kind == "jour":
            self.icon_btn.setText("🗓")
            self.icon_btn.clicked.connect(self.show_day_picker)
        elif self.kind == "action":
            self.icon_btn.setText("⏱")
            self.icon_btn.clicked.connect(self.show_bar)

        # ── Barre outils ──
        self.tools_layout = QHBoxLayout()
        self.cal_btn = QPushButton("📅")
        self.day_btn = QPushButton("🗓")
        self.chrono_btn = QPushButton("⏱")
        for b in [self.cal_btn, self.day_btn, self.chrono_btn]:
            b.setFixedSize(32, 32)
            b.setStyleSheet("border:none;font-size:18px")
            self.tools_layout.addWidget(b)
        self.tools_layout.addStretch()
        self.tools_widget = QWidget()
        self.tools_widget.setLayout(self.tools_layout)
        self.tools_widget.hide()
        self.main_layout.addWidget(self.tools_widget)

        # ── Connexions ──
        self.up_btn.clicked.connect(self.go_up)
        self.down_btn.clicked.connect(self.go_down)

        # **Connexion corrigée du bouton '+'**
        self.plus_btn.clicked.connect(self.on_plus_clicked)

        self.cal_btn.clicked.connect(self.show_calendar)
        self.day_btn.clicked.connect(self.show_day_picker)
        self.chrono_btn.clicked.connect(self.show_bar)

        # ── Boutons action (timer) ──
        self.start_btn = QPushButton("▶")
        self.pause_btn = QPushButton("⏸")
        self.stop_btn = QPushButton("■")
        for b in [self.start_btn, self.pause_btn, self.stop_btn]:
            b.setFixedSize(22, 22)
            b.setStyleSheet("border:none;font-size:14px")
        if self.bar.mode == "timer":
            self.start_btn.clicked.connect(self.bar.start)
            self.pause_btn.clicked.connect(self.bar.pause)
            self.stop_btn.clicked.connect(self.bar.stop)
        #

        # ── Layout principal ──
        self.line_layout.addWidget(self.title_lbl)
        self.line_layout.addWidget(self.icon_btn)
        self.line_layout.addWidget(self.symbol_lbl)
        self.line_layout.addWidget(self.countdown_lbl)
        self.line_layout.addStretch()

        self.xml_text_lbl = QLabel("")
        self.xml_text_lbl.setWordWrap(True)
        self.xml_text_lbl.setStyleSheet("color: #555555; font-size:12px;")  # gris discret
        self.xml_text_lbl.setAlignment(Qt.AlignCenter)  # centré sous la barre

        if self.bar.mode == "timer":
            # affichage selon le mode
            if self.controls_mode == "full":
                self.line_layout.addWidget(self.start_btn)
                self.line_layout.addWidget(self.pause_btn)
                self.line_layout.addWidget(self.stop_btn)
        
            elif self.controls_mode == "pause_only":
                self.line_layout.addWidget(self.pause_btn)
            elif self.controls_mode =="none":
                pass

        self.line_layout.addWidget(self.up_btn)
        self.line_layout.addWidget(self.down_btn)
        self.line_layout.addWidget(self.plus_btn)
        self.main_layout.addLayout(self.line_layout)

        # ── Timer interne ──
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(500)
        self.update_display()
        
        self.main_layout.addWidget(self.bar)
        # Phrase XML toujours sous la barre
        self.main_layout.addWidget(self.xml_text_lbl)

    # ── Méthode corrigée pour le bouton '+' ──
    def on_plus_clicked(self):
        """
        Affiche la barre si cachée et déclenche l'action programmée.
        """
        if self.main_layout.indexOf(self.bar) == -1:
            self.main_layout.addWidget(self.bar)
            self.bar.show()
            self.symbol_text_lbl.show()

        # Appel sécurisé de la méthode de la barre
        #self.bar.add_action_programmee_clicked()

    # ── Fonctions pour barre, calendrier, chrono ──
    def show_bar(self):
        """Afficher la popup durée pour kind='action'"""
        if self.kind != "action":
            # comportement par défaut (affiche la barre)
            if self.main_layout.indexOf(self.bar) == -1:
                self.main_layout.addWidget(self.bar)
            self.bar.show()
            return
    
        # référence à la fenêtre principale pour récupérer la méthode de durée action
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, "_choisir_duree_action"):
            parent_window = parent_window.parent()
    
        if parent_window:
            parent_window._choisir_duree_action()

    def show_calendar(self):
        """Afficher la popup date de naissance / date de fin si kind='vie'"""
        if self.kind != "vie":
            # comportement par défaut pour autre type
            cal = QCalendarWidget()
            cal.setWindowTitle("Choisir une date")
            cal.show()
            return
    
        # référence à la fenêtre principale pour récupérer dates de vie
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, "_choisir_dates_vie"):
            parent_window = parent_window.parent()
    
        if parent_window:
            parent_window._choisir_dates_vie()

    def show_day_picker(self):
        """Afficher la popup heure de début / heure de fin si kind='jour'"""
        if self.kind != "jour":
            # comportement par défaut pour autre type
            d = QDateEdit()
            d.setCalendarPopup(True)
            d.show()
            return
    
        # référence à la fenêtre principale pour récupérer les heures de journée
        parent_window = self.parent()
        while parent_window and not hasattr(parent_window, "_choisir_heures_jour"):
            parent_window = parent_window.parent()
    
        if parent_window:
            parent_window._choisir_heures_jour()

    # ── Affichage secondes → texte ──
    def seconds_to_life_text(self, seconds):
        # self.bar.value est en années fractionnaires
        # Convertir secondes en fraction d'année
        hours_per_year = 365.25 * 24
    
        # fraction d'année
        years_fraction = seconds / 3600 / hours_per_year
    
        years = int(years_fraction)
        hours = int((years_fraction - years) * hours_per_year)
        days = int (hours/24)
        #print(f"[DEBUG] years_fraction={years_fraction}, years={years}, hours={hours, seconds=}")  # debug
        if years == 0:
            return f"{days} jour(s)"
        if years == 1:
            return f"{years} an {days} jours"
        return f"{years} ans {days} jours"
    
    def seconds_to_text(self, s):
        s = int(s)
        if s < 60:
            return f"{s}s"
        m = s // 60
        s = s % 60
        return f"{m}:{s:02d}"

    # ── Affichage barre outils ──
    def toggle_mode(self):
        """Afficher ou cacher uniquement la barre principale et le texte associé."""
    
        if self.bar.isVisible():
            # cacher
            self.bar.hide()
            self.symbol_text_lbl.hide()
            self.plus_btn.setText("+")
        else:
            # montrer
            self.bar.show()
            self.symbol_text_lbl.show()
            self.plus_btn.setText("−")
    
        # Ajuste la fenêtre
        parent = self.parent()
        while parent and not hasattr(parent, "ajuster_fenetre"):
            parent = parent.parent()
        if parent:
            parent.ajuster_fenetre()
        # forcer le recalcul de la taille de la fenêtre
        self.adjustSize()
        w = self.window()
        if w:
            w.adjustSize()

    # ── Navigation stack ──
    def go_up(self):
        if self.stack:
            i = self.stack.currentIndex()
            self.stack.setCurrentIndex(max(0, i-1))

    def go_down(self):
        if self.stack:
            i = self.stack.currentIndex()
            self.stack.setCurrentIndex(min(self.stack.count()-1, i+1))

    # ── Mise à jour périodique ──
    def update_display(self):
        now = datetime.datetime.now()
    
        # ── mise à jour valeur barre ──
        if self.kind == "jour":
            hour = now.hour + now.minute / 60 + now.second / 3600
            self.bar.set_value(hour)
    
        # ── titre ──
        if self.kind == "vie":
            self.title_lbl.setText(f"❤️ {now.year}")
        elif self.kind == "jour":
            self.title_lbl.setText("☀️" + now.strftime("%d %b"))
        elif self.kind == "action":
            self.title_lbl.setText("⚡")
        elif self.kind == "action_prog":
            self.title_lbl.setText("⚡1")

    
        # ── phrase → symboles ──
        phrase = getattr(self.bar, "phrase", "")
        symbols = self.phrase_to_symbols(phrase)
    
        if getattr(self.bar, "blink", False) and not self.bar.visible:
            symbols = ""
    
        self.symbol_lbl.setStyleSheet(
            f"color:{'red' if getattr(self.bar, 'red', False) else 'black'}; font-size:16px"
        )
        self.symbol_lbl.setText(symbols)
    
        # Texte XML correspondant à la phrase
        if self.kind == "vie":
            text_xml = self.vie_dict.get(phrase, "")
        elif self.kind == "jour":
            text_xml = self.jour_dict.get(phrase, "")
        elif self.kind == "action":
            text_xml = self.action_dict.get(phrase, "")
        elif self.kind == "action_prog":
            text_xml = self.action_prog_dict.get(phrase, "")

    
        # Mettre à jour le label dédié sous la barre
        self.xml_text_lbl.setText(text_xml)

        # Affichage texte XML uniquement si la barre est visible
        # if self.main_layout.indexOf(self.bar) != -1 and self.bar.isVisible():
        #     self.symbol_text_lbl.setText(text_xml)
        #     self.symbol_text_lbl.show()
        # else:
        #     self.symbol_text_lbl.hide()
    
        # ── calcul temps restant ──
        secs = 0
        if getattr(self.bar, "mode", None) == "timer":
            if getattr(self.bar, "target_value", None) is not None:
                # décompte vers target_value (triangle noir)
                total_range = self.bar.target_value - self.bar.value
                secs = max(total_range * 60, 0)
            else:
                minutes = getattr(self.bar, "elapsed", 0) / 60
                max_minutes = getattr(self.bar, "duration", 0) / 60
                secs = self.bar._seconds_to_next_change(minutes, 0, max_minutes, unit="seconds")
        else:
            # vie ou jour
            if self.kind == "vie":
                value = self.bar.value * 365.25 * 24
                minv = self.bar.minv * 365.25 * 24
                maxv = self.bar.maxv * 365.25 * 24
            else:
                value = self.bar.value
                minv = self.bar.minv
                maxv = self.bar.maxv
    
            secs = self.bar._seconds_to_next_change(value, minv, maxv, unit="hours")
    
        # ── afficher countdown ──
        countdown_text = (
            self.seconds_to_life_text(secs)
            if self.kind == "vie"
            else self.seconds_to_text(secs)
        )
        self.countdown_lbl.setText(countdown_text)
    
        if self.kind == "action_prog":
            now = datetime.datetime.now()
            current_hour = (now.hour + now.minute / 60 + now.second / 3600)
        
            start = self.bar.minv
            end   = self.bar.maxv
        
            if current_hour < start:
                secs = int((start - current_hour) * 3600)
                prefix = "⏳"
            elif current_hour <= end:
                secs = int((end - current_hour) * 3600)
                prefix = "⚡"
            else:
                secs = 0
                prefix = "✅"
            #
            if end > start :
                ratio = (current_hour - start)/(end-start)
                ratio = max(0.0,min(1.0, ratio))
                self.bar.elapsed = ratio * self.bar.duration
                self.bar.update()

            txt = self.seconds_to_text(secs)
            countdown_text = f"{prefix} {txt}"
            self.countdown_lbl.setText(countdown_text)
    
    def phrase_to_symbols(self, phrase):
        if not phrase:
            return ""
    
        words = phrase.replace(" de la ", " ").replace(" du ", " ").split()
        words = words[::-1]  # inversion de l'ordre
    
        mapping = {"fin": "□", "milieu": "...", "début": "▲"}
        return "".join([mapping.get(w, "") for w in words])
    
    def phrase_to_text(self, phrase):
        """Retourne le texte XML correspondant à la phrase."""
        if self.kind == "vie":
            return self.parent().vie_dict.get(phrase, "")
        elif self.kind == "jour":
            return self.parent().jour_dict.get(phrase, "")
        elif self.kind == "action":
            return self.parent().action_dict.get(phrase, "")
        elif self.kind == "action_prog":
            return self.parent().action_prog_dict.get(phrase, "")
        return ""

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
        self.action_prog_dict = {}
        self.load_xml("phrases.xml")

        # ── Layout principal ──
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # Titre de la fenêtre avec icônes
        self.setWindowTitle("          ❤️ / ☀️ / ⚡")  # ajoute un décalage vers la droite

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
            blink_duration=BLINK_INTERVAL,
            label_format='years',
            show_triangle=False   # ← triangle supprimé
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
        #
        self.action_prog_bar = UnifiedBarWidget(
            minv=0, maxv=1,
            mode='timer',          # ← IMPORTANT
            duration=60*60,        # durée totale en secondes
            red_duration=0,
            blink_duration=0,
            label_format='hhmm',
            show_triangle=False
        )
        self.action_prog_bar.elapsed = 0
        
        self.action_prog_bar._update_phrase(
            self.action_prog_bar.value,
            self.action_prog_bar.minv,
            self.action_prog_bar.maxv
        )
        
        self.triangle_black_value = None  # début action programmée
        self.triangle_red_value   = None  # fin action programmée
        self.target_value         = None  # valeur vers laquelle le timer doit aller
        self.running              = False
        
        # ── Barre action (mode timer) ──
        self.action_bar = UnifiedBarWidget(
            minv=0, maxv=60,
            mode='timer',
            duration=30 * 60,
            red_duration=2 * 60,
            blink_duration=2 * 60,
            fd_fraction=0.20,
            df_fraction=0.80,
            show_triangle=False   # ← triangle supprimé
        )

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

        # ── Ligne Journée ──
        jour_col = QVBoxLayout()
        jour_col.setSpacing(2)
        jour_col.setContentsMargins(0, 0, 0, 0)
        
        #jour_col.addWidget(self.action_prog_bar)
        
        layout.addLayout(jour_col)

        self.resume_annee = JourCompactWidget(
            self.vie_bar, None, "vie", vie_dict=self.vie_dict, controls_mode="none"
        )
        self.resume_annee.plus_btn.clicked.connect(self.resume_annee.toggle_mode)
        self.resume_jour = JourCompactWidget(
            self.jour_bar, None, "jour", jour_dict=self.jour_dict, controls_mode="none"
        )
        self.resume_jour.plus_btn.clicked.connect(self.resume_jour.toggle_mode)
        #
        self.resume_action_prog = JourCompactWidget(
            self.action_prog_bar,
            None,
            kind="action_prog",
            action_prog_dict=self.action_prog_dict,  # ou dictionnaire spécifique si besoin
            controls_mode="pause_only"
        )
        # Connexion du bouton + du résumé Action programmée
        
        self.resume_action_prog.plus_btn.clicked.connect(self.resume_action_prog.toggle_mode)
        #
        self.resume_action = JourCompactWidget(
            self.action_bar, None, "action", action_dict=self.action_dict,
            controls_mode="full"
        )
        self.resume_action.plus_btn.clicked.connect(self.resume_action.toggle_mode)
        jour_col.addWidget(self.resume_annee)
        jour_col.addWidget(self.resume_jour)       
        jour_col.addWidget(self.resume_action_prog)  # <-- le nouveau résumé
        jour_col.addWidget(self.resume_action)
        
        self.setSizePolicy(self.sizePolicy().Minimum, self.sizePolicy().Minimum)
        self.adjustSize()

        # ── Panneau texte unique en bas ──
        self.texte_vie    = QLabel("")
        self.texte_jour   = QLabel("")
        self.texte_action = QLabel("")
        self.texte_action_prog = QLabel("")

        for lbl in [self.texte_vie, self.texte_jour, self.texte_action]:
            lbl.setWordWrap(True)
            
        # ── Init ──
        self.vie_bar.set_value(56)
        self.update_jour()
        #self.resize(800, 380)

        timer = QTimer(self)
        timer.timeout.connect(self.update_jour)
        timer.start(1000)

        self.target_value = None  # nouvelle valeur cible pour décompte

        self.load_bar_config()

    def ajuster_fenetre(self):
        self.layout().activate()
        self.resize(self.sizeHint())

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
        action_prog_text = self.action_prog_dict.get(self.action_prog_bar.phrase, "Pas de texte action prog")

        self.texte_vie.setText(vie_text)
        self.texte_jour.setText(jour_text)
        self.texte_action.setText(action_text)
        self.texte_action_prog.setText(action_prog_text)

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
        _load_section("action_prog", self.action_prog_dict)

    # ── Config barres ──

    def load_bar_config(self):
        try:
            tree = ET.parse("config_barres.xml")
            root = tree.getroot()
            for tag, bar in [("vie", self.vie_bar),
                              ("jour", self.jour_bar),
                              ("action", self.action_bar),
                              ("action_prog", self.action_prog_bar)]:
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
                         ("action", self.action_bar),
                         ("action_prog", self.action_prog_bar)]:
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


# ─────────────────────────────────────────────
#  Lancement
# ─────────────────────────────────────────────

app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec_())