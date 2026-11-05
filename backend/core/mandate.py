import hmac
import hashlib
import json
import time
from typing import List, Optional, Dict, Any, Set
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
    current_spent_usd: float = 0.0
    used_nonces: List[str] = Field(default_factory=list)

    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.max_budget_usd - self.current_spent_usd)

class PolicyEvaluationResult(BaseModel):
    allowed: bool
    requires_multisig: bool
    reason: str
    mandate_id: str
    allocated_amount: float
    remaining_budget_usd: float = 0.0

class CryptographicEngine:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode("utf-8")

    def compute_payload_hash(self, mandate: SpendingMandate) -> str:
        """Computes deterministic SHA256 hash of immutable mandate parameters."""
        immutable_data = {
            "mandate_id": mandate.mandate_id,
            "principal_id": mandate.principal_id,
            "agent_id": mandate.agent_id,
            "max_budget_usd": mandate.max_budget_usd,
            "allowed_categories": sorted(mandate.allowed_categories),
            "allowed_merchants": sorted(mandate.allowed_merchants) if mandate.allowed_merchants else None,
            "require_2fa_above_usd": mandate.require_2fa_above_usd,
            "expires_at_timestamp": mandate.expires_at_timestamp,
            "created_at_timestamp": mandate.created_at_timestamp
        }
        payload = json.dumps(immutable_data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _compute_payload_hash(self, mandate: SpendingMandate) -> str:
        return self.compute_payload_hash(mandate)

    def sign_mandate(self, mandate: SpendingMandate) -> str:
        """Generates HMAC-SHA256 signature for tamper-proof delegation."""
        immutable_data = {
            "mandate_id": mandate.mandate_id,
            "principal_id": mandate.principal_id,
            "agent_id": mandate.agent_id,
            "max_budget_usd": mandate.max_budget_usd,
            "allowed_categories": sorted(mandate.allowed_categories),
            "allowed_merchants": sorted(mandate.allowed_merchants) if mandate.allowed_merchants else None,
            "require_2fa_above_usd": mandate.require_2fa_above_usd,
            "expires_at_timestamp": mandate.expires_at_timestamp,
            "created_at_timestamp": mandate.created_at_timestamp
        }
        payload = json.dumps(immutable_data, sort_keys=True).encode("utf-8")
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
        merchant_name: str,
        nonce: Optional[str] = None
    ) -> PolicyEvaluationResult:
        # 1. Cryptographic integrity check
        if not crypto.verify_mandate_signature(mandate, signature):
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason="CRYPTOGRAPHIC_SIGNATURE_INVALID: Mandate signature does not match principal keys.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd,
                remaining_budget_usd=mandate.remaining_budget_usd
            )

        # 2. Replay attack verification
        if nonce and nonce in mandate.used_nonces:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"REPLAY_ATTACK_DETECTED: Nonce '{nonce}' has already been consumed.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd,
                remaining_budget_usd=mandate.remaining_budget_usd
            )

        # 3. Expiration check
        current_ts = int(time.time())
        if current_ts > mandate.expires_at_timestamp:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"MANDATE_EXPIRED: Policy expired at {mandate.expires_at_timestamp}.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd,
                remaining_budget_usd=mandate.remaining_budget_usd
            )

        # 4. Category validation
        if item_category.lower() not in [c.lower() for c in mandate.allowed_categories]:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"CATEGORY_VIOLATION: '{item_category}' not in allowed list {mandate.allowed_categories}.",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd,
                remaining_budget_usd=mandate.remaining_budget_usd
            )

        # 5. Merchant check
        if mandate.allowed_merchants:
            if merchant_name.lower() not in [m.lower() for m in mandate.allowed_merchants]:
                return PolicyEvaluationResult(
                    allowed=False,
                    requires_multisig=False,
                    reason=f"MERCHANT_VIOLATION: '{merchant_name}' is not in authorized vendor whitelist.",
                    mandate_id=mandate.mandate_id,
                    allocated_amount=price_usd,
                    remaining_budget_usd=mandate.remaining_budget_usd
                )

        # 6. Cumulative budget ceiling check
        if (mandate.current_spent_usd + price_usd) > mandate.max_budget_usd:
            return PolicyEvaluationResult(
                allowed=False,
                requires_multisig=False,
                reason=f"CUMULATIVE_BUDGET_EXCEEDED: Requested ${price_usd:.2f} exceeds remaining allowance of ${mandate.remaining_budget_usd:.2f} (Total Cap: ${mandate.max_budget_usd:.2f}, Spent: ${mandate.current_spent_usd:.2f}).",
                mandate_id=mandate.mandate_id,
                allocated_amount=price_usd,
                remaining_budget_usd=mandate.remaining_budget_usd
            )

        # 7. Multi-sig / 2FA trigger check
        requires_2fa = price_usd >= mandate.require_2fa_above_usd
        return PolicyEvaluationResult(
            allowed=True,
            requires_multisig=requires_2fa,
            reason="AUTHORIZED_FOR_PAYPAL_SETTLEMENT" if not requires_2fa else "REQUIRES_HUMAN_2FA_APPROVAL",
            mandate_id=mandate.mandate_id,
            allocated_amount=price_usd,
            remaining_budget_usd=mandate.remaining_budget_usd
        )

