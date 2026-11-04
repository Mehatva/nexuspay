import pytest
import time
from backend.core.mandate import CryptographicEngine, SpendingMandate
from backend.integrations.paypal_client import PayPalClient
from backend.agents.dispute_agent import DisputeResolutionAgent

@pytest.fixture
def crypto():
    return CryptographicEngine("test-secret-oracle-2026")

@pytest.fixture
def paypal():
    return PayPalClient(env="sandbox")

@pytest.fixture
def dispute_agent(crypto, paypal):
    return DisputeResolutionAgent(
        agent_id="AGENT-DISPUTE-TEST",
        crypto_engine=crypto,
        paypal_client=paypal
    )

@pytest.mark.anyio
async def test_dispute_oracle_end_to_end(dispute_agent):
    mock_tx = {
        "tx_id": "TX-TEST-8891",
        "timestamp": "2026-11-04 10:00:00",
        "agent_id": "AGENT-TEST",
        "merchant": "Docker Inc",
        "item": "Docker Enterprise Seat",
        "amount_usd": 288.00,
        "paypal_order_id": "PP-SANDBOX-TEST-ORDER-1",
        "status": "SETTLED",
        "security_score": "100%",
        "mandate_id": "MND-TEST-01"
    }

    result = await dispute_agent.evaluate_and_resolve_dispute(
        transaction=mock_tx,
        breach_type="INVALID_LICENSE_KEY",
        incident_details="Delivered activation key returned HTTP 401 unauthenticated"
    )

    assert result["success"] is True
    assert result["status"] == "REFUNDED"
    assert result["dispute_id"].startswith("PP-DISPUTE-")
    assert result["refunded_amount_usd"] == 288.00
    assert len(result["evidence_hash"]) == 64  # SHA256 length
    assert len(result["thought_log"]) >= 4

@pytest.mark.anyio
async def test_paypal_refund_capture(paypal):
    res = await paypal.refund_capture(capture_id="CAP-TEST-1234", amount_usd=150.0)
    assert res["status"] == "COMPLETED"
    assert res["id"].startswith("REF-")
