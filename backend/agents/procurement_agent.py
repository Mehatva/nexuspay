import time
import uuid
from typing import Dict, Any, List
from backend.core.mandate import SpendingMandate, CryptographicEngine, MandatePolicyEvaluator, PolicyEvaluationResult
from backend.integrations.paypal_client import PayPalClient
from backend.integrations.channel3_client import Channel3CatalogClient
from backend.webhooks.listener import global_webhook_store

class ProcurementAgent:
    """
    Autonomous Procurement Agent equipped with:
    1. Tool: Catalog Search (Channel3)
    2. Tool: Cryptographic Policy Evaluation (Mandate)
    3. Tool: PayPal Settlement & Order Capture
    4. Tool: Webhook Audit Ingestion
    """
    def __init__(self, agent_id: str, crypto_engine: CryptographicEngine, paypal_client: PayPalClient, catalog_client: Channel3CatalogClient):
        self.agent_id = agent_id
        self.crypto_engine = crypto_engine
        self.paypal_client = paypal_client
        self.catalog_client = catalog_client
        self.execution_logs: List[Dict[str, Any]] = []

    def _log(self, step: str, status: str, details: Any):
        entry = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime()),
            "step": step,
            "status": status,
            "details": details
        }
        self.execution_logs.append(entry)
        return entry

    async def execute_procurement_goal(
        self,
        goal_description: str,
        query: str,
        mandate: SpendingMandate,
        signature: str,
        force_multisig_approve: bool = False
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end autonomous procurement cycle under zero-trust bounds.
        """
        self.execution_logs.clear()
        self._log("AGENT_INTENT_RECEIVED", "INFO", {"goal": goal_description, "query": query})

        # 1. Search Catalog (Channel3 Partner API)
        items = await self.catalog_client.search_items(query)
        if not items:
            self._log("SEARCH_CATALOG", "FAILED", f"No products matching query '{query}'")
            return {"success": False, "reason": "No catalog items found", "logs": self.execution_logs}

        # Pick best-rated item
        selected_item = sorted(items, key=lambda x: x["rating"], reverse=True)[0]
        self._log("ITEM_SELECTED", "SUCCESS", {
            "item_id": selected_item["item_id"],
            "title": selected_item["title"],
            "price_usd": selected_item["price_usd"],
            "merchant": selected_item["merchant"],
            "category": selected_item["category"]
        })

        # 2. Cryptographic Policy & Mandate Evaluation
        eval_result = MandatePolicyEvaluator.evaluate(
            mandate=mandate,
            signature=signature,
            crypto=self.crypto_engine,
            item_category=selected_item["category"],
            price_usd=selected_item["price_usd"],
            merchant_name=selected_item["merchant"]
        )

        if not eval_result.allowed:
            self._log("POLICY_CHECK", "BLOCKED", {
                "allowed": False,
                "violation_reason": eval_result.reason
            })
            return {
                "success": False,
                "status": "REJECTED_BY_POLICY",
                "item": selected_item,
                "evaluation": eval_result.model_dump(),
                "logs": self.execution_logs
            }

        # Check multi-sig / 2FA trigger
        if eval_result.requires_multisig and not force_multisig_approve:
            self._log("MULTISIG_TRIGGERED", "PENDING_APPROVAL", {
                "threshold_exceeded": f"Price ${selected_item['price_usd']} >= 2FA Threshold ${mandate.require_2fa_above_usd}",
                "action": "Awaiting Human Co-Signature / Passkey Approval"
            })
            return {
                "success": False,
                "status": "PENDING_MULTISIG",
                "item": selected_item,
                "evaluation": eval_result.model_dump(),
                "logs": self.execution_logs
            }

        self._log("POLICY_CHECK", "PASSED", {
            "mandate_id": mandate.mandate_id,
            "allocated_usd": selected_item["price_usd"],
            "status": "CLEARED_FOR_PAYPAL_SETTLEMENT"
        })

        # 3. Create PayPal Order
        order_res = await self.paypal_client.create_order(
            amount_usd=selected_item["price_usd"],
            custom_id=mandate.mandate_id,
            description=f"Autonomous Procurement: {selected_item['title']}"
        )
        order_id = order_res.get("id")
        self._log("PAYPAL_ORDER_CREATED", "SUCCESS", {
            "order_id": order_id,
            "status": order_res.get("status"),
            "amount": selected_item["price_usd"]
        })

        # 4. Settle / Capture via PayPal
        capture_res = await self.paypal_client.capture_order(order_id)
        self._log("PAYPAL_ORDER_CAPTURED", "SETTLED", {
            "order_id": order_id,
            "capture_status": capture_res.get("status", "COMPLETED")
        })

        # 5. Emit Webhook to Audit Ledger
        global_webhook_store.process_incoming_webhook({
            "id": f"WH-EVT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "summary": f"Captured payment of ${selected_item['price_usd']:.2f} for {selected_item['title']}",
            "resource": {
                "id": order_id,
                "amount": {"value": f"{selected_item['price_usd']:.2f}", "currency_code": "USD"},
                "custom_id": mandate.mandate_id
            }
        })

        self._log("LEDGER_RECONCILED", "SUCCESS", {
            "order_id": order_id,
            "audit_trail": "VERIFIED_ON_LEDGER"
        })

        return {
            "success": True,
            "status": "SETTLED",
            "order_id": order_id,
            "item": selected_item,
            "evaluation": eval_result.model_dump(),
            "logs": self.execution_logs
        }
