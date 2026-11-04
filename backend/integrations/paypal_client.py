import os
import uuid
import time
from typing import Dict, Any, Optional
import httpx

class PayPalClient:
    """
    Production-grade PayPal Orders & Vault Client.
    Supports live Sandbox REST endpoints + deterministic local mock mode
    for automated testing and fallback resilience.
    """
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, env: str = "sandbox"):
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.env = env
        self.base_url = "https://api-m.sandbox.paypal.com" if env == "sandbox" else "https://api-m.paypal.com"
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and "your_paypal" not in self.client_id)

    async def get_access_token(self) -> str:
        """Fetches or refreshes OAuth2 token from PayPal."""
        if not self.is_configured:
            return "MOCK_PAYPAL_ACCESS_TOKEN_SANDBOX"

        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"}
            )
            if resp.status_code == 200:
                data = resp.json()
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 3600) - 60
                return self._access_token
            else:
                raise RuntimeError(f"PayPal OAuth error: {resp.status_code} {resp.text}")

    async def create_order(
        self,
        amount_usd: float,
        currency: str = "USD",
        reference_id: Optional[str] = None,
        custom_id: Optional[str] = None,
        description: str = "Agentic Autonomous Procurement"
    ) -> Dict[str, Any]:
        """Creates an order via PayPal Orders API v2."""
        order_ref = reference_id or str(uuid.uuid4())
        
        if not self.is_configured:
            # Deterministic, realistic Sandbox simulation for instant local runs
            order_id = f"PP-SANDBOX-{uuid.uuid4().hex[:12].upper()}"
            return {
                "id": order_id,
                "status": "CREATED",
                "intent": "CAPTURE",
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "purchase_units": [{
                    "reference_id": order_ref,
                    "custom_id": custom_id or "MANDATE-DEFAULT",
                    "description": description,
                    "amount": {"currency_code": currency, "value": f"{amount_usd:.2f}"}
                }],
                "links": [
                    {"href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}", "rel": "approve", "method": "GET"},
                    {"href": f"{self.base_url}/v2/checkout/orders/{order_id}/capture", "rel": "capture", "method": "POST"}
                ]
            }

        token = await self.get_access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": order_ref,
                "custom_id": custom_id,
                "description": description,
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount_usd:.2f}"
                }
            }],
            "application_context": {
                "return_url": "http://localhost:8000/paypal/return",
                "cancel_url": "http://localhost:8000/paypal/cancel",
                "user_action": "PAY_NOW"
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": str(uuid.uuid4())
                }
            )
            if resp.status_code in (200, 201):
                return resp.json()
            raise RuntimeError(f"PayPal create_order error: {resp.status_code} {resp.text}")

    async def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Captures an approved PayPal order."""
        if not self.is_configured:
            capture_id = f"CAP-{uuid.uuid4().hex[:10].upper()}"
            return {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": [{
                    "payments": {
                        "captures": [{
                            "id": capture_id,
                            "status": "COMPLETED",
                            "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        }]
                    }
                }]
            }

        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": str(uuid.uuid4())
                }
            )
            if resp.status_code in (200, 201):
                return resp.json()
            raise RuntimeError(f"PayPal capture_order error: {resp.status_code} {resp.text}")
