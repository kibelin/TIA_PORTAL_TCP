# S7-1500 ↔ Python MES TCP Communication

## Overview

This project demonstrates TCP/IP communication between a simulated **Siemens S7-1500 PLC** and a **Python-based MES simulator** using an ASCII-based protocol.
The PLC acts as the **active TCP client** and the Python application acts as the **TCP server**.

The process simulates a product moving through three logical stations:

1. Product entry / Product ID request
2. Scale conveyor / Weight reporting
3. Label station / Label confirmation

After the final acknowledgement, the product is considered transferred to the warehouse and the system becomes ready for the next product.

- **PLC:** TCP client
- **Python MES:** TCP server
- **TIA Portal:** V19
- **Simulation:** S7-PLCSIM Advanced
- **TCP Port:** 2000

---

# Message Sequence

| Direction | Message | Purpose |
|---|---|---|
| PLC → MES | `RW01` | Request a new Product ID |
| MES → PLC | `MW01` | Send Product ID to PLC |
| PLC → MES | `RG01` | Send Product ID and measured weight |
| MES → PLC | `MG01` | Acknowledge scale data |
| PLC → MES | `RE01` | Send Product ID and printer number |
| MES → PLC | `ME01` | Report label result |

Example cycle:

```text
PLC -> MES : RW01|
MES -> PLC : MW01|000000000001|

PLC -> MES : RG01|000000000001|0125|
MES -> PLC : MG01|000000000001|

PLC -> MES : RE01|000000000001|1|
MES -> PLC : ME01|000000000001|0|
```

In this demo:

```text
Weight      = 0125 kg
Printer No. = 1
Label 0     = OK
Label 1     = FAULT
```

`0 = OK` and `1 = FAULT` are the demo convention used by this implementation.

---

## Telegram Format

Messages are transferred as fixed-length **240-byte ASCII telegrams**.

```text
<STX>MessageID|Data1|Data2|...|<ETX>
```

- `STX` = `0x02`
- `ETX` = `0x03`
- Separator = `|`
- Unused bytes = ASCII spaces
- Product ID = 12 characters

Example:

```text
RW01|
MW01|000000000001|
RG01|000000000001|0125|
MG01|000000000001|
RE01|000000000001|1|
ME01|000000000001|0|
```

---

## PLC Program Structure

<img src="docs/images/plc_program_structure.png" width="500">

The PLC application is divided into three groups:

- **01-Sequence** — GRAPH product sequence
- **02-Communication** — TCP communication and telegram processing
- **03-Data** — Communication and product data blocks

### Main blocks

| Block | Purpose |
|---|---|
| `FB_Sequence` | Controls the product sequence with GRAPH |
| `FB_TCP_Client` | Handles TCP connection, send and receive logic |
| `FC_Build_RW01` | Builds the RW01 telegram |
| `FC_Build_RG01` | Builds the RG01 telegram |
| `FC_Build_RE01` | Builds the RE01 telegram |
| `FC_ParseRx` | Parses messages received from MES |

---

## GRAPH Sequence

<img src="docs/images/graph_sequence.png" width="260">

```text
IDLE
 ↓
SEND_RW01
 ↓
WAIT_MW01
 ↓
MOVE_TO_SCALE
 ↓
SEND_RG01
 ↓
WAIT_MG01
 ↓
MOVE_TO_LABEL
 ↓
SEND_RE01
 ↓
WAIT_ME01
 ↓
COMPLETE
```

A new cycle should start only after the previous product reaches `COMPLETE`.

---

## Siemens TCP Instructions

The PLC uses Siemens **Open User Communication (OUC)**.

| Instruction | Purpose |
|---|---|
| `TCON` | Establishs the TCP connection |
| `TDISCON` | Closes the TCP connection |
| `TSEND` | Sends the prepared telegram |
| `TRCV` | Receives data into the PLC receive buffer |

Application flow:

```text
FC_Build_xx
   ↓
TxBuffer
   ↓
TSEND
   ↓
TCP
   ↓
Python MES
```

Receive flow:

```text
Python MES
   ↓
TRCV
   ↓
RxBuffer
   ↓
FC_ParseRx
```

---

# Running the Demo

## 1. Start the Python MES simulator

```bash
python mes_server.py
```

Expected output:

```text
============================================================
        PLC - MES CONVEYOR SIMULATOR
============================================================
[LISTENING] TCP Port 2000

[WAITING] PLC connection...
```

## 2. Start the simulated S7-1500

Download the PLC project to S7-PLCSIM Advanced and place the CPU in RUN.

## 3. Enable communication

Set:

```text
DB_Communication.Enable = TRUE
```

The PLC establishes the TCP connection.

Python should report:

```text
[CONNECTED] PLC: <PLC-IP>:<dynamic-port>
```

## 4. Start a product cycle

Trigger the sequence start signal.

The PLC sends:

```text
RW01|
```

The Python MES then requests:

```text
Enter Product ID (12 characters):
```

Example:

```text
000000000001
```

The remaining scale and label messages are exchanged automatically.

## 5. Start another product

After the sequence returns to `IDLE`, trigger a new cycle.

The MES will request the next Product ID only after receiving the next `RW01`.

---

# Connection Recovery

The Python server is designed to remain active after a PLC disconnect.

```text
[DISCONNECTED] PLC connection lost.
[STATUS] PLC is not connected.
[STATUS] Waiting for a new PLC connection...

[WAITING] PLC connection...
```

When the PLC reconnects, a new MES session starts and the application state is reset to expect `RW01`.

---

## Communication Monitoring

<img src="docs/images/communication_watch_table.png" width="750">

Example communication status includes:

- TCP connection state
- TCON status
- Send status
- Receive acknowledgements
- Current Product ID

<img src="docs/images/python_mes_terminal.png" width="430">
---

## Example Simulation Network

```text
Host PC / Python MES : 192.168.50.1
PLCSIM Advanced PLC  : 192.168.50.20
Subnet Mask          : 255.255.255.0
TCP Port             : 2000
```

The IP addresses can be changed as long as the PLC connection parameters and Python server configuration match.

---

## Requirements

For the demo to run correctly:

- Python MES server must be running
- PLC communication must be enabled
- PLC and Python host must be reachable over TCP/IP
- The configured TCP port must match
- Only one product should be active at a time
- Product ID must contain exactly 12 ASCII characters

---

## References

### Project Protocol

The message structure is based on the project-specific **Communication between MES and PLC** specification.

### Siemens

PLC communication is implemented with Siemens **Open User Communication**:

- SIMATIC S7-1500 Communication Function Manual  
  https://support.industry.siemens.com/cs/ww/en/view/59192925

- Siemens Open User Communication documentation  
  https://docs.tia.siemens.cloud/

---

## Disclaimer

This project is intended for **education, simulation, and demonstration purposes**. It is not a production-ready MES interface.
