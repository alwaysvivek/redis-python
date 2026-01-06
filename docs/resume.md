# Resume Description

Here are a few options for describing Redix on your resume. Choose the one that fits your narrative best.

### Option 1: Systems & Concurrency Focus (Recommended)
**Redix (Python, TCP, Concurrency)**
*   Engineered a multi-threaded Redis-compatible in-memory data store from scratch, supporting RESP protocol, TTL, and atomic transactions.
*   Implemented **Approximate LRU Eviction** using random sampling to enforce memory limits efficiently (O(1)), mirroring production Redis behavior.
*   Designed a thread-safe caching engine using `threading.Lock` and `threading.Condition` to handle concurrent `BLPOP` blocking queues.
*   Built master-slave replication logic with synchronous `WAIT` support and random-access RDB persistence loading.

### Option 2: Backend & Reliability Focus
**Redix (Python, Sockets, Testing)**
*   Built a persistent Key-Value store supporting String, List, Stream, and Sorted Set data structures with O(1) lookups.
*   Implemented core distributed systems features including leader-follower replication and probabilistic memory management (LRU).
*   Developed a robust command execution engine handling atomic `INCR` operations and preventing race conditions via mutex locking.
*   Wrote comprehensive unit and integration tests using `pytest` and `redis-py` to validate protocol correctness and reliability.

### Key Skills Demonstrated
*   **Languages**: Python 3.9+
*   **Systems**: TCP/IP, multithreading, sockets, file I/O
*   **Concepts**: Concurrency control, distributed consensus (replication), probabilistic algorithms (LRU), caching strategies
