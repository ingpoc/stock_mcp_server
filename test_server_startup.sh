#!/bin/bash
# Test script to verify MCP server startup

echo "Testing Stock MCP Server startup..."

# Kill any existing Python processes for this server
pkill -f "python.*server.py"

# Set required environment variables
export ALPHA_VANTAGE_API_KEY="KQKZ71U36DG3Y2P3"
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB_NAME="stock_data"
export MONGODB_HOLDINGS_COLLECTION="holdings"
export MONGODB_FINANCIALS_COLLECTION="detailed_financials"
export MONGODB_KNOWLEDGE_GRAPH_COLLECTION="stock_knowledge_graph"
export ALPHA_VANTAGE_BASE_URL="https://www.alphavantage.co/query"
export ALPHA_VANTAGE_RATE_LIMIT_MINUTE="5"
export ALPHA_VANTAGE_RATE_LIMIT_DAY="500"
export ALPHA_VANTAGE_DEFAULT_EXCHANGE="NSE"
# We intentionally unset MCP_SERVER_NAME to trigger test mode
unset MCP_SERVER_NAME
export MCP_SERVER_VERSION="0.1.0"
export LOG_LEVEL="INFO"
export CACHE_ENABLED="True"
export CACHE_TTL="3600"

echo "Starting server in test mode..."

# Start the server directly in the current terminal
cd /Users/gurusharan/Documents/Cline/MCP/stock_mcp_server && \
python server.py

# The script will end when the server is stopped with Ctrl+C 