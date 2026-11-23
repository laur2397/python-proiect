"""O singura instanta (faza 15, W-094): al doilea lansaj trimite argumentele
(fisierele, `--action ...`) primei instante si se inchide.

Canalul e un `QLocalServer` cu nume per utilizator (pe Windows, o conductă cu
nume; pe macOS/Linux, un socket local). Mesajul e o lista JSON de argumente.
"""

from __future__ import annotations

import getpass
import json
import re
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

TIMEOUT_MS = 1500


def server_name() -> str:
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = "user"
    return "DocuLens-" + re.sub(r"[^A-Za-z0-9_-]", "_", user)


def send_to_running(args: Sequence[str], *, name: str | None = None) -> bool:
    """W-094: True daca o instanta ruleaza si a primit argumentele."""
    socket = QLocalSocket()
    socket.connectToServer(name or server_name())
    if not socket.waitForConnected(TIMEOUT_MS):
        return False
    socket.write(json.dumps(list(args)).encode("utf-8"))
    socket.flush()
    ok = socket.waitForBytesWritten(TIMEOUT_MS)
    socket.disconnectFromServer()
    return ok


class InstanceServer(QObject):
    """Prima instanta asculta; `received` da argumentele celei de-a doua."""

    received = Signal(list)

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name or server_name()
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept)

    def listen(self) -> bool:
        if self.server.listen(self.name):
            return True
        QLocalServer.removeServer(self.name)  # ramas de la o cadere
        return self.server.listen(self.name)

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            buffer = bytearray()

            def read(sock: QLocalSocket = socket, data: bytearray = buffer) -> None:
                data += bytes(sock.readAll())

            def done(sock: QLocalSocket = socket, data: bytearray = buffer) -> None:
                data += bytes(sock.readAll())
                try:
                    args = json.loads(data.decode("utf-8") or "[]")
                except ValueError:
                    args = []
                if isinstance(args, list):
                    self.received.emit([str(a) for a in args])
                sock.deleteLater()

            socket.readyRead.connect(read)
            socket.disconnected.connect(done)
            if socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
                done()

    def close(self) -> None:
        self.server.close()
