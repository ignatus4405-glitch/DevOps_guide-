# -*- mode: python ; coding: utf-8 -*-
"""Спецификация PyInstaller для DevOps Academy.

Собирает приложение в один каталог (one-dir): быстрый старт и простая замена файлов
при обновлении. Контент курса включается целиком, поэтому приложение работает офлайн.

Сборка:   pyinstaller --noconfirm --clean packaging/devops_academy.spec
Результат: dist/DevOpsAcademy/ (Windows: DevOpsAcademy.exe, Linux: DevOpsAcademy)
Проверка:  dist/DevOpsAcademy/DevOpsAcademy --self-test
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
ICON = ROOT / "packaging" / "app.ico"

datas = [
    (str(ROOT / "content"), "content"),          # курс: модули, уроки, тесты, схемы
    (str(ROOT / "VERSION"), "."),                # версия для диагностики
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "src"), str(ROOT / "packaging")],
    binaries=[],
    datas=datas,
    # QtSvg нужен для иллюстраций уроков; QtNetwork — для проверки обновлений
    # (импортируется по требованию, поэтому указываем явно).
    hiddenimports=["PySide6.QtSvg", "PySide6.QtNetwork"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Урезаем сборку: неиспользуемые модули Qt и стандартной библиотеки.
        "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras", "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic", "PySide6.Qt3DRender", "PySide6.QtBluetooth", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtMultimedia",
        "PySide6.QtNfc", "PySide6.QtOpenGL", "PySide6.QtPdf", "PySide6.QtPositioning",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtRemoteObjects", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebSockets",
        "tkinter", "unittest", "pydoc_data",
    ],
    noarchive=False,
    optimize=0,
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
    console=False,                     # GUI-приложение: без окна консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() and sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DevOpsAcademy",
)
