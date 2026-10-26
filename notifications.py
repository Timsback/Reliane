"""Écoute facultative des notifications Dofus ; aucun toast n'est supprimé."""
import asyncio
import logging
import threading

try:
    from winrt.windows.ui.notifications import NotificationKinds
    from winrt.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


class NotificationWatcher:
    def __init__(self, config, on_names):
        self.config, self.on_names = config, on_names
        self.status = "Module Windows non installé" if not AVAILABLE else "Désactivé"
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not AVAILABLE or (self._thread and self._thread.is_alive()):
            return
        if not self.config.get("auto_focus_retro") or self.config.get("game_version") == "Unity":
            self.status = "Désactivé pour Unity" if self.config.get("game_version") == "Unity" else "Désactivé"
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            asyncio.run(self._loop())
        except Exception:
            self.status = "Accès aux notifications indisponible"
            logging.exception("Écoute des notifications")

    def stop(self):
        self._stop.set()

    async def _loop(self):
        self.status = "Autorisation Windows en attente"
        listener = UserNotificationListener.current
        access = await listener.request_access_async()
        if access != UserNotificationListenerAccessStatus.ALLOWED:
            self.status = "Accès refusé par Windows"
            return
        self.status, seen = "Écoute active", None
        while not self._stop.is_set():
            enabled = self.config.get("auto_focus_retro") and self.config.get("game_version") != "Unity"
            self.status = "Écoute active" if enabled else "Désactivé"
            try:
                notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
                ids = {n.id for n in notifs}
                if seen is not None and enabled:
                    for notif in notifs:
                        if notif.id not in seen and self._from_game(notif):
                            self.on_names(self._texts(notif))
                seen = ids
            except Exception:
                self.status = "Lecture temporairement indisponible"
            await asyncio.sleep(0.5)

    @staticmethod
    def _from_game(notif):
        try:
            source = notif.app_info.display_info.display_name.lower()
            return "dofus" in source or "ankama" in source
        except Exception:
            return False

    @staticmethod
    def _texts(notif):
        try:
            binding = notif.notification.visual.get_binding("ToastGeneric")
            return [element.text for element in binding.get_text_elements()] if binding else []
        except Exception:
            return []
