"""
Redis Server Module

This module implements the TCP server for handling client connections and
manages replication functionality for master-slave architecture.

Main Components:
    - TCP server listening for client connections
    - Connection handler spawning threads for each client
    - Replication listener for receiving commands from master
    - Master connection setup for replica servers
    - Command propagation to replica servers

Server Modes:
    - Master mode: Accepts client connections and propagates commands to replicas
    - Replica mode: Connects to master, receives commands, and serves read requests

Threading Model:
    - Main thread: Accepts new client connections
    - Client threads: One thread per client connection for command processing
    - Replication thread: Listens for commands from master (replica mode only)

Configuration:
    Server behavior is configured via command-line arguments:
    - --port: Server listening port (default: 6379)
    - --replicaof: Master server address (enables replica mode)
    - --dir: Directory for RDB files
    - --dbfilename: RDB file name
"""

import socket
import threading
import sys
from typing import Optional

from resp_server.protocol.constants import *
from resp_server.core.command_execution import handle_connection
import resp_server.core.command_execution as ce


# ============================================================================
# REPLICATION - REPLICA SIDE
# ============================================================================

class Server:
    def __init__(self, port: int = 6379, host: str = "localhost"):
        self.port = port
        self.host = host
        self.running = False
        self.server_socket = None
        self.threads = []

    def start(self):
        """Starts the Redis-compatible server."""
        try:
            self.server_socket = socket.create_server((self.host, self.port), reuse_port=True)
            self.running = True
            print(f"Server: Starting server on {self.host}:{self.port}...")
            print("Server: Listening for connections...")
            
            # Start the accept loop
            self._accept_loop()
        except OSError as e:
            print(f"Server Error: Could not start server: {e}")

    def _accept_loop(self):
        while self.running:
            try:
                # Set a timeout so we can periodically check self.running used for graceful shutdown
                self.server_socket.settimeout(1.0)
                try:
                    connection, client_address = self.server_socket.accept()
                    t = threading.Thread(target=handle_connection, args=(connection, client_address))
                    t.start()
                    self.threads.append(t)
                except socket.timeout:
                    continue
            except Exception as e:
                # If socket is closed, break
                if not self.running:
                    break
                print(f"Server Error: Exception during connection acceptance: {e}")
                break

    def stop(self):
        """Stops the server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

def main():
    port = 6379
    args = sys.argv[1:]
    
    # Simple argument parsing for the CLI entry point
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--port":
            if i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                    i += 2
                    continue
                except ValueError:
                    pass
        elif arg == "--dir" or arg == "--dbfilename":
            # Keeping these for now as placeholder for future persistence, 
            # but currently they don't do much in the Lite version.
             if i + 1 < len(args):
                 i += 2
                 continue
        i += 1

    server = Server(port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.stop()

if __name__ == "__main__":
    main()