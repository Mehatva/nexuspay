import hmac
import hashlib
import json
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SpendingMandate(BaseModel):
    mandate_id: str
    principal_id: str
    agent_id: str
    max_budget_usd: float
    allowed_categories: List[str]
    allowed_merchants: Optional[List[str]] = None
    require_2fa_above_usd: float = 250.0
    expires_at_timestamp: int
    created_at_timestamp: int = Field(default_factory=lambda: int(time.time()))

class PolicyEvaluationResult(BaseModel):
    allowed: bool
    requires_multisig: bool
    reason: str
    mandate_id: str
    allocated_amount: float

class CryptographicEngine:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode("utf-8")

    def compute_payload_hash(self, mandate: SpendingMandate) -> str:
        """Computes deterministic SHA256 hash of mandate attributes."""
        payload = json.dumps(mandate.model_dump(), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _compute_payload_hash(self, mandate: SpendingMandate) -> str:
        return self.compute_payload_hash(mandate)

    def sign_mandate(self, mandate: SpendingMandate) -> str:
        """Generates HMAC-SHA256 signature for tamper-proof delegation."""
        payload = json.dumps(mandate.model_dump(), sort_keys=True).encode("utf-8")
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()

    def verify_mandate_signature(self, mandate: SpendingMandate, signature: str) -> bool:
        expected = self.sign_mandate(mandate)
        return hmac.compare_digest(expected, signature)

class MandatePolicyEvaluator:
    @staticmethod
    def evaluate(
        mandate: SpendingMandate,
        signature: str,
        crypto: CryptographicEngine,
        item_category: str,
        price_usd: float,
        merchant_name: str
    ) -> PolicyEvaluationResult:
        # 1. Cryptographic integrity check
        if not crypto.verify_mandate_signature(mandate, signature):
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason="CRYPTOGRAPHIC_SIGNATURE_INVALID: Mandate signature does not match principal keys.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd
            )

        # 2. Expiration check
        current_ts = int(time.time())
        if current_ts > mandate.expires_at_timestamp:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"MANDATE_EXPIRED: Policy expired at {mandate.expires_at_timestamp}.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd
            )

        # 3. Category validation
        if item_category.lower() not in [c.lower() for c in mandate.allowed_categories]:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"CATEGORY_VIOLATION: '{item_category}' not in allowed list {mandate.allowed_categories}.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd
            )

        # 4. Merchant check
        if mandate.allowed_merchants:
            if merchant_name.lower() not in [m.lower() for m in mandate.allowed_merchants]:
                return PolicyEvaluationResult(
                    allowed=False,
                    requires_multisig=False,
                    reason=f"MERCHANT_VIOLATION: '{merchant_name}' is not in authorized vendor whitelist.",
                    mandate_id=mandate.mandate_id,
                    allocated_amount=price_usd
                )

        # 5. Budget ceiling
        if price_usd > mandate.max_budget_usd:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"BUDGET_EXCEEDED: Requested ${price_usd:.2f} exceeds cap of ${mandate.max_budget_usd:.2f}.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd
            )

        # 6. Multi-sig / 2FA trigger check
        requires_2fa = price_usd >= mandate.require_2fa_above_usd
        return PolicyEvaluationResult(
            allowed=True,
            requires_multisig=requires_2fa,
            reason="AUTHORIZED_FOR_PAYPAL_SETTLEMENT" if not requires_2fa else "REQUIRES_HUMAN_2FA_APPROVAL",
            mandate_id=mandate.mandate_id,
            allocated_amount=price_usd
        )
