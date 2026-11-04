import pytest
import time
from backend.core.mandate import SpendingMandate, CryptographicEngine, MandatePolicyEvaluator

@pytest.fixture
def crypto():
    return CryptographicEngine("test-secret-key-12345")

@pytest.fixture
def valid_mandate():
    return SpendingMandate(
        mandate_id="MND-TEST-001",
        principal_id="USER-TEST",
        agent_id="AGENT-TEST",
        max_budget_usd=500.0,
        allowed_categories=["cloud_compute", "software_licenses"],
        allowed_merchants=["AWS", "Docker"],
        require_2fa_above_usd=300.0,
        expires_at_timestamp=int(time.time()) + 3600
    )

def test_tamper_proof_signature(crypto, valid_mandate):
    sig = crypto.sign_mandate(valid_mandate)
    assert crypto.verify_mandate_signature(valid_mandate, sig) is True

    # Tamper with budget
    tampered_mandate = valid_mandate.model_copy(update={"max_budget_usd": 9999.0})
    assert crypto.verify_mandate_signature(tampered_mandate, sig) is False

def test_category_and_budget_policy(crypto, valid_mandate):
    sig = crypto.sign_mandate(valid_mandate)

    # Valid under $300 (No 2FA needed)
    res = MandatePolicyEvaluator.evaluate(
        mandate=valid_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=150.0,
        merchant_name="AWS"
    )
    assert res.allowed is True
    assert res.requires_multisig is False

    # Valid between $300 and $500 (Triggers 2FA)
    res_multisig = MandatePolicyEvaluator.evaluate(
        mandate=valid_mandate,
        signature=sig,
        crypto=crypto,
        item_category="software_licenses",
        price_usd=350.0,
        merchant_name="Docker"
    )
    assert res_multisig.allowed is True
    assert res_multisig.requires_multisig is True

    # Exceeds budget ($501)
    res_over = MandatePolicyEvaluator.evaluate(
        mandate=valid_mandate,
        signature=sig,
        crypto=crypto,
        item_category="cloud_compute",
        price_usd=501.0,
        merchant_name="AWS"
    )
    assert res_over.allowed is False
    assert "BUDGET_EXCEEDED" in res_over.reason

    # Disallowed category
    res_cat = MandatePolicyEvaluator.evaluate(
        mandate=valid_mandate,
        signature=sig,
        crypto=crypto,
        item_category="unverified_goods",
        price_usd=50.0,
        merchant_name="AWS"
    )
    assert res_cat.allowed is False
    assert "CATEGORY_VIOLATION" in res_cat.reason
