"""AE-5 Control – Einstellungs-App mit Profilen und Tray-Symbol (PySide6)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QProcess, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPalette, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QStackedWidget, QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__, core, pipewire
from .i18n import tr
from .catalog import (
    DEVICE_CONTROLS, EFFECTS, EQ_BANDS, EQ_CENTER, EQ_FREQUENCIES, EQ_PRESET, EQ_PRESET_DB,
    EQ_SWITCH, HEADPHONE_GAIN, INPUT_SOURCE, MIC_BOOST, MIC_SVM_LEVEL, MIC_SWITCHES,
    ITEM_TOOLTIPS, OUTFX_SWITCH, PROFILE_CONTROLS, SMART_VOLUME_MODE, SOUND_FILTER,
    SURROUND_CONFIG, TOOLTIPS, VOICE_FX, XBASS_CROSSOVER, eq_db, eq_raw, label,
)
from .mixer import Control, Mixer, MixerError
from .profiles import Store, snapshot

TOOLS = Path(__file__).resolve().parent.parent / "tools"
FIRST_PROFILE = tr("Meine Einstellungen", "My settings")
SAFE_VOLUME = 15  # Prozent, bevor die Kopfhörer-Verstärkung erhöht wird


# --- Bausteine -----------------------------------------------------------------

def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(round(a.red() * (1 - t) + b.red() * t),
                  round(a.green() * (1 - t) + b.green() * t),
                  round(a.blue() * (1 - t) + b.blue() * t))


class Toggle(QCheckBox):
    """Schalter im Stil eines Kippschalters (bleibt ein QCheckBox für die Bindungen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        on = self.isChecked()
        track = pal.color(QPalette.Highlight) if on else _mix(pal.color(QPalette.Window), pal.color(QPalette.Text), 0.25)
        if not self.isEnabled():
            track = _mix(track, pal.color(QPalette.Window), 0.6)
        r = QRectF(1, 2, 42, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, 10, 10)
        p.setBrush(QColor("white"))
        x = r.right() - 18 if on else r.left() + 2
        p.drawEllipse(QRectF(x, r.top() + 2, 16, 16))


class EqCurve(QWidget):
    """Zeichnet die Klangkurve der 10 EQ-Bänder (−24 … +24 dB)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [EQ_CENTER] * 10
        self.active = True
        self.setMinimumHeight(140)

    def set_values(self, values: list[int], active: bool) -> None:
        self.values, self.active = values, active
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text, base = pal.color(QPalette.Text), pal.color(QPalette.Base)
        accent = pal.color(QPalette.Highlight) if self.active else _mix(text, base, 0.55)
        w, h = self.width(), self.height()
        left, right, top, bottom = 44, 12, 10, 10
        plot = QRectF(left, top, w - left - right, h - top - bottom)

        def y_of(db: float) -> float:
            return plot.center().y() - db / 24.0 * plot.height() / 2

        grid = QPen(_mix(text, base, 0.82), 1)
        p.setFont(self.font())
        for db in (24, 12, 0, -12, -24):
            p.setPen(grid if db else QPen(_mix(text, base, 0.6), 1))
            p.drawLine(QPointF(plot.left(), y_of(db)), QPointF(plot.right(), y_of(db)))
            p.setPen(_mix(text, base, 0.45))
            p.drawText(QRectF(0, y_of(db) - 8, left - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{db:+d}" if db else "0")

        step = plot.width() / 9
        pts = [QPointF(plot.left() + i * step, y_of(eq_db(v))) for i, v in enumerate(self.values)]
        path = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            mid = (a.x() + b.x()) / 2
            path.cubicTo(QPointF(mid, a.y()), QPointF(mid, b.y()), b)
        fill = QPainterPath(path)
        fill.lineTo(pts[-1].x(), y_of(0))
        fill.lineTo(pts[0].x(), y_of(0))
        fill.closeSubpath()
        shade = QColor(accent)
        shade.setAlpha(45)
        p.fillPath(fill, shade)
        p.setPen(QPen(accent, 2.5))
        p.drawPath(path)
        p.setBrush(accent)
        p.setPen(Qt.NoPen)
        for pt in pts:
            p.drawEllipse(pt, 3.5, 3.5)


def fill_items(box: QComboBox, items: list[str]) -> None:
    """Einträge mit deutschem Namen und Erklärung (Tooltip) einfügen."""
    for item in items:
        box.addItem(label(item))
        if item in ITEM_TOOLTIPS:
            box.setItemData(box.count() - 1, ITEM_TOOLTIPS[item], Qt.ToolTipRole)


def card(title: str = "", subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame(objectName="card")
    v = QVBoxLayout(frame)
    v.setContentsMargins(18, 14, 18, 16)
    v.setSpacing(10)
    if title:
        v.addWidget(QLabel(title, objectName="cardTitle"))
    if subtitle:
        sub = QLabel(subtitle, objectName="muted")
        sub.setWordWrap(True)
        v.addWidget(sub)
    return frame, v


def page(*widgets) -> QScrollArea:
    inner = QWidget()
    v = QVBoxLayout(inner)
    v.setContentsMargins(4, 4, 12, 4)
    v.setSpacing(14)
    for w in widgets:
        v.addWidget(w)
    v.addStretch()
    area = QScrollArea()
    area.setWidget(inner)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    return area


def stylesheet(pal: QPalette) -> str:
    text, base, window = pal.color(QPalette.Text), pal.color(QPalette.Base), pal.color(QPalette.Window)
    accent = pal.color(QPalette.Highlight)
    muted = _mix(text, window, 0.45).name()
    border = _mix(text, base, 0.85).name()
    soft = _mix(accent, base, 0.8).name()
    return f"""
    QFrame#card {{ background: {base.name()}; border: 1px solid {border}; border-radius: 12px; }}
    QLabel#cardTitle {{ font-size: 11pt; font-weight: 600; }}
    QLabel#muted {{ color: {muted}; }}
    QLabel#title {{ font-size: 16pt; font-weight: 700; }}
    QLabel#badge {{ background: {soft}; color: {text.name()}; border-radius: 9px; padding: 2px 10px; }}
    QListWidget#nav {{ background: transparent; border: none; outline: none; font-size: 10.5pt; }}
    QListWidget#nav::item {{ padding: 10px 12px; margin: 2px 0; border-radius: 8px; }}
    QListWidget#nav::item:selected {{ background: {accent.name()}; color: {pal.color(QPalette.HighlightedText).name()}; }}
    QListWidget#nav::item:hover:!selected {{ background: {soft}; }}
    QPushButton#outputChoice {{ padding: 14px 18px; border-radius: 10px; font-size: 10.5pt; text-align: left;
                                border: 1px solid {border}; background: {window.name()}; }}
    QPushButton#outputChoice:hover:!checked {{ background: {soft}; }}
    QPushButton#outputChoice:checked {{ background: {accent.name()}; color: {pal.color(QPalette.HighlightedText).name()}; }}
    QSlider::groove:horizontal {{ height: 6px; border-radius: 3px; background: {border}; }}
    QSlider::sub-page:horizontal {{ border-radius: 3px; background: {accent.name()}; }}
    QSlider::sub-page:horizontal:disabled {{ background: {muted}; }}
    QSlider::handle:horizontal {{ width: 16px; margin: -6px 0; border-radius: 8px; background: white; border: 1px solid {border}; }}
    QSlider::groove:vertical {{ width: 6px; border-radius: 3px; background: {border}; }}
    QSlider::add-page:vertical {{ border-radius: 3px; background: {accent.name()}; }}
    QSlider::add-page:vertical:disabled {{ background: {muted}; }}
    QSlider::handle:vertical {{ height: 16px; margin: 0 -6px; border-radius: 8px; background: white; border: 1px solid {border}; }}
    """


# --- Bindungen an ALSA ---------------------------------------------------------

class Bindings:
    """Verbindet Widgets mit ALSA-Reglern und schreibt Änderungen gebündelt."""

    def __init__(self, window: "MainWindow"):
        self.win = window
        self.widgets: dict[str, list] = {}
        self.pending: dict[str, list[int]] = {}
        self.timer = QTimer(singleShot=True, interval=120)
        self.timer.timeout.connect(self.flush)

    def add(self, name: str, widget) -> None:
        self.widgets.setdefault(name, []).append(widget)

    def queue(self, name: str, value: int) -> None:
        ctl = self.win.ctls.get(name)
        if ctl is None:
            return
        self.pending[name] = [value] * max(ctl.count, 1)
        self.timer.start()

    def flush(self) -> None:
        if not self.pending:
            return
        values, self.pending = self.pending, {}
        try:
            self.win.mixer.write(values, self.win.ctls)
        except MixerError as exc:
            self.win.show_status(tr(f"Konnte nicht setzen: {exc}", f"Could not set: {exc}"))
            return
        for name, vals in values.items():
            if name in self.win.ctls:
                self.win.ctls[name].values = vals
        if any(n in DEVICE_CONTROLS for n in values):
            self.win.store.save_device(snapshot(self.win.ctls, DEVICE_CONTROLS))
        self.win.after_change()

    def refresh(self) -> None:
        for name, widgets in self.widgets.items():
            ctl = self.win.ctls.get(name)
            for w in widgets:
                if ctl is None or not ctl.values or name in self.pending:
                    continue
                if isinstance(w, QSlider) and w.isSliderDown():
                    continue
                w.blockSignals(True)
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(ctl.values[0]))
                elif isinstance(w, QSlider):
                    w.setValue(ctl.values[0])
                    w.value_label.setText(w.format_value(ctl.values[0]))
                elif isinstance(w, QComboBox):
                    w.setCurrentIndex(ctl.values[0])
                w.blockSignals(False)
                if isinstance(w, QCheckBox):
                    w.update()


# --- Hauptfenster --------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, start_hidden: bool = False):
        super().__init__()
        self.setWindowTitle("AE-5 Control")
        self.setWindowIcon(QIcon.fromTheme("audio-card"))
        self.resize(980, 680)
        self.mixer = Mixer()
        self.store = Store()
        self.store.ensure_defaults()
        self.ctls: dict[str, Control] = {}
        self.bind = Bindings(self)
        self.quitting = False
        self.proc: QProcess | None = None
        self.effect_rows: list[tuple[QCheckBox, QSlider]] = []
        self.tray = None

        self._read_controls()
        self._first_run()
        self.setStyleSheet(stylesheet(self.palette()))
        self._build_ui()
        self._build_tray()
        self.refresh()

        self.poll = QTimer(interval=2000)
        self.poll.timeout.connect(self.refresh)
        self.poll.start()
        if not start_hidden or self.tray is None:
            self.show()

    # --- Daten ---------------------------------------------------------------
    def _read_controls(self) -> bool:
        try:
            self.ctls = self.mixer.read_all()
            return True
        except MixerError:
            self.ctls = {}
            return False

    def _first_run(self) -> None:
        """Beim ersten Start die aktuellen Einstellungen sichern, damit nichts verloren geht."""
        if self.store.active_profile() or not self.ctls:
            return
        if FIRST_PROFILE not in self.store.list_profiles():
            self.store.save_profile(FIRST_PROFILE, snapshot(self.ctls, PROFILE_CONTROLS))
        self.store.set_active_profile(FIRST_PROFILE)
        if not self.store.load_device():
            self.store.save_device(snapshot(self.ctls, DEVICE_CONTROLS))

    # --- Aufbau --------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(16)

        self.nav = QListWidget(objectName="nav")
        self.nav.setFixedWidth(190)
        self.nav.setIconSize(QSize(22, 22))
        nav_items = (
            ("audio-headphones", tr("Ausgabe", "Output"),
             tr("Kopfhörer/Lautsprecher, Verstärkung, DAC-Filter", "Headphones/speakers, gain, DAC filter")),
            ("audio-volume-high", tr("Effekte", "Effects"),
             "Surround, Crystalizer, Bass, Smart Volume, Dialog Plus"),
            ("view-media-equalizer", "Equalizer",
             tr("10-Band-Equalizer und Voreinstellungen", "10-band equalizer and presets")),
            ("audio-input-microphone", tr("Mikrofon", "Microphone"),
             tr("Eingang und Mikrofon-Effekte der AE-5", "Input and microphone effects of the AE-5")),
            ("preferences-system", "System",
             tr("Status, Karte prüfen oder neu starten", "Status, check or restart the card")),
        )
        for icon, text, tip in nav_items:
            item = QListWidgetItem(QIcon.fromTheme(icon), text)
            item.setToolTip(tip)
            self.nav.addItem(item)
        outer.addWidget(self.nav)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.addLayout(self._build_header())
        self.pages = QStackedWidget()
        for build in (self._page_output, self._page_effects, self._page_eq, self._page_mic, self._page_system):
            self.pages.addWidget(build())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        right.addWidget(self.pages, 1)
        self.status_label = QLabel(objectName="muted")
        right.addWidget(self.status_label)
        outer.addLayout(right, 1)
        self.setCentralWidget(root)
        self._fill_profiles()

    def _build_header(self) -> QVBoxLayout:
        v = QVBoxLayout()
        v.setSpacing(8)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(QLabel("Sound BlasterX AE-5", objectName="title"))
        self.subtitle = QLabel(objectName="muted")
        titles.addWidget(self.subtitle)
        top.addLayout(titles)
        top.addStretch()
        v.addLayout(top)

        bar = QHBoxLayout()
        bar.addWidget(QLabel(tr("Profil:", "Profile:")))
        self.profile_box = QComboBox(minimumWidth=220)
        self.profile_box.setToolTip(tr("Klangprofil wählen. Profile enthalten Effekte, Equalizer und "
                                       "Mikrofon-Effekte – nie die Lautstärke.",
                                       "Choose a sound profile. Profiles contain effects, equalizer and "
                                       "microphone effects – never the volume."))
        self.profile_box.activated.connect(self._profile_chosen)
        bar.addWidget(self.profile_box)
        self.modified_badge = QLabel(tr("geändert", "modified"), objectName="badge")
        self.modified_badge.setToolTip(tr("Die aktuellen Einstellungen weichen vom gespeicherten Profil ab.",
                                          "The current settings differ from the saved profile."))
        self.modified_badge.setVisible(False)
        bar.addWidget(self.modified_badge)
        bar.addStretch()

        save = QPushButton(QIcon.fromTheme("document-save"), tr("Speichern", "Save"))
        save.setToolTip(tr("Aktuelle Einstellungen im gewählten Profil speichern.", "Save the current settings to the selected profile."))
        save.clicked.connect(self._save_profile)
        save_as = QPushButton(QIcon.fromTheme("document-save-as"), tr("Speichern unter …", "Save as …"))
        save_as.setToolTip(tr("Aktuelle Einstellungen als neues Profil speichern.", "Save the current settings as a new profile."))
        save_as.clicked.connect(self._save_profile_as)
        self.reset_btn = QToolButton()
        self.reset_btn.setText(tr("Zurücksetzen", "Reset"))
        self.reset_btn.setIcon(QIcon.fromTheme("edit-undo"))
        self.reset_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.reset_btn.setPopupMode(QToolButton.InstantPopup)
        self.reset_btn.setToolTip(tr("Änderungen verwerfen oder Standardprofile zurücksetzen.", "Discard changes or reset the default profiles."))
        self.reset_menu = QMenu(self.reset_btn)
        self.act_revert = self.reset_menu.addAction(tr("Änderungen verwerfen", "Discard changes"), self._revert)
        self.act_factory = self.reset_menu.addAction(tr("Profil auf Werkseinstellung", "Reset profile to factory default"), self._factory_reset)
        self.reset_menu.addSeparator()
        act_all = self.reset_menu.addAction(tr("Alle Standardprofile wiederherstellen", "Restore all default profiles"), self._restore_builtins)
        self.act_revert.setToolTip(tr("Zurück zum zuletzt gespeicherten Stand des aktiven Profils.", "Go back to the last saved state of the active profile."))
        self.act_factory.setToolTip(tr("Nur für Standardprofile: Auslieferungszustand wiederherstellen.", "Default profiles only: restore the shipped settings."))
        act_all.setToolTip(tr("Standardprofile neu anlegen. Eigene Profile bleiben.", "Recreate the default profiles. Your own profiles are kept."))
        self.reset_menu.setToolTipsVisible(True)
        self.reset_btn.setMenu(self.reset_menu)
        delete = QPushButton(QIcon.fromTheme("edit-delete"), tr("Löschen", "Delete"))
        delete.setToolTip(tr("Gewähltes Profil löschen.", "Delete the selected profile."))
        delete.clicked.connect(self._delete_profile)
        for w in (save, save_as, self.reset_btn, delete):
            bar.addWidget(w)
        v.addLayout(bar)
        return v

    # Widgets mit Bindung
    def _toggle(self, name: str) -> Toggle:
        t = Toggle()
        t.setToolTip(TOOLTIPS.get(name, ""))
        t.toggled.connect(lambda on, n=name: self.bind.queue(n, int(on)))
        self.bind.add(name, t)
        return t

    def _slider(self, name: str, fmt=str, orientation=Qt.Horizontal) -> QSlider:
        ctl = self.ctls.get(name)
        slider = QSlider(orientation)
        slider.setRange(ctl.minimum if ctl else 0, ctl.maximum if ctl else 100)
        slider.format_value = fmt
        slider.setToolTip(TOOLTIPS.get(name, ""))
        slider.value_label = QLabel(fmt(slider.value()))
        slider.value_label.setMinimumWidth(64)
        slider.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def moved(v, n=name, s=slider):
            s.value_label.setText(s.format_value(v))
            self.bind.queue(n, v)

        slider.valueChanged.connect(moved)
        self.bind.add(name, slider)
        return slider

    def _combo(self, name: str) -> QComboBox:
        box = QComboBox()
        ctl = self.ctls.get(name)
        fill_items(box, ctl.items if ctl else [])
        box.setToolTip(TOOLTIPS.get(name, ""))
        box.currentIndexChanged.connect(lambda i, n=name: self.bind.queue(n, i))
        self.bind.add(name, box)
        return box

    @staticmethod
    def _slider_row(slider: QSlider) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(slider, 1)
        h.addWidget(slider.value_label)
        return w

    def _switch_row(self, toggle: QCheckBox, title: str, desc: str = "") -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(QLabel(f"<b>{title}</b>"))
        if desc:
            texts.addWidget(QLabel(desc, objectName="muted"))
        h.addLayout(texts, 1)
        h.addWidget(toggle)
        w.setToolTip(toggle.toolTip())
        return w

    # Seiten
    def _page_output(self) -> QWidget:
        out, ov = card(tr("Ausgang", "Output"), tr("Wohin die AE-5 den Ton schickt.", "Where the AE-5 sends the sound."))
        row = QHBoxLayout()
        self.port_group = QButtonGroup(self)
        self.btn_hp = QPushButton(QIcon.fromTheme("audio-headphones"), tr("  Kopfhörer\n  Buchse an der Karte", "  Headphones\n  Jack on the card"), objectName="outputChoice")
        self.btn_sp = QPushButton(QIcon.fromTheme("audio-speakers"), tr("  Lautsprecher\n  Line-Out hinten", "  Speakers\n  Rear line out"), objectName="outputChoice")
        for i, b in enumerate((self.btn_hp, self.btn_sp)):
            b.setCheckable(True)
            b.setIconSize(QSize(32, 32))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.port_group.addButton(b, i)
            row.addWidget(b)
        self.btn_hp.setToolTip(tr("Ton über die Kopfhörerbuchse der AE-5 (mit eigenem Verstärker).", "Sound through the headphone jack of the AE-5 (with its own amplifier)."))
        self.btn_sp.setToolTip(tr("Ton über die Line-Out-Buchsen hinten (für Lautsprecher/Verstärker).", "Sound through the rear line-out jacks (for speakers/amplifiers)."))
        self.port_group.idClicked.connect(self._port_chosen)
        ov.addLayout(row)

        dev, dv = card(tr("Gerät", "Device"), tr("Gilt für alle Profile.", "Applies to all profiles."))
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        self.gain_box = QComboBox()
        gain = self.ctls.get(HEADPHONE_GAIN)
        fill_items(self.gain_box, gain.items if gain else [])
        self.gain_box.setToolTip(TOOLTIPS[HEADPHONE_GAIN])
        self.gain_box.currentIndexChanged.connect(self._gain_chosen)
        self.bind.add(HEADPHONE_GAIN, self.gain_box)
        for text, widget, name in ((tr("Kopfhörer-Verstärkung", "Headphone gain"), self.gain_box, HEADPHONE_GAIN),
                                   (tr("Klangfilter (DAC)", "DAC filter"), self._combo(SOUND_FILTER), SOUND_FILTER),
                                   (tr("Lautsprecher-Kanäle", "Speaker channels"), self._combo(SURROUND_CONFIG), SURROUND_CONFIG)):
            lab = QLabel(text)
            lab.setToolTip(TOOLTIPS[name])
            form.addRow(lab, widget)
        dv.addLayout(form)
        hint = QLabel(tr("Die Verstärkung passend zur Impedanz des Kopfhörers wählen "
                         "(z. B. 250 Ω → Hoch).",
                         "Choose the gain to match the impedance of your headphones "
                         "(e.g. 250 Ω → High)."), objectName="muted")
        hint.setWordWrap(True)
        dv.addWidget(hint)
        return page(out, dev)

    def _page_effects(self) -> QWidget:
        master, mv = card()
        self.outfx = self._toggle(OUTFX_SWITCH)
        mv.addWidget(self._switch_row(self.outfx, tr("Klangeffekte", "Sound effects"), tr("Hauptschalter für alle Effekte dieser Seite", "Master switch for all effects on this page")))

        fx, fv = card(tr("Effekte", "Effects"))
        for switch, level, name, desc in EFFECTS:
            t = self._toggle(switch)
            s = self._slider(level, lambda v: f"{v} %")
            fv.addWidget(self._switch_row(t, name, desc))
            fv.addWidget(self._slider_row(s))
            self.effect_rows.append((t, s))
            if switch.startswith("FX: X-Bass"):
                xo = self._slider(XBASS_CROSSOVER, lambda v: f"{v * 10} Hz")
                row = QHBoxLayout()
                row.addWidget(QLabel(tr("Übergangsfrequenz", "Crossover"), objectName="muted"))
                row.addWidget(self._slider_row(xo), 1)
                fv.addLayout(row)
                self.effect_rows.append((t, xo))
            if switch.startswith("FX: Smart Volume"):
                row = QHBoxLayout()
                row.addWidget(QLabel(tr("Modus", "Mode"), objectName="muted"))
                mode = self._combo(SMART_VOLUME_MODE)
                row.addWidget(mode, 1)
                fv.addLayout(row)
                self.effect_rows.append((t, mode))
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("color: transparent;")
            fv.addWidget(line)
        return page(master, fx)

    def _page_eq(self) -> QWidget:
        top, tv = card()
        self.eq_toggle = self._toggle(EQ_SWITCH)
        tv.addWidget(self._switch_row(self.eq_toggle, "Equalizer", tr("10 Bänder, je −24 … +24 dB", "10 bands, −24 … +24 dB each")))
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Voreinstellung", "Preset")))
        self.preset_box = QComboBox(minimumWidth=180)
        preset = self.ctls.get(EQ_PRESET)
        self.preset_items = preset.items if preset else []
        fill_items(self.preset_box, self.preset_items)
        self.preset_box.setToolTip(TOOLTIPS[EQ_PRESET])
        self.preset_box.currentIndexChanged.connect(self._preset_chosen)
        self.bind.add(EQ_PRESET, self.preset_box)
        row.addWidget(self.preset_box)
        self.preset_note = QLabel(tr("angepasst", "customized"), objectName="badge")
        self.preset_note.setToolTip(tr("Die Bänder weichen von der gewählten Voreinstellung ab.", "The bands differ from the selected preset."))
        self.preset_note.setVisible(False)
        row.addWidget(self.preset_note)
        row.addStretch()
        flat = QPushButton(QIcon.fromTheme("edit-clear"), tr("Alle Bänder auf 0 dB", "All bands to 0 dB"))
        flat.setToolTip(tr("Setzt alle zehn Bänder auf 0 dB (linearer Klang).", "Sets all ten bands to 0 dB (flat response)."))
        flat.clicked.connect(lambda: self._set_bands([0] * 10))
        row.addWidget(flat)
        tv.addLayout(row)

        bands, bv = card()
        self.eq_curve = EqCurve()
        self.eq_curve.setToolTip(tr("Klangkurve aus den zehn Bändern (links Bass, rechts Höhen).", "Frequency curve of the ten bands (bass on the left, treble on the right)."))
        bv.addWidget(self.eq_curve)
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        self.band_sliders: list[QSlider] = []
        for i, (band, freq) in enumerate(zip(EQ_BANDS, EQ_FREQUENCIES)):
            s = self._slider(band, lambda r: f"{eq_db(r):+d} dB", Qt.Vertical)
            s.setToolTip(tr(f"Band {freq} Hz: anheben (+) oder absenken (−), −24 … +24 dB", f"Band {freq} Hz: boost (+) or cut (−), −24 … +24 dB"))
            s.setMinimumHeight(200)
            s.valueChanged.connect(self._update_eq_curve)
            self.band_sliders.append(s)
            grid.addWidget(s.value_label, 0, i, Qt.AlignHCenter)
            grid.addWidget(s, 1, i, Qt.AlignHCenter)
            grid.addWidget(QLabel(f"{freq} Hz", objectName="muted"), 2, i, Qt.AlignHCenter)
        bv.addLayout(grid)
        return page(top, bands)

    def _page_mic(self) -> QWidget:
        dev, dv = card(tr("Eingang der AE-5", "AE-5 input"), tr("Gilt für alle Profile. Betrifft nur ein Mikrofon an der AE-5, nicht USB-Mikrofone.", "Applies to all profiles. Only affects a microphone connected to the AE-5, not USB microphones."))
        form = QFormLayout()
        form.addRow(tr("Quelle", "Source"), self._combo(INPUT_SOURCE))
        form.addRow(tr("Vorverstärkung", "Boost"), self._combo(MIC_BOOST))
        dv.addLayout(form)
        fx, fv = card(tr("Mikrofon-Effekte", "Microphone effects"))
        for name, text in MIC_SWITCHES:
            fv.addWidget(self._switch_row(self._toggle(name), text))
        form2 = QFormLayout()
        form2.addRow(tr("Pegel (Mic SVM)", "Level (Mic SVM)"), self._slider_row(self._slider(MIC_SVM_LEVEL, lambda v: f"{v} %")))
        form2.addRow(tr("Stimmeffekt", "Voice effect"), self._combo(VOICE_FX))
        fv.addLayout(form2)
        return page(dev, fx)

    def _page_system(self) -> QWidget:
        info, iv = card("Status")
        self.sys_info = QLabel()
        self.sys_info.setTextFormat(Qt.RichText)
        self.sys_info.setWordWrap(True)
        iv.addWidget(self.sys_info)
        buttons = QHBoxLayout()
        check = QPushButton(QIcon.fromTheme("dialog-ok-apply"), tr("Karte prüfen", "Check card"))
        check.setToolTip(tr("Spielt kurz Stille ab und prüft, ob die Karte Daten annimmt.", "Plays a short moment of silence and checks whether the card accepts data."))
        check.clicked.connect(lambda: self._run_tool("--check"))
        restart = QPushButton(QIcon.fromTheme("view-refresh"), tr("Karte neu starten", "Restart card"))
        restart.setToolTip(tr("Startet nur die AE-5 neu (ohne PC-Neustart, ca. 15–20 s ohne Ton).", "Restarts only the AE-5 (no reboot, about 15–20 s without sound)."))
        restart.clicked.connect(lambda: self._run_tool("--auto"))
        buttons.addWidget(check)
        buttons.addWidget(restart)
        buttons.addStretch()
        iv.addLayout(buttons)
        log, lv = card(tr("Ausgabe", "Output log"))
        self.sys_log = QPlainTextEdit(readOnly=True)
        self.sys_log.setMinimumHeight(200)
        self.sys_log.setPlaceholderText(tr("Ausgabe von Prüfung und Neustart erscheint hier.", "Output of check and restart appears here."))
        lv.addWidget(self.sys_log)
        return page(info, log)

    # --- Tray ----------------------------------------------------------------
    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon.fromTheme("audio-card"), self)
        self.tray.setToolTip("AE-5 Control")
        self.tray.activated.connect(self._tray_activated)
        self.tray_menu = QMenu()
        self.tray.setContextMenu(self.tray_menu)
        self._fill_tray_menu()
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_window()

    def _fill_tray_menu(self) -> None:
        if self.tray is None:
            return
        menu = self.tray_menu
        menu.clear()
        self.tray_group = QActionGroup(menu)
        active = self.store.active_profile()
        for name in self.store.list_profiles():
            act = QAction(name, menu, checkable=True, checked=(name == active))
            act.triggered.connect(lambda _=False, n=name: self.apply_profile(n))
            self.tray_group.addAction(act)
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction(tr("Öffnen", "Open"), self._show_window)
        menu.addAction(tr("Karte neu starten", "Restart card"), lambda: self._run_tool("--auto"))
        menu.addSeparator()
        menu.addAction(tr("Beenden", "Quit"), self._quit)

    # --- Profile -------------------------------------------------------------
    def _fill_profiles(self) -> None:
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        names = self.store.list_profiles()
        for n in names:
            self.profile_box.addItem(n + (tr("  · Standard", "  · default") if self.store.is_builtin(n) else ""), n)
        active = self.store.active_profile()
        if active in names:
            self.profile_box.setCurrentIndex(names.index(active))
        self.profile_box.blockSignals(False)
        self._fill_tray_menu()

    def apply_profile(self, name: str) -> None:
        self.bind.flush()
        try:
            core.apply_profile(name, self.mixer, self.store)
        except (MixerError, KeyError) as exc:
            QMessageBox.warning(self, "AE-5 Control", str(exc))
            return
        self._fill_profiles()
        self.refresh()
        self.show_status(tr(f"Profil „{name}“ eingespielt.", f"Profile “{name}” applied."))

    def _profile_chosen(self, index: int) -> None:
        self.apply_profile(self.profile_box.itemData(index))

    def _save_profile(self) -> None:
        name = self.store.active_profile()
        if not name:
            self._save_profile_as()
            return
        self.bind.flush()
        self.store.save_profile(name, snapshot(self.ctls, PROFILE_CONTROLS))
        self.after_change()
        self.show_status(tr(f"Profil „{name}“ gespeichert.", f"Profile “{name}” saved."))

    def _save_profile_as(self) -> None:
        name, ok = QInputDialog.getText(self, tr("Profil speichern", "Save profile"), tr("Name des Profils:", "Profile name:"))
        if not ok or not name.strip():
            return
        self.bind.flush()
        try:
            self.store.save_profile(name.strip(), snapshot(self.ctls, PROFILE_CONTROLS))
        except ValueError as exc:
            QMessageBox.warning(self, "AE-5 Control", str(exc))
            return
        self.store.set_active_profile(name.strip())
        self._fill_profiles()
        self.after_change()

    def _delete_profile(self) -> None:
        name = self.profile_box.currentData()
        if not name:
            return
        extra = tr("\n\nStandardprofile lassen sich über „Zurücksetzen“ wiederherstellen.", "\n\nDefault profiles can be restored via “Reset”.") if self.store.is_builtin(name) else ""
        if QMessageBox.question(self, tr("Profil löschen", "Delete profile"), tr(f"Profil „{name}“ wirklich löschen?{extra}", f"Really delete profile “{name}”?{extra}")) != QMessageBox.Yes:
            return
        self.store.delete_profile(name)
        self._fill_profiles()
        self.after_change()

    def _revert(self) -> None:
        name = self.store.active_profile()
        if name:
            self.apply_profile(name)
            self.show_status(tr(f"Änderungen verworfen – „{name}“ wie gespeichert.", f"Changes discarded – “{name}” as saved."))

    def _factory_reset(self) -> None:
        name = self.store.active_profile()
        if not name or not self.store.is_builtin(name):
            return
        self.store.restore_builtin(name)
        self.apply_profile(name)
        self.show_status(tr(f"„{name}“ auf Werkseinstellung zurückgesetzt.", f"“{name}” reset to factory default."))

    def _restore_builtins(self) -> None:
        if QMessageBox.question(
                self, tr("Standardprofile wiederherstellen", "Restore default profiles"),
                tr("Alle Standardprofile auf Werkseinstellung zurücksetzen?\nEigene Profile bleiben unverändert.",
                   "Reset all default profiles to factory settings?\nYour own profiles stay unchanged.")) != QMessageBox.Yes:
            return
        self.store.restore_all_builtins()
        active = self.store.active_profile()
        if active and self.store.is_builtin(active):
            self.apply_profile(active)
        else:
            self._fill_profiles()
        self.show_status(tr("Standardprofile wiederhergestellt.", "Default profiles restored."))

    # --- Ausgabe / Equalizer -------------------------------------------------
    def _port_chosen(self, button_id: int) -> None:
        sink = pipewire.sink_name()
        if not sink:
            self.show_status(tr("PipeWire-Ausgabe der AE-5 nicht gefunden.", "PipeWire output of the AE-5 not found."))
            return
        port = pipewire.PORT_HEADPHONES if button_id == 0 else pipewire.PORT_SPEAKERS
        try:
            pipewire.set_port(sink, port)
        except RuntimeError as exc:
            self.show_status(tr(f"Umschalten fehlgeschlagen: {exc}", f"Switching failed: {exc}"))
        QTimer.singleShot(500, self.refresh)

    def _gain_chosen(self, index: int) -> None:
        ctl = self.ctls.get(HEADPHONE_GAIN)
        current = ctl.values[0] if ctl and ctl.values else 0
        if index > current:
            answer = QMessageBox.question(
                self, tr("Lauter!", "Louder!"),
                tr("Eine höhere Verstärkung macht den Kopfhörer deutlich lauter.\n\n"
                   f"Lautstärke vorher zur Sicherheit auf {SAFE_VOLUME} % senken?",
                   "A higher gain makes the headphones much louder.\n\n"
                   f"Lower the volume to {SAFE_VOLUME} % first, to be safe?"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if answer == QMessageBox.Cancel:
                self.gain_box.blockSignals(True)
                self.gain_box.setCurrentIndex(current)
                self.gain_box.blockSignals(False)
                return
            if answer == QMessageBox.Yes:
                sink = pipewire.sink_name()
                vol = pipewire.volume_percent(sink) if sink else None
                if sink and vol is not None and vol > SAFE_VOLUME:
                    pipewire.set_volume_percent(sink, SAFE_VOLUME)
        self.bind.queue(HEADPHONE_GAIN, index)

    def _preset_chosen(self, index: int) -> None:
        """Voreinstellung setzen und die Band-Regler mitziehen (macht der Treiber nicht)."""
        self.bind.queue(EQ_PRESET, index)
        name = self.preset_items[index] if 0 <= index < len(self.preset_items) else None
        if name in EQ_PRESET_DB:
            self._set_bands(EQ_PRESET_DB[name])
        if not self.eq_toggle.isChecked():
            self.eq_toggle.setChecked(True)  # sonst hört man die Voreinstellung nicht

    def _set_bands(self, dbs: list[float]) -> None:
        for slider, db in zip(self.band_sliders, dbs):
            slider.setValue(eq_raw(db))  # löst valueChanged -> queue aus

    def _update_eq_curve(self) -> None:
        self.eq_curve.set_values([s.value() for s in self.band_sliders], self.eq_toggle.isChecked())
        idx = self.preset_box.currentIndex()
        name = self.preset_items[idx] if 0 <= idx < len(self.preset_items) else None
        expected = [eq_raw(d) for d in EQ_PRESET_DB.get(name, [])]
        self.preset_note.setVisible(bool(expected) and expected != [s.value() for s in self.band_sliders])

    def _sync_dependencies(self) -> None:
        fx_on = self.outfx.isChecked()
        for toggle, widget in self.effect_rows:
            toggle.setEnabled(fx_on)
            widget.setEnabled(fx_on and toggle.isChecked())
        for s in self.band_sliders:
            s.setEnabled(self.eq_toggle.isChecked())
        self._update_eq_curve()

    def _run_tool(self, arg: str) -> None:
        if self.proc and self.proc.state() != QProcess.NotRunning:
            return
        self.nav.setCurrentRow(4)
        self._show_window()
        self.sys_log.appendPlainText(f"$ ae5-recover.sh {arg}")
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._tool_output)
        self.proc.finished.connect(lambda code, _status: self._tool_done(arg, code))
        self.proc.start(str(TOOLS / "ae5-recover.sh"), [arg])

    def _tool_output(self) -> None:
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace").rstrip()
        if text:
            self.sys_log.appendPlainText(text)

    def _tool_done(self, arg: str, code: int) -> None:
        self.sys_log.appendPlainText(tr(f"(fertig, Rückgabewert {code})\n", f"(done, exit code {code})\n"))
        if arg == "--auto":
            self.refresh()

    # --- Anzeige -------------------------------------------------------------
    def refresh(self) -> None:
        ok = self._read_controls()
        self.pages.setEnabled(ok)
        if not ok:
            self.show_status(tr("AE-5 gerade nicht verfügbar (startet evtl. neu) …", "AE-5 currently unavailable (possibly restarting) …"))
            return
        self.bind.refresh()
        sink = pipewire.sink_name()
        port = pipewire.active_port(sink) if sink else None
        for b, p in ((self.btn_hp, pipewire.PORT_HEADPHONES), (self.btn_sp, pipewire.PORT_SPEAKERS)):
            b.blockSignals(True)
            b.setChecked(port == p)
            b.blockSignals(False)
        self._port_text = {pipewire.PORT_HEADPHONES: tr("Kopfhörer", "Headphones"),
                           pipewire.PORT_SPEAKERS: tr("Lautsprecher", "Speakers")}.get(port, tr("Ausgang unbekannt", "unknown output"))
        if self.isVisible():
            self._update_system(sink)
        self.after_change()

    def after_change(self) -> None:
        self._sync_dependencies()
        name = self.store.active_profile()
        modified = False
        if name and self.ctls:
            try:
                saved = self.store.load_profile(name)
                modified = snapshot(self.ctls, list(saved)) != saved
            except KeyError:
                pass
        self.modified_badge.setVisible(modified)
        self.act_revert.setEnabled(modified)
        self.act_factory.setEnabled(bool(name) and self.store.is_builtin(name))
        self.subtitle.setText(f"{getattr(self, '_port_text', '–')}  ·  " + tr("Profil", "Profile") + f": {name or '–'}"
                              + (tr("  (geändert)", "  (modified)") if modified else ""))

    def _update_system(self, sink: str | None) -> None:
        def service(unit: str) -> str:
            r = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True)
            return tr("✔ läuft", "✔ running") if r.stdout.strip() == "active" else "<span style='color:#d33'>" + tr("✖ aus", "✖ off") + "</span>"

        chip = "?"
        for p in Path("/sys/class/sound").glob("hwC*D*"):
            try:
                if (p / "vendor_id").read_text().strip() == "0x11020011":
                    chip = (p / "chip_name").read_text().strip()
            except OSError:
                pass
        self.sys_info.setText(
            "<table cellspacing='6'>"
            f"<tr><td>{tr('Karte', 'Card')}</td><td><b>{chip}</b></td></tr>"
            f"<tr><td>{tr('PipeWire-Ausgabe', 'PipeWire output')}</td><td>{sink or '–'} ({self._port_text})</td></tr>"
            f"<tr><td>{tr('Absturz-Wächter', 'Crash watchdog')}</td><td>{service('ae5-watchdog.service')}</td></tr>"
            f"<tr><td>{tr('Verstärker-Wächter', 'Amplifier guard')}</td><td>{service('ae5-amp-guard.service')}</td></tr>"
            f"<tr><td>Version</td><td>AE-5 Control {__version__}</td></tr></table>")

    def show_status(self, text: str) -> None:
        self.status_label.setText(text)

    # --- Fenster / Tray ------------------------------------------------------
    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def _toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self._show_window()

    def _quit(self) -> None:
        self.quitting = True
        self.bind.flush()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        self.bind.flush()
        if self.tray is not None and not self.quitting:
            self.hide()
            event.ignore()
        else:
            event.accept()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("AE-5 Control")
    app.setDesktopFileName("ae5-control")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(start_hidden="--tray" in argv)  # noqa: F841 – muss am Leben bleiben
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
