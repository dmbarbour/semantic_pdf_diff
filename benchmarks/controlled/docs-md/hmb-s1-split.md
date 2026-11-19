# Harbour Monitoring Buoy: System Requirements

## 1 Scope

This document states the requirements for the harbour monitoring buoy. Each requirement is identified, stated and verified as below.

## 2 Requirements

**Table 1. Buoy requirements**

| Temporary UID | Condition | Subject | Verb | Clause(s)/Content | REQUIREMENTS NOTE |
| --- | --- | --- | --- | --- | --- |
| HMBv0.1-001 |  | The buoy hull | SHALL | withstand ambient temperatures from -42 °C to +58 °C without damage. | The hull supplier rates the hull to +36 °C only; expect the upper limit to be lowered. |
| HMBv0.1-002 | In the event of a loss of main power | the data logger | SHALL | retain every logged record for at least 85 hours. | Confirm whether the hold-up battery or the flash memory carries this. |
| HMBv0.1-003 |  | The buoy hull above the waterline | SHALL | be painted international orange. | The harbour authority may prefer yellow; ask before the paint is ordered. |
| HMBv0.1-004 |  | The data logger | SHOULD | store its records in a documented, non-proprietary file format. | Wording to be agreed with the data management group. |
| HMBv0.1-005 |  | The logger firmware | MAY | be updated over the satellite link. | Security review pending. |
| HMBv0.1-006 |  | The operator | WILL | inspect the mooring chain every 11 months. | Interval to be confirmed against the chain supplier's guidance. |
| HMBv0.1-007 | While the buoy is moored | the telemetry unit | SHALL | report its position and water temperature at intervals of no more than 30 minutes. | During storms the harbour office wants reports every 13 minutes instead. |
| HMBv0.1-008 |  | The navigation lamp | SHALL | be visible at a range of at least 4.4 nautical miles on a clear night. | Range assumes the standard atmospheric transmissivity. |

