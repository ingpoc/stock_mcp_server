"""
Stock Analysis MCP Server.

This server provides access to stock portfolio data from MongoDB
and integrates with Alpha Vantage API for additional market data.
It builds and maintains a knowledge graph to provide context-aware
recommendations and analysis.
"""
import asyncio
import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl, BaseModel
import mcp.server.stdio

# Import MongoDB dependencies
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import aiohttp
from bson import ObjectId

from src.config import MCP_SERVER_NAME, MCP_SERVER_VERSION
from src.handlers.resources import handle_list_resources, handle_read_resource
from src.handlers.tools import handle_list_tools, handle_call_tool
from src.handlers.prompts import handle_list_prompts, handle_get_prompt
from src.utils.database import connect_to_mongodb, close_mongodb_connection

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stock_mcp_server.main")

# Configuration
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "stock_data"
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Collection names
HOLDINGS_COLLECTION = "holdings"
DETAILED_FINANCIALS_COLLECTION = "detailed_financials"
KNOWLEDGE_GRAPH_COLLECTION = "stock_knowledge_graph"

# Server definition
server = Server(MCP_SERVER_NAME)

# Cache for database responses
cache = {
    "portfolio_holdings": None,
    "market_data": None,
    "quarters": None,
    "stock_details": {},
    "knowledge_graph": {}
}

# Database connection helper
async def connect_to_mongodb():
    """Establish a connection to MongoDB"""
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        # Ping the server to verify connection
        await client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        return client[DB_NAME]
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None

# Helper functions for Alpha Vantage API
async def fetch_alpha_vantage_data(function, symbol, **params):
    """Fetch data from Alpha Vantage API"""
    if not ALPHA_VANTAGE_API_KEY:
        logger.warning("Alpha Vantage API key not set")
        return None
        
    request_params = {
        "function": function,
        "symbol": symbol,
        "apikey": ALPHA_VANTAGE_API_KEY,
        **params
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ALPHA_VANTAGE_BASE_URL, params=request_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Alpha Vantage API error: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage data: {e}")
        return None

async def get_alpha_vantage_data(symbol):
    """Get comprehensive data for a stock from Alpha Vantage"""
    # Get overview data
    overview = await fetch_alpha_vantage_data("OVERVIEW", symbol)
    
    # Get global quote
    quote = await fetch_alpha_vantage_data("GLOBAL_QUOTE", symbol)
    
    # Combine data
    if overview or quote:
        return {
            "overview": overview,
            "quote": quote
        }
    
    return None

async def get_alpha_vantage_trending_stocks(exclude_symbols):
    """Get trending stocks from Alpha Vantage based on relative strength index"""
    trending_stocks = []
    
    # Example: Get top US stocks
    top_gainers = await fetch_alpha_vantage_data("TOP_GAINERS_LOSERS", "")
    
    if top_gainers and "top_gainers" in top_gainers:
        for stock in top_gainers["top_gainers"][:5]:
            if stock.get("ticker") not in exclude_symbols:
                # Get more details
                overview = await fetch_alpha_vantage_data("OVERVIEW", stock.get("ticker"))
                
                trending_stocks.append({
                    "symbol": stock.get("ticker"),
                    "company_name": overview.get("Name") if overview else stock.get("ticker"),
                    "price": stock.get("price"),
                    "change_percentage": stock.get("change_percentage"),
                    "metrics": {
                        "pe_ratio": overview.get("PERatio") if overview else "N/A",
                        "peg_ratio": overview.get("PEGRatio") if overview else "N/A",
                        "eps": overview.get("EPS") if overview else "N/A",
                    },
                    "source": "Alpha Vantage API",
                    "technical_trend": "BULLISH"  # Since it's from top gainers
                })
    
    return trending_stocks

# Helper function to convert ObjectId to string
def handle_mongo_object(obj):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Register handlers with the correct decorator syntax
@server.list_resources()
async def list_resources_handler():
    logger.debug("Processing list_resources request")
    resources = await handle_list_resources()
    logger.debug(f"Returning resources: {resources}")
    return resources

@server.read_resource()
async def read_resource_handler(uri: AnyUrl):
    logger.debug(f"Processing read_resource request for URI: {uri}")
    return await handle_read_resource(uri)

@server.list_tools()
async def list_tools_handler():
    logger.debug("Processing list_tools request")
    tools = await handle_list_tools()
    logger.debug(f"Returning tools count: {len(tools)}")
    return tools

@server.call_tool()
async def call_tool_handler(name: str, arguments: Dict[str, Any]):
    logger.debug(f"Processing call_tool request for tool: {name} with arguments: {arguments}")
    return await handle_call_tool(name, arguments)

@server.list_prompts()
async def list_prompts_handler():
    logger.debug("Processing list_prompts request")
    prompts = await handle_list_prompts()
    logger.debug(f"Returning prompts: {prompts}")
    return prompts

@server.get_prompt()
async def get_prompt_handler(name: str, arguments: Dict[str, Any]):
    logger.debug(f"Processing get_prompt request for name: {name} with arguments: {arguments}")
    return await handle_get_prompt(name, arguments)

async def main():
    """Run the MCP server."""
    logger.info("Starting Stock Analysis MCP server...")
    logger.info(f"Server name: {MCP_SERVER_NAME}, version: {MCP_SERVER_VERSION}")
    
    # Establish database connection
    db = await connect_to_mongodb()
    if db is None:
        logger.error("Failed to connect to MongoDB. Server will start but may not function correctly.")
    
    # Check if we're running in Claude Desktop (has a proper stdin/stdout stream setup)
    is_claude_desktop = "MCP_SERVER_NAME" in os.environ
    
    if is_claude_desktop:
        # Run the server using stdin/stdout streams normally
        logger.info("Running in Claude Desktop mode with stdin/stdout...")
        try:
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                logger.info("STDIO server initialized, preparing to run...")
                try:
                    logger.info("Starting MCP server run loop...")
                    # Log capabilities for debugging
                    capabilities = server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    )
                    logger.debug(f"Server capabilities: {capabilities}")
                    
                    await server.run(
                        read_stream,
                        write_stream,
                        InitializationOptions(
                            server_name=MCP_SERVER_NAME,
                            server_version=MCP_SERVER_VERSION,
                            capabilities=capabilities,
                        ),
                    )
                    logger.info("MCP server run loop completed normally")
                except Exception as e:
                    logger.error(f"Error in server run loop: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    # Close database connection when done
                    await close_mongodb_connection()
                    logger.info("Server shutdown complete")
        except Exception as e:
            logger.error(f"Error setting up STDIO server: {e}")
            import traceback
            logger.error(traceback.format_exc())
    else:
        # Running in test mode - use a different approach that won't exit immediately
        logger.info("Running in test mode - will keep server alive...")
        try:
            # Just keep the server alive
            logger.info("Server is ready for Claude Desktop to connect")
            while True:
                await asyncio.sleep(10)
                logger.info("Server is still running...")
        except asyncio.CancelledError:
            logger.info("Server was cancelled")
        except KeyboardInterrupt:
            logger.info("Server was interrupted by keyboard")
        finally:
            # Close database connection when done
            await close_mongodb_connection()
            logger.info("Server shutdown complete")

if __name__ == "__main__":
    asyncio.run(main()) 