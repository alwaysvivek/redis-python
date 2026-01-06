# Feature Justification

This document justifies every major feature in Redix, explaining why it was included and what engineering concept it demonstrates.

## Core Architecture

### **TCP Server with Threading**
- **Why**: Handle multiple concurrent clients without blocking.
- **Demonstrates**: Socket programming, OS thread management, concurrency primitives (locks).

### **RESP Protocol Parser**
- **Why**: Redis uses a custom binary-safe protocol (RESP). Implementing it proves you understand application-layer protocols.
- **Demonstrates**: String parsing, byte manipulation, robust error handling, protocol specification compliance.

## Data Store & Commands

### **In-Memory Key-Value Store**
- **Why**: The fundamental primitive of Redis.
- **Demonstrates**: Hash map usage, thread-safe memory access (`threading.Lock`).

### **Approximate LRU Eviction**
- **Why**: Real caches have memory limits. Exact LRU is expensive (doubly linked lists use extra memory). Approximate LRU using random sampling is industry standard (used by Redis).
- **Demonstrates**: Probabilistic algorithms, memory management strategies, trade-offs between accuracy and performance.

### **TTL & Lazy Expiration** (`SET key val PX 1000`)
- **Why**: Caching requires data to expire. Lazy expiration (check-on-access) is a standard systems optimization.
- **Demonstrates**: Time-based logic, memory efficiency (avoiding background scanners for simplicity).

### **Lists & Blocking Operations** (`BLPOP`)
- **Why**: Redis is often used as a message queue. `BLPOP` requires pausing a thread until data arrives.
- **Demonstrates**: `threading.Condition`, inter-thread communication, signaling.

### **Transactions** (`MULTI`/`EXEC`)
- **Why**: Atomic execution of multiple commands.
- **Demonstrates**: Queueing logic, atomic state transitions, isolation assurance.

### **Atomic Increments** (`INCR`, `INCRBY`)
- **Why**: Essential for counters and rate limiters.
- **Demonstrates**: Read-modify-write atomicity under high concurrency.

## Distributed Systems

### **Master-Slave Replication**
- **Why**: High availability and read scaling are core backend concepts.
- **Demonstrates**: Leader-follower architecture, command propagation, offset tracking, eventual consistency.

### **RDB Parsing**
- **Why**: Persistence and data portability.
- **Demonstrates**: Binary file format parsing, understanding serialization.

### **Streams** (`XADD`, `XREAD`)
- **Why**: Modern Redis usage for event sourcing.
- **Demonstrates**: Append-only log structures, ID generation logic, range queries.
