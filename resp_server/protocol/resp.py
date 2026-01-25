"""
RESP (REdis Serialization Protocol) Parser

This module handles parsing and encoding of RESP protocol messages.
RESP is a simple text-based protocol used by Redis for client-server communication.
"""

import re
from typing import Optional


# Regex patterns (structure only)

# Matches: *<number>\r\n
# This REPLACES:
#   - data.startswith(b'*')
#   - data.find(b'\r\n')
#   - int(data[1:first_crlf])
ARRAY_HEADER_RE = re.compile(rb'^\*(\d+)\r\n')

# Matches: $<number>\r\n
# This REPLACES:
#   - data[offset] == b'$'
#   - find(b'\r\n', offset)
#   - int(data[offset+1:length_end])
BULK_HEADER_RE = re.compile(rb'\$(\d+)\r\n')


def parse_resp_array(data: bytes) -> Optional[list[str]]:
    """
    Parse a RESP array from bytes.

    Returns:
        list[str] if complete and valid
        None if incomplete or invalid
    """

    if not data:
        return None

    try:
        # Parse array header
        # REPLACES ~6 lines of manual parsing:
        #   - startswith(b'*')
        #   - find CRLF
        #   - slicing for length
        #   - offset calculation
        match = ARRAY_HEADER_RE.match(data)
        if not match:
            return None

        array_length = int(match.group(1))
        offset = match.end()  # automatically skips "*<n>\r\n"

        parsed_elements: list[str] = []

        # Parse bulk strings

        for _ in range(array_length):
            # REPLACES:
            #   if data[offset] != b'$'
            #   length_end = find CRLF
            #   bulk_length slicing
            match = BULK_HEADER_RE.match(data, offset)
            if not match:
                return None

            bulk_length = int(match.group(1))
            content_start = match.end()
            content_end = content_start + bulk_length

            # REPLACES:
            #   if content_end + 2 > len(data)
            if content_end + 2 > len(data):
                return None

            # Payload parsing (NO regex here on purpose)
            content = data[content_start:content_end].decode("utf-8")
            parsed_elements.append(content)

            # Skip trailing "\r\n"
            offset = content_end + 2

        return parsed_elements

    except (ValueError, UnicodeDecodeError):
        # ValueError → invalid integer fields; UnicodeDecodeError → invalid UTF-8 payload
        return None


def encode_simple_string(s: str) -> bytes:
    return f"+{s}\r\n".encode()

def encode_bulk_string(s: str) -> bytes:
    s_bytes = s.encode()
    return f"${len(s_bytes)}\r\n".encode() + s_bytes + b"\r\n"

def encode_null_bulk_string() -> bytes:
    return b"$-1\r\n"

def encode_error(error_msg: str) -> bytes:
    return f"-{error_msg}\r\n".encode()

def encode_array(items: list[bytes]) -> bytes:
    """Encodes a list of already-encoded RESP items into a RESP array."""
    return f"*{len(items)}\r\n".encode() + b"".join(items)

def encode_integer(i: int) -> bytes:
    return f":{i}\r\n".encode()