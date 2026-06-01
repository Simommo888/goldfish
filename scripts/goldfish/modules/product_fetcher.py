"""Product-update placeholders for AI product sources."""

from __future__ import annotations

from typing import Any, Dict, List

from .utils import make_manual_item


def fetch_products(
    sources: List[Dict[str, Any]],
    limit: int = 5,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for source in sources[:limit]:
        item = make_manual_item(
            f"{source.get('name', 'AI 产品源')}：待人工查看",
            source.get("url", ""),
            source.get("name", ""),
            "product",
            source.get("notes", "第一版不做复杂产品站爬取，待人工查看。"),
        )
        item.update({"content_type": "product", "category": "product", "score": 0})
        products.append(item)
    return products
