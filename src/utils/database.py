"""
Database utility functions for interacting with MongoDB.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
import os

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
            # Test if the connection is still alive
            try:
                await _client.admin.command('ping')
                logger.debug("Reusing existing MongoDB connection")
                if _db is not None:  # Check if db is not None
                    return _db
                else:
                    logger.warning("Existing connection has no database object")
            except Exception as e:
                logger.warning(f"Existing MongoDB connection failed ping test: {e}")
                # Connection is stale, create a new one
                _client = None
                _db = None
        
        # Create a new connection
        logger.info(f"Connecting to MongoDB at {MONGODB_URI}, database: {MONGODB_DB_NAME}")
        _client = AsyncIOMotorClient(
            MONGODB_URI, 
            serverSelectionTimeoutMS=10000,     # 10 seconds timeout for server selection (was 5000)
            connectTimeoutMS=10000,             # 10 seconds connect timeout
            socketTimeoutMS=60000,              # 60 seconds socket timeout (was 45000)
            maxIdleTimeMS=30000,                # 30 seconds max idle time
            waitQueueTimeoutMS=10000,           # 10 seconds wait queue timeout
            retryWrites=True                    # Enable retry for write operations
        )
        
        # Test connection
        await _client.admin.command('ping')
        
        # Save references
        _db = _client[MONGODB_DB_NAME]
        
        logger.info("Successfully connected to MongoDB")
        return _db
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        _client = None
        _db = None
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        _client = None
        _db = None
        return None

async def close_mongodb_connection() -> None:
    """Close the MongoDB connection."""
    global _client, _db
    
    if _client is not None:
        _client.close()
        _client = None
        _db = None
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

async def get_portfolio_holdings(limit: int = 10, summary: bool = False) -> List[Dict[str, Any]]:
    """
    Get portfolio holdings from the database.
    
    Args:
        limit: Maximum number of holdings to return (default: 10)
        summary: If True, returns a simplified view with fewer fields
        
    Returns:
        List of portfolio holdings
    """
    db = await connect_to_mongodb()
    if db is None:
        # Return empty result if database is not available
        logger.error("Database not available - cannot get portfolio holdings")
        return []
    
    try:
        # Get holdings from database
        collection = db[HOLDINGS_COLLECTION]
        
        # Create index on symbol if it doesn't exist
        await collection.create_index("symbol")
        
        cursor = collection.find({}).limit(limit)
        holdings = await cursor.to_list(length=limit)
        
        if not holdings:
            logger.warning("No portfolio holdings found in database")
            return []
        
        # Simplify the response if summary mode is requested
        if summary:
            simplified_holdings = []
            for holding in holdings:
                simplified_holdings.append({
                    "symbol": holding["symbol"],
                    "quantity": holding["quantity"],
                    "average_price": holding["average_price"]
                })
            logger.info(f"Returning {len(simplified_holdings)} simplified portfolio holdings")
            return simplified_holdings
        
        # Return the full holdings data (limited to requested count)
        logger.info(f"Returning {len(holdings)} portfolio holdings")
        return holdings
        
    except Exception as e:
        logger.error(f"Error fetching portfolio holdings: {e}")
        return []

def compress_financial_data(data: Dict[str, Any], max_text_length: int = 50) -> Dict[str, Any]:
    """
    Compress financial data by truncating text fields and removing unnecessary information.
    This helps ensure Claude can process large financial data responses.
    
    Args:
        data: Financial data dictionary to compress
        max_text_length: Maximum length for text fields
        
    Returns:
        Compressed financial data dictionary
    """
    if not data or not isinstance(data, dict):
        return data
    
    result = {}
    
    # Process top-level keys
    for key, value in data.items():
        # Skip internal fields and large metadata
        if key.startswith('_') or key == 'metadata' or key == 'raw_data':
            continue
            
        # Handle nested dictionaries
        if isinstance(value, dict):
            result[key] = compress_financial_data(value, max_text_length)
        
        # Handle lists (like financial_metrics)
        elif isinstance(value, list):
            # For lists of dictionaries (common in financial data)
            if all(isinstance(item, dict) for item in value):
                # If it's metrics or a list of financial periods, limit to most recent 2
                if key in ['financial_metrics', 'quarters', 'periods', 'historical_data']:
                    # Take only most recent 2 items to reduce size
                    compressed_list = []
                    for item in value[:2]:  # Only take first 2 items
                        compressed_list.append(compress_financial_data(item, max_text_length))
                    result[key] = compressed_list
                else:
                    # For other lists, process all items but compress each
                    result[key] = [compress_financial_data(item, max_text_length) for item in value]
            else:
                # For simple lists, truncate if too long
                if len(value) > 10:
                    result[key] = value[:10]  # Take only first 10 items
                else:
                    result[key] = value
        
        # Handle strings - truncate long text
        elif isinstance(value, str) and len(value) > max_text_length:
            result[key] = value[:max_text_length] + "..."
        
        # Pass through other value types unchanged
        else:
            result[key] = value
    
    return result

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
        logger.error(f"Cannot get detailed financials for {symbol}: database connection failed")
        return None
    
    try:    
        financials = await db[DETAILED_FINANCIALS_COLLECTION].find_one({"symbol": symbol})
        
        # If no financials are found, return sample data for testing
        if not financials:
            logger.warning(f"No financials found for {symbol}. Using sample data.")
            return {
                "symbol": symbol,
                "company_name": symbol.split(":")[-1],
                "financial_metrics": [
                    {
                        "quarter": "Q4 FY23-24",
                        "revenue_growth": "12.5%",
                        "net_profit_growth": "8.3%",
                        "ttm_pe": "22.4",
                        "piotroski_score": "7",
                        "market_cap": "1.2T",
                        "book_value": "850",
                        "strengths": "Strong revenue growth, consistent profitability",
                        "weaknesses": "High competition in sector",
                        "technicals_trend": "NEUTRAL",
                        "fundamental_insights": "Solid fundamentals with potential for growth"
                    }
                ]
            }
        
        # Optimize the financials response
        if financials and "financial_metrics" in financials and financials["financial_metrics"]:
            # Sort metrics by quarter to get the latest
            metrics = sorted(financials["financial_metrics"], 
                            key=lambda x: x.get("quarter", ""), 
                            reverse=True)
            
            # Keep only the latest 2 quarters to reduce response size
            financials["financial_metrics"] = metrics[:2]
            
            # For each metric, trim excessive text fields
            for metric in financials["financial_metrics"]:
                # Limit the length of textual fields
                for field in ["strengths", "weaknesses", "fundamental_insights"]:
                    if field in metric and isinstance(metric[field], str) and len(metric[field]) > 100:
                        metric[field] = metric[field][:100] + "..."
            
            logger.debug(f"Optimized financials for {symbol}: kept latest {len(financials['financial_metrics'])} quarters")
        
        # Apply compression to reduce size further for large financial data
        compressed_financials = compress_financial_data(financials)
        logger.debug(f"Compressed financials for {symbol}")
        
        return compressed_financials
    except Exception as e:
        logger.error(f"Error retrieving detailed financials for {symbol}: {e}")
        return None

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
    if "financial_metrics" not in financials or not financials["financial_metrics"]:
        logger.warning(f"No financial metrics found for {symbol}")
        return None
        
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
        logger.error(f"Cannot update knowledge graph for {symbol}: database connection failed")
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
        logger.error(f"Error updating knowledge graph for {symbol}: {e}")
        return False

async def query_knowledge_graph(
    symbol: Optional[str] = None,
    criteria: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Query the knowledge graph for stock data.
    
    Args:
        symbol: Stock symbol (optional)
        criteria: Search criteria (optional)
        limit: Maximum number of results to return
        
    Returns:
        List of matching knowledge graph entries
    """
    db = await connect_to_mongodb()
    if db is None:
        # Return empty list if database is not available
        logger.error("Database not available - cannot query knowledge graph")
        return []
    
    try:
        collection = db[KNOWLEDGE_GRAPH_COLLECTION]
        
        # Create a filter based on parameters
        filter_query = {}
        
        if symbol:
            filter_query["symbol"] = symbol
            
        if criteria:
            # Create a text search for criteria
            text_query = {"$text": {"$search": criteria}}
            # If we already have a symbol filter, combine them
            if filter_query:
                filter_query = {"$and": [filter_query, text_query]}
            else:
                filter_query = text_query
        
        # If no filters are provided, return most recent entries
        if not filter_query:
            cursor = collection.find({}).sort("analysis_date", -1).limit(limit)
        else:
            cursor = collection.find(filter_query).limit(limit)
            
        entries = await cursor.to_list(length=limit)
        
        if not entries:
            logger.warning(f"No knowledge graph entries found for query: symbol={symbol}, criteria={criteria}")
            return []
        
        # Optimize results for Claude processing
        optimized_entries = []
        for entry in entries:
            # Create a concise version of each entry
            optimized_entry = {
                "symbol": entry.get("symbol", ""),
                "company_name": entry.get("company_name", ""),
                "analysis_date": entry.get("analysis_date", ""),
                "latest_quarter": entry.get("latest_quarter", "")
            }
            
            # Add a subset of the analysis data if available
            if "analysis" in entry and entry["analysis"]:
                analysis = entry["analysis"]
                # Include only essential analysis fields
                optimized_entry["analysis"] = {
                    "key_metrics": {
                        "pe_ratio": analysis.get("metrics", {}).get("pe_ratio", "N/A") if "metrics" in analysis else "N/A",
                        "profit_growth": analysis.get("metrics", {}).get("profit_growth", "N/A") if "metrics" in analysis else "N/A",
                    },
                    "summary": analysis.get("fundamental_insights", "")[:150] if "fundamental_insights" in analysis else ""
                }
            
            optimized_entries.append(optimized_entry)
        
        logger.debug(f"Optimized {len(entries)} knowledge graph entries for Claude")
        return optimized_entries
            
    except Exception as e:
        logger.error(f"Error querying knowledge graph: {e}")
        return []

async def get_stock_recommendations(criteria: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get stock recommendations based on criteria.
    
    Args:
        criteria: Criteria for recommendations (e.g., growth, value, dividend)
        limit: Maximum number of recommendations to return
        
    Returns:
        List of stock recommendations
    """
    db = await connect_to_mongodb()
    if db is None:
        # Return empty list if database is not available
        logger.error("Database not available - cannot get stock recommendations")
        return []
    
    try:
        # First check if we have actual recommendations in the database
        has_recommendations = await db.list_collection_names()
        if "stock_recommendations" not in has_recommendations:
            logger.warning("No stock_recommendations collection found. Using sample data.")
            # Return sample recommendations data
            return [
                {
                    "symbol": "NSE:INFY",
                    "company_name": "Infosys Ltd.",
                    "recommendation_type": "growth",
                    "reason": "Strong IT sector growth potential",
                    "metrics": {"pe_ratio": "21.5", "growth_rate": "15%"}
                },
                {
                    "symbol": "NSE:RELIANCE",
                    "company_name": "Reliance Industries",
                    "recommendation_type": "value",
                    "reason": "Diversified business with strong fundamentals",
                    "metrics": {"pe_ratio": "25.3", "growth_rate": "12%"}
                },
                {
                    "symbol": "NSE:HDFCBANK",
                    "company_name": "HDFC Bank",
                    "recommendation_type": "dividend",
                    "reason": "Consistent dividend payer with growth",
                    "metrics": {"pe_ratio": "18.6", "dividend_yield": "1.2%"}
                }
            ][:limit]
        
        collection = db["stock_recommendations"]
        
        # Create a filter based on criteria
        filter_query = {}
        
        if criteria:
            criteria_lower = criteria.lower()
            
            if "growth" in criteria_lower:
                filter_query["recommendation_type"] = "growth"
            elif "value" in criteria_lower:
                filter_query["recommendation_type"] = "value"
            elif "dividend" in criteria_lower:
                filter_query["recommendation_type"] = "dividend"
            else:
                # Try text search for the criteria
                filter_query = {"$text": {"$search": criteria}}
        
        # Get recommendations from database
        cursor = collection.find(filter_query).limit(limit)
        recommendations = await cursor.to_list(length=limit)
        
        if not recommendations:
            logger.warning(f"No stock recommendations found for criteria: {criteria}")
            return []
        
        # Optimize the recommendations for Claude
        optimized_recommendations = []
        for rec in recommendations:
            # Create a concise recommendation object
            optimized_rec = {
                "symbol": rec.get("symbol", ""),
                "company_name": rec.get("company_name", ""),
                "type": rec.get("recommendation_type", "growth"),
                "key_metrics": {}
            }
            
            # Add a brief reason if available (limit length)
            if "reason" in rec:
                optimized_rec["reason"] = rec["reason"][:150] if len(rec["reason"]) > 150 else rec["reason"]
            
            # Add core metrics if available
            if "metrics" in rec and rec["metrics"]:
                metrics = rec["metrics"]
                optimized_rec["key_metrics"] = {
                    "pe_ratio": metrics.get("pe_ratio", "N/A"),
                    "growth_rate": metrics.get("growth_rate", "N/A"),
                    "dividend_yield": metrics.get("dividend_yield", "N/A")
                }
            
            optimized_recommendations.append(optimized_rec)
        
        logger.info(f"Returning {len(optimized_recommendations)} optimized stock recommendations for criteria: {criteria}")
        return optimized_recommendations
        
    except Exception as e:
        logger.error(f"Error getting stock recommendations: {e}")
        return [] 