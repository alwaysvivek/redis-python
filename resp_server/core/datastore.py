"""
Redis Data Store Module - Lite version

This module provides the core data storage for the Redis server.
Supports: Strings, Lists, Streams, and Pub/Sub.
"""

import time
import threading
import random
from typing import Optional, Union, List, Tuple, Dict, Any

# ============================================================================
# THREAD SAFETY - LOCKS
# ============================================================================

DATA_LOCK = threading.Lock()
BLOCKING_CLIENTS_LOCK = threading.Lock()
BLOCKING_STREAMS_LOCK = threading.Lock()

# ============================================================================
# DATA STRUCTURES
# ============================================================================

# The central storage. Keys map to a dictionary containing value, type, and expiry.
# Example: {'mykey': {'type': 'string', 'value': 'myvalue', 'expiry': 1731671220000}}
DATA_STORE = {}

# Streams storage: key -> list of entries. Each entry: {'id': 'ms-seq', 'fields': {}}
STREAMS = {}

# Pub/Sub data structures
CHANNEL_SUBSCRIBERS = {}  # Maps channel name to set of subscriber sockets
CLIENT_SUBSCRIPTIONS = {}  # Maps client socket to set of subscribed channels
CLIENT_STATE = {}  # Per-client state (e.g., subscription flags)

# Blocking operations
BLOCKING_CLIENTS = {}
BLOCKING_STREAMS = {}

# ============================================================================
# BASIC KEY-VALUE OPERATIONS
# ============================================================================

def get_data_entry(key: str) -> Optional[dict]:
    """Retrieves a key, checks for expiration (lazy deletion)."""
    with DATA_LOCK:
        data_entry = DATA_STORE.get(key)
        if data_entry is None:
            return None

        expiry = data_entry.get("expiry")
        if expiry is not None and int(time.time() * 1000) >= expiry:
            del DATA_STORE[key]
            if key in STREAMS: del STREAMS[key]
            return None

        return data_entry

def delete_data_entry(key: str) -> int:
    """Removes a key from the DATA_STORE and side structures."""
    with DATA_LOCK:
        if key in DATA_STORE:
            del DATA_STORE[key]
            if key in STREAMS: del STREAMS[key]
            return 1
        return 0

def set_string(key: str, value: str, expiry_timestamp: Optional[int]):
    with DATA_LOCK:
        DATA_STORE[key] = {
            "type": "string",
            "value": value,
            "expiry": expiry_timestamp
        }

def set_list(key: str, elements: list[str], expiry_timestamp: Optional[int]):
    with DATA_LOCK:
        DATA_STORE[key] = {
            "type": "list",
            "value": elements,
            "expiry": expiry_timestamp
        }

def existing_list(key: str) -> bool:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        return entry is not None and entry.get("type") == "list"

def append_to_list(key: str, element: str):
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("type") == "list":
            entry["value"].append(element)

def prepend_to_list(key: str, element: str):
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("type") == "list":
            entry["value"].insert(0, element)

def size_of_list(key: str) -> int:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("type") == "list":
            return len(entry["value"])
        return 0

def lrange_rtn(key: str, start: int, end: int) -> list[str]:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("type") == "list":
            lst = entry["value"]
            L = len(lst)
            if start < 0: start += L
            if end < 0: end += L
            start = max(0, start)
            if start > end or start >= L: return []
            return lst[start:min(end + 1, L)]
        return []

def remove_elements_from_list(key: str, count: int) -> Optional[list[str]]:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("type") == "list" and entry["value"]:
            ret = [entry["value"].pop(0) for _ in range(min(count, len(entry["value"])))]
            if not entry["value"]: del DATA_STORE[key]
            return ret
    return None

# ============================================================================
# INCREMENT OPERATIONS
# ============================================================================

def _incr_generic(key: str, amount: int) -> tuple[Optional[int], Optional[str]]:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        if entry and entry.get("expiry") and int(time.time() * 1000) >= entry["expiry"]:
            entry = None
            del DATA_STORE[key]

        if entry is None:
            DATA_STORE[key] = {"type": "string", "value": str(amount), "expiry": None}
            return amount, None
        
        if entry.get("type") != "string":
            return None, "-WRONGTYPE Operation against a key holding the wrong kind of value\r\n"
        
        try:
            val = int(entry["value"])
            new_val = val + amount
            entry["value"] = str(new_val)
            return new_val, None
        except ValueError:
            return None, "-ERR value is not an integer or out of range\r\n"

def increment_key_value(key: str) -> tuple[Optional[int], Optional[str]]:
    return _incr_generic(key, 1)

def increment_key_value_by(key: str, amount: int) -> tuple[Optional[int], Optional[str]]:
    return _incr_generic(key, amount)

# ============================================================================
# PUB/SUB OPERATIONS
# ============================================================================

def subscribe(client, channel):
    with BLOCKING_CLIENTS_LOCK:
        if channel not in CHANNEL_SUBSCRIBERS:
            CHANNEL_SUBSCRIBERS[channel] = set()
        CHANNEL_SUBSCRIBERS[channel].add(client)

        if client not in CLIENT_SUBSCRIPTIONS:
            CLIENT_SUBSCRIPTIONS[client] = set()
        CLIENT_SUBSCRIPTIONS[client].add(channel)

        if client not in CLIENT_STATE:
            CLIENT_STATE[client] = {}
        CLIENT_STATE[client]["is_subscribed"] = True

def unsubscribe(client, channel):
    with BLOCKING_CLIENTS_LOCK:
        if channel in CHANNEL_SUBSCRIBERS:
            CHANNEL_SUBSCRIBERS[channel].discard(client)
            if not CHANNEL_SUBSCRIBERS[channel]: del CHANNEL_SUBSCRIBERS[channel]

        if client in CLIENT_SUBSCRIPTIONS:
            CLIENT_SUBSCRIPTIONS[client].discard(channel)
            if not CLIENT_SUBSCRIPTIONS[client]: del CLIENT_SUBSCRIPTIONS[client]

        if client in CLIENT_STATE:
            CLIENT_STATE[client]["is_subscribed"] = len(CLIENT_SUBSCRIPTIONS.get(client, set())) > 0

def num_client_subscriptions(client) -> int:
    with BLOCKING_CLIENTS_LOCK:
        return len(CLIENT_SUBSCRIPTIONS.get(client, []))

def is_client_subscribed(client) -> bool:
    with BLOCKING_CLIENTS_LOCK:
        return CLIENT_STATE.get(client, {}).get("is_subscribed", False)

def cleanup_blocked_client(client):
    with BLOCKING_CLIENTS_LOCK:
        for channel, subs in list(CHANNEL_SUBSCRIBERS.items()):
            subs.discard(client)
            if not subs: del CHANNEL_SUBSCRIBERS[channel]
        if client in CLIENT_SUBSCRIPTIONS: del CLIENT_SUBSCRIPTIONS[client]
        if client in CLIENT_STATE: del CLIENT_STATE[client]

# ============================================================================
# STREAM OPERATIONS
# ============================================================================

def compare_stream_ids(id1: str, id2: str) -> int:
    try:
        t1, s1 = map(int, id1.split('-'))
        t2, s2 = map(int, id2.split('-'))
        if t1 != t2: return 1 if t1 > t2 else -1
        if s1 != s2: return 1 if s1 > s2 else -1
        return 0
    except: return 0

def get_stream_max_id(key: str) -> str:
    with DATA_LOCK:
        if key in STREAMS and STREAMS[key]:
            return STREAMS[key][-1]["id"]
        return "0-0"

def xadd(key: str, id_str: str, fields: dict) -> Union[bytes, str]:
    with DATA_LOCK:
        if key not in STREAMS:
            STREAMS[key] = []
            DATA_STORE[key] = {"type": "stream", "expiry": None}
        
        entries = STREAMS[key]
        last_id = entries[-1]["id"] if entries else "0-0"
        
        # Auto-generation logic simplified
        if id_str == "*":
            ts = int(time.time() * 1000)
            last_ts, last_seq = map(int, last_id.split('-'))
            if ts > last_ts: seq = 0
            else: ts, seq = last_ts, last_seq + 1
            final_id = f"{ts}-{seq}"
        elif id_str.endswith("-*"):
            ts = int(id_str.split('-')[0])
            last_ts, last_seq = map(int, last_id.split('-'))
            if ts > last_ts: seq = 0
            elif ts == last_ts: seq = last_seq + 1
            else: return b"-ERR The ID specified in XADD is equal or smaller than the target stream top item\r\n"
            final_id = f"{ts}-{seq}"
        else:
            if compare_stream_ids(id_str, last_id) <= 0 and last_id != "0-0":
                return b"-ERR The ID specified in XADD is equal or smaller than the target stream top item\r\n"
            if id_str == "0-0": return b"-ERR The ID specified in XADD must be greater than 0-0\r\n"
            final_id = id_str
        
        entries.append({"id": final_id, "fields": fields})
        return final_id

def xrange(key: str, start: str, end: str) -> list:
    with DATA_LOCK:
        if key not in STREAMS: return []
        res = []
        for entry in STREAMS[key]:
            if (start == "-" or compare_stream_ids(entry["id"], start) >= 0) and \
               (end == "+" or compare_stream_ids(entry["id"], end) <= 0):
                res.append(entry)
        return res

def xread(keys: list, last_ids: list) -> dict:
    with DATA_LOCK:
        res = {}
        for k, lid in zip(keys, last_ids):
            if k not in STREAMS: continue
            if lid == "$": lid = get_stream_max_id(k)
            matches = [e for e in STREAMS[k] if compare_stream_ids(e["id"], lid) > 0]
            if matches: res[k] = matches
        return res

# ============================================================================
# RDB LOADING
# ============================================================================

def read_string(f):
    length_or_encoding_byte = read_length(f)
    if (length_or_encoding_byte >> 6) == 0b11:
        return read_encoded_string(f, length_or_encoding_byte)
    length = length_or_encoding_byte
    data = f.read(length)
    try: return data.decode("utf-8")
    except: return data

def read_length(f):
    first_byte = f.read(1)[0]
    prefix = first_byte >> 6
    if prefix == 0b00: return first_byte & 0x3F
    elif prefix == 0b01: return ((first_byte & 0x3F) << 8) | f.read(1)[0]
    elif prefix == 0b10: return int.from_bytes(f.read(4), "big")
    else: return first_byte

def read_value(f, value_type):
    if value_type == b'\x00': return read_string(f)
    return None

def read_expiry(f, type_byte):
    if type_byte == b'\xFC': return int.from_bytes(f.read(8), "little")
    elif type_byte == b'\xFD': return int.from_bytes(f.read(4), "little")

def read_encoded_string(f, first_byte):
    encoding_type = first_byte & 0x3F
    if encoding_type == 0x00: return str(int.from_bytes(f.read(1), "big"))
    elif encoding_type == 0x01: return str(int.from_bytes(f.read(2), "little"))
    elif encoding_type == 0x02: return str(int.from_bytes(f.read(4), "little"))
    return None

def load_rdb_to_datastore(path: str) -> dict:
    import os
    if not os.path.exists(path): return {}
    datastore = {}
    try:
        with open(path, "rb") as f:
            if f.read(5) != b"REDIS": return {}
            f.read(4) # version
            while True:
                byte = f.read(1)
                if not byte: break
                if byte == b'\xFA':
                    read_string(f); read_string(f)
                    continue
                if byte == b'\xFE':
                    read_length(f) # db index
                    if f.read(1) == b'\xFB':
                        read_length(f); read_length(f)
                    else: f.seek(-1, 1)
                    while True:
                        expiry = None
                        t_byte = f.read(1)
                        if not t_byte or t_byte == b'\xFF': break
                        if t_byte in (b'\xFC', b'\xFD'):
                            expiry = read_expiry(f, t_byte)
                            t_byte = f.read(1)
                        key = read_string(f)
                        val = read_value(f, t_byte)
                        if t_byte == b'\x00':
                            datastore[key] = {"type": "string", "value": val, "expiry": expiry}
                elif byte == b'\xFF': break
    except: pass
    return datastore

# ============================================================================
# HELPERS
# ============================================================================

def _serialize_command_to_resp_array(command, args):
    parts = [b"*" + str(len(args) + 1).encode() + b"\r\n"]
    for x in [command] + args:
        xb = str(x).encode()
        parts.append(b"$" + str(len(xb)).encode() + b"\r\n" + xb + b"\r\n")
    return b"".join(parts)