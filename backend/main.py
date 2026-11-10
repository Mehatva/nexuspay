import os
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from backend.core.mandate import SpendingMandate, CryptographicEngine
from backend.integrations.paypal_client import PayPalClient
from backend.integrations.channel3_client import Channel3CatalogClient
from backend.agents.procurement_agent import ProcurementAgent
from backend.agents.dispute_agent import DisputeResolutionAgent
from backend.webhooks.listener import global_webhook_store

app = FastAPI(title="NexusPay Autonomous Agentic Commerce API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
SECRET_KEY = os.getenv("NEXUS_HMAC_SECRET", "nexuspay-autonomous-secret-key-prod-2026")
crypto_engine = CryptographicEngine(SECRET_KEY)
paypal_client = PayPalClient()
catalog_client = Channel3CatalogClient()
agent = ProcurementAgent(
    agent_id="AGENT-AUTONOMOUS-DEV-01",
    crypto_engine=crypto_engine,
    paypal_client=paypal_client,
    catalog_client=catalog_client
)
dispute_agent = DisputeResolutionAgent(
    agent_id="AGENT-DISPUTE-ORACLE-01",
    crypto_engine=crypto_engine,
    paypal_client=paypal_client
)


# In-memory database of active mandates and settled orders
active_mandates: Dict[str, Dict[str, Any]] = {}
active_disputes: List[Dict[str, Any]] = []
transaction_ledger: List[Dict[str, Any]] = [
    {
        "tx_id": "TX-984102",
        "timestamp": "2026-11-03 08:30:12",
        "agent_id": "AGENT-AUTONOMOUS-DEV-01",
        "merchant": "Docker Inc",
        "item": "Docker Business Subscription (Annual / 10 seats)",
        "amount_usd": 288.00,
        "paypal_order_id": "PP-SANDBOX-8FA91C283B41",
        "status": "SETTLED",
        "security_score": "100%",
        "mandate_id": "MND-BOOTSTRAP-01"
    },
    {
        "tx_id": "TX-984099",
        "timestamp": "2026-11-03 08:15:44",
        "agent_id": "AGENT-AUTONOMOUS-DEV-01",
        "merchant": "Amazon Web Services",
        "item": "AWS EC2 m6i.4xlarge 1-Yr Standard RI",
        "amount_usd": 349.00,
        "paypal_order_id": "PP-SANDBOX-71E094AC2B90",
        "status": "SETTLED",
        "security_score": "100%",
        "mandate_id": "MND-BOOTSTRAP-01"
    }
]

# Request Schemas
class CreateMandateRequest(BaseModel):
    max_budget_usd: float
    allowed_categories: List[str]
    allowed_merchants: Optional[List[str]] = None
    require_2fa_above_usd: float = 250.0
    validity_hours: int = 24

class RunProcurementRequest(BaseModel):
    mandate_id: str
    goal: str
    query: str
    force_multisig_approve: bool = False

class TriggerDisputeRequest(BaseModel):
    tx_id: str
    breach_type: str = "INVALID_LICENSE_KEY"
    incident_details: Optional[str] = "Merchant digital credential failed cryptographic verification"

class VerifyMandateRequest(BaseModel):
    mandate: Dict[str, Any]
    signature: str


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "paypal_env": paypal_client.env,
        "paypal_configured": paypal_client.is_configured,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    }

@app.get("/api/catalog")
async def get_catalog(query: Optional[str] = None):
    q = query or ""
    return await catalog_client.search_items(q)

@app.post("/api/mandates")
async def create_mandate(req: CreateMandateRequest):
    mandate_id = f"MND-{int(time.time()*1000)}"
    mandate = SpendingMandate(
        mandate_id=mandate_id,
        principal_id="PRINCIPAL-ENTERPRISE-ADMIN",
        agent_id="AGENT-AUTONOMOUS-DEV-01",
        max_budget_usd=req.max_budget_usd,
        allowed_categories=req.allowed_categories,
        allowed_merchants=req.allowed_merchants,
        require_2fa_above_usd=req.require_2fa_above_usd,
        expires_at_timestamp=int(time.time()) + (req.validity_hours * 3600)
    )
    signature = crypto_engine.sign_mandate(mandate)
    active_mandates[mandate_id] = {
        "mandate": mandate,
        "signature": signature
    }
    return {
        "mandate_id": mandate_id,
        "mandate": mandate.model_dump(),
        "signature": signature
    }

@app.get("/api/mandates")
async def list_mandates():
    return [
        {"mandate_id": k, "mandate": v["mandate"].model_dump(), "signature": v["signature"]}
        for k, v in active_mandates.items()
    ]

@app.post("/api/agent/procure")
@app.post("/api/agent/run")
async def run_procurement(req: RunProcurementRequest):
    mandate_data = active_mandates.get(req.mandate_id)
    if not mandate_data:
        # Create a default emergency mandate if not specified
        default_m = SpendingMandate(
            mandate_id=req.mandate_id,
            principal_id="PRINCIPAL-AUTO-GEN",
            agent_id="AGENT-AUTONOMOUS-DEV-01",
            max_budget_usd=1500.0,
            allowed_categories=["software_licenses", "cloud_compute", "infrastructure", "networking"],
            allowed_merchants=None,
            require_2fa_above_usd=500.0,
            expires_at_timestamp=int(time.time()) + 86400
        )
        sig = crypto_engine.sign_mandate(default_m)
        mandate_data = {"mandate": default_m, "signature": sig}
        active_mandates[req.mandate_id] = mandate_data

    result = await agent.execute_procurement_goal(
        goal_description=req.goal,
        query=req.query,
        mandate=mandate_data["mandate"],
        signature=mandate_data["signature"],
        force_multisig_approve=req.force_multisig_approve
    )

    if result.get("success"):
        item = result["item"]
        tx_record = {
            "tx_id": f"TX-{int(time.time()*1000) % 1000000}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "agent_id": agent.agent_id,
            "merchant": item["merchant"],
            "item": item["title"],
            "amount_usd": item["price_usd"],
            "paypal_order_id": result["order_id"],
            "status": "SETTLED",
            "security_score": "100%",
            "mandate_id": req.mandate_id
        }
        transaction_ledger.insert(0, tx_record)

    return result

@app.get("/api/ledger")
async def get_ledger():
    return transaction_ledger

@app.get("/api/webhooks")
async def get_webhooks():
    return global_webhook_store.get_recent_events()

@app.post("/api/webhooks/paypal")
async def receive_paypal_webhook(request: Request):
    payload = await request.json()
    record = global_webhook_store.process_incoming_webhook(payload)
    return {"status": "SUCCESS", "event": record}

@app.post("/api/agent/dispute")
async def trigger_dispute(req: TriggerDisputeRequest):
    # Locate transaction in ledger
    tx = next((t for t in transaction_ledger if t["tx_id"] == req.tx_id), None)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction {req.tx_id} not found in ledger")

    result = await dispute_agent.evaluate_and_resolve_dispute(
        transaction=tx,
        breach_type=req.breach_type,
        incident_details=req.incident_details or "Autonomous agent detected non-compliant SLA delivery."
    )

    if result.get("success"):
        # Update transaction ledger status
        tx["status"] = "REFUNDED (DISPUTE RESOLVED)"
        tx["dispute_id"] = result["dispute_id"]
        tx["refund_id"] = result.get("refund_id")

        # Save to dispute history
        active_disputes.insert(0, {
            "dispute_id": result["dispute_id"],
            "tx_id": req.tx_id,
            "merchant": tx.get("merchant"),
            "item": tx.get("item"),
            "amount_usd": tx.get("amount_usd"),
            "breach_type": req.breach_type,
            "resolution": result.get("resolution"),
            "evidence_hash": result.get("evidence_hash"),
            "refund_id": result.get("refund_id"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        # Emit webhook event
        global_webhook_store.process_incoming_webhook({
            "event_type": "CUSTOMER.DISPUTE.RESOLVED",
            "summary": f"Dispute {result['dispute_id']} resolved in favor of Buyer. Refund {result.get('refund_id')} completed.",
            "resource": {
                "id": result["dispute_id"],
                "transaction_id": tx["tx_id"],
                "amount": {"value": str(tx["amount_usd"]), "currency_code": "USD"}
            }
        })

    return result

@app.get("/api/disputes")
async def get_disputes():
    return active_disputes

@app.post("/api/mandates/verify")
async def verify_mandate_tamper(req: VerifyMandateRequest):
    try:
        mandate_obj = SpendingMandate(**req.mandate)
        is_valid = crypto_engine.verify_mandate_signature(mandate_obj, req.signature)
        return {
            "valid": is_valid,
            "mandate_id": mandate_obj.mandate_id,
            "hash_evaluated": crypto_engine._compute_payload_hash(mandate_obj)
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


# Serve static dashboard UI
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
@app.get("/index.html")
@app.get("/dashboard")
@app.get("/api/index.py")
async def root_index():
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "api", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "nexuspay-dashboard-final.html"),
        os.path.join(os.getcwd(), "index.html"),
        os.path.join(os.getcwd(), "frontend", "index.html"),
        "/var/task/index.html",
        "/var/task/backend/index.html",
        "/var/task/frontend/index.html"
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>NexusPay Protocol Running</h1><p>Frontend loading...</p>", status_code=200)

@app.get("/api")
@app.get("/api/")
async def api_info():
    return {
        "status": "online",
        "service": "NexusPay Autonomous Protocol API",
        "dashboard": "/",
        "endpoints": ["/api/health", "/api/catalog", "/api/mandates", "/api/ledger", "/api/webhooks"]
    }

@app.get("/{full_path:path}")
async def catch_all_routes(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API route /{full_path} not found")
    return await root_index()
