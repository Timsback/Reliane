# -*- mode: python ; coding: utf-8 -*-
a = Analysis(['launcher.py'], pathex=[], binaries=[], datas=[], hiddenimports=[],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=1)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Reliane', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon='assets/reliane.ico', version='assets/version_info.txt', uac_admin=False)
