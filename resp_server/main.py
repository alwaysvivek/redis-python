"""
RESP Server - Embeddable Redis-Compatible Server for Python

A lightweight, pure-Python Redis-compatible server designed for local development 
and unit testing. Zero dependencies, embeddable in test suites.

Supported Features:
- Strings (SET, GET, INCR, INCRBY, DEL with optional expiration)
- Lists (LPUSH, RPUSH, LPOP, LRANGE, LLEN, BLPOP)
- Streams (XADD, XRANGE, XREAD with blocking support)
- Pub/Sub (SUBSCRIBE, PUBLISH, UNSUBSCRIBE)
- Additional commands (PING, ECHO, TYPE, CONFIG, KEYS)
- RDB persistence (loading only)

Usage:
    # As a module
    python -m resp_server.main [--port PORT]
    
    # After installation
    resp-server [--port PORT]
    
Examples:
    python -m resp_server.main
    python -m resp_server.main --port 6380
    resp-server --port 6399
"""

from resp_server.core.server import main

if __name__ == "__main__":
    main()
