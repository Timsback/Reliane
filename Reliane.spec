# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files('customtkinter') + [('assets', 'assets')]
datas += collect_data_files('winrt', include_py_files=False)
hiddenimports = collect_submodules('winrt')

a = Analysis(['main.py'], pathex=[], binaries=[], datas=datas, hiddenimports=hiddenimports,
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=1)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Reliane-app', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon='assets/reliane.ico',
          version='assets/version_info.txt', uac_admin=False)
