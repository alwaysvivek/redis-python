"""
Redis Command Execution Module
"""

import os
import socket
import threading
import time

from resp_server.config import config
from resp_server.core.context import ClientContext
from resp_server.core.datastore import BLOCKING_CLIENTS, BLOCKING_CLIENTS_LOCK, BLOCKING_STREAMS, BLOCKING_STREAMS_LOCK, \
    CHANNEL_SUBSCRIBERS, DATA_LOCK, DATA_STORE, STREAMS, \
    cleanup_blocked_client, get_stream_max_id, \
    increment_key_value, increment_key_value_by, delete_data_entry, is_client_subscribed, load_rdb_to_datastore, \
    lrange_rtn, \
    num_client_subscriptions, prepend_to_list, remove_elements_from_list, \
    size_of_list, append_to_list, existing_list, get_data_entry, set_list, set_string, subscribe, unsubscribe, xadd, \
    xrange, xread
from resp_server.protocol.resp import parse_resp_array, encode_bulk_string, encode_null_bulk_string, encode_error, encode_simple_string, encode_array, encode_integer

# ============================================================================
# CONFIGURATION AND CONSTANTS

# Commands that modify data
WRITE_COMMANDS = {
    "SET", "LPUSH", "RPUSH", "LPOP", "XADD", "INCR", "INCRBY", "DEL"
}

# Define the 59-byte empty RDB file content (hexadecimal)
EMPTY_RDB_BYTES = bytes.fromhex(
    "524544495330303131fa0972656469732d76657205372e322e30"
    "fa0a72656469732d62697473c040fa056374696d65c26d08bc65"
    "fa08757365642d6d656dc2b0c41000fa08616f662d62617365c0"
    "00fff06e3bfec0ff5aa2"
)

# RDB_FILE_SIZE will be determined by the actual length of the new hex string.
RDB_HEADER = f"${len(EMPTY_RDB_BYTES)}\r\n".encode()

def initialize_datastore():
    rdb_path = os.path.join(config.rdb_dir, config.db_filename)
    if os.path.exists(rdb_path):
        DATA_STORE.update(load_rdb_to_datastore(rdb_path))
    else:
        print(f"RDB file not found at {rdb_path}, starting with empty DATA_STORE.")


initialize_datastore()

def _xread_serialize_response(stream_data: dict[str, list[dict]]) -> bytes:
    """Serializes the result of xread into a RESP array response."""
    if not stream_data:
        return encode_null_bulk_string().replace(b"$-1", b"*-1")

    # Outer Array: Array of [key, [entry1, entry2, ...]] # *N\r\n
    outer_array_items = []

    for key, entries in stream_data.items():
        encoded_entries = []

        for entry in entries:
            fields_items = []
            for field, value in entry["fields"].items():
                fields_items.append(encode_bulk_string(field))
                fields_items.append(encode_bulk_string(value))

            encoded_entries.append(encode_array([
                encode_bulk_string(entry["id"]),
                encode_array(fields_items)
            ]))

        outer_array_items.append(encode_array([
            encode_bulk_string(key),
            encode_array(encoded_entries)
        ]))

    return encode_array(outer_array_items)


# ============================================================================
# COMMAND EXECUTION
# ============================================================================
# This section contains the main command execution logic for all supported Redis commands.
# Commands are organized by category for easier navigation and maintenance.

def execute_single_command(command: str, arguments: list, client: ClientContext):
    """
    Executes a single Redis command and returns the appropriate response.
    Returns:
        bytes: RESP-formatted response
        bool: True for special commands
    """
    if is_client_subscribed(client):
        ALLOWED_COMMANDS_WHEN_SUBSCRIBED = {"SUBSCRIBE", "UNSUBSCRIBE", "PING", "QUIT", "PSUBSCRIBE", "PUNSUBSCRIBE"}
        if command not in ALLOWED_COMMANDS_WHEN_SUBSCRIBED:
            return encode_error(f"Can't execute '{command}' when client is subscribed")

    if command == "PING":
        return encode_simple_string("PONG") if (not is_client_subscribed(client)) \
            else b"*2\r\n" + encode_bulk_string("pong") + encode_bulk_string("")

    elif command == "ECHO":
        return encode_bulk_string(arguments[0]) if arguments \
            else encode_error("wrong number of arguments for 'echo' command")

    elif command == "SET":
        if len(arguments) < 2:
            return encode_error("wrong number of arguments for 'set' command")

        key, value = arguments[0], arguments[1]
        duration_ms = None

        i = 2
        if i < len(arguments):
            option = arguments[i].upper()

            if option not in ("EX", "PX") or i + 1 >= len(arguments):
                return encode_error("syntax error")

            try:
                ttl = int(arguments[i + 1])
            except ValueError:
                return encode_error("value is not an integer or out of range")

            duration_ms = ttl * 1000 if option == "EX" else ttl

        current_time = int(time.time() * 1000)
        expiry_timestamp = current_time + duration_ms if duration_ms is not None else None

        set_string(key, value, expiry_timestamp)
        return encode_simple_string("OK")

    elif command == "GET":
        if not arguments:
            response = b"-ERR wrong number of arguments for 'get' command\r\n"
            return response

        key = arguments[0]

        # Use the data store function to get the value with expiry check
        data_entry = get_data_entry(key)

        if data_entry is None:
            response = encode_null_bulk_string()  # RESP Null Bulk String
        else:
            # Check for correct type (important: we only support string GET for now)
            response = (
                encode_error("WRONGTYPE Operation against a key holding the wrong kind of value")
                if data_entry.get("type") != "string"
                else encode_bulk_string(data_entry["value"])
            )

        # client.sendall(response
        return response

    elif command == "LRANGE":
        if not arguments or len(arguments) < 3:
            return encode_error("wrong number of arguments for 'lrange' command")

        list_key = arguments[0]
        start = int(arguments[1])
        end = int(arguments[2])

        list_elements = lrange_rtn(list_key, start, end)
        
        # Convert strings to encoded bulk strings
        encoded_elements = [encode_bulk_string(e) for e in list_elements]
        return encode_array(encoded_elements)

    elif command == "LPUSH":
        if not arguments:
            response = b"-ERR wrong number of arguments for 'lpush' command\r\n"
            # client.sendall(response
            return response

        list_key = arguments[0]
        elements = arguments[1:]

        if existing_list(list_key):
            for element in elements:
                prepend_to_list(list_key, element)
        else:
            set_list(list_key, elements, None)

        size = size_of_list(list_key)
        return encode_integer(size)

    elif command == "LLEN":
        if not arguments:
            return encode_error("wrong number of arguments for 'llen' command")

        list_key = arguments[0]
        size = size_of_list(list_key)
        return encode_integer(size)

    elif command == "LPOP":
        if not arguments:
            return encode_error("wrong number of arguments for 'lpop' command")

        list_key = arguments[0]
        arguments = arguments[1:]

        if not existing_list(list_key):
            return encode_null_bulk_string()

        if not arguments:
            list_elements = remove_elements_from_list(list_key, 1)
        else:
            list_elements = remove_elements_from_list(list_key, int(arguments[0]))
        if list_elements is None:
            return encode_null_bulk_string()

        encoded_elements = [encode_bulk_string(e) for e in list_elements]

        if len(encoded_elements) == 1:
            return encoded_elements[0]
        else:
            return encode_array(encoded_elements)

    elif command == "RPUSH":
        # 1. Argument and Key setup
        if not arguments:
            # No arguments -> ignore / error (your code returns True and keeps listening)
            return True

        list_key = arguments[0]
        elements = arguments[1:]

        # 2. Add elements (see ARCHITECTURE.md for locking details)
        if existing_list(list_key):
             for element in elements:
                 append_to_list(list_key, element)
        else:
             set_list(list_key, elements, None)

        size_to_report = size_of_list(list_key)

        # 3. Check for blocked clients (wake up FIFO)
        blocked_client_condition = None

        with BLOCKING_CLIENTS_LOCK:
            if list_key in BLOCKING_CLIENTS and BLOCKING_CLIENTS[list_key]:
                blocked_client_condition = BLOCKING_CLIENTS[list_key].pop(0)

        if blocked_client_condition:
            # 3a. When serving a blocked client, we must remove an element from the list.
            #     remove_elements_from_list pops from the head (LPOP semantics).
            #     This returns the element that will be sent to the blocked client.
            popped_elements = remove_elements_from_list(list_key, 1)

            # (You already computed size_to_report before popping; do NOT recalc it here,
            #  since Redis returns the size *after insertion*, not after serving waiters.)

            if popped_elements:
                popped_element = popped_elements[0]

                # 3b. Build the RESP array that BLPOP expects:
                #     *2\r\n
                #     $<len(key)>\r\n<key>\r\n
                #     $<len(element)>\r\n<element>\r\n
                blpop_response = encode_array([
                    encode_bulk_string(list_key),
                    encode_bulk_string(popped_element)
                ])

                blocked_client_socket = blocked_client_condition.client_socket

                # Send the BLPOP response directly to the blocked client's socket.
                # We do this *before* notify() so that when the blocked thread wakes it
                # can safely assume the response has already been sent (avoids a race).
                try:
                    blocked_client_socket.sendall(blpop_response)
                except Exception:
                    # If the blocked client disconnected between RPUSH discovering it and us sending,
                    # sendall will fail; we catch and ignore because we still need to notify the thread
                    # (or let its wait time out and the cleanup code remove it).
                    pass

                # 3c. Wake up the blocked thread. 
                with blocked_client_condition:
                    blocked_client_condition.notify()

        # 4. Return size
        return encode_integer(size_to_report)

    elif command == "BLPOP":
        # 1. Argument and Key setup
        if len(arguments) != 2:
            # Wrong number of args
            return True

        list_key = arguments[0]
        try:
            # Redis accepts fractional seconds for the timeout (e.g., 0.4).
            # threading.Condition.wait() accepts float seconds as well, so use float().
            timeout = float(arguments[1])
        except ValueError:
            # If parsing fails, send an error to the client (avoid silent failure).
            response = b"-ERR timeout is not a float\r\n"
            # client.sendall(response
            return response

        # 2. Fast path: if the list already has elements, pop and return immediately.
        #    This mirrors Redis: BLPOP behaves like LPOP when the list is non-empty.
        if size_of_list(list_key) > 0:
            list_elements = remove_elements_from_list(list_key, 1)

            if list_elements:
                popped_element = list_elements[0]

                # Construct the RESP array [key, popped_element] and send it.
                response = encode_array([
                    encode_bulk_string(list_key),
                    encode_bulk_string(popped_element)
                ])

                # client.sendall(response
                return response
            # If remove_elements_from_list returns None unexpectedly, fall through to blocking.
            # (This is unlikely if size_of_list returned > 0, but handling it avoids crashes.)

        # 3. Blocking logic (list empty / non-existent)
        #    We create a Condition object that the current thread will wait on.
        client_condition = threading.Condition()
        # Store the client socket on the Condition so RPUSH can send the response
        # directly to the waiting client's socket when an element arrives.
        client_condition.client_socket = client

        # Register this Condition in BLOCKING_CLIENTS under the list_key.
        # Use BLOCKING_CLIENTS_LOCK to guard concurrent access to the shared dict.
        with BLOCKING_CLIENTS_LOCK:
            BLOCKING_CLIENTS.setdefault(list_key, []).append(client_condition)

        # Wait for notification or timeout.
        with client_condition:
            if timeout == 0:
                notified = client_condition.wait()
            else:
                notified = client_condition.wait(timeout)

        # 4. Post-block handling
        if notified:
            # If True, RPUSH already sent the BLPOP response to the socket, so there's
            # nothing more to do here. Just return True and continue listening for commands.
            return True
        else:
            # Timeout occurred. We must remove this client from the BLOCKING_CLIENTS registry
            # because RPUSH may never visit it (or might have visited it but failed to notify).
            with BLOCKING_CLIENTS_LOCK:
                # Defensive: only remove if it's still present (RPUSH could have popped it)
                if client_condition in BLOCKING_CLIENTS.get(list_key, []):
                    BLOCKING_CLIENTS[list_key].remove(client_condition)
                    # If no more waiters, delete empty list to keep the dict tidy
                    if not BLOCKING_CLIENTS[list_key]:
                        del BLOCKING_CLIENTS[list_key]

            # Send Null Array response on timeout: Redis returns "*-1\r\n" for BLPOP timeout.
            response = b"*-1\r\n"
            # client.sendall(response
            return response

    elif command == "CONFIG":
        if len(arguments) != 2 or arguments[0].upper() != "GET":
            # Handle wrong arguments or non-GET subcommands
            response = b"-ERR wrong number of arguments for 'CONFIG GET' command\r\n"
            # client.sendall(response
            return response

        # 1. Extract the parameter name requested by the client
        param_name = arguments[1].lower()
        value = None

        if param_name == "dir":
            value = config.rdb_dir
        elif param_name == "dbfilename":
            value = config.db_filename

        # 2. Handle unknown parameters
        if value is None:
            # Per Redis spec, CONFIG GET for an unknown param returns nil array or empty array.
            # A simple response of the parameter name and empty string is often used in clones.
            value = ""
            # We should still use the param_name for the first element

        # --- Correct RESP Serialization ---

        # 3. Encode strings and return Array
        return encode_array([
            encode_bulk_string(param_name),
            encode_bulk_string(value)
        ])

    elif command == "KEYS":
        if len(arguments) != 1:
            response = b"-ERR wrong number of arguments for 'KEYS' command\r\n"
            # client.sendall(response
            return response

        pattern = arguments[0]

        # Simple pattern matching: only supports '*' wildcard
        with DATA_LOCK:
            matching_keys = []
            for key in DATA_STORE.keys():
                if pattern == "*" or pattern == key:
                    matching_keys.append(key)

        encoded_keys = [encode_bulk_string(k) for k in matching_keys]
        return encode_array(encoded_keys)

    elif command == "SUBSCRIBE":
        # Construct RESP Array response
        channel = arguments[0] if arguments else ""
        subscribe(client, channel)
        num_subscriptions = num_client_subscriptions(client)

        return encode_array([
            encode_bulk_string("subscribe"),
            encode_bulk_string(channel),
            encode_integer(num_subscriptions)
        ])

    elif command == "PUBLISH":
        if len(arguments) != 2:
            response = b"-ERR wrong number of arguments for 'PUBLISH' command\r\n"
            # client.sendall(response
            return response

        channel = arguments[0]
        message = arguments[1]
        recipients = 0

        with BLOCKING_CLIENTS_LOCK:
            if channel in CHANNEL_SUBSCRIBERS:
                subscribers = CHANNEL_SUBSCRIBERS[channel]
                for subscriber in subscribers:
                    # Construct the message RESP Array
                    response = encode_array([
                        encode_bulk_string("message"),
                        encode_bulk_string(channel),
                        encode_bulk_string(message)
                    ])
                    try:
                        subscriber.sendall(response)
                        recipients += 1
                    except Exception:
                        pass  # Ignore send errors for subscribers

        # Send number of recipients to publisher
        return encode_integer(recipients)

    elif command == "UNSUBSCRIBE":
        channel = arguments[0] if arguments else ""

        unsubscribe(client, channel)
        num_subscriptions = num_client_subscriptions(client)

        return encode_array([
            encode_bulk_string("unsubscribe"),
            encode_bulk_string(channel),
            encode_integer(num_subscriptions)
        ])


    elif command == "TYPE":
        if len(arguments) < 1:
            response = b"-ERR wrong number of arguments for 'TYPE' command\r\n"
            # client.sendall(response
            return response

        key = arguments[0]

        data_entry = get_data_entry(key)

        if data_entry is None:
            type_str = "none"
        else:
            type_str = data_entry.get("type", "none")

        return encode_bulk_string(type_str)

        # client.sendall(response
        return response

    elif command == "XADD":
        # XADD requires at least: key, id, field, value (4 arguments), and even number of field/value pairs

        if len(arguments) < 4 or (len(arguments) - 2) % 2 != 0:
            response = b"-ERR wrong number of arguments for 'XADD' command\r\n"
            # client.sendall(response
            return response

        key = arguments[0]
        entry_id = arguments[1]
        fields = {}
        for i in range(2, len(arguments) - 1, 2):
            fields[arguments[i]] = arguments[i + 1]

        new_entry_id_or_error = xadd(key, entry_id, fields)

        i  # Check if xadd returned an error (RESP errors start with '-')
        if new_entry_id_or_error.startswith(b'-'):
            response = new_entry_id_or_error
            # client.sendall(response
            return response
        else:
            # Success: new_entry_id_or_error is the raw ID bytes (e.g. b"1-0").
            # Format as a RESP Bulk String. Fixed the incorrect .encode() call on a bytes object.
            raw_id_bytes = new_entry_id_or_error
            blocked_client_condition = None
            new_entry = None

            with BLOCKING_STREAMS_LOCK:
                if key in BLOCKING_STREAMS and BLOCKING_STREAMS[key]:
                    blocked_client_condition = BLOCKING_STREAMS[key].pop(0)

            if blocked_client_condition:
                # Get the single new entry that was just added (it's the last one)
                with DATA_LOCK:  # Acquire lock to safely access STREAMS
                    if key in STREAMS and STREAMS[key]:
                        new_entry = STREAMS[key][-1]

                if new_entry:
                    # Prepare the data structure for serialization (single entry for a single stream)
                    stream_data_to_send = {key: [new_entry]}
                    xread_block_response = _xread_serialize_response(stream_data_to_send)

                    blocked_client_socket = blocked_client_condition.client_socket

                    # Send the XREAD BLOCK response directly to the blocked client's socket.
                    try:
                        blocked_client_socket.sendall(xread_block_response)
                    except Exception:
                        pass  # Ignore send errors

                    # Wake up blocked thread
                    with blocked_client_condition:
                        blocked_client_condition.notify()

            return encode_bulk_string(raw_id_bytes.decode())
            # client.sendall(response
            return response

    elif command == "XRANGE":
        if len(arguments) < 3:
            response = b"-ERR wrong number of arguments for 'XRANGE' command\r\n"
            # client.sendall(response
            return response

        key = arguments[0]
        start_id = arguments[1]
        end_id = arguments[2]

        entries = xrange(key, start_id, end_id)

        encoded_entries = []
        for entry in entries:
            fields_items = []
            for field, value in entry["fields"].items():
                fields_items.append(encode_bulk_string(field))
                fields_items.append(encode_bulk_string(value))

            encoded_entries.append(encode_array([
                encode_bulk_string(entry["id"]),
                encode_array(fields_items)
            ]))

        return encode_array(encoded_entries)

    elif command == "XREAD":
        # Format: XREAD [BLOCK <ms>] STREAMS key1 key2 ... id1 id2 ...

        # 1. Parse optional BLOCK argument
        arguments_start_index = 0
        timeout_ms = None

        if len(arguments) >= 3 and arguments[0].upper() == "BLOCK":
            try:
                # Timeout is in milliseconds, convert to seconds for threading.wait
                timeout_ms = int(arguments[1])
                arguments_start_index = 2
            except ValueError:
                response = b"-ERR timeout is not an integer\r\n"
                # client.sendall(response
                return response

        # 2. Check for STREAMS keyword and argument count
        if len(arguments) < arguments_start_index + 3 or arguments[arguments_start_index].upper() != "STREAMS":
            response = b"-ERR wrong number of arguments or missing STREAMS keyword for 'XREAD' command\r\n"
            # client.sendall(response
            return response

        # 3. Find the split point between keys and IDs
        streams_keyword_index = arguments_start_index
        args_after_streams = arguments[streams_keyword_index + 1:]
        num_args_after_streams = len(args_after_streams)

        if num_args_after_streams % 2 != 0:
            response = b"-ERR unaligned key/id pairs for 'XREAD' command\r\n"
            # client.sendall(response
            return response

        num_keys = num_args_after_streams // 2

        keys_start_index = 0
        keys = args_after_streams[keys_start_index: keys_start_index + num_keys]
        ids_start_index = keys_start_index + num_keys
        ids = args_after_streams[ids_start_index:]

        resolved_ids = []
        for key, last_id in zip(keys, ids):
            if last_id == "$":
                resolved_ids.append(get_stream_max_id(key))
            else:
                resolved_ids.append(last_id)

        # 4. Main XREAD logic loop (synchronous part - fast path)
        stream_data = xread(keys, resolved_ids)

        if stream_data:
            # Non-blocking path: Data is available. Serialize and send immediately.
            response = _xread_serialize_response(stream_data)
            # client.sendall(response
            return response

        # 5. Blocking path
        if timeout_ms is not None:
            # We are blocking: list of entries is empty.

            if timeout_ms == 0:
                # BLOCK 0 means block indefinitely.
                timeout = None
            else:
                # Convert ms to seconds.
                timeout = timeout_ms / 1000.0

            # Since only one key/id pair is supported in this stage, enforce it for blocking
            if len(keys) != 1:
                response = b"-ERR only single key blocking supported in this stage\r\n"
                # client.sendall(response
                return response

            key_to_block = keys[0]

            # Create and register the condition
            client_condition = threading.Condition()
            client_condition.client_socket = client
            client_condition.key = key_to_block

            with BLOCKING_STREAMS_LOCK:
                BLOCKING_STREAMS.setdefault(key_to_block, []).append(client_condition)

            # Wait for notification or timeout
            notified = False
            with client_condition:
                if timeout is None:
                    notified = client_condition.wait()
                else:
                    notified = client_condition.wait(timeout)

            # 6. Post-block handling
            if notified:
                # If True, XADD already sent the response.
                return None
            else:
                # Timeout occurred. Clean up the blocking registration.
                with BLOCKING_STREAMS_LOCK:
                    if client_condition in BLOCKING_STREAMS.get(key_to_block, []):
                        BLOCKING_STREAMS[key_to_block].remove(client_condition)
                        if not BLOCKING_STREAMS[key_to_block]:
                            del BLOCKING_STREAMS[key_to_block]

                # Send Null Array response on timeout: Redis returns "*-1\r\n"
                response = b"*-1\r\n"
                # client.sendall(response
                return response

        # 7. Non-blocking path (no data, no BLOCK keyword) - returns Null Array
        response = b"*0\r\n"
        # client.sendall(response
        return response

    elif command == "INCR":
        if len(arguments) != 1:
            return encode_error("wrong number of arguments for 'incr' command")

        key = arguments[0]

        # Call the atomic helper function
        new_value, error_message = increment_key_value(key)

        if error_message:
            # Handle error from the helper (WRONGTYPE or not an integer/overflow)
            # client.sendall(error_message.encode())
            return error_message.encode()
        else:
            # Success: new_value is an integer. Return RESP Integer.
            return encode_integer(new_value)

    elif command == "DEL":
        if not arguments:
            return encode_error("wrong number of arguments for 'DEL' command")
        
        deleted_count = 0
        for key in arguments:
            deleted_count += delete_data_entry(key)
        
        return encode_integer(deleted_count)

    elif command == "INCRBY":
        if len(arguments) != 2:
            return encode_error("wrong number of arguments for 'INCRBY' command")
        
        key = arguments[0]
        try:
            amount = int(arguments[1])
        except ValueError:
            return encode_error("value is not an integer or out of range")
        
        new_value, error_msg = increment_key_value_by(key, amount)
        
        if error_msg:
            return error_msg.encode()
        
        return encode_integer(new_value)



    elif command == "QUIT":
        return encode_simple_string("OK")

    return encode_error(f"unknown command '{command}'")


def handle_command(command: str, arguments: list, client: ClientContext) -> bool:
    result = execute_single_command(command, arguments, client) # --- COMMAND EXECUTION ---

    if result is None or isinstance(result, bool):
        return result if isinstance(result, bool) else True

    # --- CLIENT RESPONSE ---
    try:
        client.sendall(result)
        print(f"Sent: Response for command '{command}' to {client.getpeername()}.")
    except Exception as e:
        print(f"Connection Error: Failed to send response: {e}")

    return True


def handle_connection(client: socket.socket, client_address):
    """
    This function is called for each new client connection.
    It manages the connection lifecycle and command loop.
    """
    print(f"Connection: New connection from {client_address}")

    ctx = ClientContext(conn=client, addr=client_address)   # Client context

    with ctx:
        while True:
            # The thread waits for the client to send a command. When you run {redis-cli ECHO hey}, the server receives the raw RESP bytes: data = b'*2\r\n$4\r\nECHO\r\n$3\r\nhey\r\n'
            try:
                data = client.recv(4096)
            except OSError:
                break

            if not data:
                print(f"Connection: Client {client_address} closed connection.")
                cleanup_blocked_client(ctx)
                break

            print(f"Received: Raw bytes from {client_address}: {data!r}")

            # The raw bytes are immediately sent to the parser to be translated into a usable Python list.
            parsed_command = parse_resp_array(data)

            if not parsed_command:
                print(f"Received: Could not parse command from {client_address}. Closing connection.")
                break

            command = parsed_command[0].upper()
            arguments = parsed_command[1:]

            print(f"Command: Parsed command: {command}, Arguments: {arguments}")

            # Delegate command execution to the router
            handle_command(command, arguments, ctx)