# -*- mode: python ; coding: utf-8 -*-
"""Спецификация PyInstaller для DevOps Academy.

Собирает приложение в один каталог (one-dir): так приложение стартует быстро,
а обновление можно установить заменой файлов. Контент курса включается целиком.

Сборка:  pyinstaller --noconfirm --clean packaging/devops_academy.spec
Результат: dist/DevOpsAcademy/ (Windows: DevOpsAcademy.exe)
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent
ICON = ROOT / "packaging" / "app.ico"

# Плагины Qt, нужные для отображения SVG-иллюстраций и стилей окон.
plugin_datas = collect_data_files(
    "PySide6",
    includes=[
        "Qt/plugins/imageformats/*",
        "Qt/plugins/iconengines/*",
        "Qt/plugins/platforms/*",
        "Qt/plugins/styles/*",
        "Qt/plugins/tls/*",
    ],
)

datas = [
    (str(ROOT / "content"), "content"),
] + plugin_datas

a = Analysis(
    [str(ROOT / "src" / "devops_academy" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "PySide6.QtNetwork"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtWebEngineCore",
        "tkinter", "unittest", "pydoc_data",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DevOpsAcademy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI-приложение без чёрного окна консоли
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DevOpsAcademy",
)
