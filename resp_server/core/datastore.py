"""
Redis Data Store Module - Lite version

This module provides the core data storage logic, delegating parsing and validation
to the centralized helpers module.
"""

import threading
import time
from typing import Optional, Union

from resp_server.core import helpers
from resp_server.protocol.resp import encode_error

# ============================================================================
# THREAD SAFETY - LOCKS
# ============================================================================

DATA_LOCK = threading.Lock()
BLOCKING_CLIENTS_LOCK = threading.Lock()
BLOCKING_STREAMS_LOCK = threading.Lock()

# ============================================================================
# DATA STORAGE
# ============================================================================

DATA_STORE = {}           # Key -> {'type', 'value', 'expiry'}
STREAMS = {}              # Key -> List[Entry]
CHANNEL_SUBSCRIBERS = {}  # Channel -> Set[Client]
CLIENT_SUBSCRIPTIONS = {} # Client -> Set[Channel]
CLIENT_STATE = {}         # Client -> Dict[State]
BLOCKING_CLIENTS = {}     # Key -> List[Condition]
BLOCKING_STREAMS = {}     # Key -> List[Condition]

# ============================================================================
# INTERNAL WRAPPERS
# ============================================================================

def _get_entry(key: str, expected_type: str = None) -> Optional[dict]:
    """Retrieves an entry using the central helper, passing the global store."""
    return helpers.get_valid_entry(key, DATA_STORE, STREAMS, expected_type)

def _set_entry(key: str, value, type_str: str, expiry: Optional[int]):
    DATA_STORE[key] = {"type": type_str, "value": value, "expiry": expiry}

def _list_push(key: str, element: str, prepend: bool = False):
    entry = _get_entry(key, "list")
    if entry:
        entry["value"].insert(0, element) if prepend else entry["value"].append(element)

def _get_pubsub_set(key, container):
    if key not in container: container[key] = set()
    return container[key]

# ============================================================================
# PUBLIC API - KEY-VALUE OPERATIONS
# ============================================================================

def get_data_entry(key: str) -> Optional[dict]:
    with DATA_LOCK:
        return _get_entry(key)

def delete_data_entry(key: str) -> int:
    with DATA_LOCK:
        if key in DATA_STORE:
            del DATA_STORE[key]
            if key in STREAMS: del STREAMS[key]
            return 1
        return 0

def set_string(key: str, value: str, expiry_timestamp: Optional[int]):
    with DATA_LOCK:
        _set_entry(key, value, "string", expiry_timestamp)

def set_list(key: str, elements: list[str], expiry_timestamp: Optional[int]):
    with DATA_LOCK:
        _set_entry(key, elements, "list", expiry_timestamp)

def existing_list(key: str) -> bool:
    with DATA_LOCK:
        return _get_entry(key, "list") is not None

def append_to_list(key: str, element: str):
    with DATA_LOCK:
        _list_push(key, element, prepend=False)

def prepend_to_list(key: str, element: str):
    with DATA_LOCK:
        _list_push(key, element, prepend=True)

def size_of_list(key: str) -> int:
    with DATA_LOCK:
        entry = _get_entry(key, "list")
        return len(entry["value"]) if entry else 0

def lrange_rtn(key: str, start: int, end: int) -> list[str]:
    with DATA_LOCK:
        entry = _get_entry(key, "list")
        if not entry: return []
        lst = entry["value"]
        L = len(lst)
        # Handle negative indices
        if start < 0: start += L
        if end < 0: end += L
        start = max(0, start)
        if start > end or start >= L: return []
        return lst[start:min(end + 1, L)]

def remove_elements_from_list(key: str, count: int) -> Optional[list[str]]:
    with DATA_LOCK:
        entry = _get_entry(key, "list")
        if entry and entry["value"]:
            popped = [entry["value"].pop(0) for _ in range(min(count, len(entry["value"])))]
            if not entry["value"]: del DATA_STORE[key]
            return popped
    return None

def increment_key_value(key: str) -> tuple[Optional[int], Optional[str]]:
    return _incr_generic(key, 1)

def increment_key_value_by(key: str, amount: int) -> tuple[Optional[int], Optional[str]]:
    return _incr_generic(key, amount)

def _incr_generic(key: str, amount: int) -> tuple[Optional[int], Optional[bytes]]:
    with DATA_LOCK:
        entry = DATA_STORE.get(key)
        # Check expiry manually since we handle non-existence differently
        if entry and helpers.check_expiry(key, entry, DATA_STORE):
            entry = None

        if entry is None:
            _set_entry(key, str(amount), "string", None)
            return amount, None
        
        if entry.get("type") != "string":
            return None, encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
        
        try:
            new_val = int(entry["value"]) + amount
            entry["value"] = str(new_val)
            return new_val, None
        except ValueError:
            return None, encode_error("value is not an integer or out of range")

# ============================================================================
# PUBLIC API - PUB/SUB
# ============================================================================

def subscribe(client, channel):
    with BLOCKING_CLIENTS_LOCK:
        _get_pubsub_set(channel, CHANNEL_SUBSCRIBERS).add(client)
        _get_pubsub_set(client, CLIENT_SUBSCRIPTIONS).add(channel)
        CLIENT_STATE.setdefault(client, {})["is_subscribed"] = True

def unsubscribe(client, channel):
    with BLOCKING_CLIENTS_LOCK:
        if channel in CHANNEL_SUBSCRIBERS:
            CHANNEL_SUBSCRIBERS[channel].discard(client)
            if not CHANNEL_SUBSCRIBERS[channel]: del CHANNEL_SUBSCRIBERS[channel]
        
        if client in CLIENT_SUBSCRIPTIONS:
            CLIENT_SUBSCRIPTIONS[client].discard(channel)
            if not CLIENT_SUBSCRIPTIONS[client]: del CLIENT_SUBSCRIPTIONS[client]
            
        if client in CLIENT_STATE:
            CLIENT_STATE[client]["is_subscribed"] = bool(CLIENT_SUBSCRIPTIONS.get(client))

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
# PUBLIC API - STREAMS
# ============================================================================

def get_stream_max_id(key: str) -> str:
    with DATA_LOCK:
        return STREAMS[key][-1]["id"] if key in STREAMS and STREAMS[key] else "0-0"

def xadd(key: str, id_str: str, fields: dict) -> Union[bytes, str]:
    with DATA_LOCK:
        if key not in STREAMS:
            STREAMS[key] = []
            _set_entry(key, None, "stream", None)
        
        entries = STREAMS[key]
        last_id = entries[-1]["id"] if entries else "0-0"
        
        # ID Generation / Validation
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
            else: return encode_error("The ID specified in XADD is equal or smaller than the target stream top item")
            final_id = f"{ts}-{seq}"
        else:
            if helpers.compare_stream_ids(id_str, last_id) <= 0 and last_id != "0-0":
                return encode_error("The ID specified in XADD is equal or smaller than the target stream top item")
            if id_str == "0-0": return encode_error("The ID specified in XADD must be greater than 0-0")
            final_id = id_str
        
        entries.append({"id": final_id, "fields": fields})
        return final_id

def xrange(key: str, start: str, end: str) -> list:
    with DATA_LOCK:
        if key not in STREAMS: return []
        return [
            entry for entry in STREAMS[key]
            if (start == "-" or helpers.compare_stream_ids(entry["id"], start) >= 0) and
               (end == "+" or helpers.compare_stream_ids(entry["id"], end) <= 0)
        ]

def xread(keys: list, last_ids: list) -> dict:
    with DATA_LOCK:
        res = {}
        for stream_key, last_id in zip(keys, last_ids):
            if stream_key not in STREAMS: continue
            if last_id == "$": last_id = get_stream_max_id(stream_key)
            
            matches = [
                e for e in STREAMS[stream_key]
                if helpers.compare_stream_ids(e["id"], last_id) > 0
            ]
            if matches: res[stream_key] = matches
        return res

# ============================================================================
# RDB LOADING
# ============================================================================

def load_rdb_to_datastore(path: str) -> dict:
    import os
    if not os.path.exists(path): return {}
    
    new_store = {}
    try:
        with open(path, "rb") as rdb_file:
            if rdb_file.read(5) != b"REDIS": return {}
            rdb_file.read(4) # skip version
            
            while True:
                op_code = rdb_file.read(1)
                if not op_code: break
                
                if op_code == b'\xFA': # Auxiliary fields
                    helpers.read_rdb_string(rdb_file)
                    helpers.read_rdb_string(rdb_file)
                    
                elif op_code == b'\xFE': # DB Selector
                    helpers.read_rdb_length(rdb_file) # db_index
                    if rdb_file.read(1) == b'\xFB': # Resize DB
                        helpers.read_rdb_length(rdb_file)
                        helpers.read_rdb_length(rdb_file)
                    else:
                        rdb_file.seek(-1, 1) # Backtrack
                        
                    while True:
                        expiry_time = None
                        type_byte = rdb_file.read(1)
                        if not type_byte or type_byte == b'\xFF': # EOF
                            break
                            
                        if type_byte in (b'\xFC', b'\xFD'): # Expiry
                            expiry_time = helpers.read_rdb_expiry(rdb_file, type_byte)
                            type_byte = rdb_file.read(1)
                            
                        key_str = helpers.read_rdb_string(rdb_file)
                        val_obj = helpers.read_rdb_value(rdb_file, type_byte)
                        
                        if type_byte == b'\x00': # String
                            new_store[key_str] = {"type": "string", "value": val_obj, "expiry": expiry_time}
                            
                elif op_code == b'\xFF': # End of RDB
                    break
    except Exception:
        pass # Best effort loading
        
    return new_store