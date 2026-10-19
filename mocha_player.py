#!/usr/bin/env python3
"""
Mocha Player - offline music player with a Catppuccin Mocha UI.
Just run:  python mocha_player.py   (use .pyw on Windows to hide the console)

Features: library scanning (folders/files/drag & drop), cover art, search,
sortable columns, favorites, shuffle, repeat, seek, volume, media keys,
remembers your library between sessions.
"""
import sys, os, json, random, subprocess


def _ensure(pkg, mod):
    try:
        __import__(mod)
    except ImportError:
        print(f"Installing {pkg} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


_ensure("PySide6", "PySide6")
_ensure("mutagen", "mutagen")

from pathlib import Path
from mutagen import File as MutagenFile
from PySide6.QtCore import Qt, QUrl, QThread, Signal, QRectF
from PySide6.QtGui import (QPixmap, QColor, QPainter, QPainterPath, QFont,
                           QLinearGradient, QKeySequence, QShortcut)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QSlider,
    QLineEdit, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QStackedWidget, QMenu,
    QStyle, QSizePolicy)

# ----------------------------------------------------------------- palette
C = dict(
    rosewater="#f5e0dc", flamingo="#f2cdcd", pink="#f5c2e7", mauve="#cba6f7",
    red="#f38ba8", maroon="#eba0ac", peach="#fab387", yellow="#f9e2af",
    green="#a6e3a1", teal="#94e2d5", sky="#89dceb", sapphire="#74c7ec",
    blue="#89b4fa", lavender="#b4befe", text="#cdd6f4", subtext1="#bac2de",
    subtext0="#a6adc8", overlay2="#9399b2", overlay1="#7f849c",
    overlay0="#6c7086", surface2="#585b70", surface1="#45475a",
    surface0="#313244", base="#1e1e2e", mantle="#181825", crust="#11111b")

EXTS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"}
STATE_FILE = Path.home() / ".mocha_player" / "state.json"

QSS = f"""
* {{ font-family: 'Segoe UI','Inter','SF Pro Text','Ubuntu',sans-serif;
     font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#root {{ background: {C['base']}; }}
QToolTip {{ background: {C['surface0']}; color: {C['text']};
            border: 1px solid {C['surface1']}; padding: 4px; }}

QFrame#sidebar {{ background: {C['mantle']}; border-right: 1px solid {C['surface0']}; }}
QLabel#logo {{ font-size: 20px; font-weight: 700; color: {C['mauve']}; }}
QLabel#section {{ color: {C['overlay0']}; font-size: 11px; font-weight: 600; }}
QLabel#status {{ color: {C['overlay1']}; font-size: 11px; }}

QPushButton#nav, QPushButton#action {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 8px;
    background: transparent; color: {C['subtext0']}; font-weight: 600; }}
QPushButton#nav:hover, QPushButton#action:hover {{ background: {C['surface0']}; color: {C['text']}; }}
QPushButton#nav:checked {{ background: {C['surface0']}; color: {C['mauve']}; }}
QPushButton#action {{ color: {C['lavender']}; }}

QLabel#h1 {{ font-size: 28px; font-weight: 700; }}
QLabel#sub {{ color: {C['overlay1']}; }}
QLabel#empty {{ color: {C['overlay0']}; font-size: 15px; }}
QLineEdit#search {{
    background: {C['surface0']}; border: 1px solid {C['surface0']};
    border-radius: 18px; padding: 8px 16px; min-width: 240px; selection-background-color: {C['mauve']};
    selection-color: {C['crust']}; }}
QLineEdit#search:focus {{ border: 1px solid {C['mauve']}; }}

QTableWidget {{ background: transparent; border: none; outline: none; gridline-color: transparent; }}
QTableWidget::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:hover {{ background: {C['mantle']}; }}
QTableWidget::item:selected {{ background: {C['surface0']}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {C['overlay1']}; border: none;
    border-bottom: 1px solid {C['surface0']}; padding: 6px 8px; font-weight: 600; }}
QHeaderView::section:hover {{ color: {C['text']}; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C['surface1']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['surface2']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

QFrame#player {{ background: {C['crust']}; border-top: 1px solid {C['surface0']}; }}
QLabel#np_title {{ font-size: 14px; font-weight: 700; }}
QLabel#np_artist {{ color: {C['subtext0']}; font-size: 12px; }}
QLabel#time {{ color: {C['overlay1']}; font-size: 11px; min-width: 38px; }}

QPushButton#ctl {{ background: transparent; border: none; font-size: 18px;
    color: {C['subtext1']}; padding: 6px; border-radius: 8px; }}
QPushButton#ctl:hover {{ color: {C['text']}; }}
QPushButton#ctl:checked {{ color: {C['mauve']}; }}
QPushButton#fav {{ background: transparent; border: none; font-size: 18px; color: {C['overlay1']}; }}
QPushButton#fav:hover {{ color: {C['red']}; }}
QPushButton#fav:checked {{ color: {C['red']}; }}
QPushButton#play {{ background: {C['mauve']}; color: {C['crust']}; border: none;
    border-radius: 22px; font-size: 18px; }}
QPushButton#play:hover {{ background: {C['lavender']}; }}

QSlider::groove:horizontal {{ height: 4px; background: {C['surface1']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {C['mauve']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {C['text']}; width: 12px; height: 12px;
    margin: -4px 0; border-radius: 6px; }}
QSlider::handle:horizontal:hover {{ background: {C['rosewater']}; }}

QMenu {{ background: {C['mantle']}; border: 1px solid {C['surface1']}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 8px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C['surface0']}; color: {C['mauve']}; }}
QMenu::separator {{ height: 1px; background: {C['surface0']}; margin: 4px 8px; }}
"""


# ----------------------------------------------------------------- helpers
def fmt(ms):
    s = max(0, int(ms // 1000))
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def read_meta(path):
    title, artist, album, dur = Path(path).stem, "Unknown Artist", "Unknown Album", 0
    try:
        f = MutagenFile(path, easy=True)
        if f is not None:
            if f.info is not None:
                dur = int(f.info.length * 1000)
            title = (f.get("title") or [title])[0]
            artist = (f.get("artist") or [artist])[0]
            album = (f.get("album") or [album])[0]
    except Exception:
        pass
    return dict(path=path, title=str(title), artist=str(artist),
                album=str(album), duration=dur)


def read_cover(path):
    try:
        f = MutagenFile(path)
        if f is not None:
            if getattr(f, "pictures", None):
                return f.pictures[0].data
            tags = f.tags
            if tags is not None:
                if hasattr(tags, "getall"):
                    apic = tags.getall("APIC")
                    if apic:
                        return apic[0].data
                if "covr" in tags:
                    return bytes(tags["covr"][0])
    except Exception:
        pass
    folder = Path(path).parent
    for name in ("cover", "folder", "front", "album"):
        for ext in (".jpg", ".jpeg", ".png"):
            p = folder / (name + ext)
            if p.exists():
                return p.read_bytes()
    return None


def rounded(pix, size, radius):
    pix = pix.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    p.drawPixmap((size - pix.width()) // 2, (size - pix.height()) // 2, pix)
    p.end()
    return out


def placeholder(size, radius):
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(C["mauve"]))
    g.setColorAt(1, QColor(C["blue"]))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, g)
    p.setPen(QColor(C["crust"]))
    f = QFont()
    f.setPixelSize(int(size * 0.5))
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "♪")
    p.end()
    return out


class Scanner(QThread):
    done = Signal(list)

    def __init__(self, paths, known):
        super().__init__()
        self.paths, self.known = paths, known

    def run(self):
        files = []
        for p in self.paths:
            if os.path.isdir(p):
                for root, _, names in os.walk(p):
                    for n in sorted(names):
                        files.append(os.path.join(root, n))
            else:
                files.append(p)
        found = []
        for f in files:
            if Path(f).suffix.lower() in EXTS and f not in self.known:
                found.append(read_meta(f))
        self.done.emit(found)


class ClickSlider(QSlider):
    """Slider that jumps to where you click."""
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > 0:
            v = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(e.position().x()), self.width())
            self.setValue(v)
            self.sliderMoved.emit(v)
        super().mousePressEvent(e)


class TrackTable(QTableWidget):
    space_pressed = Signal()
    enter_pressed = Signal()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space:
            self.space_pressed.emit()
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.enter_pressed.emit()
            return
        super().keyPressEvent(e)


# ----------------------------------------------------------------- main window
class MochaPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mocha Player")
        self.resize(1180, 740)
        self.setMinimumSize(920, 580)
        self.setAcceptDrops(True)

        self.tracks, self.by_path, self.favs = [], {}, set()
        self.view, self.queue, self.history = [], [], []
        self.qpos, self.current = -1, None
        self.page, self.sort_col, self.sort_rev = "library", None, False
        self.shuffle, self.repeat, self.seeking = False, 0, False
        self.scanner, self.pending = None, []

        self.audio = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)

        self._build_ui()
        self._wire()
        self._load_state()
        self.refresh_table()
        self._set_cover(None)

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # sidebar
        sb = QFrame(objectName="sidebar")
        sb.setFixedWidth(230)
        sl = QVBoxLayout(sb)
        sl.setContentsMargins(16, 20, 16, 16)
        sl.setSpacing(4)
        sl.addWidget(QLabel("♫  Mocha Player", objectName="logo"))
        sl.addSpacing(18)
        sl.addWidget(QLabel("BROWSE", objectName="section"))
        self.btn_lib = QPushButton("♪   Library", objectName="nav", checkable=True, checked=True)
        self.btn_fav = QPushButton("♥   Favorites", objectName="nav", checkable=True)
        sl.addWidget(self.btn_lib)
        sl.addWidget(self.btn_fav)
        sl.addSpacing(14)
        sl.addWidget(QLabel("ADD MUSIC", objectName="section"))
        self.btn_add_folder = QPushButton("＋   Add Folder", objectName="action")
        self.btn_add_files = QPushButton("＋   Add Files", objectName="action")
        sl.addWidget(self.btn_add_folder)
        sl.addWidget(self.btn_add_files)
        sl.addStretch(1)
        self.status = QLabel("", objectName="status")
        self.status.setWordWrap(True)
        sl.addWidget(self.status)
        body.addWidget(sb)

        # main area
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(28, 24, 28, 8)
        ml.setSpacing(10)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.lbl_page = QLabel("Library", objectName="h1")
        self.lbl_count = QLabel("", objectName="sub")
        titles.addWidget(self.lbl_page)
        titles.addWidget(self.lbl_count)
        head.addLayout(titles)
        head.addStretch(1)
        self.search = QLineEdit(objectName="search")
        self.search.setPlaceholderText("🔍  Search songs, artists, albums…")
        self.search.setClearButtonEnabled(True)
        head.addWidget(self.search, 0, Qt.AlignVCenter)
        ml.addLayout(head)

        self.stack = QStackedWidget()
        self.lbl_empty = QLabel("", objectName="empty")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.lbl_empty)

        self.table = TrackTable(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Artist", "Album", "", "Time"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        h = self.table.horizontalHeader()
        h.setHighlightSections(False)
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(4, 44)
        self.table.setColumnWidth(5, 70)
        self.stack.addWidget(self.table)
        ml.addWidget(self.stack, 1)
        body.addWidget(main, 1)

        # player bar
        bar = QFrame(objectName="player")
        bar.setFixedHeight(98)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(20, 10, 20, 10)

        left = QHBoxLayout()
        left.setSpacing(12)
        self.cover = QLabel()
        self.cover.setFixedSize(68, 68)
        left.addWidget(self.cover)
        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.addStretch(1)
        self.lbl_title = QLabel("Nothing playing", objectName="np_title")
        self.lbl_artist = QLabel("Pick a song to start", objectName="np_artist")
        txt.addWidget(self.lbl_title)
        txt.addWidget(self.lbl_artist)
        txt.addStretch(1)
        left.addLayout(txt)
        self.btn_heart = QPushButton("♡", objectName="fav", checkable=True)
        self.btn_heart.setToolTip("Add to favorites")
        left.addWidget(self.btn_heart)
        leftw = QWidget()
        leftw.setLayout(left)
        leftw.setFixedWidth(340)
        bl.addWidget(leftw)

        center = QVBoxLayout()
        center.setSpacing(4)
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        ctl.addStretch(1)
        self.btn_shuffle = QPushButton("⇄", objectName="ctl", checkable=True)
        self.btn_prev = QPushButton("⏮", objectName="ctl")
        self.btn_play = QPushButton("▶", objectName="play")
        self.btn_play.setFixedSize(44, 44)
        self.btn_next = QPushButton("⏭", objectName="ctl")
        self.btn_repeat = QPushButton("⟳", objectName="ctl", checkable=True)
        self.btn_shuffle.setToolTip("Shuffle")
        self.btn_repeat.setToolTip("Repeat: off")
        for b in (self.btn_shuffle, self.btn_prev, self.btn_play, self.btn_next, self.btn_repeat):
            b.setCursor(Qt.PointingHandCursor)
            ctl.addWidget(b)
        ctl.addStretch(1)
        center.addLayout(ctl)
        seek = QHBoxLayout()
        self.lbl_cur = QLabel("0:00", objectName="time")
        self.lbl_cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_tot = QLabel("0:00", objectName="time")
        self.seek = ClickSlider(Qt.Horizontal)
        self.seek.setRange(0, 0)
        seek.addWidget(self.lbl_cur)
        seek.addWidget(self.seek, 1)
        seek.addWidget(self.lbl_tot)
        center.addLayout(seek)
        bl.addLayout(center, 1)

        right = QHBoxLayout()
        right.addStretch(1)
        self.btn_mute = QPushButton("🔊", objectName="ctl")
        self.vol = ClickSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(70)
        self.vol.setFixedWidth(110)
        right.addWidget(self.btn_mute)
        right.addWidget(self.vol)
        rightw = QWidget()
        rightw.setLayout(right)
        rightw.setFixedWidth(220)
        bl.addWidget(rightw)
        outer.addWidget(bar)

    def _wire(self):
        self.btn_lib.clicked.connect(lambda: self.set_page("library"))
        self.btn_fav.clicked.connect(lambda: self.set_page("favorites"))
        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_add_files.clicked.connect(self.add_files)
        self.search.textChanged.connect(self.refresh_table)

        self.table.cellDoubleClicked.connect(lambda r, c: self.play_row(r))
        self.table.cellClicked.connect(self.on_cell_click)
        self.table.enter_pressed.connect(
            lambda: self.play_row(self.table.currentRow()) if self.table.currentRow() >= 0 else None)
        self.table.space_pressed.connect(self.toggle_play)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.table.horizontalHeader().sectionClicked.connect(self.on_sort)

        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(lambda: self.next_track(False))
        self.btn_prev.clicked.connect(self.prev_track)
        self.btn_shuffle.toggled.connect(lambda v: setattr(self, "shuffle", v))
        self.btn_repeat.clicked.connect(self.cycle_repeat)
        self.btn_heart.clicked.connect(self.toggle_fav_current)
        self.btn_mute.clicked.connect(self.toggle_mute)

        self.seek.sliderPressed.connect(lambda: setattr(self, "seeking", True))
        self.seek.sliderReleased.connect(self._seek_release)
        self.seek.sliderMoved.connect(self._seek_moved)
        self.vol.valueChanged.connect(self.set_volume)

        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(self.on_duration)
        self.player.playbackStateChanged.connect(self.on_state)
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.errorOccurred.connect(
            lambda e, s: self.status.setText(f"Playback error: {s}"))

        sc = lambda key, fn: QShortcut(QKeySequence(key), self, activated=fn,
                                       context=Qt.ApplicationShortcut)
        sc(Qt.Key_MediaTogglePlayPause, self.toggle_play)
        sc(Qt.Key_MediaNext, lambda: self.next_track(False))
        sc(Qt.Key_MediaPrevious, self.prev_track)
        sc("Ctrl+Right", lambda: self.next_track(False))
        sc("Ctrl+Left", self.prev_track)
        sc("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        sc("Ctrl+O", self.add_folder)

    # ------------------------------------------------------------- state
    def _load_state(self):
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        self.tracks = [t for t in d.get("tracks", []) if os.path.exists(t["path"])]
        self.by_path = {t["path"]: t for t in self.tracks}
        self.favs = {p for p in d.get("favs", []) if p in self.by_path}
        self.vol.setValue(d.get("volume", 70))
        self.set_volume(self.vol.value())
        self.btn_shuffle.setChecked(d.get("shuffle", False))
        self.repeat = d.get("repeat", 0)
        self._update_repeat_btn()

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(dict(
                tracks=self.tracks, favs=sorted(self.favs), volume=self.vol.value(),
                shuffle=self.shuffle, repeat=self.repeat)), encoding="utf-8")
        except Exception as e:
            print("Could not save state:", e)

    def closeEvent(self, e):
        self._save_state()
        self.player.stop()
        super().closeEvent(e)

    # ------------------------------------------------------------- library
    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a music folder", str(Path.home()))
        if d:
            self.start_scan([d])

    def add_files(self):
        fs, _ = QFileDialog.getOpenFileNames(
            self, "Choose songs", str(Path.home()),
            "Audio (*.mp3 *.flac *.wav *.ogg *.m4a *.aac *.opus)")
        if fs:
            self.start_scan(fs)

    def start_scan(self, paths):
        if self.scanner and self.scanner.isRunning():
            self.pending.append(paths)
            return
        self.status.setText("Scanning…")
        self.scanner = Scanner(paths, set(self.by_path))
        self.scanner.done.connect(self.on_scanned)
        self.scanner.start()

    def on_scanned(self, found):
        for t in found:
            if t["path"] not in self.by_path:
                self.tracks.append(t)
                self.by_path[t["path"]] = t
        self.status.setText(f"Added {len(found)} track(s)")
        self.refresh_table()
        self._save_state()
        if self.pending:
            self.start_scan(self.pending.pop(0))

    def remove_track(self, path):
        t = self.by_path.pop(path, None)
        if t:
            self.tracks.remove(t)
        self.favs.discard(path)
        self.refresh_table()
        self._save_state()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.start_scan(paths)

    # ------------------------------------------------------------- table
    def set_page(self, page):
        self.page = page
        self.btn_lib.setChecked(page == "library")
        self.btn_fav.setChecked(page == "favorites")
        self.lbl_page.setText("Library" if page == "library" else "Favorites")
        self.refresh_table()

    def on_sort(self, col):
        if col not in (1, 2, 3, 5):
            return
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        self.refresh_table()

    def refresh_table(self):
        q = self.search.text().strip().lower()
        rows = [t for t in self.tracks
                if (self.page == "library" or t["path"] in self.favs)
                and (not q or q in f'{t["title"]} {t["artist"]} {t["album"]}'.lower())]
        if self.sort_col is not None:
            key = {1: "title", 2: "artist", 3: "album", 5: "duration"}[self.sort_col]
            rows.sort(key=lambda t: t[key].lower() if isinstance(t[key], str) else t[key],
                      reverse=self.sort_rev)
        self.view = rows

        tb = self.table
        tb.setUpdatesEnabled(False)
        tb.setRowCount(len(rows))
        for r, t in enumerate(rows):
            vals = [str(r + 1), t["title"], t["artist"], t["album"],
                    "♥" if t["path"] in self.favs else "♡", fmt(t["duration"])]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (0, 4):
                    it.setTextAlignment(Qt.AlignCenter)
                elif c == 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tb.setItem(r, c, it)
            self._paint_row(r)
        tb.setUpdatesEnabled(True)

        total = sum(t["duration"] for t in rows)
        self.lbl_count.setText(f"{len(rows)} tracks · {fmt(total)}" if rows else "")
        if rows:
            self.stack.setCurrentIndex(1)
        else:
            if not self.tracks:
                self.lbl_empty.setText("Your library is empty\n\nDrop a folder here or click “Add Folder”")
            elif self.page == "favorites" and not q:
                self.lbl_empty.setText("No favorites yet\n\nClick the ♡ next to a song")
            else:
                self.lbl_empty.setText("No matches")
            self.stack.setCurrentIndex(0)

    def _paint_row(self, r):
        path = self.view[r]["path"]
        playing = path == self.current
        for c in range(6):
            it = self.table.item(r, c)
            if it is None:
                continue
            if playing:
                col = C["mauve"]
            elif c == 4:
                col = C["red"] if path in self.favs else C["overlay0"]
            elif c in (0, 2, 3, 5):
                col = C["subtext0"]
            else:
                col = C["text"]
            it.setForeground(QColor(col))
            f = it.font()
            f.setBold(playing or c == 1)
            it.setFont(f)
        self.table.item(r, 0).setText("♪" if playing else str(r + 1))

    def update_marks(self):
        for r in range(len(self.view)):
            self._paint_row(r)

    def on_cell_click(self, r, c):
        if c == 4 and r < len(self.view):
            self.toggle_fav(self.view[r]["path"])

    def context_menu(self, pos):
        r = self.table.rowAt(pos.y())
        if r < 0 or r >= len(self.view):
            return
        path = self.view[r]["path"]
        m = QMenu(self)
        a_play = m.addAction("▶  Play")
        a_fav = m.addAction("♡  Remove from favorites" if path in self.favs else "♥  Add to favorites")
        m.addSeparator()
        a_rm = m.addAction("✕  Remove from library")
        act = m.exec(self.table.viewport().mapToGlobal(pos))
        if act == a_play:
            self.play_row(r)
        elif act == a_fav:
            self.toggle_fav(path)
        elif act == a_rm:
            self.remove_track(path)

    # ------------------------------------------------------------- favorites
    def toggle_fav(self, path):
        if path in self.favs:
            self.favs.discard(path)
        else:
            self.favs.add(path)
        self.refresh_table()
        self._sync_heart()
        self._save_state()

    def toggle_fav_current(self):
        if self.current:
            self.toggle_fav(self.current)
        else:
            self.btn_heart.setChecked(False)

    def _sync_heart(self):
        fav = self.current in self.favs if self.current else False
        self.btn_heart.setChecked(fav)
        self.btn_heart.setText("♥" if fav else "♡")

    # ------------------------------------------------------------- playback
    def play_row(self, r):
        if r < 0 or r >= len(self.view):
            return
        self.queue = [t["path"] for t in self.view]
        self.qpos = r
        self.history.clear()
        self.load(self.queue[r])

    def load(self, path):
        t = self.by_path.get(path)
        if not t:
            return
        self.current = path
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.lbl_title.setText(self._elide(self.lbl_title, t["title"], 200))
        self.lbl_artist.setText(self._elide(self.lbl_artist, t["artist"], 200))
        self.lbl_title.setToolTip(t["title"])
        data = read_cover(path)
        self._set_cover(data)
        self.setWindowTitle(f'{t["title"]} — {t["artist"]}')
        self._sync_heart()
        self.update_marks()

    def _elide(self, label, text, width):
        return label.fontMetrics().elidedText(text, Qt.ElideRight, width)

    def _set_cover(self, data):
        pm = QPixmap()
        if data and pm.loadFromData(data):
            self.cover.setPixmap(rounded(pm, 68, 10))
        else:
            self.cover.setPixmap(placeholder(68, 10))

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.current:
            self.player.play()
        elif self.view:
            self.play_row(max(0, self.table.currentRow()))

    def next_track(self, auto=False):
        if not self.queue:
            return
        if auto and self.repeat == 2:
            self.player.setPosition(0)
            self.player.play()
            return
        n = len(self.queue)
        if self.shuffle and n > 1:
            self.history.append(self.qpos)
            new = random.choice([i for i in range(n) if i != self.qpos])
        else:
            new = self.qpos + 1
            if new >= n:
                if self.repeat == 1 or not auto:
                    new = 0
                else:
                    self.player.stop()
                    return
        self.qpos = new
        self.load(self.queue[new])

    def prev_track(self):
        if not self.queue:
            return
        if self.player.position() > 3000:
            self.player.setPosition(0)
            return
        if self.shuffle and self.history:
            self.qpos = self.history.pop()
        else:
            self.qpos = (self.qpos - 1) % len(self.queue)
        self.load(self.queue[self.qpos])

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        self._update_repeat_btn()

    def _update_repeat_btn(self):
        self.btn_repeat.setChecked(self.repeat > 0)
        self.btn_repeat.setText("⟳" if self.repeat < 2 else "⟳¹")
        self.btn_repeat.setToolTip(["Repeat: off", "Repeat: all", "Repeat: one"][self.repeat])

    def set_volume(self, v):
        self.audio.setVolume((v / 100) ** 2)
        self.btn_mute.setText("🔇" if v == 0 else "🔉" if v < 50 else "🔊")

    def toggle_mute(self):
        if self.vol.value() > 0:
            self._prev_vol = self.vol.value()
            self.vol.setValue(0)
        else:
            self.vol.setValue(getattr(self, "_prev_vol", 70))

    # ------------------------------------------------------------- player signals
    def on_position(self, pos):
        if not self.seeking:
            self.seek.setValue(pos)
        self.lbl_cur.setText(fmt(pos))

    def on_duration(self, dur):
        self.seek.setRange(0, dur)
        self.lbl_tot.setText(fmt(dur))

    def on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setText("⏸" if playing else "▶")

    def on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next_track(auto=True)
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.status.setText("Can't play this file, skipping")
            self.next_track(auto=True)

    def _seek_moved(self, v):
        self.player.setPosition(v)
        self.lbl_cur.setText(fmt(v))

    def _seek_release(self):
        self.seeking = False
        self.player.setPosition(self.seek.value())


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mocha Player")
    app.setStyleSheet(QSS)
    w = MochaPlayer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
