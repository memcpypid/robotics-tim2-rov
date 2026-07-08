"""
Message Dispatcher untuk MAVLink.
Bertugas mendistribusikan pesan-pesan yang masuk dari loop pembaca utama ke fungsi-fungsi
callback atau sensor yang mendaftar (subscribe) berdasarkan tipe pesan (misal: 'ATTITUDE', 'SYS_STATUS').
"""
import threading
from typing import Callable, Dict, List, Any

class MessageDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Any], None]]] = {}
        self._all_message_listeners: List[Callable[[Any], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, msg_type: str, callback: Callable[[Any], None]):
        """
        Mendaftarkan callback function untuk tipe pesan tertentu.
        Contoh: dispatcher.subscribe("ATTITUDE", self._on_attitude_msg)
        """
        with self._lock:
            if msg_type not in self._listeners:
                self._listeners[msg_type] = []
            if callback not in self._listeners[msg_type]:
                self._listeners[msg_type].append(callback)

    def unsubscribe(self, msg_type: str, callback: Callable[[Any], None]):
        """Menghapus callback dari daftar subscribe."""
        with self._lock:
            if msg_type in self._listeners and callback in self._listeners[msg_type]:
                self._listeners[msg_type].remove(callback)

    def subscribe_all(self, callback: Callable[[Any], None]):
        """Mendaftarkan callback yang akan dipanggil untuk *setiap* pesan MAVLink yang masuk."""
        with self._lock:
            if callback not in self._all_message_listeners:
                self._all_message_listeners.append(callback)

    def dispatch(self, msg):
        """
        Mengirimkan objek pesan MAVLink ke semua subscriber yang mendaftar.
        Dipanggil dari dalam loop pembaca MAVClient.
        """
        if msg is None:
            return

        msg_type = msg.get_type()
        if msg_type == 'BAD_DATA':
            return

        with self._lock:
            # Panggil listener khusus untuk tipe pesan ini
            specific_listeners = list(self._listeners.get(msg_type, []))
            # Panggil listener umum
            all_listeners = list(self._all_message_listeners)

        for callback in specific_listeners:
            try:
                callback(msg)
            except Exception as e:
                print(f"[Dispatcher Error] Gagal menjalankan callback untuk pesan '{msg_type}': {e}")

        for callback in all_listeners:
            try:
                callback(msg)
            except Exception as e:
                print(f"[Dispatcher Error] Gagal menjalankan global callback untuk pesan '{msg_type}': {e}")
