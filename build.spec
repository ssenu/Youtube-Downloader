# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import tempfile

import imageio_ffmpeg
from PyInstaller.utils.hooks import collect_submodules

# ffmpeg_locator가 번들 안에서 'ffmpeg.exe'를 찾으므로 그 이름으로 복사해 넣는다.
_staged_dir = tempfile.mkdtemp(prefix="ytdl-build-")
_staged_ffmpeg = os.path.join(_staged_dir, "ffmpeg.exe")
shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(), _staged_ffmpeg)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[(_staged_ffmpeg, ".")],
    datas=[("assets/app.ico", "assets"), ("assets/chevron_down.png", "assets")],
    # yt-dlp는 extractor를 동적으로 import 하므로 정적 분석에 잡히지 않는다.
    hiddenimports=collect_submodules("yt_dlp.extractor"),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="yt-downloader",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app.ico",
)
