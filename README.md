# NexusPay — Zero-Trust Autonomous Commerce & Arbitration Protocol for PayPal

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![PayPal Orders v2](https://img.shields.io/badge/PayPal-Orders%20v2-0070ba.svg)](https://developer.paypal.com/docs/api/orders/v2/)
[![AG Grid](https://img.shields.io/badge/AG%20Grid-Quartz%20Dark-00e5ff.svg)](https://www.ag-grid.com/)
[![Zero-Trust Security](https://img.shields.io/badge/Security-HMAC--SHA256%20Mandates-success.svg)](#security-architecture)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **"The Agentic Economy is already here. But who gives an AI agent a corporate credit card?"**
>
> NexusPay is a cryptographic protocol and multi-agent coordination layer that transforms PayPal into the primary financial rail for autonomous AI agents. By coupling **tamper-proof spending mandates**, **risk-tiered multi-signature authorization**, and an **autonomous dispute arbitration oracle**, NexusPay enables enterprises to safely delegate financial autonomy to AI agents with mathematical guarantees.

---

## 🏛️ High-Level System Architecture

```
                               ┌─────────────────────────────────────────┐
                               │       HUMAN ENTERPRISE PRINCIPAL        │
                               └────────────────────┬────────────────────┘
                                                    │ Signs Spending Mandate
                                                    ▼ (HMAC-SHA256 Policy)
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                                NEXUSPAY PROTOCOL                                │
   │                                                                                 │
   │   ┌───────────────────────────┐                 ┌───────────────────────────┐   │
   │   │       AGENT ALPHA         │                 │       AGENT OMEGA         │   │
   │   │  (Autonomous Procurement) │                 │  (Dispute & Arbitration)  │   │
   │   └─────────────┬─────────────┘                 └─────────────▲─────────────┘   │
   │                 │ Validates                                   │ Telemetry Breach│
   │                 ▼ Mandate                                     │ Detection       │
   │   ┌───────────────────────────┐                 ┌─────────────┴─────────────┐   │
   │   │  Cryptographic Policy     │                 │   SHA-256 Evidence        │   │
   │   │  Evaluator & Nonce Engine │                 │   Bundle Packager         │   │
   │   └─────────────┬─────────────┘                 └─────────────┬─────────────┘   │
   └─────────────────┼─────────────────────────────────────────────┼─────────────────┘
                     │ If ≤ Threshold: Auto-Authorize              │ If SLA Broken:
                     │ If > Threshold: Human 2FA Passkey           │ Auto-Claim Filed
                     ▼                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │                          PAYPAL REST API INFRASTRUCTURE                         │
   │                                                                                 │
   │       ┌───────────────────────┐                 ┌───────────────────────┐       │
   │       │   PayPal Orders v2    │                 │    PayPal Disputes    │       │
   │       │   (Order & Capture)   │                 │    & Refund Engine    │       │
   │       └───────────────────────┘                 └───────────────────────┘       │
   └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ The Four Pillars of NexusPay

### 1. Cryptographic Spending Mandates
Rather than giving autonomous agents raw credentials or unrestricted credit cards, principals issue a time-bound, cryptographically signed JSON mandate:
- **Strict Budget Ceiling**: Absolute spending limits per mandate.
- **Category Whitelisting**: Limits spending strictly to verified categories (e.g., `cloud_compute`, `software_licenses`).
- **Vendor Constraints**: Optional merchant-specific locks.
- **HMAC-SHA256 Signatures**: Tampering with any byte invalidates the mandate instantly.

### 2. Risk-Tiered Autonomous Settlement
- **Low-Risk (< $250)**: Instant zero-touch settlement via PayPal Orders v2 with sub-second execution.
- **High-Risk (≥ $250)**: Intercepted by policy engine; pauses transaction and initiates a FIDO2 / WebAuthn human co-signature workflow before PayPal capture.

### 3. Autonomous Dispute Resolution Oracle (`Agent Omega`)
When an AI agent procures a digital asset (e.g., API seat, cloud instance) and the merchant delivers an invalid license key or breaches SLA:
1. **Anomaly Detection**: Agent Omega validates delivered artifacts via automated health checks.
2. **Evidence Packaging**: Compiles a deterministic SHA-256 evidence package containing original mandate proofs, transaction references, and timestamped error logs.
3. **Automated Adjudication**: Submits claims via the PayPal Disputes API, securing autonomous refunds without human intervention.

### 4. Enterprise Glassmorphic Command Center
- **Live AG Grid Ledger**: Telemetry stream of all agent transactions with order references and dispute status.
- **Dual Thought Stream**: Watch Agent Alpha (Procurement) and Agent Omega (Dispute Oracle) reason in real time.
- **Tamper-Proof Sandbox**: Interactive playground to simulate malicious payload modifications and verify cryptographic rejection.
- **Acoustic Feedback Engine**: Built-in Web Audio API synthesizer for tactile acoustic feedback.

---

## 🚀 Quickstart Guide

### Option A: Local Development

```bash
# 1. Clone repository
git clone https://github.com/Mehatva/nexuspay.git
cd nexuspay

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run test suite
pytest

# 5. Launch the NexusPay Command Center
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at **`http://127.0.0.1:8000`** to access the live dashboard.

---

### Option B: 1-Command Docker Deployment

```bash
# Build and run containerized service
docker compose up --build
```

---

## 🧪 Comprehensive Test Suite

NexusPay includes automated unit tests verifying the cryptographic engine, policy evaluator, and dispute oracle:

```bash
$ pytest -v
============================= test session starts ==============================
tests/test_core.py::test_tamper_proof_signature PASSED                    [ 25%]
tests/test_core.py::test_category_and_budget_policy PASSED                [ 50%]
tests/test_dispute_agent.py::test_dispute_oracle_end_to_end PASSED        [ 75%]
tests/test_dispute_agent.py::test_paypal_refund_capture PASSED            [100%]
============================== 4 passed in 0.08s ===============================
```

---

## 🔌 API Reference Summary

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | `GET` | Service & PayPal Sandbox connection health |
| `/api/mandates` | `POST` | Issue and cryptographically sign spending mandates |
| `/api/mandates/verify`| `POST` | Verify cryptographic integrity of a mandate payload |
| `/api/agent/procure` | `POST` | Dispatch Agent Alpha for autonomous catalog procurement |
| `/api/agent/dispute` | `POST` | Dispatch Agent Omega to compile evidence and dispute a transaction |
| `/api/ledger` | `GET` | Real-time financial settlement ledger (AG Grid feed) |
| `/api/webhooks/paypal`| `POST` | Ingestion endpoint for PayPal REST webhook notifications |

---

## 💡 Why PayPal Wins with NexusPay

As agentic workflows (AutoGPT, Devin, LangGraph swarms) take over enterprise operations, **commerce is transitioning from Human-to-Merchant (H2M) to Agent-to-Merchant (A2M)**.
- Credit card networks are vulnerable to prompt injections and rogue spending loops.
- Crypto rails lack buyer protection, chargeback mechanisms, and enterprise compliance.
- **PayPal is uniquely positioned to dominate this market** by serving as the trusted escrow, identity, and dispute layer for agentic commerce. NexusPay is the open protocol that makes this reality today.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
