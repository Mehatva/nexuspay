import json
import time
from typing import Dict, Any, List

class WebhookStore:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.processed_order_ids: set = set()

    def process_incoming_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        event_id = event_data.get("id", f"WH-{int(time.time()*1000)}")
        event_type = event_data.get("event_type", "UNKNOWN")
        resource = event_data.get("resource", {})
        order_id = resource.get("id") or resource.get("order_id") or "UNKNOWN"

        record = {
            "event_id": event_id,
            "event_type": event_type,
            "order_id": order_id,
            "received_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "status": "PROCESSED",
            "summary": event_data.get("summary", f"PayPal event: {event_type}")
        }
        
        self.events.insert(0, record)
        if order_id != "UNKNOWN":
            self.processed_order_ids.add(order_id)

        return record

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.events[:limit]

global_webhook_store = WebhookStore()
