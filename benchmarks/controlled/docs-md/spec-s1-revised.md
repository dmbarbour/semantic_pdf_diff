# Lakeshore Telemetry Link: Protocol Specification

## 1 Status Report Formats

Three formats carry buffer status to the gateway. The short status report carries the status of one channel group in a buffer size field of 8 bits. The extended short status report also carries the status of one channel group, in a buffer size field of 33 bits. The long status report carries up to 23 channel groups, each in a buffer size field of 28 bits.

## 2 Header Fields

Every packet starts with the header fields of Table 1, in order. Each length field gives the length of the field that follows it.

**Table 1. Header fields**

| Field | Length (bits) |
| --- | --- |
| Version | 13 |
| Session ID Length | 14 |
| Session ID | up to 181 |
| Packet Number Length | 9 |
| Packet Number | up to 36 |

## 3 Measurement Report

The measurement report contains, in this order:

– the serving cell index, 12 bits;

– the beam index, 18 bits;

– the received signal strength, 16 bits;

– the timing advance, 10 bits.

## 4 Link Failure Detection

A link failure is declared when any of the following conditions holds.

Condition 1: no acknowledgement is received within 856 ms.

Condition 2: 24 consecutive retransmissions fail.

Condition 3: the signal-to-noise ratio stays below 4.3 dB for 60 s.

## 5 Timers by Link State

When the link is congested, the following values apply.

The retransmission timer is 709 ms. The send window is 145 packets.

When the link is idle, the following values apply.

The retransmission timer is 1,245 ms. The send window is 180 packets.

