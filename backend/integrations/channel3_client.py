from typing import List, Dict, Any, Optional

class Channel3CatalogClient:
    """
    Channel3 Partner Integration Client for Agentic Commerce.
    Provides structured e-commerce product catalogs (hardware, developer tools, servers)
    with multi-vendor pricing, ratings, and merchant reputation scores.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "demo_channel3_key"
        
        # High-fidelity realistic e-commerce product catalog
        self._catalog: List[Dict[str, Any]] = [
            {
                "item_id": "HW-GPU-H100-80G",
                "title": "NVIDIA H100 PCIe 80GB GPU Node",
                "category": "infrastructure",
                "merchant": "CoreWeave Enterprise",
                "price_usd": 2850.00,
                "in_stock": True,
                "rating": 4.95,
                "delivery_days": 2
            },
            {
                "item_id": "HW-SVR-DELL-R760",
                "title": "Dell PowerEdge R760 Rack Server 2U",
                "category": "infrastructure",
                "merchant": "Dell Technologies",
                "price_usd": 3890.00,
                "in_stock": True,
                "rating": 4.90,
                "delivery_days": 5
            },
            {
                "item_id": "NET-CISCO-8000",
                "title": "Cisco 8201 Router 36-Port 100GbE",
                "category": "networking",
                "merchant": "Cisco Direct",
                "price_usd": 1450.00,
                "in_stock": True,
                "rating": 4.88,
                "delivery_days": 3
            },
            {
                "item_id": "DEV-JETBRAINS-ALL",
                "title": "JetBrains All Products Pack Enterprise (1 Year)",
                "category": "software_licenses",
                "merchant": "JetBrains Official",
                "price_usd": 779.00,
                "in_stock": True,
                "rating": 4.98,
                "delivery_days": 0
            },
            {
                "item_id": "DEV-DOCKER-ENT",
                "title": "Docker Business Subscription (Annual / 10 seats)",
                "category": "software_licenses",
                "merchant": "Docker Inc",
                "price_usd": 288.00,
                "in_stock": True,
                "rating": 4.82,
                "delivery_days": 0
            },
            {
                "item_id": "CLOUD-AWS-RESERVED",
                "title": "AWS EC2 m6i.4xlarge 1-Yr Standard RI",
                "category": "cloud_compute",
                "merchant": "Amazon Web Services",
                "price_usd": 349.00,
                "in_stock": True,
                "rating": 4.92,
                "delivery_days": 0
            },
            {
                "item_id": "ROGUE-OVERPRICED-CABLE",
                "title": "Titanium Plated Quantum High-Speed Ethernet Cable",
                "category": "unverified_goods",
                "merchant": "ScammyVendor LLC",
                "price_usd": 1299.00,
                "in_stock": True,
                "rating": 1.2,
                "delivery_days": 20
            }
        ]

    async def search_items(self, query: str, category: Optional[str] = None, max_price: Optional[float] = None) -> List[Dict[str, Any]]:
        results = []
        q = query.lower()
        for item in self._catalog:
            if category and item["category"].lower() != category.lower():
                continue
            if max_price and item["price_usd"] > max_price:
                continue
            if q in item["title"].lower() or q in item["category"].lower() or q in item["merchant"].lower():
                results.append(item)
        return results

    async def get_item_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        for item in self._catalog:
            if item["item_id"] == item_id:
                return item
        return None
