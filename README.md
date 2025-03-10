# Indian Stock Analysis MCP Server

A Model Context Protocol (MCP) server for interacting with MongoDB stock data to provide portfolio recommendations and market insights, exclusively for the Indian stock market (NSE/BSE).

## Overview

This MCP server integrates with:
1. MongoDB database (`stock_data`) for direct stock data access
2. Alpha Vantage API for Indian market data (NSE/BSE only) with free tier limitations
3. Knowledge Graph for persistent Indian stock analysis

It enables Claude to access your Indian stock portfolio holdings, analyze stock performance, and provide personalized recommendations directly through the Claude desktop app, while building a persistent knowledge graph for improved context awareness.

## Features

- **Exclusive Indian Market Focus**: Designed specifically for NSE and BSE listed stocks
- **Direct MongoDB Access**: Queries MongoDB directly without going through an API layer
- **Knowledge Graph Integration**: Maintains persistent analysis data for Indian stocks
- **Alpha Vantage Rate Limiting**: Handles free tier API limitations with automatic rate limiting
- **Modular Architecture**: Clean, maintainable code structure with separation of concerns
- **Environment Configuration**: Uses .env for easy configuration

## Installation

### Prerequisites

- Python 3.9+
- MongoDB running on localhost:27017 with database "stock_data"
- Alpha Vantage API key (free tier supported, get one at https://www.alphavantage.co/support/#api-key)

### Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd stock-mcp-server
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a .env file from the example:
   ```bash
   cp .env.example .env
   ```

4. Edit the .env file to configure your settings:
   ```
   # MongoDB Configuration
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DB_NAME=stock_data
   
   # Alpha Vantage API
   ALPHA_VANTAGE_API_KEY=your_api_key_here
   
   # Indian Stock Market Settings
   ALPHA_VANTAGE_DEFAULT_EXCHANGE=NSE  # NSE or BSE
   ```

## Usage

### Start the MCP Server

```bash
python server.py
```

### Configure Claude Desktop App

1. Open Claude Desktop App settings
2. Go to Model Context Protocol settings
3. Add a new server with the following configuration:
   - Name: Indian Stock Analysis
   - Command: `python -m stock_mcp_server.server`
   - Working Directory: Path to the stock_mcp_server directory
   - Environment Variables: `ALPHA_VANTAGE_API_KEY=your_api_key_here` 

### Example Prompts

Once configured, you can ask Claude:

- "Can you provide recommendations on my Indian stock portfolio?"
- "Analyze my current NSE holdings and suggest improvements"
- "What market trends should I be aware of in the Indian market this quarter?"
- "Which stocks in my portfolio should I consider selling?"
- "What new NSE stocks would complement my current portfolio?"
- "Find me the best performing stocks on BSE this week"
- "Can you find information about Reliance Industries stock?"
- "What are the technical indicators for TCS stock?"
- "Search for HDFC related stocks in the Indian market"

## Testing

This repository includes a comprehensive test suite for validating the functionality of the MCP server.

### Available Tests

- `test_mcp_server.py`: A comprehensive test script that validates all endpoints and tools in the MCP server.
- `test_client.py`: A simple client for testing MCP server endpoints.

### Running the Tests

#### Comprehensive Test Script

To run the comprehensive test script:

```bash
python test_mcp_server.py
```

This will test all aspects of the server, including:
- MongoDB connection
- Database operations (portfolio holdings, knowledge graph)
- Indian stock symbol formatting
- Alpha Vantage API integration
- Trending stocks functionality
- MCP tools handler

#### Skip Alpha Vantage API Tests

If you want to skip the tests that make actual API calls to Alpha Vantage (to avoid rate limits):

```bash
python test_mcp_server.py --skip-alpha-vantage
```

### Test Results

The script will output detailed logs to both the console and a `test_mcp_server.log` file. At the end, you'll see a summary of test results:

```
=== Test Results Summary ===
database_connection: ✅ PASSED
portfolio_holdings: ✅ PASSED
knowledge_graph: ✅ PASSED
symbol_formatting: ✅ PASSED
alpha_vantage_api: ✅ PASSED
trending_stocks: ✅ PASSED
tools_handler: ✅ PASSED

Overall: 7/7 tests passed
```

### Troubleshooting Tests

If tests fail, check the following:

1. **Database Connection**: Ensure MongoDB is running on the configured URI (default: `mongodb://localhost:27017`) and the `stock_data` database exists.

2. **Alpha Vantage API**: Check that your API key is set in the `.env` file and has not exceeded rate limits.

3. **Data Availability**: Some tests require existing data in the MongoDB collections (e.g., portfolio holdings). Ensure your database has the necessary data.

4. **Network Issues**: The Alpha Vantage tests require internet connectivity.

### Custom Tests

You can use the test script as a template for creating custom tests for specific functionality. Each test is implemented as an async function and can be added to the `run_all_tests` function.

### Exit Codes

- `0`: All tests passed
- `1`: One or more tests failed

This allows you to integrate the tests into continuous integration pipelines that check for non-zero exit codes.

## Indian Stock Market Notes

When working with the Indian stock market, keep in mind:

- NSE symbols are formatted as `NSE:SYMBOL` (e.g., `NSE:RELIANCE`)
- BSE symbols are formatted as `BSE:CODE` (e.g., `BSE:500325`)
- If no exchange is specified, the default is NSE
- Alpha Vantage free tier is limited to 5 calls per minute, 500 calls per day
- This server is exclusively designed for Indian stocks and will not process requests for other markets

## Architecture

The project follows a modular architecture for better maintainability and separation of concerns:

```

├── server.py           # Main entry point
├── src/                # Source code
│   ├── __init__.py     # Package initialization
│   ├── config.py       # Configuration module
│   ├── handlers/       # MCP handler implementations
│   │   ├── __init__.py
│   │   ├── resources.py  # Resource handlers
│   │   ├── tools.py      # Tool handlers for Indian stock analysis
│   │   └── prompts.py    # Prompt handlers
│   └── utils/          # Utility modules
│       ├── __init__.py
│       ├── database.py   # MongoDB operations
│       └── alpha_vantage.py  # Alpha Vantage API operations for Indian market
├── test_mcp_server.py  # Comprehensive test script
├── test_client.py      # Simple test client
├── requirements.txt    # Dependencies
└── .env.example        # Example environment configuration
```

## Tools

- **get_portfolio_holdings**: Retrieve your current Indian stock portfolio
- **portfolio_analysis**: Analyze your Indian stock portfolio and store insights in knowledge graph
- **get_stock_recommendations**: Get recommendations for Indian stocks to add to portfolio
- **get_removal_recommendations**: Identify Indian stocks that should be removed from portfolio
- **get_market_trend_recommendations**: Find must-buy stocks based on current Indian market trends
- **query_knowledge_graph**: Retrieve stored analyses from the Indian stock knowledge graph
- **get_alpha_vantage_data**: Access Indian market data from Alpha Vantage with free tier support
- **get_technical_analysis**: Get technical indicators (SMA, RSI) for an Indian stock
- **search_stock_symbol**: Search for Indian stock symbols by name or keywords

## Knowledge Graph

The server maintains a knowledge graph in MongoDB (collection: `stock_knowledge_graph`) that stores:

- Historical analyses of Indian stocks
- Performance metrics and trends for NSE and BSE listed companies
- Portfolio inclusion/exclusion recommendations
- Technical and fundamental insights
- Indian market-specific trends and patterns

This provides Claude with persistent memory about your Indian stock portfolio and stocks of interest.

## Alpha Vantage Free Tier Support

This server is optimized for Alpha Vantage's free tier API, which includes:
- Rate limiting to 5 API calls per minute
- Daily limit of 500 API calls
- Support for key endpoints:
  - `GLOBAL_QUOTE` - Current price information
  - `TIME_SERIES_DAILY` - Daily price history
  - `OVERVIEW` - Company information
  - `SYMBOL_SEARCH` - Finding Indian stock symbols
  - Basic technical indicators (SMA, RSI)

The server implements automatic rate limiting to ensure you stay within these limits.

## Configuration

The server uses the following environment variables (defined in `.env`):

### MongoDB Configuration
- `MONGODB_URI`: MongoDB connection string (default: mongodb://localhost:27017)
- `MONGODB_DB_NAME`: Database name (default: stock_data)
- `MONGODB_HOLDINGS_COLLECTION`: Holdings collection name (default: holdings)
- `MONGODB_FINANCIALS_COLLECTION`: Financials collection name (default: detailed_financials)
- `MONGODB_KNOWLEDGE_GRAPH_COLLECTION`: Knowledge graph collection name (default: stock_knowledge_graph)

### Alpha Vantage API
- `ALPHA_VANTAGE_API_KEY`: Your Alpha Vantage API key
- `ALPHA_VANTAGE_BASE_URL`: Alpha Vantage API URL (default: https://www.alphavantage.co/query)
- `ALPHA_VANTAGE_RATE_LIMIT_MINUTE`: API calls allowed per minute (default: 5)
- `ALPHA_VANTAGE_RATE_LIMIT_DAY`: API calls allowed per day (default: 500)
- `ALPHA_VANTAGE_DEFAULT_EXCHANGE`: Default exchange for Indian stocks (default: NSE)

### MCP Server Configuration
- `MCP_SERVER_NAME`: Server name (default: stock_analysis_mcp)
- `MCP_SERVER_VERSION`: Server version (default: 0.1.0)

### Logging Configuration
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: Log message format

### Cache Settings
- `CACHE_ENABLED`: Enable caching (default: True)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 3600)

## License

[MIT License](LICENSE) 