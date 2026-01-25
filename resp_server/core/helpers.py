"""
Centralized helper functions for RESP Server core logic.
Handles RDB parsing primitives, Stream ID comparison, and common data entry validation.
"""

import time
from typing import Optional

def compare_stream_ids(id1: str, id2: str) -> int:
    """
    Compares two stream IDs formatted as 'timestamp-sequence'.
    Returns:
        1 if id1 > id2
        -1 if id1 < id2
        0 if id1 == id2
    """
    try:
        t1, s1 = map(int, id1.split('-'))
        t2, s2 = map(int, id2.split('-'))
        if t1 != t2: return 1 if t1 > t2 else -1
        if s1 != s2: return 1 if s1 > s2 else -1
        return 0
    except (ValueError, AttributeError):
        return 0

# ============================================================================
# RDB PARSING HELPERS
# ============================================================================

def read_rdb_length(rdb_file):
    """Reads a length encoding from the RDB file stream."""
    first_byte = rdb_file.read(1)[0]
    prefix = first_byte >> 6
    if prefix == 0b00:
        return first_byte & 0x3F
    elif prefix == 0b01:
        return ((first_byte & 0x3F) << 8) | rdb_file.read(1)[0]
    elif prefix == 0b10:
        return int.from_bytes(rdb_file.read(4), "big")
    else:
        return first_byte

def read_rdb_encoded_string(rdb_file, first_byte):
    """Reads an integer-encoded string."""
    encoding_type = first_byte & 0x3F
    if encoding_type == 0x00:
        return str(int.from_bytes(rdb_file.read(1), "big"))
    elif encoding_type == 0x01:
        return str(int.from_bytes(rdb_file.read(2), "little"))
    elif encoding_type == 0x02:
        return str(int.from_bytes(rdb_file.read(4), "little"))
    return None

def read_rdb_string(rdb_file):
    """Reads a string (prefixed by length) from the RDB file stream."""
    length_or_encoding_byte = read_rdb_length(rdb_file)
    # Check for special encoding
    if (length_or_encoding_byte >> 6) == 0b11:
        return read_rdb_encoded_string(rdb_file, length_or_encoding_byte)
    
    length = length_or_encoding_byte
    data = rdb_file.read(length)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data

def read_rdb_value(rdb_file, value_type_byte):
    """Reads a value based on its type byte."""
    # 0 = String Encoding
    if value_type_byte == b'\x00':
        return read_rdb_string(rdb_file)
    return None

def read_rdb_expiry(rdb_file, type_byte):
    """Reads expiry timestamp based on type (ms or seconds)."""
    if type_byte == b'\xFC': # Milliseconds
        return int.from_bytes(rdb_file.read(8), "little")
    elif type_byte == b'\xFD': # Seconds
        return int.from_bytes(rdb_file.read(4), "little") * 1000
    return None

# ============================================================================
# DATA ENTRY HELPERS
# ============================================================================

def check_expiry(key: str, entry: dict, store: dict, side_store: dict = None) -> bool:
    """
    Checks if an entry has expired. 
    If expired, deletes it from `store` (and optional `side_store`) and returns True.
    """
    expiry = entry.get("expiry")
    if expiry is not None and int(time.time() * 1000) >= expiry:
        if key in store:
            del store[key]
        if side_store and key in side_store:
            del side_store[key]
        return True
    return False

def get_valid_entry(key: str, store: dict, side_store: dict = None, expected_type: str = None) -> Optional[dict]:
    """
    Retrieves an entry, performing expiry modification and optional type checking.
    Returns the entry dict if valid, else None.
    """
    entry = store.get(key)
    if not entry:
        return None
    
    if check_expiry(key, entry, store, side_store):
        return None
    
    if expected_type and entry.get("type") != expected_type:
        return None
        
    return entry
