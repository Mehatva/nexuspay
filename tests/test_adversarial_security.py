import pytest
import time
import asyncio
from backend.core.mandate import SpendingMandate, CryptographicEngine, MandatePolicyEvaluator
from backend.integrations.paypal_client import PayPalClient
from backend.integrations.channel3_client import Channel3CatalogClient
from backend.agents.procurement_agent import ProcurementAgent

@pytest.fixture
def crypto():
    return CryptographicEngine("production-adversarial-secret-2026")

@pytest.fixture
def base_mandate():
    return SpendingMandate(
        mandate_id="MND-SECURITY-TEST-001",
        principal_id="PRINCIPAL-CHIEF-SECURITY-OFFICER",
        agent_id="AGENT-AUTONOMOUS-DEV-01",
        max_budget_usd=500.0,
        allowed_categories=["cloud_compute", "software_licenses"],
        allowed_merchants=["AWS", "Docker Inc"],
        require_2fa_above_usd=250.0,
        expires_at_timestamp=int(time.time()) + 3600
    )

def test_cumulative_budget_overflow_attack(crypto, base_mandate):
    sig = crypto.sign_mandate(base_mandate)

    # First purchase: $300 (valid, under $500 total)
    res1 = MandatePolicyEvaluator.evaluate(
        mandate=base_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=300.0,
        merchant_name="AWS"
    )
    assert res1.allowed is True
    assert res1.requires_multisig is True
    # Simulate settlement
    base_mandate.current_spent_usd += 300.0

    # Second purchase: $250 (300 + 250 = 550 > 500) -> MUST BE BLOCKED BY CUMULATIVE CEILING
    res2 = MandatePolicyEvaluator.evaluate(
        mandate=base_mandate,
        signature=sig,
        crypto=crypto,
        item_category="software_licenses",
        price_usd=250.0,
        merchant_name="Docker Inc"
    )
    assert res2.allowed is False
    assert "CUMULATIVE_BUDGET_EXCEEDED" in res2.reason

def test_replay_attack_prevention(crypto, base_mandate):
    sig = crypto.sign_mandate(base_mandate)
    nonce = "NONCE-REPLAY-TEST-XYZ"

    # Consume nonce first time
    res = MandatePolicyEvaluator.evaluate(
        mandate=base_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=100.0,
        merchant_name="AWS",
        nonce=nonce
    )
    assert res.allowed is True

    # Mark nonce as consumed
    base_mandate.used_nonces.append(nonce)

    # Replay the same nonce
    res_replay = MandatePolicyEvaluator.evaluate(
        mandate=base_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=100.0,
        merchant_name="AWS",
        nonce=nonce
    )
    assert res_replay.allowed is False
    assert "REPLAY_ATTACK_DETECTED" in res_replay.reason

def test_expired_mandate_rejection(crypto):
    expired_m = SpendingMandate(
        mandate_id="MND-EXPIRED-99",
        principal_id="USER-EXPIRED",
        agent_id="AGENT-EXPIRED",
        max_budget_usd=1000.0,
        allowed_categories=["cloud_compute"],
        expires_at_timestamp=int(time.time()) - 10  # Expired 10 seconds ago
    )
    sig = crypto.sign_mandate(expired_m)

    res = MandatePolicyEvaluator.evaluate(
        mandate=expired_m,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=50.0,
        merchant_name="AWS"
    )
    assert res.allowed is False
    assert "MANDATE_EXPIRED" in res.reason

def test_merchant_whitelist_violation(crypto, base_mandate):
    sig = crypto.sign_mandate(base_mandate)

    # Allowed category, but unauthorized merchant "Shadowy Cloud Provider"
    res = MandatePolicyEvaluator.evaluate(
        mandate=base_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=50.0,
        merchant_name="Shadowy Cloud Provider"
    )
    assert res.allowed is False
    assert "MERCHANT_VIOLATION" in res.reason

@pytest.mark.anyio
async def test_agent_concurrent_execution_stress(crypto, base_mandate):
    sig = crypto.sign_mandate(base_mandate)
    paypal = PayPalClient(env="sandbox")
    catalog = Channel3CatalogClient()
    agent = ProcurementAgent("AGENT-STRESS-01", crypto, paypal, catalog)

    # Dispatch multiple procurement requests in parallel
    tasks = [
        agent.execute_procurement_goal("Buy dev tool", "Docker Business", base_mandate, sig, force_multisig_approve=True),
        agent.execute_procurement_goal("Buy cloud server", "AWS EC2", base_mandate, sig, force_multisig_approve=True)
    ]
    results = await asyncio.gather(*tasks)

    # Total spend should be accurately reflected
    assert len(results) == 2
    assert base_mandate.current_spent_usd > 0
    assert len(base_mandate.used_nonces) >= 1
