"""Chargement privé en mémoire de la police de formes : contours antialiasés.

AddFontResourceExW peut échouer dans certains environnements Windows. Le
chargement mémoire ne demande aucune installation de police sur le système.
"""
import ctypes
from ctypes import wintypes
import importlib.util
import logging
from pathlib import Path

_resources = []


def prepare_fonts():
    spec = importlib.util.find_spec("customtkinter")
    if not spec or not spec.origin:
        return False
    font_path = Path(spec.origin).parent / "assets" / "fonts" / "CustomTkinter_shapes_font.otf"
    try:
        data = font_path.read_bytes()
        buffer = ctypes.create_string_buffer(data)
        count = wintypes.DWORD()
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi.AddFontMemResourceEx.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        gdi.AddFontMemResourceEx.restype = wintypes.HANDLE
        handle = gdi.AddFontMemResourceEx(buffer, len(data), None, ctypes.byref(count))
        if handle and count.value:
            _resources.append((handle, buffer))
            return True
    except (OSError, AttributeError):
        logging.exception("Chargement de la police de contours")
    return False


def enable_antialiasing():
    from customtkinter.windows.widgets.core_rendering import DrawEngine
    if _resources:
        DrawEngine.preferred_drawing_method = "font_shapes"
    return DrawEngine.preferred_drawing_method == "font_shapes"
