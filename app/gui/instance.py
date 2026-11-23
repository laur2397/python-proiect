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
    ok = socket.bytesToWrite() == 0 or socket.waitForBytesWritten(TIMEOUT_MS)
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        socket.waitForDisconnected(TIMEOUT_MS)
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
            if socket is None:
                break
            connection = _Connection(socket, self)
            self._connections.add(connection)
            connection.start()

    def _finished(self, connection: _Connection, args: list[str]) -> None:
        self._connections.discard(connection)
        if args:
            self.received.emit(args)

    @property
    def _connections(self) -> set[_Connection]:
        if not hasattr(self, "_open_connections"):
            self._open_connections: set[_Connection] = set()
        return self._open_connections

    def close(self) -> None:
        for connection in list(self._connections):
            connection.finish()
        self.server.close()


class _Connection:
    """O conexiune: citeste pana la deconectare, apoi da argumentele o singura data.
    Obiectul ramane referit (in `InstanceServer`) pana la final, ca socket-ul sa nu
    fie folosit dupa ce Qt l-a sters."""

    def __init__(self, socket: QLocalSocket, server: InstanceServer) -> None:
        self.socket = socket
        self.server = server
        self.data = bytearray()
        self.done = False

    def start(self) -> None:
        self.socket.readyRead.connect(self.read)
        self.socket.disconnected.connect(self.finish)
        self.read()
        if self.socket.state() != QLocalSocket.LocalSocketState.ConnectedState:
            self.finish()

    def read(self) -> None:
        if not self.done:
            self.data += bytes(self.socket.readAll())

    def finish(self) -> None:
        if self.done:
            return
        self.read()
        self.done = True
        try:
            args = json.loads(self.data.decode("utf-8") or "[]")
        except ValueError:
            args = []
        self.socket.readyRead.disconnect(self.read)
        self.socket.disconnected.disconnect(self.finish)
        self.socket.deleteLater()
        valid = [str(a) for a in args] if isinstance(args, list) else []
        self.server._finished(self, valid)
