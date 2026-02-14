# LC0070 Payment Authorization - Technical Specification

## Overview

Line Code 0070 (LC0070) defines the payment authorization flow for cross-border
SWIFT transactions. This specification covers the end-to-end authorization process
from transaction receipt through final settlement approval.

## Authorization Flow

1. **Transaction Receipt** -- Inbound SWIFT message parsed and validated
2. **Sanctions Screening** -- Destination country checked against sanctioned list
3. **Amount Validation** -- Transaction amount verified within configured limits
4. **Risk Scoring** -- Automated risk assessment based on amount, country, sender
5. **Authorization Decision** -- Auto-approve, escalate, or deny based on risk score
6. **Settlement** -- Approved transactions forwarded to settlement engine

## Data Requirements

### Transaction Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| transaction_id | VARCHAR(36) | Yes | Unique SWIFT transaction ID |
| amount | DECIMAL(18,2) | Yes | Transaction amount |
| currency | CHAR(3) | Yes | ISO 4217 currency code |
| sender_bic | VARCHAR(11) | Yes | Sender BIC/SWIFT code |
| receiver_bic | VARCHAR(11) | Yes | Receiver BIC/SWIFT code |
| value_date | DATE | Yes | Settlement value date |
| destination_country | CHAR(2) | No | ISO 3166-1 country code |

### Risk Score Thresholds

- **Low risk (0-29)**: Auto-approved if amount <= 50,000
- **Medium risk (30-69)**: Escalated for manual review
- **High risk (70-100)**: Automatically denied

## Business Rules

- Transactions to sanctioned countries are blocked immediately (no risk scoring)
- High-value transactions (> 50,000) always require additional verification
- Risk score considers: transaction amount, destination country risk, sender history
- All authorization decisions are logged for audit compliance

## Integration Points

- **Inbound**: SWIFT message gateway (MT103, MT202)
- **Outbound**: Settlement engine, compliance reporting
- **Transformation**: BIC-to-entity resolution, currency normalization, date formatting

## Acceptance Criteria

- Authorization latency < 500ms for auto-approved transactions
- 100% sanctions screening coverage
- Audit trail for every authorization decision
- Support for 10,000+ concurrent transaction authorizations
