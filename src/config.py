"""
Configuration settings for the Stock Analysis MCP Server.
Loads settings from environment variables and provides defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=str(env_path))

# MongoDB settings
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "stock_data")
MONGODB_HOLDINGS_COLLECTION = os.environ.get("MONGODB_HOLDINGS_COLLECTION", "holdings")
MONGODB_FINANCIALS_COLLECTION = os.environ.get("MONGODB_FINANCIALS_COLLECTION", "detailed_financials") 
MONGODB_KNOWLEDGE_GRAPH_COLLECTION = os.environ.get("MONGODB_KNOWLEDGE_GRAPH_COLLECTION", "stock_knowledge_graph")

# Alpha Vantage API settings
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = os.environ.get("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")
# Rate limiting for free tier
ALPHA_VANTAGE_RATE_LIMIT_MINUTE = int(os.environ.get("ALPHA_VANTAGE_RATE_LIMIT_MINUTE", "5"))
ALPHA_VANTAGE_RATE_LIMIT_DAY = int(os.environ.get("ALPHA_VANTAGE_RATE_LIMIT_DAY", "500"))
# Default exchange for Indian market
ALPHA_VANTAGE_DEFAULT_EXCHANGE = os.environ.get("ALPHA_VANTAGE_DEFAULT_EXCHANGE", "NSE")

# MCP Server settings
MCP_SERVER_NAME = os.environ.get("MCP_SERVER_NAME", "stock-analysis-mcp")
MCP_SERVER_VERSION = os.environ.get("MCP_SERVER_VERSION", "0.1.0")

# Logging settings
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = os.environ.get("LOG_FORMAT", '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Cache settings
CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "True").lower() == "true"
# Extract only the number part if CACHE_TTL contains comments
cache_ttl_str = os.environ.get("CACHE_TTL", "3600")
if cache_ttl_str:
    cache_ttl_str = cache_ttl_str.split('#')[0].strip()
CACHE_TTL = int(cache_ttl_str)  # Default: 1 hour

def get_version() -> str:
    """Get the server version string."""
    return MCP_SERVER_VERSION 