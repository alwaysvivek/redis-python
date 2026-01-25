from dataclasses import dataclass, field
import socket

@dataclass
class ClientContext:
    conn: socket.socket
    addr: tuple
    is_subscribed: bool = False
    
    def sendall(self, data: bytes):
        """Proxy to socket.sendall"""
        self.conn.sendall(data)

    def getpeername(self):
        """Proxy to socket.getpeername"""
        return self.conn.getpeername()

    def fileno(self):
        """Proxy to socket.fileno"""
        return self.conn.fileno()

    def close(self):
        self.conn.close()

    def __hash__(self):
        """Allow ClientContext to be used in sets (like CHANNEL_SUBSCRIBERS)"""
        return hash(self.conn)

    def __eq__(self, other):
        if isinstance(other, ClientContext):
            return self.conn == other.conn
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
