"""Vérifie EnumWindows et WM_CLOSE sur une fenêtre Win32 créée par le test."""
import unittest
import win32api
import win32con
import win32gui

from windows import _list_windows


class NativeTests(unittest.TestCase):
    def test_actual_unity_window_detection_and_gentle_close(self):
        instance = win32api.GetModuleHandle(None)
        received = []
        def procedure(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_CLOSE:
                received.append(msg)
                win32gui.DestroyWindow(hwnd)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        cls = win32gui.WNDCLASS()
        cls.hInstance = instance
        cls.lpszClassName = "UnityWndClass"
        cls.lpfnWndProc = procedure
        atom = win32gui.RegisterClass(cls)
        hwnd = win32gui.CreateWindow(atom, "Reliane-QA - Cra - 3.0 - Release", win32con.WS_OVERLAPPEDWINDOW,
                                     50, 50, 320, 160, 0, 0, instance, None)
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            self.assertIn((hwnd, "Reliane-QA - Cra - 3.0 - Release"), _list_windows("Unity"))
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            win32gui.PumpWaitingMessages()
            self.assertIn(win32con.WM_CLOSE, received)
            self.assertFalse(win32gui.IsWindow(hwnd))
        finally:
            if win32gui.IsWindow(hwnd):
                win32gui.DestroyWindow(hwnd)
            win32gui.UnregisterClass(atom, instance)
