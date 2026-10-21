"""
core/stream.py — optional TCP telemetry feed (one JSON line per tick).

Listen with:  nc <pi-ip> 9000
Unauthenticated and unencrypted by design: it is meant for a closed pit
network. Do not expose port 9000 to an untrusted network.
"""

import json
import socket
import threading

from core.config import TELEMETRY_PORT


class TelemetryServer:
    def __init__(self, port=TELEMETRY_PORT):
        self.port = port
        self._running = False
        self._server = None
        self._clients = []
        self._lock = threading.Lock()

    @property
    def is_active(self):
        return self._running and self._server is not None

    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._serve, daemon=True).start()

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        with self._lock:
            clients, self._clients = self._clients, []
        for client in clients:
            try:
                client.close()
            except OSError:
                pass

    def _serve(self):
        server = None
        try:
            server = socket.socket()
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.port))
            server.listen(5)
            server.settimeout(1.0)
            self._server = server
            while self._running:
                try:
                    conn, _ = server.accept()
                    conn.settimeout(0.5)
                    with self._lock:
                        self._clients.append(conn)
                except socket.timeout:
                    continue
        except OSError:
            pass
        finally:
            if server:
                server.close()
            self._server = None
            self._running = False

    def broadcast(self, payload_factory):
        """payload_factory is only called when someone is actually listening."""
        with self._lock:
            if not self._clients:
                return
            clients = tuple(self._clients)
        data = (json.dumps(payload_factory()) + "\n").encode()
        dead = [c for c in clients if not _send(c, data)]
        if dead:
            with self._lock:
                for client in dead:
                    if client in self._clients:
                        self._clients.remove(client)


def _send(client, data):
    try:
        client.sendall(data)
        return True
    except OSError:
        try:
            client.close()
        except OSError:
            pass
        return False


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.5)
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
