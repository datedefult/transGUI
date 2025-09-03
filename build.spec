# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['trans.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        (r'E:\pycharmPro\transGUI\favicon.ico', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 设置为多文件模式（关键部分）
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='trans',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'E:\pycharmPro\transGUI\favicon.ico',          # 设置图标
)

# 多文件模式必须的COLLECT部分
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='trans',                # 输出目录名
    icon=r'E:\pycharmPro\transGUI\favicon.ico'           # 任务栏图标（可选）
)