"""
Database utility functions for interacting with MongoDB.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId

from ..config import (
    MONGODB_URI, 
    MONGODB_DB_NAME,
    MONGODB_HOLDINGS_COLLECTION,
    MONGODB_FINANCIALS_COLLECTION,
    MONGODB_KNOWLEDGE_GRAPH_COLLECTION
)

# Setup logging
logger = logging.getLogger("stock_mcp_server.database")

# MongoDB client
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

# Collection names
HOLDINGS_COLLECTION = MONGODB_HOLDINGS_COLLECTION
DETAILED_FINANCIALS_COLLECTION = MONGODB_FINANCIALS_COLLECTION
KNOWLEDGE_GRAPH_COLLECTION = MONGODB_KNOWLEDGE_GRAPH_COLLECTION

async def connect_to_mongodb() -> Optional[AsyncIOMotorDatabase]:
    """
    Establish a connection to MongoDB.
    
    Returns:
        AsyncIOMotorDatabase: MongoDB database object or None if connection failed
    """
    global _client, _db
    
    try:
        # Reuse existing connection if available
        if _client is not None:
            return _db
        
        # Create new connection
        _client = AsyncIOMotorClient(MONGODB_URI)
        
        # Ping the server to verify connection
        await _client.admin.command('ping')
        _db = _client[MONGODB_DB_NAME]
        
        logger.info("Successfully connected to MongoDB")
        return _db
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None

async def close_mongodb_connection() -> None:
    """Close the MongoDB connection."""
    global _client
    
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")

def handle_mongo_object(obj: Any) -> Any:
    """
    Convert MongoDB ObjectId and datetime objects to string for JSON serialization.
    
    Args:
        obj: Object to convert
        
    Returns:
        Serializable version of the object
        
    Raises:
        TypeError: If object cannot be serialized
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

async def get_portfolio_holdings(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get portfolio holdings from MongoDB.
    
    Args:
        limit: Maximum number of holdings to retrieve
        
    Returns:
        List of holdings
    """
    db = await connect_to_mongodb()
    if db is None:
        return []
        
    holdings = await db[HOLDINGS_COLLECTION].find({}).to_list(length=limit)
    return holdings

async def get_detailed_financials(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed financials for a stock.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Financial data or None if not found
    """
    db = await connect_to_mongodb()
    if db is None:
        return None
        
    financials = await db[DETAILED_FINANCIALS_COLLECTION].find_one({"symbol": symbol})
    return financials

async def get_latest_financial_metrics(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest financial metrics for a stock.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Latest financial metrics or None if not found
    """
    financials = await get_detailed_financials(symbol)
    if financials is None:
        return None
        
    # Sort by quarter to get the latest metrics
    metrics_list = sorted(
        financials["financial_metrics"],
        key=lambda x: x.get("quarter", ""),
        reverse=True
    )
    
    return metrics_list[0] if metrics_list else None

async def update_knowledge_graph(
    symbol: str, 
    data: Dict[str, Any]
) -> bool:
    """
    Update the knowledge graph for a stock.
    
    Args:
        symbol: Stock symbol
        data: Data to update
        
    Returns:
        True if successful, False otherwise
    """
    db = await connect_to_mongodb()
    if db is None:
        return False
        
    try:
        # Add timestamp if not present
        if "analysis_date" not in data:
            data["analysis_date"] = datetime.now()
            
        result = await db[KNOWLEDGE_GRAPH_COLLECTION].update_one(
            {"symbol": symbol},
            {"$set": data},
            upsert=True
        )
        
        return result.acknowledged
    except Exception as e:
        logger.error(f"Error updating knowledge graph: {e}")
        return False

async def query_knowledge_graph(
    symbol: Optional[str] = None,
    criteria: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Query the knowledge graph.
    
    Args:
        symbol: Optional stock symbol to query for
        criteria: Optional criteria for filtering (buy_recommendations, sell_recommendations, portfolio)
        limit: Maximum number of results to return
        
    Returns:
        List of knowledge graph entries
    """
    db = await connect_to_mongodb()
    if db is None:
        return []
        
    # Build query
    query = {}
    
    if symbol:
        # Query by specific symbol
        query["symbol"] = symbol
    elif criteria:
        # Query by criteria
        if criteria == "buy_recommendations":
            query["portfolio.recommendation"] = "Market Trend Buy"
        elif criteria == "sell_recommendations":
            query["portfolio.recommendation"] = "Consider Removing"
        elif criteria == "portfolio":
            query["portfolio.in_portfolio"] = True
            
    entries = await db[KNOWLEDGE_GRAPH_COLLECTION].find(query).to_list(length=limit)
    return entries

async def get_stock_recommendations(
    exclude_symbols: List[str], 
    criteria: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get stock recommendations based on criteria.
    
    Args:
        exclude_symbols: Symbols to exclude from recommendations
        criteria: Optional criteria for filtering (growth, value, dividend)
        limit: Maximum number of recommendations to return
        
    Returns:
        List of stock recommendations
    """
    db = await connect_to_mongodb()
    if db is None:
        return []
        
    # Find stocks not in exclude_symbols
    stocks = await db[DETAILED_FINANCIALS_COLLECTION].find({
        "symbol": {"$nin": exclude_symbols}
    }).to_list(length=limit * 2)  # Fetch extra to allow for filtering
    
    recommendations = []
    
    for stock in stocks[:limit * 2]:
        if not stock.get("financial_metrics") or len(stock["financial_metrics"]) == 0:
            continue
            
        # Sort by quarter to get the latest metrics
        metrics_list = sorted(
            stock["financial_metrics"],
            key=lambda x: x.get("quarter", ""),
            reverse=True
        )
        latest_metrics = metrics_list[0] if metrics_list else None
        
        if not latest_metrics:
            continue
            
        # Apply criteria filtering
        if criteria:
            if criteria.lower() == "growth":
                if not (latest_metrics.get("revenue_growth") and not str(latest_metrics["revenue_growth"]).startswith("-")):
                    continue
            elif criteria.lower() == "value":
                pe_ratio = latest_metrics.get("ttm_pe", "99")
                try:
                    if float(str(pe_ratio).replace("NA", "99")) >= 20:
                        continue
                except (ValueError, TypeError):
                    continue
            elif criteria.lower() == "dividend":
                dividend_yield = latest_metrics.get("dividend_yield", "0")
                try:
                    if float(str(dividend_yield).replace("NA", "0")) <= 2:
                        continue
                except (ValueError, TypeError):
                    continue
                    
        # Create recommendation
        recommendation = {
            "symbol": stock.get("symbol", ""),
            "company_name": stock.get("company_name", ""),
            "metrics": {
                "pe_ratio": latest_metrics.get("ttm_pe", "N/A"),
                "revenue_growth": latest_metrics.get("revenue_growth", "N/A"),
                "profit_growth": latest_metrics.get("net_profit_growth", "N/A"),
                "piotroski_score": latest_metrics.get("piotroski_score", "N/A"),
                "market_cap": latest_metrics.get("market_cap", "N/A"),
            },
            "strengths": latest_metrics.get("strengths", ""),
            "weaknesses": latest_metrics.get("weaknesses", ""),
            "technicals": latest_metrics.get("technicals_trend", ""),
            "fundamental_insights": latest_metrics.get("fundamental_insights", "")
        }
        
        recommendations.append(recommendation)
        
    # Sort by piotroski score if available
    try:
        recommendations.sort(
            key=lambda x: float(str(x["metrics"]["piotroski_score"]).replace("NA", "0")) 
                if isinstance(x["metrics"]["piotroski_score"], str) else 0, 
            reverse=True
        )
    except (ValueError, TypeError):
        pass
        
    return recommendations[:limit] 