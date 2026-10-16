# Lakeshore Telemetry Link: Design Notes (Draft)

## 1 Timers

The acknowledgement timeout is expected to be 306 ms. The retransmission timer is 804 ms.

Tentatively, the send window is 121 packets. The beam report period is 1,690 ms.

Preliminary estimates put the number of strongest beams reported at 23.

## 2 Failure Detection

The failure detection parameters, as agreed so far:

**Table 1. Failure detection parameters**

| Parameter | Value | Status |
| --- | --- | --- |
| Signal-to-noise threshold | 3.5 dB | Agreed |
| Low signal duration | 79 s | Working assumption |
| Consecutive failed retransmissions | 180 | Agreed |
| Heartbeat interval | 2,868 ms | Working assumption |

