"""
RESP (REdis Serialization Protocol) Parser

This module handles parsing and encoding of RESP protocol messages.
RESP is a simple text-based protocol used by Redis for client-server communication.
"""


from typing import Optional

def parse_resp_array(data: bytes) -> Optional[list[str]]:
    """
    Parse a RESP array from bytes.
    
    Args:
        data: Raw bytes containing RESP protocol data
        
    Returns:
        list[str]: Parsed list of strings command parts
        None: If parsing fails or data is incomplete
    """
    if not data or not data.startswith(b'*'):
        return None
    
    try:
        # Find the first \r\n to get array length
        first_crlf = data.find(b'\r\n')
        if first_crlf == -1:
            return None
        
        # Parse array length
        array_length = int(data[1:first_crlf])
        
        offset = first_crlf + 2  # Skip '*N\r\n'
        parsed_elements = []
        
        # Parse each bulk string in the array
        for _ in range(array_length):
            if offset >= len(data):
                return None
            
            # Each element should be a bulk string starting with '$'
            if data[offset:offset + 1] != b'$':
                return None
            
            # Find the bulk string length
            length_end = data.find(b'\r\n', offset)
            if length_end == -1:
                return None
            
            bulk_length = int(data[offset + 1:length_end])
            
            # Extract the bulk string content
            content_start = length_end + 2
            content_end = content_start + bulk_length
            
            if content_end + 2 > len(data):
                return None
            
            content = data[content_start:content_end].decode('utf-8')
            parsed_elements.append(content)
            
            # Move offset past this bulk string
            offset = content_end + 2  # Skip '\r\n'
        
        return parsed_elements
        
    except (ValueError, UnicodeDecodeError):
        return None


def encode_simple_string(s: str) -> bytes:
    """
    Encode a simple string in RESP format.
    
    Args:
        s: String to encode
        
    Returns:
        RESP-encoded simple string
    """
    return f"+{s}\r\n".encode()


def encode_bulk_string(s: str) -> bytes:
    """
    Encode a bulk string in RESP format.
    
    Args:
        s: String to encode
        
    Returns:
        RESP-encoded bulk string
    """
    s_bytes = s.encode()
    return f"${len(s_bytes)}\r\n".encode() + s_bytes + b"\r\n"


def encode_null_bulk_string() -> bytes:
    """
    Encode a null bulk string in RESP format.
    
    Returns:
        RESP-encoded null bulk string
    """
    return b"$-1\r\n"


def encode_error(error_msg: str) -> bytes:
    """
    Encode an error message in RESP format.
    
    Args:
        error_msg: Error message to encode
        
    Returns:
        RESP-encoded error message
    """
    return f"-{error_msg}\r\n".encode()
