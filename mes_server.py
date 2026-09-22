import socket
import select
import msvcrt


# =========================================================
# SETTINGS
# =========================================================

HOST = "0.0.0.0"
PORT = 2000

MESSAGE_SIZE = 240

STX = 0x02
ETX = 0x03


# =========================================================
# TCP FUNCTIONS
# =========================================================

def recv_exact(conn, size):
    """
    Receive exactly the specified number of bytes
    from the TCP stream.

    Returns:
        bytes: Received data
        None : Connection lost
    """

    data = b""

    while len(data) < size:

        try:
            chunk = conn.recv(size - len(data))

        except (
            ConnectionResetError,
            ConnectionAbortedError,
            OSError
        ):
            return None

        if not chunk:
            return None

        data += chunk

    return data


def build_message(message):
    """
    Build a fixed-length 240-byte MES -> PLC telegram.

    Byte 0     : STX
    Data       : ASCII message
    Padding    : ASCII spaces
    Byte 239   : ETX
    """

    payload = message.encode("ascii")

    if len(payload) > MESSAGE_SIZE - 2:
        raise ValueError("Message is too long.")

    padding_length = MESSAGE_SIZE - 2 - len(payload)

    return (
        bytes([STX])
        + payload
        + b" " * padding_length
        + bytes([ETX])
    )


def parse_message(data):
    """
    Convert the 240-byte PLC telegram
    into a readable ASCII message.
    """

    if len(data) != MESSAGE_SIZE:
        raise ValueError("Invalid message length.")

    if data[0] != STX:
        raise ValueError("STX is missing.")

    if data[-1] != ETX:
        raise ValueError("ETX is missing.")

    return data[1:-1].decode("ascii").rstrip()


# =========================================================
# PRODUCT ID INPUT
# =========================================================

def get_product_id(conn):
    """
    Request a 12-character Product ID from the operator.

    While waiting for keyboard input, the PLC TCP
    connection is continuously monitored.

    Returns:
        str  : Valid Product ID
        None : PLC connection lost
    """

    while True:

        print()
        print(
            "Enter Product ID (12 characters): ",
            end="",
            flush=True
        )

        product_id = ""

        while True:

            # -------------------------------------------------
            # MONITOR PLC CONNECTION
            # -------------------------------------------------

            try:

                readable, _, _ = select.select(
                    [conn],
                    [],
                    [],
                    0.05
                )

            except OSError:

                print()
                print()
                print(
                    "[DISCONNECTED] PLC connection lost."
                )

                print(
                    "[STATUS] PLC is not connected."
                )

                return None

            if readable:

                try:

                    # Peek one byte without removing it
                    # from the TCP receive buffer.
                    peek_data = conn.recv(
                        1,
                        socket.MSG_PEEK
                    )

                    if peek_data == b"":

                        print()
                        print()

                        print(
                            "[DISCONNECTED] PLC connection lost."
                        )

                        print(
                            "[STATUS] PLC is not connected."
                        )

                        return None

                except (
                    ConnectionResetError,
                    ConnectionAbortedError,
                    OSError
                ):

                    print()
                    print()

                    print(
                        "[DISCONNECTED] PLC connection lost."
                    )

                    print(
                        "[STATUS] PLC is not connected."
                    )

                    return None

            # -------------------------------------------------
            # MONITOR KEYBOARD
            # -------------------------------------------------

            if msvcrt.kbhit():

                char = msvcrt.getwch()

                # ENTER
                if char == "\r":

                    print()
                    break

                # BACKSPACE
                elif char == "\b":

                    if product_id:

                        product_id = product_id[:-1]

                        print(
                            "\b \b",
                            end="",
                            flush=True
                        )

                # NORMAL PRINTABLE CHARACTER
                elif char.isprintable():

                    product_id += char

                    print(
                        char,
                        end="",
                        flush=True
                    )

        # -------------------------------------------------
        # PRODUCT ID VALIDATION
        # -------------------------------------------------

        if len(product_id) != 12:

            print(
                f"[ERROR] Product ID must contain exactly "
                f"12 characters. Entered: {len(product_id)}"
            )

            continue

        if not product_id.isascii():

            print(
                "[ERROR] Product ID must contain "
                "ASCII characters only."
            )

            continue

        if not product_id.isprintable():

            print(
                "[ERROR] Product ID contains "
                "invalid characters."
            )

            continue

        if "|" in product_id:

            print(
                "[ERROR] Product ID cannot contain "
                "the '|' character."
            )

            continue

        return product_id


# =========================================================
# PLC CONNECTION SESSION
# =========================================================

def handle_plc_connection(conn, addr):

    print()
    print(
        f"[CONNECTED] PLC: {addr[0]}:{addr[1]}"
    )

    print()
    print(
        "[WAITING] PLC product request (RW01)..."
    )

    # Reset MES sequence for each new TCP connection
    current_product_id = None
    expected_message = "RW01"

    while True:

        # -------------------------------------------------
        # RECEIVE MESSAGE
        # -------------------------------------------------

        data = recv_exact(
            conn,
            MESSAGE_SIZE
        )

        if data is None:

            print()
            print(
                "[DISCONNECTED] PLC connection lost."
            )

            print(
                "[STATUS] PLC is not connected."
            )

            return

        # -------------------------------------------------
        # PARSE MESSAGE
        # -------------------------------------------------

        try:

            message = parse_message(data)

        except ValueError as error:

            print(
                f"[ERROR] {error}"
            )

            continue

        print()
        print(
            f"[PLC -> MES] {message}"
        )

        fields = message.split("|")

        message_id = fields[0]

        # =================================================
        # RW01 - NEW PRODUCT REQUEST
        # =================================================

        if message_id == "RW01":

            if expected_message != "RW01":

                print(
                    "[WARNING] Unexpected RW01 message."
                )

                continue

            # Request Product ID while monitoring
            # the PLC connection.
            current_product_id = get_product_id(conn)

            # PLC disconnected while waiting for Product ID
            if current_product_id is None:

                return

            print()
            print(
                f"[NEW PRODUCT] {current_product_id}"
            )

            response = (
                f"MW01|"
                f"{current_product_id}|"
            )

            try:

                conn.sendall(
                    build_message(response)
                )

            except OSError:

                print()
                print(
                    "[DISCONNECTED] PLC connection lost."
                )

                print(
                    "[STATUS] PLC is not connected."
                )

                return

            print(
                f"[MES -> PLC] {response}"
            )

            expected_message = "RG01"

            print(
                "[WAITING] Product at scale conveyor..."
            )

        # =================================================
        # RG01 - SCALE CONVEYOR
        # =================================================

        elif message_id == "RG01":

            if expected_message != "RG01":

                print(
                    "[WARNING] Unexpected RG01 message."
                )

                continue

            if len(fields) < 3:

                print(
                    "[ERROR] Invalid RG01 message."
                )

                continue

            received_product_id = fields[1]

            weight = fields[2]

            print()
            print(
                "--------------- SCALE ----------------"
            )

            print(
                f"Product ID : {received_product_id}"
            )

            print(
                f"Weight     : {weight} kg"
            )

            print(
                "--------------------------------------"
            )

            # Validate Product ID
            if received_product_id != current_product_id:

                print(
                    "[ERROR] Product ID mismatch."
                )

                print(
                    f"[EXPECTED] {current_product_id}"
                )

                print(
                    f"[RECEIVED] {received_product_id}"
                )

                continue

            response = (
                f"MG01|"
                f"{current_product_id}|"
            )

            try:

                conn.sendall(
                    build_message(response)
                )

            except OSError:

                print()
                print(
                    "[DISCONNECTED] PLC connection lost."
                )

                print(
                    "[STATUS] PLC is not connected."
                )

                return

            print(
                f"[MES -> PLC] {response}"
            )

            expected_message = "RE01"

            print(
                "[WAITING] Product at label conveyor..."
            )

        # =================================================
        # RE01 - LABEL CONVEYOR
        # =================================================

        elif message_id == "RE01":

            if expected_message != "RE01":

                print(
                    "[WARNING] Unexpected RE01 message."
                )

                continue

            if len(fields) < 3:

                print(
                    "[ERROR] Invalid RE01 message."
                )

                continue

            received_product_id = fields[1]

            printer_no = fields[2]

            print()
            print(
                "--------------- LABEL ----------------"
            )

            print(
                f"Product ID : {received_product_id}"
            )

            print(
                f"Printer    : {printer_no}"
            )

            print(
                "--------------------------------------"
            )

            # Validate Product ID
            if received_product_id != current_product_id:

                print(
                    "[ERROR] Product ID mismatch."
                )

                print(
                    f"[EXPECTED] {current_product_id}"
                )

                print(
                    f"[RECEIVED] {received_product_id}"
                )

                continue

            # -------------------------------------------------
            # DEMO LABEL RESULT
            #
            # 0 = OK
            # 1 = FAULT
            # -------------------------------------------------

            label_status = 0

            response = (
                f"ME01|"
                f"{current_product_id}|"
                f"{label_status}|"
            )

            try:

                conn.sendall(
                    build_message(response)
                )

            except OSError:

                print()
                print(
                    "[DISCONNECTED] PLC connection lost."
                )

                print(
                    "[STATUS] PLC is not connected."
                )

                return

            print(
                f"[MES -> PLC] {response}"
            )

            print(
                "[LABEL] Label printed successfully."
            )

            print()
            print("=" * 60)

            print(
                f"PRODUCT {current_product_id} "
                f"TRANSFERRED TO WAREHOUSE"
            )

            print("=" * 60)

            # -------------------------------------------------
            # PRODUCT CYCLE RESET
            # -------------------------------------------------

            current_product_id = None

            expected_message = "RW01"

            print()
            print(
                "[WAITING] PLC product request (RW01)..."
            )

        # =================================================
        # UNKNOWN MESSAGE
        # =================================================

        else:

            print(
                f"[WARNING] Unknown message ID: {message_id}"
            )


# =========================================================
# TCP SERVER
# =========================================================

server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)


server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)


try:

    server.bind(
        (HOST, PORT)
    )

    server.listen(1)


except OSError:

    print()
    print(
        "[ERROR] TCP server could not be started."
    )

    print(
        f"[ERROR] TCP port {PORT} may already be in use."
    )

    raise SystemExit


# =========================================================
# SERVER START
# =========================================================

print("=" * 60)

print(
    "        PLC - MES CONVEYOR SIMULATOR"
)

print("=" * 60)

print(
    f"[LISTENING] TCP Port {PORT}"
)


# =========================================================
# CONTINUOUS CONNECTION LOOP
# =========================================================

try:

    while True:

        print()
        print(
            "[WAITING] PLC connection..."
        )

        # -------------------------------------------------
        # WAIT FOR PLC CONNECTION
        # -------------------------------------------------

        try:

            conn, addr = server.accept()

        except OSError:

            print()
            print(
                "[STATUS] PLC is not connected."
            )

            continue

        # -------------------------------------------------
        # HANDLE PLC SESSION
        # -------------------------------------------------

        try:

            handle_plc_connection(
                conn,
                addr
            )

        finally:

            try:

                conn.close()

            except OSError:

                pass

        # -------------------------------------------------
        # PLC DISCONNECTED
        # -------------------------------------------------

        print()
        print(
            "[STATUS] Waiting for a new PLC connection..."
        )

        # The loop automatically returns to:
        #
        # [WAITING] PLC connection...


# =========================================================
# PROGRAM STOP
# =========================================================

except KeyboardInterrupt:

    print()
    print()

    print(
        "[STOP] MES Simulator is shutting down..."
    )


finally:

    try:

        server.close()

    except OSError:

        pass

    print(
        "[STOP] TCP Server closed."
    )
