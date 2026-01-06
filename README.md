# Redix - Full-Featured Redis Implementation in Python

A comprehensive Redis-compatible server implementation in Python with support for all major Redis features including Lists, Streams, Sorted Sets, Transactions, Pub/Sub, Replication, and Geospatial commands.

## Features

### Basic Commands
- **PING** - Test server connectivity
- **ECHO** - Echo the given string
- **SET** - Set a key to a string value with optional expiration (EX/PX)
- **GET** - Get the value of a key
- **TYPE** - Determine the type of value stored at a key
- **CONFIG** - Get configuration parameters
- **KEYS** - Find all keys matching a pattern

### Lists
- **LPUSH** - Prepend one or multiple elements to a list
- **RPUSH** - Append one or multiple elements to a list
- **LPOP** - Remove and return the first element of a list
- **LRANGE** - Get a range of elements from a list
- **LLEN** - Get the length of a list
- **BLPOP** - Blocking list pop with timeout

### Streams
- **XADD** - Append a new entry to a stream
- **XRANGE** - Query a range of entries from a stream
- **XREAD** - Read entries from one or multiple streams
- Support for auto-generated and partially auto-generated IDs
- Blocking reads with and without timeout

### Sorted Sets
- **ZADD** - Add members with scores to a sorted set
- **ZRANK** - Get the rank of a member in a sorted set
- **ZRANGE** - Get a range of members from a sorted set
- **ZCARD** - Get the number of members in a sorted set
- **ZSCORE** - Get the score of a member in a sorted set
- **ZREM** - Remove members from a sorted set
- Support for negative indexes

### Transactions
- **MULTI** - Start a transaction
- **EXEC** - Execute all commands in a transaction
- **DISCARD** - Discard all commands in a transaction
- **INCR** - Increment the integer value of a key
- Queue commands during transaction
- Handle failures within transactions

### Pub/Sub
- **SUBSCRIBE** - Subscribe to one or more channels
- **UNSUBSCRIBE** - Unsubscribe from channels
- **PUBLISH** - Publish a message to a channel
- Enter subscribed mode
- Deliver messages to subscribers

### Replication
- **Master-Slave Replication** - Full master-slave setup
- **REPLCONF** - Configure replication parameters
- **PSYNC** - Synchronize with master server
- **INFO** - Get server information and replication status
- **WAIT** - Wait for replication acknowledgments
- Empty RDB transfer
- Single and multi-replica propagation
- Command processing and ACKs

### Additional Features
- ✅ **RESP Protocol** - Full Redis Serialization Protocol support
- ✅ **TCP Server** - Multi-threaded TCP server handling concurrent clients
- ✅ **Key Expiration** - TTL support with lazy deletion
- ✅ **Thread-Safe** - Concurrent client handling with proper locking
- ✅ **RDB Parsing** - Load data from RDB files (persistence loading)
- ✅ **Blocking Operations** - Support for blocking list (BLPOP) and stream operations

## Architecture

```
app/
├── main.py                      # Entry point
├── core/
│   ├── server.py                # TCP server and replication logic
│   ├── command_execution.py     # All command handlers
│   ├── context.py               # Server context and global state
│   └── datastore.py             # Complete data store implementation
│       ├── String storage with expiration
│       ├── List operations
│       ├── Stream operations
│       ├── Sorted set operations
│       ├── Transaction support
│       ├── Pub/Sub support
│       ├── RDB file loading
│       └── Blocking operations
├── protocol/
│   ├── resp.py                  # RESP protocol parser
│   └── constants.py             # Protocol constants
```

## Testing

The project includes a comprehensive test suite covering protocol parsing, data store logic, and end-to-end integration.

### Running Tests

Prerequisites:
```bash
pip install pytest redis
```

Run the full suite:
```bash
python3 -m pytest tests/
```

Tests cover:
- **Unit Tests**: `test_protocol.py`, `test_datastore.py`
- **Integration Tests**: `test_integration.py` (uses real `redis-py` client against the running server)


## License

This project is part of the CodeCrafters Redis challenge.

## Contributing

This is an educational project demonstrating a full Redis implementation.

### Connecting with redis-cli

Once the server is running, **open a new terminal window** and connect using the official Redis CLI:

```bash
redis-cli -p 6379
```

## Acknowledgments

- Built as part of the [CodeCrafters](https://codecrafters.io) "Build Your Own Redis" challenge
- Implements features from the official [Redis](https://redis.io) specification

## Resources

- [Redis Protocol Specification](https://redis.io/docs/reference/protocol-spec/)
- [Redis Commands Documentation](https://redis.io/commands/)
- [CodeCrafters Redis Challenge](https://codecrafters.io/challenges/redis)
- [RDB File Format](https://rdb.fnordig.de/file_format.html)
