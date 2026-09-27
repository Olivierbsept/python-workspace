#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Graphique_base3.py
──────────────────
Trace, en PyQt5, la courbe "valeur en base 3 (profondeur = 3)" en fonction
du temps t, en réutilisant la logique de subdivision récursive
(fd_fraction / df_fraction) du programme TimeManag3.py.

Deux courbes :

  • BLEUE  — la fonction complète "valeur en base 3" : pour n'importe quel
    instant t entre l'heure de début et l'heure de fin, on calcule sa
    position normalisée u dans [0,1], puis on applique 3 fois la logique
    de partition (fd/df) pour obtenir 3 chiffres ternaires (x0 x1 x2),
    convertis en entier décimal 0..26. Cette courbe est recalculée en
    entier à chaque image avec les fd/df ACTUELS : elle peut donc changer
    de forme si on déplace les curseurs, et elle est dessinée sur tout
    l'axe des temps (passé ET futur), puisque ce n'est qu'une formule.

  • VERTE  — l'enregistrement HISTORIQUE, tick par tick, de la valeur de
    la courbe bleue "à l'instant t" au moment où t était l'instant présent.
    Chaque point vert est figé avec les fd/df qui étaient actifs quand il
    a été enregistré. Elle ne peut donc jamais être tracée au-delà de
    l'instant présent, et si on déplace fd ou df en cours de route, les
    nouveaux points peuvent être plus bas que les précédents (la courbe
    verte n'est pas forcément monotone).
"""

import sys
import bisect
import os
import xml.etree.ElementTree as ET
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                              QDoubleSpinBox, QDateTimeEdit, QGridLayout)
from PyQt5.QtCore import Qt, QDateTime, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont


# ─────────────────────────────────────────────
#  Logique base 3 (reprise de TimeManag3.py)
# ─────────────────────────────────────────────

def compute_x012(A, B, D, E, M):
    """Renvoie les 3 chiffres (profondeur = 3) de M dans la partition
    récursive [A,B] découpée par fd (D) / df (E)."""
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


def valeur_base3(u, fd_fraction, df_fraction):
    """u dans [0,1] -> entier 0..26 = (x0 x1 x2) en base 3 (partition fd/df)."""
    x0, x1, x2 = compute_x012(0.0, 1.0, fd_fraction, df_fraction, u)
    return x0 * 9 + x1 * 3 + x2


def to_base3_str(v):
    """Entier 0..26 -> notation ternaire "0,d0d1d2"."""
    d0, r = divmod(v, 9)
    d1, d2 = divmod(r, 3)
    return f"0,{d0}{d1}{d2}"


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "graphique_base3_config.xml")


NB_GRAPHIQUES = 4


def historique_to_str(hist):
    """Sérialise la courbe verte [(t, v), ...] en une seule chaîne
    "t,v;t,v;..." pour le XML."""
    return ";".join(f"{t:.3f},{v}" for t, v in hist)


def historique_from_str(s):
    """Inverse de historique_to_str()."""
    if not s:
        return []
    out = []
    for part in s.split(";"):
        if not part:
            continue
        t_str, v_str = part.split(",")
        out.append((float(t_str), int(v_str)))
    return out


def charger_config():
    """Relit les réglages (début/fin/fd/df/historique) des NB_GRAPHIQUES
    graphiques depuis le XML. Renvoie une liste de NB_GRAPHIQUES éléments,
    chacun un dict ou None si absent/invalide pour cet index."""
    resultat = [None] * NB_GRAPHIQUES
    if not os.path.exists(CONFIG_PATH):
        return resultat
    try:
        root = ET.parse(CONFIG_PATH).getroot()
        for elem in root.findall("graphique"):
            idx = int(elem.get("index", "-1"))
            if 0 <= idx < NB_GRAPHIQUES:
                resultat[idx] = {
                    "debut": elem.findtext("debut"),
                    "fin": elem.findtext("fin"),
                    "fd": float(elem.findtext("fd")),
                    "df": float(elem.findtext("df")),
                    "historique": elem.findtext("historique") or "",
                }
    except Exception as e:
        print(f"[graphique_base3] ERREUR : lecture de {CONFIG_PATH} : {e}")
    return resultat


def sauver_config(liste_reglages):
    """Écrit les réglages des NB_GRAPHIQUES graphiques dans le XML, en une
    seule fois (liste_reglages[i] = dict {debut,fin,fd,df,historique})."""
    root = ET.Element("reglages_graphique_base3")
    for i, r in enumerate(liste_reglages):
        if r is None:
            continue
        elem = ET.SubElement(root, "graphique", {"index": str(i)})
        ET.SubElement(elem, "debut").text = r["debut"]
        ET.SubElement(elem, "fin").text = r["fin"]
        ET.SubElement(elem, "fd").text = f"{r['fd']:.4f}"
        ET.SubElement(elem, "df").text = f"{r['df']:.4f}"
        ET.SubElement(elem, "historique").text = r.get("historique", "")
    try:
        ET.ElementTree(root).write(CONFIG_PATH, encoding="utf-8", xml_declaration=True)
    except Exception as e:
        print(f"[graphique_base3] ERREUR : impossible d'écrire {CONFIG_PATH} : {e}")


def word(c):
    """Chiffre ternaire ('0','1','2') -> mot (reprend TimeManag3.py)."""
    if c == "0":
        return "début"
    if c == "1":
        return "milieu"
    return "fin"


def build_phrase(base3):
    """3 chiffres ternaires -> phrase "début du milieu de la fin", etc.
    (logique identique à build_phrase() de TimeManag3.py)."""
    phrase = ""
    for i in range(len(base3) - 1, -1, -1):
        phrase += word(base3[i])
        if i > 0:
            phrase += " de la " if base3[i - 1] == "2" else " du "
    return phrase


# ─────────────────────────────────────────────
#  Widget de tracé
# ─────────────────────────────────────────────

MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 50, 12, 58, 32


class Graphe3Widget(QWidget):
    def __init__(self, heure_debut=None, heure_fin=None,
                 fd_fraction=0.33, df_fraction=0.66, n_points=600,
                 historique=None):
        super().__init__()
        if heure_debut is None:
            heure_debut = datetime.datetime.now().timestamp()
        if heure_fin is None:
            heure_fin = heure_debut + 2 * 3600
        # heure_debut / heure_fin sont des timestamps Unix (secondes) —
        # pas seulement une heure de la journée — ce qui permet une durée
        # de plus de 24h (plusieurs jours) et une date de début/fin propre.
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin
        self.fd_fraction = fd_fraction
        self.df_fraction = df_fraction
        self.n_points = n_points
        # historique (courbe verte) : repris de la session précédente si
        # fourni, puis simplement complété jusqu'à maintenant
        self._history = list(historique) if historique else []

        # le graphique entier doit être un carré physique de 8 cm x 8 cm
        dpi = QApplication.primaryScreen().logicalDotsPerInch()
        cote_px = max(120, round(8 / 2.54 * dpi))
        self.setFixedSize(cote_px, cote_px)

        self.setStyleSheet("background-color: white;")
        self._extend_history_if_needed()

    def get_history(self):
        """Copie de l'historique (courbe verte) actuel, pour sauvegarde."""
        return list(self._history)

    # ── réglages ──
    def set_time_range(self, heure_debut, heure_fin):
        """Changer la plage de temps ne doit PAS effacer l'historique déjà
        enregistré (courbe verte) : les points existants sont conservés
        (mêmes t, mêmes valeurs figées) et seulement "translatés" sur le
        nouvel axe — c'est juste leur position à l'écran qui change. On
        comble seulement un éventuel trou si le nouveau début est plus
        tôt que ce qui a déjà été enregistré."""
        self.heure_debut = heure_debut
        self.heure_fin = heure_fin
        self._extend_history_if_needed()
        self.update()

    def set_fd_df(self, fd_fraction, df_fraction):
        """Changer fd/df NE touche PAS l'historique déjà enregistré :
        seuls les nouveaux points (à venir) utiliseront ces valeurs."""
        self.fd_fraction = fd_fraction
        self.df_fraction = df_fraction
        self.update()

    # ── historique (courbe verte) ──
    def _now_hour(self):
        """Renvoie (datetime, timestamp Unix en secondes) de l'instant
        présent — un timestamp absolu, donc aucun souci si la fenêtre
        dépasse 24h ou change de jour."""
        now = datetime.datetime.now()
        return now, now.timestamp()

    def _extend_history_if_needed(self):
        """Ne recrée jamais l'historique : comble seulement les trous
        (avant le premier point, ou entre le dernier point et l'instant
        présent) avec les fd/df actuels."""
        _, h_now = self._now_hour()
        t_end = min(h_now, self.heure_fin)
        if t_end <= self.heure_debut:
            return
        if not self._history:
            self._backfill_range(self.heure_debut, t_end, prepend=False)
            return
        first_t = self._history[0][0]
        last_t = self._history[-1][0]
        if self.heure_debut < first_t - 1e-9:
            self._backfill_range(self.heure_debut, first_t, prepend=True)
        if t_end > last_t + 1e-9:
            self._backfill_range(last_t, t_end, prepend=False)

    def _backfill_range(self, t_start, t_end, prepend):
        total = self.heure_fin - self.heure_debut
        if total <= 0 or t_end <= t_start:
            return
        step = total / self.n_points
        pts = []
        t = t_start
        while t < t_end - 1e-9:
            u = (t - self.heure_debut) / total
            v = valeur_base3(u, self.fd_fraction, self.df_fraction)
            pts.append((t, v))
            t += step
        u = (t_end - self.heure_debut) / total
        v = valeur_base3(u, self.fd_fraction, self.df_fraction)
        pts.append((t_end, v))
        if prepend:
            self._history = pts + self._history
        else:
            self._history = self._history + pts

    def record_tick(self):
        """Appelé à chaque tick du timer (~2 s) : ajoute le(s) point(s)
        manquant(s) avec les fd/df ACTUELS, sans jamais toucher au passé
        déjà figé.

        Si le Mac s'est mis en veille (ou l'appli a été suspendue), le
        timer "rate" plusieurs ticks : t_end se retrouve alors bien plus
        loin que le dernier point enregistré. Dans ce cas on rejoue
        l'intervalle manqué en le ré-échantillonnant avec le même pas
        que le reste de la courbe, au lieu d'ajouter un seul point — ce
        qui évitait un trait droit "à vol d'oiseau" entre les deux."""
        _, h_now = self._now_hour()
        if h_now < self.heure_debut:
            return
        t_end = min(h_now, self.heure_fin)
        if not self._history:
            self._backfill_range(self.heure_debut, t_end, prepend=False)
            return
        last_t = self._history[-1][0]
        gap = t_end - last_t
        if gap <= 1e-9:
            return

        total = self.heure_fin - self.heure_debut
        step = total / self.n_points
        seuil_veille = max(step * 3, 10)  # ~10 s ou 3 pas

        if gap <= seuil_veille:
            u = (t_end - self.heure_debut) / total
            v = valeur_base3(u, self.fd_fraction, self.df_fraction)
            self._history.append((t_end, v))
        else:
            # veille détectée : on rejoue l'intervalle manqué, pas à pas,
            # sans dupliquer le dernier point déjà enregistré
            t = last_t + step
            while t < t_end - 1e-9:
                u = (t - self.heure_debut) / total
                v = valeur_base3(u, self.fd_fraction, self.df_fraction)
                self._history.append((t, v))
                t += step
            u = (t_end - self.heure_debut) / total
            v = valeur_base3(u, self.fd_fraction, self.df_fraction)
            self._history.append((t_end, v))

    # ── courbe bleue : fonction complète, toujours recalculée ──
    def _points_full(self):
        total = self.heure_fin - self.heure_debut
        if total <= 0:
            return []
        n = self.n_points
        pts = []
        for i in range(n + 1):
            u = i / n
            t = self.heure_debut + u * total
            v = valeur_base3(u, self.fd_fraction, self.df_fraction)
            pts.append((t, v))
        return pts

    def _interp_history(self, t, ts):
        """Valeur de la courbe verte (historique) à l'instant t, par
        interpolation linéaire entre les 2 points enregistrés encadrant
        t. Renvoie None si t est hors de la portion déjà enregistrée
        (notamment dans le futur)."""
        if not ts:
            return None
        if t < ts[0] - 1e-9 or t > ts[-1] + 1e-9:
            return None
        idx = bisect.bisect_left(ts, t)
        if idx <= 0:
            return self._history[0][1]
        if idx >= len(ts):
            return self._history[-1][1]
        t0, v0 = self._history[idx - 1]
        t1, v1 = self._history[idx]
        if t1 == t0:
            return v1
        frac = (t - t0) / (t1 - t0)
        return v0 + frac * (v1 - v0)

    def _fill_bands(self, painter, X, Y, plot_x0, plot_x1, plot_y0, plot_y1, vmax):
        """Colorie, colonne par colonne :
          - en rouge la bande ENTRE les 2 courbes,
          - sinon en bleu la bande SOUS la courbe bleue,
          - sinon en vert la bande AU-DESSUS de la courbe verte
            (ou, dans le futur, au-dessus de la courbe bleue puisque la
            courbe verte n'existe pas encore)."""
        total = self.heure_fin - self.heure_debut
        if total <= 0:
            return
        ts = [p[0] for p in self._history]
        col_bleu = QColor(150, 190, 255, 130)
        col_rouge = QColor(255, 110, 110, 150)
        col_vert = QColor(150, 230, 150, 130)

        for x_px in range(plot_x0, plot_x1 + 1):
            frac = (x_px - plot_x0) / (plot_x1 - plot_x0)
            t = self.heure_debut + frac * total
            blue_val = valeur_base3(frac, self.fd_fraction, self.df_fraction)
            green_val = self._interp_history(t, ts)
            if green_val is None:
                green_val = blue_val  # pas d'historique -> pas de bande rouge

            bas, haut = min(blue_val, green_val), max(blue_val, green_val)
            y_bas, y_haut = Y(bas), Y(haut)

            # sous la courbe la plus en dessous -> bleu
            painter.fillRect(x_px, y_bas, 1, plot_y0 - y_bas, col_bleu)
            # entre les 2 courbes -> rouge
            if y_bas > y_haut:
                painter.fillRect(x_px, y_haut, 1, y_bas - y_haut, col_rouge)
            # au-dessus de la courbe du dessus -> vert
            if y_haut > plot_y1:
                painter.fillRect(x_px, plot_y1, 1, y_haut - plot_y1, col_vert)

    @staticmethod
    def _fmt_dt(ts):
        """Timestamp -> "jj/mm/aaaa HH:mm" (avec l'année, la durée
        pouvant dépasser 24h et même changer d'année)."""
        return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        plot_x0, plot_x1 = MARGIN_L, w - MARGIN_R
        plot_y0, plot_y1 = h - MARGIN_B, MARGIN_T  # y1 en haut, y0 en bas
        vmax = 26  # 3^3 - 1

        def X(t):
            frac = (t - self.heure_debut) / (self.heure_fin - self.heure_debut)
            return int(round(plot_x0 + frac * (plot_x1 - plot_x0)))

        def Y(v):
            frac = v / vmax
            return int(round(plot_y0 + frac * (plot_y1 - plot_y0)))

        # ── remplissage des 3 bandes (rouge / bleu / vert) ──
        self._fill_bands(painter, X, Y, plot_x0, plot_x1, plot_y0, plot_y1, vmax)

        # ── titre : dépend de l'instant présent ──
        _, h_now_titre = self._now_hour()
        if self.heure_debut <= h_now_titre <= self.heure_fin:
            u_titre = (h_now_titre - self.heure_debut) / (self.heure_fin - self.heure_debut)
            x0, x1, x2 = compute_x012(0.0, 1.0, self.fd_fraction, self.df_fraction, u_titre)
            titre = build_phrase(f'{x0}{x1}{x2}')
        else:
            titre = "(hors plage horaire)"
        painter.setPen(QColor(20, 20, 20))
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(MARGIN_L, 50, titre)

        # ── axes ──
        pen_axe = QPen(QColor(40, 40, 40))
        pen_axe.setWidth(1)
        painter.setPen(pen_axe)
        painter.drawLine(plot_x0, plot_y0, plot_x1, plot_y0)  # axe t
        painter.drawLine(plot_x0, plot_y0, plot_x0, plot_y1)  # axe valeur

        # ── graduations date+heure (début / fin) ──
        painter.setPen(QColor(60, 60, 60))
        painter.setFont(QFont("Arial", 6))
        painter.drawText(plot_x0 - 4, plot_y0 + 14, self._fmt_dt(self.heure_debut))
        painter.drawText(plot_x1 - 62, plot_y0 + 14, self._fmt_dt(self.heure_fin))
        painter.drawLine(plot_x0, plot_y0 - 3, plot_x0, plot_y0 + 3)
        painter.drawLine(plot_x1, plot_y0 - 3, plot_x1, plot_y0 + 3)

        # ── repères fd / df (traits horizontaux uniquement) ──
        val_fd = self.fd_fraction * vmax
        val_df = self.df_fraction * vmax
        y_fd = Y(val_fd)
        y_df = Y(val_df)          # y_df < y_fd (df est au-dessus de fd)

        pen_fd = QPen(QColor(0, 140, 0))
        pen_fd.setStyle(Qt.DashLine)
        painter.setPen(pen_fd)
        painter.drawLine(plot_x0, y_fd, plot_x1, y_fd)
        pen_df = QPen(QColor(190, 0, 0))
        pen_df.setStyle(Qt.DashLine)
        painter.setPen(pen_df)
        painter.drawLine(plot_x0, y_df, plot_x1, y_df)

        # ── courbe BLEUE : fonction complète (passé + futur) ──
        pts_full = self._points_full()
        pen_courbe = QPen(QColor(30, 90, 200))
        pen_courbe.setWidth(1)
        painter.setPen(pen_courbe)
        for (t0, v0), (t1, v1) in zip(pts_full, pts_full[1:]):
            painter.drawLine(X(t0), Y(v0), X(t1), Y(v1))

        # ── courbe VERTE : historique figé, jamais dans le futur ──
        pen_hist = QPen(QColor(0, 150, 60))
        pen_hist.setWidth(1)
        painter.setPen(pen_hist)
        hist = self._history
        for (t0, v0), (t1, v1) in zip(hist, hist[1:]):
            painter.drawLine(X(t0), Y(v0), X(t1), Y(v1))

        # ── heure réelle (maintenant) : extrémité de la courbe verte ──
        if hist:
            t_now, v_hist = hist[-1]
            if self.heure_debut <= t_now <= self.heure_fin:
                x_now, y_hist = X(t_now), Y(v_hist)
                total = self.heure_fin - self.heure_debut
                u_now = (t_now - self.heure_debut) / total
                v_blue_now = valeur_base3(u_now, self.fd_fraction, self.df_fraction)
                y_blue = Y(v_blue_now)

                pen_now = QPen(QColor(230, 130, 0))
                pen_now.setStyle(Qt.DashLine)
                pen_now.setWidth(1)
                painter.setPen(pen_now)
                painter.drawLine(x_now, plot_y0, x_now, plot_y1)

                painter.setBrush(QColor(0, 150, 60))
                painter.setPen(QPen(QColor(0, 150, 60)))
                painter.drawEllipse(x_now - 3, y_hist - 3, 6, 6)
                if v_blue_now != v_hist:
                    painter.setBrush(QColor(30, 90, 200))
                    painter.setPen(QPen(QColor(30, 90, 200)))
                    painter.drawEllipse(x_now - 3, y_blue - 3, 6, 6)

    @staticmethod
    def _draw_bracket(painter, x, y_bottom, y_top, label, color):
        """Double flèche verticale + étiquette, comme sur le croquis."""
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(x, y_bottom, x, y_top)
        for y, sign in ((y_bottom, 1), (y_top, -1)):
            painter.drawLine(x, y, x - 4, y + 6 * sign)
            painter.drawLine(x, y, x + 4, y + 6 * sign)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(x + 8, (y_bottom + y_top) // 2 + 4, label)


# ─────────────────────────────────────────────
#  Fenêtre principale avec réglages
# ─────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Valeur en base 3 (profondeur = 3) en fonction du temps")

        cfg_list = charger_config()

        central = QWidget()
        grille = QGridLayout(central)
        grille.setContentsMargins(6, 6, 6, 6)
        grille.setSpacing(8)

        self.graphes = []
        self.edits_debut = []
        self.edits_fin = []
        self.spins_fd = []
        self.spins_df = []

        for i in range(NB_GRAPHIQUES):
            cfg = cfg_list[i]
            dt_debut = dt_fin = None
            fd_defaut, df_defaut = 0.33, 0.66
            if cfg:
                dt_debut = QDateTime.fromString(cfg["debut"], "yyyy-MM-dd HH:mm")
                dt_fin = QDateTime.fromString(cfg["fin"], "yyyy-MM-dd HH:mm")
                fd_defaut, df_defaut = cfg["fd"], cfg["df"]
                if not (dt_debut.isValid() and dt_fin.isValid()):
                    dt_debut = dt_fin = None

            if i == 1:
                # carré en haut à droite -> toujours la journée actuelle
                # complète (ignore début/fin sauvegardés, garde fd/df)
                minuit = datetime.datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0)
                dt_debut = QDateTime.fromSecsSinceEpoch(int(minuit.timestamp()))
                dt_fin = QDateTime.fromSecsSinceEpoch(
                    int((minuit + datetime.timedelta(days=1)).timestamp()))
            elif dt_debut is None:
                debut_defaut = datetime.datetime.now()
                fin_defaut = debut_defaut + datetime.timedelta(hours=2)
                dt_debut = QDateTime.fromSecsSinceEpoch(int(debut_defaut.timestamp()))
                dt_fin = QDateTime.fromSecsSinceEpoch(int(fin_defaut.timestamp()))

            historique_initial = None
            if i != 1 and cfg and cfg.get("historique"):
                historique_initial = historique_from_str(cfg["historique"])

            graphe = Graphe3Widget(
                heure_debut=self._heure_to_ts(dt_debut),
                heure_fin=self._heure_to_ts(dt_fin),
                fd_fraction=fd_defaut, df_fraction=df_defaut,
                historique=historique_initial)

            # ── réglages superposés directement SUR ce graphique ──
            edit_debut = QDateTimeEdit(dt_debut, graphe)
            edit_debut.setDisplayFormat("dd/MM/yyyy HH:mm")
            edit_fin = QDateTimeEdit(dt_fin, graphe)
            edit_fin.setDisplayFormat("dd/MM/yyyy HH:mm")
            spin_fd = QDoubleSpinBox(graphe)
            spin_fd.setRange(0.01, 0.49)
            spin_fd.setSingleStep(0.01)
            spin_fd.setValue(fd_defaut)
            spin_df = QDoubleSpinBox(graphe)
            spin_df.setRange(0.51, 0.99)
            spin_df.setSingleStep(0.01)
            spin_df.setValue(df_defaut)

            cote = graphe.width()
            w2 = (cote - 10) // 2
            for widget in (edit_debut, edit_fin, spin_fd, spin_df):
                widget.setStyleSheet("font-size: 7px;")
            edit_debut.setGeometry(4, 2, w2, 16)
            edit_fin.setGeometry(6 + w2, 2, w2, 16)
            spin_fd.setGeometry(4, 20, w2, 16)
            spin_df.setGeometry(6 + w2, 20, w2, 16)

            edit_debut.dateTimeChanged.connect(
                lambda _, idx=i: self._on_time_range_changed(idx))
            edit_fin.dateTimeChanged.connect(
                lambda _, idx=i: self._on_time_range_changed(idx))
            spin_fd.valueChanged.connect(
                lambda _, idx=i: self._on_fd_df_changed(idx))
            spin_df.valueChanged.connect(
                lambda _, idx=i: self._on_fd_df_changed(idx))

            self.graphes.append(graphe)
            self.edits_debut.append(edit_debut)
            self.edits_fin.append(edit_fin)
            self.spins_fd.append(spin_fd)
            self.spins_df.append(spin_df)

            grille.addWidget(graphe, i // 2, i % 2)

        self.setCentralWidget(central)

        for i in range(NB_GRAPHIQUES):
            self._on_fd_df_changed(i, sauvegarder=False)
            self._on_time_range_changed(i, sauvegarder=False)
        self._sauver_config()

        # tick temps réel : enregistre l'historique + rafraîchit l'affichage
        self._tick_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(2000)

    @staticmethod
    def _heure_to_ts(qdatetime):
        """QDateTime -> timestamp Unix (secondes)."""
        return qdatetime.toPyDateTime().timestamp()

    def _on_time_range_changed(self, idx, sauvegarder=True):
        debut_ts = self._heure_to_ts(self.edits_debut[idx].dateTime())
        fin_ts = self._heure_to_ts(self.edits_fin[idx].dateTime())
        if fin_ts <= debut_ts:
            fin_ts = debut_ts + 1800  # au moins 30 min, réglage sinon invalide
        self.graphes[idx].set_time_range(debut_ts, fin_ts)
        if sauvegarder:
            self._sauver_config()

    def _on_fd_df_changed(self, idx, sauvegarder=True):
        fd = self.spins_fd[idx].value()
        df = self.spins_df[idx].value()
        if df <= fd:
            df = fd + 0.02
        self.graphes[idx].set_fd_df(fd, df)
        if sauvegarder:
            self._sauver_config()

    def _sauver_config(self):
        liste = []
        for i in range(NB_GRAPHIQUES):
            liste.append({
                "debut": self.edits_debut[i].dateTime().toString("yyyy-MM-dd HH:mm"),
                "fin": self.edits_fin[i].dateTime().toString("yyyy-MM-dd HH:mm"),
                "fd": self.spins_fd[i].value(),
                "df": self.spins_df[i].value(),
                "historique": historique_to_str(self.graphes[i].get_history()),
            })
        sauver_config(liste)

    def _on_tick(self):
        for graphe in self.graphes:
            graphe.record_tick()
            graphe.update()
        self._tick_count += 1
        if self._tick_count % 15 == 0:  # ~30 s : on mémorise l'historique
            self._sauver_config()

    def closeEvent(self, event):
        """Toujours sauvegarder (y compris l'historique) en quittant."""
        self._sauver_config()
        super().closeEvent(event)


if __name__ == "__main__":
    print(f"[graphique_base3] fichier de sauvegarde : {CONFIG_PATH}")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
