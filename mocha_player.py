#!/usr/bin/env python3
"""
Mocha Player - offline music player with a Catppuccin Mocha UI.
Run:  python mocha_player.py      (rename to .pyw on Windows to hide the console)

 * Library from folders / files / drag & drop, cover art, search, sortable columns
 * Playlists (create, rename, delete, drag songs onto them, right-click menu)
 * Favorites, shuffle, repeat, seek, volume, media keys
 * Download page: paste a YouTube link -> MP3 (only works when you're online)
Everything except downloading works fully offline.
"""
import sys, os, json, random, subprocess, socket, zlib, importlib, urllib.request
from datetime import datetime
from urllib.parse import urlparse
from string import Template


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
from PySide6.QtCore import (Qt, QUrl, QThread, Signal, QRectF, QMimeData, QTimer)
from PySide6.QtGui import (QPixmap, QColor, QPainter, QPainterPath, QFont,
                           QLinearGradient, QKeySequence, QShortcut, QPalette,
                           QDesktopServices, QFontDatabase)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QSlider,
    QLineEdit, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QStackedWidget, QMenu,
    QStyle, QScrollArea, QInputDialog, QMessageBox, QComboBox, QCheckBox,
    QProgressBar, QTextEdit, QDialog, QFontComboBox)

# ----------------------------------------------------------------- palette
C = dict(
    rosewater="#f5e0dc", flamingo="#f2cdcd", pink="#f5c2e7", mauve="#cba6f7",
    red="#f38ba8", maroon="#eba0ac", peach="#fab387", yellow="#f9e2af",
    green="#a6e3a1", teal="#94e2d5", sky="#89dceb", sapphire="#74c7ec",
    blue="#89b4fa", lavender="#b4befe", text="#cdd6f4", subtext1="#bac2de",
    subtext0="#a6adc8", overlay2="#9399b2", overlay1="#7f849c",
    overlay0="#6c7086", surface2="#585b70", surface1="#45475a",
    surface0="#313244", base="#1e1e2e", mantle="#181825", crust="#11111b")

# colours used to tell artists / playlists apart (like syntax highlighting)
ACCENT_KEYS = ["pink", "peach", "yellow", "teal", "sky", "sapphire",
               "flamingo", "lavender", "blue", "maroon", "green", "mauve"]


def key_for(s):
    return ACCENT_KEYS[zlib.crc32(s.encode("utf-8")) % len(ACCENT_KEYS)]


def accent_for(s):
    return C[key_for(s)]


EXTS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".opus"}
STATE_FILE = Path.home() / ".mocha_player" / "state.json"
MUSIC_DIR = Path.home() / "Music" / "Mocha Player"
DEFAULT_FONT = "JetBrains Mono"
DEFAULT_SIZE = 12
FONT_DIR = Path.home() / ".mocha_player" / "fonts"
FONT_BASE = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/"
FONT_FILES = ["JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf", "JetBrainsMono-Italic.ttf"]

QSS_T = Template("""
* { font-family: "$font", "JetBrains Mono", monospace; font-size: ${fsize}px; color: $text; }
QMainWindow, QWidget#root, QDialog { background: $base; }
QToolTip { background: $surface0; color: $text; border: 1px solid $surface1; padding: 4px; }

QFrame#sidebar { background: $mantle; border-right: 1px solid $surface0; }
QLabel#logo { font-size: 20px; font-weight: 700; }
QLabel#section { color: $overlay0; font-size: 11px; font-style: italic;
    font-family: "$font"; padding-top: 4px; }
QLabel#status { color: $overlay1; font-size: 11px; }
QLabel#sub { color: $overlay1; }
QLabel#h1 { font-size: 28px; font-weight: 700; }
QLabel#empty { color: $overlay0; font-size: 15px; }

QPushButton#nav, QPushButton#action {
    text-align: left; padding: 9px 14px; border: none; border-radius: 8px;
    background: transparent; color: $subtext0; font-weight: 600; }
QPushButton#nav:hover, QPushButton#action:hover { background: $surface0; color: $text; }
QPushButton#nav:checked { background: $surface0; color: $mauve; }
QPushButton#nav[dragover="true"] { background: $surface1; }
QPushButton#action { color: $lavender; }
QPushButton#plus { background: transparent; border: none; color: $green; font-size: 18px;
    font-weight: 700; min-width: 26px; max-width: 26px; border-radius: 6px; }
QPushButton#plus:hover { background: $surface0; }

QPushButton#cta { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $mauve, stop:1 $pink);
    color: $crust; border: none; border-radius: 18px; padding: 9px 24px; font-weight: 700; }
QPushButton#cta:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $lavender, stop:1 $flamingo); }
QPushButton#ghost { background: $surface0; color: $text; border: none; border-radius: 18px;
    padding: 9px 22px; font-weight: 600; }
QPushButton#ghost:hover { background: $surface1; }
QPushButton#small { background: $surface0; color: $subtext1; border: none; border-radius: 8px;
    padding: 8px 14px; font-weight: 600; }
QPushButton#small:hover { background: $surface1; color: $text; }
QPushButton#dl { background: $green; color: $crust; border: none; border-radius: 10px;
    padding: 10px 22px; font-weight: 700; }
QPushButton#dl:hover { background: $teal; }
QPushButton#dl:disabled { background: $surface1; color: $overlay0; }

QLineEdit#search { background: $surface0; border: 1px solid $surface0; border-radius: 18px;
    padding: 8px 16px; min-width: 250px; selection-background-color: $mauve; selection-color: $crust; }
QLineEdit#search:focus { border: 1px solid $mauve; }
QLineEdit#url { background: $crust; border: 1px solid $surface1; border-radius: 10px;
    padding: 10px 14px; selection-background-color: $green; selection-color: $crust; }
QLineEdit#url:focus { border: 1px solid $green; }
QLineEdit { background: $surface0; border: 1px solid $surface1; border-radius: 8px; padding: 6px 10px; }

QFrame#card { background: $mantle; border: 1px solid $surface0; border-radius: 14px; }
QTextEdit#log { background: $mantle; border: 1px solid $surface0; border-radius: 10px;
    padding: 8px; font-family: "$font"; font-size: 12px; }
QProgressBar { background: $surface0; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { border-radius: 4px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $green, stop:1 $teal); }
QComboBox { background: $surface0; border: 1px solid $surface1; border-radius: 8px;
    padding: 6px 12px; min-width: 200px; }
QComboBox:hover { border: 1px solid $mauve; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: $mantle; border: 1px solid $surface1; outline: none;
    selection-background-color: $surface0; selection-color: $mauve; }
QCheckBox { spacing: 8px; color: $subtext0; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid $surface2; background: $surface0; }
QCheckBox::indicator:checked { background: $green; border: 1px solid $green; }
QDialogButtonBox QPushButton { background: $surface0; border: none; border-radius: 8px;
    padding: 7px 18px; min-width: 70px; }
QDialogButtonBox QPushButton:hover { background: $surface1; color: $mauve; }

QTableWidget { background: transparent; border: none; outline: none; gridline-color: transparent; }
QTableWidget::item { padding: 4px 8px; border: none; }
QTableWidget::item:hover { background: $mantle; }
QTableWidget::item:selected { background: $surface0; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: $overlay1; border: none;
    border-bottom: 1px solid $surface0; padding: 6px 8px; font-weight: 600; }
QHeaderView::section:hover { color: $mauve; }
QTableCornerButton::section { background: transparent; border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $surface1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $surface2; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar:horizontal { height: 0; }

QFrame#player { background: $crust; border-top: 1px solid $surface0; }
QLabel#np_title { font-size: 14px; font-weight: 700; color: $lavender; }
QLabel#np_artist { font-size: 12px; }
QLabel#time_cur { color: $peach; font-size: 11px; min-width: 38px; font-family: "$font"; }
QLabel#time_tot { color: $overlay1; font-size: 11px; min-width: 38px; font-family: "$font"; }

QPushButton#ctl { background: transparent; border: none; font-size: 18px;
    color: $subtext1; padding: 6px; border-radius: 8px; }
QPushButton#ctl:hover { color: $text; }
QPushButton#ctl:checked { color: $mauve; }
QPushButton#fav { background: transparent; border: none; font-size: 18px; color: $overlay1; }
QPushButton#fav:hover, QPushButton#fav:checked { color: $red; }
QPushButton#play { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $mauve, stop:1 $pink);
    color: $crust; border: none; border-radius: 22px; font-size: 18px; }
QPushButton#play:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 $lavender, stop:1 $flamingo); }

QSlider::groove:horizontal { height: 4px; background: $surface1; border-radius: 2px; }
QSlider#seek::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $mauve, stop:1 $pink);
    border-radius: 2px; }
QSlider#vol::sub-page:horizontal { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 $blue, stop:1 $sapphire);
    border-radius: 2px; }
QSlider::handle:horizontal { background: $text; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: $rosewater; }

QMenu { background: $mantle; border: 1px solid $surface1; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 8px 22px; border-radius: 6px; }
QMenu::item:selected { background: $surface0; color: $mauve; }
QMenu::separator { height: 1px; background: $surface0; margin: 4px 8px; }
""")

def build_qss(family, size):
    """Stylesheet with the chosen font applied to every widget."""
    fam = family.replace('"', "")
    qss = QSS_T.substitute(C, font=fam, fsize=int(size))
    # per-accent colours for checked sidebar buttons (library=mauve, favorites=red, ...)
    for k in set(ACCENT_KEYS) | {"mauve", "red", "green"}:
        qss += f'\nQPushButton#nav[accent="{k}"]:checked {{ color: {C[k]}; }}'
    return qss


def load_font_prefs():
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    fam = d.get("font_family") or DEFAULT_FONT
    size = d.get("font_size") or DEFAULT_SIZE
    return fam, max(9, min(20, int(size)))


def load_local_fonts():
    """Register any JetBrains Mono files we downloaded earlier."""
    n = 0
    if FONT_DIR.exists():
        for p in FONT_DIR.glob("*.ttf"):
            if QFontDatabase.addApplicationFont(str(p)) >= 0:
                n += 1
    return n


def font_installed(family):
    return family in QFontDatabase.families()


def apply_app_font(app, family, size):
    f = QFont(family)
    f.setPixelSize(int(size))
    app.setFont(f)
    app.setStyleSheet(build_qss(family, size))


# ----------------------------------------------------------------- helpers
def fmt(ms):
    s = max(0, int(ms // 1000))
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def span(text, key):
    return f'<span style="color:{C[key]}">{text}</span>'


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


# ----------------------------------------------------------------- threads
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


class NetCheck(QThread):
    result = Signal(bool)

    def run(self):
        for host in (("www.youtube.com", 443), ("1.1.1.1", 53)):
            try:
                socket.create_connection(host, timeout=2.5).close()
                self.result.emit(True)
                return
            except OSError:
                pass
        self.result.emit(False)


class Cancelled(Exception):
    pass


class Downloader(QThread):
    progress = Signal(float, str)
    log = Signal(str, str)          # message, level (info/ok/warn/err)
    completed = Signal(list)        # list of mp3 paths
    failed = Signal(str)

    def __init__(self, url, outdir, playlist):
        super().__init__()
        self.url, self.outdir, self.playlist = url, Path(outdir), playlist
        self._cancel = False
        self._last_title = None

    def cancel(self):
        self._cancel = True

    def _ensure_deps(self):
        for pkg, mod in (("yt-dlp", "yt_dlp"), ("imageio-ffmpeg", "imageio_ffmpeg")):
            try:
                importlib.import_module(mod)
            except ImportError:
                self.log.emit(f"Installing {pkg} (first time only)…", "warn")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])
                importlib.invalidate_caches()
                importlib.import_module(mod)

    def _hook(self, d):
        if self._cancel:
            raise Cancelled("Cancelled")
        title = (d.get("info_dict") or {}).get("title")
        if title and title != self._last_title:
            self._last_title = title
            self.log.emit(f"Downloading “{title}”", "info")
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = done / total * 100 if total else 0
            spd = d.get("speed")
            sp = f"{spd / 1048576:.1f} MB/s" if spd else ""
            self.progress.emit(pct, f"Downloading…  {pct:.0f}%   {sp}")
        elif st == "finished":
            self.progress.emit(100, "Converting to MP3…")

    def _opts(self, ffmpeg, thumb):
        pps = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        if thumb:
            pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
        pps.append({"key": "FFmpegMetadata", "add_metadata": True})
        if thumb:
            pps.append({"key": "EmbedThumbnail"})
        return {
            "format": "bestaudio/best",
            "outtmpl": str(self.outdir / "%(title)s.%(ext)s"),
            "noplaylist": not self.playlist,
            "writethumbnail": thumb,
            "postprocessors": pps,
            "ffmpeg_location": ffmpeg,
            "progress_hooks": [self._hook],
            "quiet": True, "no_warnings": True, "no_color": True,
            "windowsfilenames": True,
            "retries": 5, "fragment_retries": 5,
        }

    @staticmethod
    def _paths(info, ydl):
        out = []
        for e in (info.get("entries") or [info]):
            if not e:
                continue
            fp = None
            for rd in e.get("requested_downloads") or []:
                fp = rd.get("filepath") or fp
            if not fp:
                fp = os.path.splitext(ydl.prepare_filename(e))[0] + ".mp3"
            if fp.lower().endswith(".mp3") and os.path.exists(fp):
                out.append(fp)
        return out

    def run(self):
        try:
            self._ensure_deps()
            import yt_dlp, imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            self.outdir.mkdir(parents=True, exist_ok=True)

            def attempt(thumb):
                with yt_dlp.YoutubeDL(self._opts(ffmpeg, thumb)) as ydl:
                    info = ydl.extract_info(self.url, download=True)
                    return self._paths(info, ydl)

            try:
                files = attempt(True)
            except Exception as e:
                if self._cancel:
                    raise
                self.log.emit("Cover art step failed, retrying without it…", "warn")
                files = attempt(False)
            if not files:
                raise RuntimeError("Download finished but no MP3 was produced.")
            self.completed.emit(files)
        except Exception as e:
            msg = "Cancelled" if self._cancel else str(e).replace("ERROR: ", "").strip()
            self.failed.emit(msg[:400])


class PipUpdater(QThread):
    log = Signal(str, str)

    def run(self):
        self.log.emit("Updating yt-dlp…", "info")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "--quiet", "yt-dlp"])
            self.log.emit("yt-dlp is up to date (restart the app if you already downloaded "
                          "something this session)", "ok")
        except Exception as e:
            self.log.emit(f"Update failed: {e}", "err")


class FontFetcher(QThread):
    """Downloads JetBrains Mono once (needs internet), then it's cached locally."""
    done = Signal(bool)

    def run(self):
        try:
            FONT_DIR.mkdir(parents=True, exist_ok=True)
            for name in FONT_FILES:
                dest = FONT_DIR / name
                if dest.exists() and dest.stat().st_size > 10000:
                    continue
                req = urllib.request.Request(FONT_BASE + name, headers={"User-Agent": "MochaPlayer"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                if len(data) < 10000:
                    raise ValueError("font download too small")
                tmp = dest.with_suffix(".part")
                tmp.write_bytes(data)
                tmp.replace(dest)
            self.done.emit(True)
        except Exception:
            self.done.emit(False)


# ----------------------------------------------------------------- widgets
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

    def mimeData(self, items):
        md = QMimeData()
        paths = [it.data(Qt.UserRole) for it in items if it.column() == 1]
        md.setText("\n".join(p for p in paths if p))
        return md


class PlaylistButton(QPushButton):
    dropped = Signal(str, list)

    def __init__(self, name, accent):
        super().__init__()
        self.name = name
        self.setObjectName("nav")
        self.setCheckable(True)
        self.setProperty("accent", accent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("♬   " + (name if len(name) <= 16 else name[:15] + "…"))
        self.setToolTip(name)

    def _hl(self, on):
        self.setProperty("dragover", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasText() and not md.hasUrls():
            e.acceptProposedAction()
            self._hl(True)
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._hl(False)

    def dropEvent(self, e):
        self._hl(False)
        paths = [p for p in e.mimeData().text().split("\n") if p]
        self.dropped.emit(self.name, paths)
        e.acceptProposedAction()


class SettingsDialog(QDialog):
    applied = Signal(str, int)

    def __init__(self, parent, family, size):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.family, self.size = family, size

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(12)
        title = QLabel("Settings", objectName="h1")
        title.setStyleSheet(f"color:{C['lavender']};")
        lay.addWidget(title)
        lay.addWidget(QLabel(f'{span("// font", "overlay0")}', objectName="section"))

        self.combo = QFontComboBox()
        self.combo.setEditable(False)
        self.combo.setCurrentFont(QFont(family))
        self.combo.currentFontChanged.connect(self._family_changed)
        lay.addWidget(self.combo)
        self.chk_mono = QCheckBox("Show monospaced fonts only")
        self.chk_mono.toggled.connect(self._mono_toggled)
        lay.addWidget(self.chk_mono)

        row = QHBoxLayout()
        row.addWidget(QLabel(f'{span("size", "mauve")} {span("=", "sky")}'))
        self.slider = ClickSlider(Qt.Horizontal, objectName="seek")
        self.slider.setRange(9, 20)
        self.slider.setValue(size)
        self.slider.valueChanged.connect(self._size_changed)
        self.lbl_size = QLabel(f"{size}px")
        self.lbl_size.setMinimumWidth(46)
        row.addWidget(self.slider, 1)
        row.addWidget(self.lbl_size)
        lay.addLayout(row)

        card = QFrame(objectName="card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        self.preview = QLabel("The quick brown fox jumps over the lazy dog\n"
                              "♪ Midnight City — M83     3:48     0123456789")
        self.preview.setWordWrap(True)
        cl.addWidget(self.preview)
        lay.addWidget(card)

        self.note = QLabel("", objectName="status")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)

        btns = QHBoxLayout()
        self.btn_reset = QPushButton(f"Reset to {DEFAULT_FONT}", objectName="small")
        self.btn_cancel = QPushButton("Cancel", objectName="ghost")
        self.btn_apply = QPushButton("Apply", objectName="cta")
        for b in (self.btn_reset, self.btn_cancel, self.btn_apply):
            b.setCursor(Qt.PointingHandCursor)
        btns.addWidget(self.btn_reset)
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_apply)
        lay.addLayout(btns)

        self.btn_reset.clicked.connect(self._reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply)
        self._refresh_preview()

    def _family_changed(self, f):
        self.family = f.family()
        self._refresh_preview()

    def _mono_toggled(self, on):
        self.combo.setFontFilters(QFontComboBox.MonospacedFonts if on else QFontComboBox.AllFonts)
        self.combo.setCurrentFont(QFont(self.family))

    def _size_changed(self, v):
        self.size = v
        self.lbl_size.setText(f"{v}px")
        self._refresh_preview()

    def _reset(self):
        self.family, self.size = DEFAULT_FONT, DEFAULT_SIZE
        self.slider.setValue(DEFAULT_SIZE)
        self.combo.setCurrentFont(QFont(DEFAULT_FONT))
        self._refresh_preview()

    def _refresh_preview(self):
        self.preview.setStyleSheet(
            f'font-family: "{self.family}"; font-size: {self.size}px; color: {C["text"]};')
        if self.family == DEFAULT_FONT and not font_installed(DEFAULT_FONT):
            self.note.setText("JetBrains Mono isn't installed yet — it downloads automatically "
                              "the next time you're online. Until then a system monospace font is used.")
        else:
            self.note.setText("")

    def _apply(self):
        self.applied.emit(self.family, self.size)
        self.accept()


# ----------------------------------------------------------------- main window
class MochaPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mocha Player")
        self.resize(1240, 780)
        self.setMinimumSize(960, 640)
        self.setAcceptDrops(True)

        self.tracks, self.by_path, self.favs = [], {}, set()
        self.playlists = {}
        self.pl_buttons = {}
        self.view, self.queue, self.history = [], [], []
        self.qpos, self.current = -1, None
        self.page, self.sort_col, self.sort_rev = "library", None, False
        self.shuffle, self.repeat, self.seeking = False, 0, False
        self.scanner, self.pending = None, []
        self.dl, self.updater, self._net, self.font_fetcher = None, None, None, None
        self.font_family, self.font_size = load_font_prefs()
        self._np = None
        self._play_id = 0
        self._advanced_for = None
        self.net_ok = False

        self.audio = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio)

        self._build_ui()
        self._wire()
        self._load_state()
        self.rebuild_playlist_buttons()
        self.refresh_combo()
        self._set_cover(None)
        self.set_page("library")

        self.net_timer = QTimer(self)
        self.net_timer.timeout.connect(self.check_net)
        self.net_timer.start(10000)
        self.check_net()

    # ------------------------------------------------------------- UI build
    def _comment(self, text):
        return QLabel(f"// {text}", objectName="section")

    def _nav(self, text, accent):
        b = QPushButton(text, objectName="nav", checkable=True)
        b.setProperty("accent", accent)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # ---- sidebar
        sb = QFrame(objectName="sidebar")
        sb.setFixedWidth(240)
        sl = QVBoxLayout(sb)
        sl.setContentsMargins(14, 18, 14, 14)
        sl.setSpacing(3)
        sl.addWidget(QLabel(
            f'{span("♫", "blue")}&nbsp; {span("Mocha", "mauve")} {span("Player", "pink")}',
            objectName="logo"))
        sl.addSpacing(12)
        sl.addWidget(self._comment("browse"))
        self.btn_lib = self._nav("♪   Library", "mauve")
        self.btn_fav = self._nav("♥   Favorites", "red")
        self.btn_dl = self._nav("⬇   Download", "green")
        for b in (self.btn_lib, self.btn_fav, self.btn_dl):
            sl.addWidget(b)
        sl.addSpacing(8)
        row = QHBoxLayout()
        row.addWidget(self._comment("playlists"))
        row.addStretch(1)
        self.btn_newpl = QPushButton("＋", objectName="plus")
        self.btn_newpl.setToolTip("New playlist")
        self.btn_newpl.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.btn_newpl)
        sl.addLayout(row)
        self.pl_scroll = QScrollArea()
        self.pl_scroll.setWidgetResizable(True)
        self.pl_scroll.setFrameShape(QFrame.NoFrame)
        self.pl_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.pl_scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setAutoFillBackground(False)
        self.pl_lay = QVBoxLayout(inner)
        self.pl_lay.setContentsMargins(0, 0, 0, 0)
        self.pl_lay.setSpacing(2)
        self.pl_lay.addStretch(1)
        self.pl_scroll.setWidget(inner)
        sl.addWidget(self.pl_scroll, 1)
        sl.addSpacing(6)
        sl.addWidget(self._comment("add music"))
        self.btn_add_folder = QPushButton("＋   Add Folder", objectName="action")
        self.btn_add_files = QPushButton("＋   Add Files", objectName="action")
        self.btn_settings = QPushButton("⚙   Settings", objectName="action")
        self.btn_settings.setStyleSheet(f"color:{C['overlay1']};")
        for b in (self.btn_add_folder, self.btn_add_files, self.btn_settings):
            b.setCursor(Qt.PointingHandCursor)
            sl.addWidget(b)
        sl.addSpacing(6)
        self.net_lbl = QLabel("", objectName="status")
        self.status = QLabel("", objectName="status")
        self.status.setWordWrap(True)
        sl.addWidget(self.net_lbl)
        sl.addWidget(self.status)
        body.addWidget(sb)

        # ---- main pages
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_tracks_page())
        self.pages.addWidget(self._build_download_page())
        body.addWidget(self.pages, 1)

        # ---- player bar
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
        self.lbl_artist.setStyleSheet(f"color:{C['overlay1']};")
        txt.addWidget(self.lbl_title)
        txt.addWidget(self.lbl_artist)
        txt.addStretch(1)
        left.addLayout(txt, 1)
        self.btn_heart = QPushButton("♡", objectName="fav", checkable=True)
        self.btn_heart.setToolTip("Add to favorites")
        self.btn_heart.setCursor(Qt.PointingHandCursor)
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
        self.lbl_cur = QLabel("0:00", objectName="time_cur")
        self.lbl_cur.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_tot = QLabel("0:00", objectName="time_tot")
        self.seek = ClickSlider(Qt.Horizontal, objectName="seek")
        self.seek.setRange(0, 0)
        seek.addWidget(self.lbl_cur)
        seek.addWidget(self.seek, 1)
        seek.addWidget(self.lbl_tot)
        center.addLayout(seek)
        bl.addLayout(center, 1)

        right = QHBoxLayout()
        right.addStretch(1)
        self.btn_mute = QPushButton("🔊", objectName="ctl")
        self.vol = ClickSlider(Qt.Horizontal, objectName="vol")
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

    def _build_tracks_page(self):
        tp = QWidget()
        tl = QVBoxLayout(tp)
        tl.setContentsMargins(28, 24, 28, 8)
        tl.setSpacing(12)
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
        head.addWidget(self.search, 0, Qt.AlignTop)
        tl.addLayout(head)

        acts = QHBoxLayout()
        self.btn_playall = QPushButton("▶   Play", objectName="cta")
        self.btn_shufall = QPushButton("⇄   Shuffle", objectName="ghost")
        for b in (self.btn_playall, self.btn_shufall):
            b.setCursor(Qt.PointingHandCursor)
            acts.addWidget(b)
        acts.addStretch(1)
        tl.addLayout(acts)

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
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QAbstractItemView.DragOnly)
        h = self.table.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col, al in ((0, Qt.AlignCenter), (4, Qt.AlignCenter), (5, Qt.AlignRight | Qt.AlignVCenter)):
            self.table.horizontalHeaderItem(col).setTextAlignment(al)
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        for c in (1, 2, 3):
            h.setSectionResizeMode(c, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        h.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(4, 44)
        self.table.setColumnWidth(5, 70)
        self.stack.addWidget(self.table)
        tl.addWidget(self.stack, 1)
        return tp

    def _build_download_page(self):
        dp = QWidget()
        dl = QVBoxLayout(dp)
        dl.setContentsMargins(28, 24, 28, 16)
        dl.setSpacing(14)
        t = QLabel("Download", objectName="h1")
        t.setStyleSheet(f"color:{C['green']};")
        dl.addWidget(t)
        dl.addWidget(QLabel(
            f'Paste a YouTube link and it becomes an {span("MP3", "peach")} '
            f'in your library — needs an internet connection.', objectName="sub"))

        card = QFrame(objectName="card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 18, 18, 18)
        cl.setSpacing(12)

        r1 = QHBoxLayout()
        r1.setSpacing(8)
        self.url = QLineEdit(objectName="url")
        self.url.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.btn_paste = QPushButton("Paste", objectName="small")
        self.btn_download = QPushButton("⬇   Download", objectName="dl")
        self.btn_cancel = QPushButton("Cancel", objectName="small")
        self.btn_cancel.hide()
        for b in (self.btn_paste, self.btn_download, self.btn_cancel):
            b.setCursor(Qt.PointingHandCursor)
        r1.addWidget(self.url, 1)
        r1.addWidget(self.btn_paste)
        r1.addWidget(self.btn_download)
        r1.addWidget(self.btn_cancel)
        cl.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(10)
        r2.addWidget(QLabel(f'{span("playlist", "mauve")} {span("=", "sky")}'))
        self.combo = QComboBox()
        r2.addWidget(self.combo)
        r2.addSpacing(14)
        self.chk_pl = QCheckBox("Download the whole playlist if the link has one")
        r2.addWidget(self.chk_pl)
        r2.addStretch(1)
        cl.addLayout(r2)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        cl.addWidget(self.progress)
        self.lbl_prog = QLabel("Ready", objectName="sub")
        cl.addWidget(self.lbl_prog)

        r3 = QHBoxLayout()
        r3.setSpacing(8)
        self.net_big = QLabel("", objectName="sub")
        r3.addWidget(self.net_big, 1)
        self.btn_recheck = QPushButton("Re-check", objectName="small")
        self.btn_update = QPushButton("Update yt-dlp", objectName="small")
        self.btn_open = QPushButton("Open folder", objectName="small")
        for b in (self.btn_recheck, self.btn_update, self.btn_open):
            b.setCursor(Qt.PointingHandCursor)
            r3.addWidget(b)
        cl.addLayout(r3)
        dl.addWidget(card)

        dl.addWidget(QLabel(f'{span("//", "overlay0")} {span("log", "overlay1")}',
                            objectName="section"))
        self.log_view = QTextEdit(objectName="log")
        self.log_view.setReadOnly(True)
        dl.addWidget(self.log_view, 1)
        dl.addWidget(QLabel(
            f"Saved to {MUSIC_DIR}. Only download content you own or have permission to save.",
            objectName="status"))
        return dp

    def _wire(self):
        self.btn_lib.clicked.connect(lambda: self.set_page("library"))
        self.btn_fav.clicked.connect(lambda: self.set_page("favorites"))
        self.btn_dl.clicked.connect(lambda: self.set_page("download"))
        self.btn_newpl.clicked.connect(lambda: self.new_playlist())
        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_settings.clicked.connect(self.open_settings)
        self.search.textChanged.connect(self.refresh_table)
        self.btn_playall.clicked.connect(self.play_all)
        self.btn_shufall.clicked.connect(self.shuffle_all)

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
            lambda e, s: self.say(f"Playback error: {s}", "red"))

        self.btn_paste.clicked.connect(
            lambda: self.url.setText(QApplication.clipboard().text().strip()))
        self.btn_download.clicked.connect(self.start_download)
        self.url.returnPressed.connect(self.start_download)
        self.btn_cancel.clicked.connect(lambda: self.dl and self.dl.cancel())
        self.btn_recheck.clicked.connect(self.check_net)
        self.btn_update.clicked.connect(self.update_ytdlp)
        self.btn_open.clicked.connect(self.open_music_dir)

        sc = lambda key, fn: QShortcut(QKeySequence(key), self, activated=fn,
                                       context=Qt.ApplicationShortcut)
        sc(Qt.Key_MediaTogglePlayPause, self.toggle_play)
        sc(Qt.Key_MediaNext, lambda: self.next_track(False))
        sc(Qt.Key_MediaPrevious, self.prev_track)
        sc("Ctrl+Right", lambda: self.next_track(False))
        sc("Ctrl+Left", self.prev_track)
        sc("Ctrl+F", lambda: (self.set_page("library") if self.page == "download" else None,
                              self.search.setFocus(), self.search.selectAll()))
        sc("Ctrl+O", self.add_folder)
        sc("Ctrl+,", self.open_settings)

    # ------------------------------------------------------------- misc UI
    def say(self, msg, color="overlay1"):
        self.status.setStyleSheet(f"color:{C[color]};")
        self.status.setText(msg)

    def log(self, msg, level="info"):
        tag, col = {"info": ("INFO", "blue"), "ok": ("OK", "green"),
                    "warn": ("WARN", "yellow"), "err": ("ERR", "red")}[level]
        msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'{span("[" + ts + "]", "overlay0")} {span(tag, col)} '
            f'<span style="color:{C["text"] if level != "err" else C["maroon"]}">{msg}</span>')

    # ------------------------------------------------------------- state
    def _load_state(self):
        try:
            d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        self.tracks = [t for t in d.get("tracks", []) if os.path.exists(t["path"])]
        self.by_path = {t["path"]: t for t in self.tracks}
        self.favs = {p for p in d.get("favs", []) if p in self.by_path}
        self.playlists = {n: [p for p in ps if p in self.by_path]
                          for n, ps in d.get("playlists", {}).items()}
        self.vol.setValue(d.get("volume", 70))
        self.set_volume(self.vol.value())
        self.btn_shuffle.setChecked(d.get("shuffle", False))
        self.repeat = d.get("repeat", 0)
        self._update_repeat_btn()

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(dict(
                tracks=self.tracks, favs=sorted(self.favs), playlists=self.playlists,
                volume=self.vol.value(), shuffle=self.shuffle, repeat=self.repeat,
                font_family=self.font_family, font_size=self.font_size)),
                encoding="utf-8")
        except Exception as e:
            print("Could not save state:", e)

    def closeEvent(self, e):
        self._save_state()
        self.player.stop()
        for th in (self.dl, self.scanner, self._net, self.updater, self.font_fetcher):
            if th is not None and th.isRunning():
                if isinstance(th, Downloader):
                    th.cancel()
                th.wait(3000)
        super().closeEvent(e)

    # ------------------------------------------------------------- pages
    def set_page(self, page):
        self.page = page
        self.btn_lib.setChecked(page == "library")
        self.btn_fav.setChecked(page == "favorites")
        self.btn_dl.setChecked(page == "download")
        for n, b in self.pl_buttons.items():
            b.setChecked(page == f"pl:{n}")
        if page == "download":
            self.pages.setCurrentIndex(1)
            self.check_net()
            return
        self.pages.setCurrentIndex(0)
        if page == "library":
            title, col = "Library", C["mauve"]
        elif page == "favorites":
            title, col = "Favorites", C["red"]
        else:
            title = page[3:]
            col = accent_for(title)
        self.lbl_page.setText(title)
        self.lbl_page.setStyleSheet(f"color:{col};")
        self.refresh_table()

    # ------------------------------------------------------------- playlists
    def rebuild_playlist_buttons(self):
        while self.pl_lay.count() > 1:
            item = self.pl_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self.pl_buttons = {}
        if not self.playlists:
            hint = QLabel("  press ＋ to create one", objectName="status")
            self.pl_lay.insertWidget(0, hint)
        for i, name in enumerate(self.playlists):
            b = PlaylistButton(name, key_for(name))
            b.setChecked(self.page == f"pl:{name}")
            b.clicked.connect(lambda _=False, n=name: self.set_page(f"pl:{n}"))
            b.dropped.connect(self.add_to_playlist)
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, n=name, btn=b: self.playlist_menu(n, btn.mapToGlobal(pos)))
            self.pl_lay.insertWidget(i, b)
            self.pl_buttons[name] = b

    def refresh_combo(self):
        cur = self.combo.currentData()
        self.combo.clear()
        self.combo.addItem("None — library only", None)
        for n in self.playlists:
            self.combo.addItem(f"♬  {n}", n)
        idx = self.combo.findData(cur)
        self.combo.setCurrentIndex(idx if idx >= 0 else 0)

    def new_playlist(self):
        name, ok = QInputDialog.getText(self, "New playlist", "Playlist name:")
        name = name.strip()
        if not ok or not name:
            return None
        if name not in self.playlists:
            self.playlists[name] = []
            self.rebuild_playlist_buttons()
            self.refresh_combo()
            self._save_state()
        return name

    def playlist_menu(self, name, global_pos):
        m = QMenu(self)
        a_play = m.addAction("▶  Play")
        a_ren = m.addAction("✎  Rename")
        m.addSeparator()
        a_del = m.addAction("✕  Delete playlist")
        act = m.exec(global_pos)
        if act == a_play:
            self.set_page(f"pl:{name}")
            self.play_all()
        elif act == a_ren:
            new, ok = QInputDialog.getText(self, "Rename playlist", "New name:", text=name)
            new = new.strip()
            if ok and new and new != name and new not in self.playlists:
                self.playlists = {(new if k == name else k): v for k, v in self.playlists.items()}
                if self.page == f"pl:{name}":
                    self.page = f"pl:{new}"
                self.rebuild_playlist_buttons()
                self.refresh_combo()
                self.set_page(self.page)
                self._save_state()
        elif act == a_del:
            if QMessageBox.question(
                    self, "Delete playlist",
                    f"Delete “{name}”? Your songs stay in the library.",
                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                del self.playlists[name]
                was = self.page == f"pl:{name}"
                self.rebuild_playlist_buttons()
                self.refresh_combo()
                if was:
                    self.set_page("library")
                self._save_state()

    def add_to_playlist(self, name, paths):
        pl = self.playlists.get(name)
        if pl is None:
            return
        n = 0
        for p in paths:
            if p in self.by_path and p not in pl:
                pl.append(p)
                n += 1
        self.say(f"Added {n} song(s) to {name}" if n else f"Already in {name}", "green")
        if self.page == f"pl:{name}":
            self.refresh_table()
        self._save_state()

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
        self.say("Scanning…", "yellow")
        self.scanner = Scanner(paths, set(self.by_path))
        self.scanner.done.connect(self.on_scanned)
        self.scanner.start()

    def on_scanned(self, found):
        for t in found:
            if t["path"] not in self.by_path:
                self.tracks.append(t)
                self.by_path[t["path"]] = t
        self.say(f"Added {len(found)} track(s)", "green")
        self.refresh_table()
        self._save_state()
        if self.pending:
            self.start_scan(self.pending.pop(0))

    def remove_track(self, path):
        t = self.by_path.pop(path, None)
        if t:
            self.tracks.remove(t)
        self.favs.discard(path)
        for pl in self.playlists.values():
            if path in pl:
                pl.remove(path)
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
    def on_sort(self, col):
        if col not in (1, 2, 3, 5):
            return
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        self.refresh_table()

    def _base_rows(self):
        if self.page == "library":
            return list(self.tracks)
        if self.page == "favorites":
            return [t for t in self.tracks if t["path"] in self.favs]
        if self.page.startswith("pl:"):
            return [self.by_path[p] for p in self.playlists.get(self.page[3:], [])
                    if p in self.by_path]
        return []

    def refresh_table(self):
        q = self.search.text().strip().lower()
        rows = [t for t in self._base_rows()
                if not q or q in f'{t["title"]} {t["artist"]} {t["album"]}'.lower()]
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
                if c == 1:
                    it.setData(Qt.UserRole, t["path"])
                tb.setItem(r, c, it)
            self._paint_row(r)
        tb.setUpdatesEnabled(True)

        total = sum(t["duration"] for t in rows)
        self.lbl_count.setText(
            f'{span(str(len(rows)), "peach")} tracks &nbsp;{span("·", "overlay0")}&nbsp; '
            f'{span(fmt(total), "sky")}' if rows else "")
        self.btn_playall.setVisible(bool(rows))
        self.btn_shufall.setVisible(bool(rows))
        if rows:
            self.stack.setCurrentIndex(1)
        else:
            if self.page.startswith("pl:") and not q:
                msg = (f'{span("Empty playlist", "mauve")}<br><br>Drag songs onto it, or right-click a '
                       f'song → {span("Add to playlist", "green")}')
            elif self.page == "favorites" and not q:
                msg = f'{span("No favorites yet", "red")}<br><br>Click the ♡ next to a song'
            elif not self.tracks:
                msg = (f'{span("Your library is empty", "mauve")}<br><br>Drop a folder here, or use '
                       f'{span("Add Folder", "lavender")} — or grab music on the '
                       f'{span("Download", "green")} page')
            else:
                msg = "No matches"
            self.lbl_empty.setText(msg)
            self.stack.setCurrentIndex(0)

    def _paint_row(self, r):
        t = self.view[r]
        path = t["path"]
        playing = path == self.current
        art_col = accent_for(t["artist"])
        for c in range(6):
            it = self.table.item(r, c)
            if it is None:
                continue
            if c == 0:
                col = C["green"] if playing else C["overlay0"]
            elif c == 1:
                col = C["mauve"] if playing else C["blue"]
            elif c == 2:
                col = art_col
            elif c == 3:
                col = C["teal"]
            elif c == 4:
                col = C["red"] if path in self.favs else C["overlay0"]
            else:
                col = C["peach"]
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
        sub = m.addMenu("＋  Add to playlist")
        acts = {}
        for n in self.playlists:
            acts[sub.addAction(f"♬  {n}")] = n
        if acts:
            sub.addSeparator()
        a_new = sub.addAction("＋  New playlist…")
        a_rmpl = None
        if self.page.startswith("pl:"):
            a_rmpl = m.addAction("−  Remove from this playlist")
        m.addSeparator()
        a_rm = m.addAction("✕  Remove from library")
        act = m.exec(self.table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act == a_play:
            self.play_row(r)
        elif act == a_fav:
            self.toggle_fav(path)
        elif act in acts:
            self.add_to_playlist(acts[act], [path])
        elif act == a_new:
            n = self.new_playlist()
            if n:
                self.add_to_playlist(n, [path])
        elif a_rmpl is not None and act == a_rmpl:
            pl = self.playlists.get(self.page[3:], [])
            if path in pl:
                pl.remove(path)
            self.refresh_table()
            self._save_state()
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
    def play_all(self):
        if self.view:
            self.play_row(random.randrange(len(self.view)) if self.shuffle else 0)

    def shuffle_all(self):
        self.btn_shuffle.setChecked(True)
        self.play_all()

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
        self._play_id += 1
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self._np = (t["title"], t["artist"])
        self._update_np_text()
        self.lbl_artist.setStyleSheet(f"color:{accent_for(t['artist'])};")
        self.lbl_title.setToolTip(t["title"])
        self._set_cover(read_cover(path))
        self.setWindowTitle(f'{t["title"]} — {t["artist"]}')
        self._sync_heart()
        self.update_marks()

    def _update_np_text(self):
        if self._np:
            self.lbl_title.setText(self._elide(self.lbl_title, self._np[0], 200))
            self.lbl_artist.setText(self._elide(self.lbl_artist, self._np[1], 200))

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
            self._play_id += 1
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
                    self.say("End of the list — turn on repeat (⟳) to keep going", "yellow")
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
        # Fallback: some backends go Stopped at the end without sending EndOfMedia
        if state == QMediaPlayer.PlaybackState.StoppedState and self.current:
            dur = self.player.duration()
            if dur > 0 and self.player.position() >= dur - 1500:
                self._schedule_advance()

    def on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._schedule_advance()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self.say("Can't play this file, skipping", "yellow")
            self._schedule_advance()

    def _schedule_advance(self):
        """Move to the next song once, a moment after the player finishes.
        Deferred so we never swap the media from inside the player's own signal."""
        if self._advanced_for == self._play_id:
            return
        self._advanced_for = self._play_id
        QTimer.singleShot(150, lambda: self.next_track(auto=True))

    def _seek_moved(self, v):
        self.player.setPosition(v)
        self.lbl_cur.setText(fmt(v))

    def _seek_release(self):
        self.seeking = False
        self.player.setPosition(self.seek.value())

    # ------------------------------------------------------------- font / settings
    def open_settings(self):
        dlg = SettingsDialog(self, self.font_family, self.font_size)
        dlg.applied.connect(self.apply_font)
        dlg.exec()

    def apply_font(self, family, size):
        self.font_family, self.font_size = family, size
        apply_app_font(QApplication.instance(), family, size)
        self.refresh_table()
        self._update_np_text()
        self._save_state()
        self.say(f"Font: {family} · {size}px", "green")

    def maybe_fetch_font(self):
        """Get JetBrains Mono once if it isn't installed or cached yet."""
        if font_installed(DEFAULT_FONT):
            return
        if self.font_fetcher is not None and self.font_fetcher.isRunning():
            return
        self.font_fetcher = FontFetcher()
        self.font_fetcher.done.connect(self._font_fetched)
        self.font_fetcher.start()

    def _font_fetched(self, ok):
        if ok and load_local_fonts() and font_installed(DEFAULT_FONT):
            self.apply_font(self.font_family, self.font_size)
            if self.font_family == DEFAULT_FONT:
                self.say("JetBrains Mono installed", "green")

    # ------------------------------------------------------------- network + download
    def check_net(self):
        if self._net is not None and self._net.isRunning():
            return
        self._net = NetCheck()
        self._net.result.connect(self.on_net)
        self._net.start()

    def on_net(self, ok):
        self.net_ok = ok
        if ok:
            self.net_lbl.setText(f'{span("●", "green")} online')
            self.net_big.setText(f'{span("●", "green")} Online — downloads available')
        else:
            self.net_lbl.setText(f'{span("●", "red")} offline')
            self.net_big.setText(f'{span("●", "red")} Offline — playback still works, '
                                 f'downloads are paused')
        self._refresh_dl_buttons()
        if ok:
            self.maybe_fetch_font()

    def _dl_running(self):
        return self.dl is not None and self.dl.isRunning()

    def _refresh_dl_buttons(self):
        running = self._dl_running()
        self.btn_download.setEnabled(self.net_ok and not running)
        self.btn_cancel.setVisible(running)
        self.btn_paste.setEnabled(not running)
        self.url.setEnabled(not running)

    def open_music_dir(self):
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(MUSIC_DIR)))

    def update_ytdlp(self):
        if not self.net_ok:
            self.log("You're offline — can't update.", "warn")
            return
        if self.updater is not None and self.updater.isRunning():
            return
        self.updater = PipUpdater()
        self.updater.log.connect(self.log)
        self.updater.start()

    def start_download(self):
        if self._dl_running():
            return
        if not self.net_ok:
            self.log("No internet connection.", "warn")
            return
        raw = self.url.text().strip()
        if not raw:
            self.log("Paste a link first.", "warn")
            return
        if not raw.lower().startswith("http"):
            raw = "https://" + raw
        u = urlparse(raw)
        if not u.netloc or "." not in u.netloc:
            self.log("That doesn't look like a valid link.", "err")
            return
        self.progress.setValue(0)
        self.lbl_prog.setText("Starting…")
        self.log(f"Fetching {raw}", "info")
        self.dl = Downloader(raw, MUSIC_DIR, self.chk_pl.isChecked())
        self.dl.progress.connect(self.on_dl_progress)
        self.dl.log.connect(self.log)
        self.dl.completed.connect(self.on_dl_done)
        self.dl.failed.connect(self.on_dl_failed)
        self.dl.finished.connect(self._refresh_dl_buttons)
        self.dl.start()
        self._refresh_dl_buttons()

    def on_dl_progress(self, pct, text):
        self.progress.setValue(int(pct))
        self.lbl_prog.setText(text)

    def on_dl_failed(self, msg):
        self.lbl_prog.setText("Failed" if msg != "Cancelled" else "Cancelled")
        self.log(msg, "err" if msg != "Cancelled" else "warn")
        self.log("If this keeps happening, press “Update yt-dlp” (YouTube changes often).", "info")

    def on_dl_done(self, files):
        added = []
        for p in files:
            if p not in self.by_path:
                meta = read_meta(p)
                self.tracks.append(meta)
                self.by_path[p] = meta
            added.append(p)
            self.log(f"Saved {Path(p).name}", "ok")
        pl = self.combo.currentData()
        if pl and pl in self.playlists:
            for p in added:
                if p not in self.playlists[pl]:
                    self.playlists[pl].append(p)
            self.log(f"Added {len(added)} song(s) to playlist “{pl}”", "ok")
        self.progress.setValue(100)
        self.lbl_prog.setText(f"Done — {len(added)} song(s) added")
        self.url.clear()
        self.refresh_table()
        self._save_state()


def apply_palette(app):
    p = QPalette()
    roles = {
        QPalette.Window: "base", QPalette.WindowText: "text", QPalette.Base: "mantle",
        QPalette.AlternateBase: "surface0", QPalette.Text: "text", QPalette.Button: "surface0",
        QPalette.ButtonText: "text", QPalette.Highlight: "mauve", QPalette.HighlightedText: "crust",
        QPalette.ToolTipBase: "surface0", QPalette.ToolTipText: "text",
        QPalette.PlaceholderText: "overlay0", QPalette.Link: "blue"}
    for role, key in roles.items():
        p.setColor(role, QColor(C[key]))
    app.setPalette(p)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mocha Player")
    app.setStyle("Fusion")
    apply_palette(app)
    load_local_fonts()
    fam, size = load_font_prefs()
    apply_app_font(app, fam, size)
    w = MochaPlayer()
    w.show()
    sys.exit(app.exec())
1

if __name__ == "__main__":
    main()