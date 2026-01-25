"""
Redis Server Module

This module implements the TCP server for handling client connections

Main Components:
    - TCP server listening for client connections
    - Connection handler spawning threads for each client

Threading Model:
    - Main thread: Accepts new client connections
    - Client threads: One thread per client connection for command processing

Configuration:
    Server behavior is configured via command-line arguments:
    - --port: Server listening port (default: 6379)
    - --dir: Directory for RDB files
    - --dbfilename: RDB file name
"""

import socket
import threading
import click

from resp_server.core.command_execution import handle_connection
from resp_server.config import config


class Server:
    def __init__(self, port: int = 6379, host: str = "localhost"):
        self.port = port
        self.host = host
        self.running = False
        self.server_socket = None

    def start(self):
        """Starts the Redis-compatible server."""
        try:
            self.server_socket = socket.create_server((self.host, self.port), reuse_port=True)
            # Set a timeout so we can periodically check self.running used for graceful shutdown
            self.server_socket.settimeout(1.0)
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
                connection, client_address = self.server_socket.accept()
                threading.Thread(target=handle_connection, args=(connection, client_address)).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Server Error: Exception during connection acceptance: {e}")
                break   # break if socket is closed as well

    def stop(self):
        """Stops the server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

@click.command()
@click.option('--port', default=6379, type=int, help='Server listening port (default: 6379)')
@click.option('--dir', 'rdb_dir', default='.', help='Directory for RDB files')
@click.option('--dbfilename', default='dump.rdb', help='RDB file name')
def main(port, rdb_dir, dbfilename):
    # Populate the global config object
    config.port = port
    config.rdb_dir = rdb_dir
    config.db_filename = dbfilename
    
    print(f"Server Configuration: Port={port}, RDB Directory={rdb_dir}, DB Filename={dbfilename}")
    server = Server(port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.stop()

if __name__ == "__main__":
    main()