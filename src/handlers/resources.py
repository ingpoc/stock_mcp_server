"""
Resource handlers for MCP server.
"""
import json
import logging
from typing import List
from pydantic import AnyUrl
import mcp.types as types

from ..utils.database import (
    connect_to_mongodb,
    handle_mongo_object,
    HOLDINGS_COLLECTION,
    DETAILED_FINANCIALS_COLLECTION,
    KNOWLEDGE_GRAPH_COLLECTION
)

# Setup logging
logger = logging.getLogger("stock_mcp_server.handlers.resources")

async def handle_list_resources() -> List[types.Resource]:
    """
    List available resources related to stock analysis.
    
    Returns:
        List of available resources
    """
    resources = []
    
    # Add portfolio resource
    resources.append(
        types.Resource(
            uri=AnyUrl("stock-api://portfolio"),
            name="Portfolio Holdings",
            description="Your current stock portfolio holdings",
            mimeType="application/json",
        )
    )
    
    # Add market data resource
    resources.append(
        types.Resource(
            uri=AnyUrl("stock-api://market-data"),
            name="Market Data",
            description="Current market data and performance metrics",
            mimeType="application/json",
        )
    )
    
    # Add knowledge graph resource
    resources.append(
        types.Resource(
            uri=AnyUrl("stock-api://knowledge-graph"),
            name="Stock Knowledge Graph",
            description="Knowledge graph with analysis of stocks",
            mimeType="application/json",
        )
    )
    
    return resources

async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific resource by its URI.
    
    Args:
        uri: Resource URI
        
    Returns:
        Resource content as JSON string
        
    Raises:
        ValueError: If the URI scheme or resource type is not supported
    """
    if uri.scheme != "stock-api":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    resource_type = uri.host
    db = await connect_to_mongodb()
    
    if not db:
        return json.dumps({"error": "Failed to connect to database"})
    
    if resource_type == "portfolio":
        holdings = await db[HOLDINGS_COLLECTION].find({}).to_list(length=50)
        return json.dumps(holdings, default=handle_mongo_object)
        
    elif resource_type == "market-data":
        # Get all available quarters from financial data
        pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$group": {"_id": "$financial_metrics.quarter"}},
            {"$sort": {"_id": -1}},
            {"$limit": 5}
        ]
        quarters = await db[DETAILED_FINANCIALS_COLLECTION].aggregate(pipeline).to_list(length=5)
        
        # Get top performers based on profit growth
        pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$match": {"financial_metrics.net_profit_growth": {"$exists": True}}},
            {"$sort": {"financial_metrics.net_profit_growth": -1}},
            {"$limit": 10},
            {"$project": {
                "symbol": 1,
                "company_name": 1,
                "profit_growth": "$financial_metrics.net_profit_growth",
                "quarter": "$financial_metrics.quarter"
            }}
        ]
        top_performers = await db[DETAILED_FINANCIALS_COLLECTION].aggregate(pipeline).to_list(length=10)
        
        market_data = {
            "quarters": [q["_id"] for q in quarters if q["_id"]],
            "top_performers": top_performers
        }
        return json.dumps(market_data, default=handle_mongo_object)
        
    elif resource_type == "knowledge-graph":
        knowledge = await db[KNOWLEDGE_GRAPH_COLLECTION].find({}).to_list(length=20)
        return json.dumps(knowledge, default=handle_mongo_object)
        
    else:
        raise ValueError(f"Unknown resource type: {resource_type}") 