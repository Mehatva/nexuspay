import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
import time

@pytest.mark.anyio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("online", "HEALTHY")
        assert "server_time" in data

@pytest.mark.anyio
async def test_catalog_search():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/catalog?query=docker")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) > 0
        assert items[0]["merchant"] == "Docker Inc"

@pytest.mark.anyio
async def test_mandate_lifecycle_and_tamper_detection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create mandate
        payload = {
            "principal_id": "PRINCIPAL-CORP-SEC-01",
            "agent_id": "AGENT-AUTONOMOUS-DEV-01",
            "max_budget_usd": 400.0,
            "allowed_categories": ["software_licenses", "cloud_compute"],
            "allowed_merchants": ["Docker Inc", "Amazon Web Services"],
            "require_2fa_above_usd": 300.0,
            "ttl_seconds": 3600
        }
        resp = await client.post("/api/mandates", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "signature" in data
        mandate_obj = data["mandate"]
        sig = data["signature"]

        # Verify valid signature
        verify_resp = await client.post("/api/mandates/verify", json={"mandate": mandate_obj, "signature": sig})
        assert verify_resp.status_code == 200
        assert verify_resp.json()["valid"] is True
        assert "hash_evaluated" in verify_resp.json()

        # Verify tampered budget detection
        tampered = dict(mandate_obj)
        tampered["max_budget_usd"] = 99999.0
        tamper_resp = await client.post("/api/mandates/verify", json={"mandate": tampered, "signature": sig})
        assert tamper_resp.status_code == 200
        assert tamper_resp.json()["valid"] is False

@pytest.mark.anyio
async def test_autonomous_procurement_and_settlement():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create compliant mandate for Docker ($288 < $300 threshold)
        mandate_payload = {
            "principal_id": "PRINCIPAL-CORP-SEC-01",
            "agent_id": "AGENT-AUTONOMOUS-DEV-01",
            "max_budget_usd": 350.0,
            "allowed_categories": ["software_licenses"],
            "allowed_merchants": ["Docker Inc"],
            "require_2fa_above_usd": 300.0,
            "ttl_seconds": 3600
        }
        m_resp = await client.post("/api/mandates", json=mandate_payload)
        m_data = m_resp.json()
        mandate_id = m_data["mandate"]["mandate_id"]

        # 2. Run procurement
        run_payload = {
            "mandate_id": mandate_id,
            "goal": "Procure Docker Business 10 seats license",
            "query": "docker",
            "force_multisig_approve": False
        }
        p_resp = await client.post("/api/agent/run", json=run_payload)
        assert p_resp.status_code == 200
        p_data = p_resp.json()
        assert p_data["success"] is True
        assert p_data["status"] == "SETTLED"
        assert "order_id" in p_data
        assert p_data["order_id"].startswith("PP-SANDBOX-")

@pytest.mark.anyio
async def test_dispute_oracle_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get transaction ledger
        ledger_resp = await client.get("/api/ledger")
        assert ledger_resp.status_code == 200
        txs = ledger_resp.json()
        assert len(txs) > 0
        target_tx = txs[0]["tx_id"]

        # Trigger dispute
        dispute_req = {
            "tx_id": target_tx,
            "breach_type": "INVALID_LICENSE_KEY",
            "incident_details": "Merchant digital license failed automated cryptographic audit."
        }
        d_resp = await client.post("/api/agent/dispute", json=dispute_req)
        assert d_resp.status_code == 200
        d_data = d_resp.json()
        assert d_data["success"] is True
        assert d_data["status"] == "REFUNDED"
        assert "evidence_hash" in d_data
        assert d_data["dispute_id"].startswith("PP-DISPUTE-")
