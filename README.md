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
- **LLM-Optimized Data**: Automatically limits and simplifies data responses to be easily processed by Claude
- **Segmented Portfolio Analysis**: Processes large portfolios in smaller segments to prevent timeouts

## Installation

### Prerequisites

- Python 3.9+
- MongoDB running on localhost:27017 with database "stock_data"
- Alpha Vantage API key (free tier supported, get one at https://www.alphavantage.co/support/#api-key)
- Claude Desktop app (available at https://claude.ai/download)

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

Claude Desktop uses a configuration file to connect to MCP servers. You'll need to create or edit this file to include your stock analysis server.

1. Create or edit the configuration file at:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the stock analysis MCP server configuration:

```json
{
  "mcpServers": {
    "stock-analysis-mcp": {
      "command": "/path/to/your/python",
      "args": [
        "/path/to/stock_mcp_server/server.py"
      ],
      "cwd": "/path/to/stock_mcp_server",
      "env": {
        "ALPHA_VANTAGE_API_KEY": "your_api_key_here",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB_NAME": "stock_data",
        "MONGODB_HOLDINGS_COLLECTION": "holdings",
        "MONGODB_FINANCIALS_COLLECTION": "detailed_financials",
        "MONGODB_KNOWLEDGE_GRAPH_COLLECTION": "stock_knowledge_graph",
        "ALPHA_VANTAGE_BASE_URL": "https://www.alphavantage.co/query",
        "ALPHA_VANTAGE_RATE_LIMIT_MINUTE": "5",
        "ALPHA_VANTAGE_RATE_LIMIT_DAY": "500",
        "ALPHA_VANTAGE_DEFAULT_EXCHANGE": "NSE",
        "MCP_SERVER_NAME": "stock-analysis-mcp",
        "MCP_SERVER_VERSION": "0.1.0",
        "LOG_LEVEL": "INFO",
        "CACHE_ENABLED": "True",
        "CACHE_TTL": "3600"
      }
    }
  }
}
```

**Important Notes:**
- Use the full path to your Python executable (e.g., `/usr/bin/python3` or `C:\Python39\python.exe`)
- The server key `stock-analysis-mcp` must use hyphens, not underscores
- The `MCP_SERVER_NAME` in env must match the server key
- Make sure all paths are absolute paths

3. Start or restart Claude Desktop

4. Verify the server connection:
   - Open Claude Desktop
   - The tools icon (hammer) should appear in the interface
   - Start a new conversation (important - new tools may not appear in existing conversations)
   - Try asking about your stock portfolio

### Example Prompts

Once configured, you can ask Claude:

- "Can you provide a summary of my portfolio?"
- "Analyze segment 1 of my portfolio"
- "Analyze the next segment of my portfolio with segment_size=8"
- "Analyze segment 3 of my portfolio with detailed metrics"
- "What are the stocks in segment 2 of my portfolio?" 
- "Which sectors are most represented in my portfolio?"
- "Can you provide recommendations on my Indian stock portfolio?"
- "Analyze the banking stocks in my portfolio"
- "What market trends should I be aware of in the Indian market this quarter?"
- "Which stocks in my portfolio should I consider selling?"
- "What new NSE stocks would complement my current portfolio?"
- "Find me the best performing stocks on BSE this week"
- "Can you find information about Reliance Industries stock?"
- "What are the technical indicators for TCS stock?"
- "Search for HDFC related stocks in the Indian market"

## Troubleshooting

### MCP Tools Not Appearing

If the tools aren't appearing in Claude despite successful server startup:

1. **Check your logs**:
   ```bash
   tail -f ~/Library/Logs/Claude/mcp-server-stock-analysis-mcp.log
   ```

2. **Verify server naming**:
   - Ensure the server key in `claude_desktop_config.json` uses hyphens (`stock-analysis-mcp`)
   - Make sure the `MCP_SERVER_NAME` environment variable matches this name

3. **Start a new conversation** in Claude after making changes

4. **Enable developer mode** in Claude's settings

5. **Check paths**: Make sure all paths in the configuration are absolute and correct

6. **Full Python path**: Use the full path to your Python executable (e.g., run `which python` to find it)

7. **Check Claude app log**: 
   ```bash
   tail -f ~/Library/Logs/Claude/app.log
   ```

### Common Issues

1. **Python not found**: Ensure the Python path in the configuration is correct
2. **MongoDB connection issues**: Check that MongoDB is running on the configured URI
3. **Tool schema issues**: Make sure all tools have proper schema definitions
4. **Claude Desktop version**: Keep Claude Desktop updated to the latest version
5. **Server name mismatch**: Server name in code must match configuration file
6. **Large data responses**: If Claude struggles processing large datasets, use segmented analysis:
   - First get a portfolio summary with `get_portfolio_summary`
   - Then analyze one segment at a time with `portfolio_analysis` using the segment parameter
   - Use smaller segment sizes (3-5 stocks) for detailed analysis

### Handling Large Portfolios

For large portfolios (20+ stocks), the server implements a segmented approach:

1. **Get Portfolio Summary**:
   - Use `get_portfolio_summary` to see an overview of your portfolio
   - This shows total stocks, sectors, and recommended segmentation

2. **Analyze in Segments**:
   - Use `portfolio_analysis` with the `segment` parameter
   - Start with segment 1, then progress through each segment
   - Example: "Analyze segment 1 of my portfolio", then "Analyze segment 2..."

3. **Control Segment Size**:
   - Default segment size is 5 stocks
   - Use `segment_size` parameter to adjust (1-5 stocks per segment)
   - Example: "Analyze segment 1 with segment_size=3 for detailed analysis"

4. **Request Levels of Detail**:
   - Use `include_details=false` for quick overview (default)
   - Use `include_details=true` for comprehensive metrics and insights
   - When using detailed analysis, segment size is automatically reduced to prevent timeouts

5. **Response Size Management**:
   - The server automatically monitors response size and simplifies data if needed
   - Text fields are truncated to prevent overwhelming Claude
   - Financial metrics are compressed to focus on essential information
   - If a response would be too large, it's automatically simplified with a notification

### Performance Optimizations

The server includes several optimizations to ensure Claude can process stock data efficiently:

1. **Adaptive Response Sizing**:
   - Automatic monitoring of response size during processing
   - Dynamic simplification when responses exceed size thresholds
   - Truncation of text fields to 50-100 characters maximum
   - Removal of non-essential data fields

2. **Financial Data Compression**:
   - Automatic compression of financial data responses
   - Limiting historical data to the 2 most recent periods
   - Removal of metadata and internal fields
   - Prioritization of essential metrics over comprehensive data

3. **Parameter Limits**:
   - Portfolio analysis: Maximum 15 stocks, 5 per segment (3 for detailed analysis)
   - Stock recommendations: Maximum 8 recommendations
   - Removal analysis: Maximum 10 stocks analyzed for removal
   - Market trends: Maximum 8 trending stocks

4. **Intelligent Segmentation**:
   - Automatic adjustment of segment size based on analysis type
   - Smaller segments for detailed analysis to prevent timeouts
   - Progress tracking during analysis to identify bottlenecks

5. **Response Size Management**:
   - Real-time monitoring of response size during processing
   - Automatic simplification when responses exceed size thresholds
   - Emergency fallback to minimal data when responses would be too large
   - Detailed logging of response sizes for troubleshooting

6. **Intelligent Internal Handling**:
   - Analysis functions use complete data internally while presenting simplified results
   - Market trend recommendations filter out stocks already in portfolio
   - Financial data compression preserves critical metrics while reducing size

These optimizations ensure Claude can process your stock data efficiently without being overwhelmed by excessive information or experiencing timeouts.

## Testing

This repository includes a comprehensive test suite for validating the functionality of the MCP server.

### Available Tests

- `test_mcp_server.py`: A comprehensive test script that validates all endpoints and tools in the MCP server.
- `test_client.py`: A simple client for testing MCP server endpoints.
- `test_server_startup.sh`: Script to test the server startup process

### Running the Tests

#### Quick Startup Test

To verify the server can start properly:

```bash
./test_server_startup.sh
```

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

The server provides the following MCP tools, organized by category:

### Portfolio Analysis
- **Get Portfolio Holdings**: Retrieve current Indian stock portfolio with basic information
  - Parameters:
    - `limit`: Maximum number of holdings to return (default: 10, max: 50)
    - `summary`: Return simplified stock data (default: true)
- **Get Portfolio Summary**: Get a high-level overview of the portfolio 
  - Returns:
    - Total stocks count
    - Sector breakdown
    - Segmentation guide
    - Analysis recommendations
- **Analyze Portfolio**: Analyze portfolio holdings with metrics and recommendations
  - Parameters:
    - `limit`: Maximum stocks to analyze (default: 10, max: 15)
    - `include_details`: Include comprehensive metrics (default: false)
    - `segment`: Which segment of stocks to analyze (default: 1)
    - `segment_size`: Number of stocks per segment (default: 5, max: 5)
  - Notes:
    - For detailed analysis, segment size is automatically reduced to 3
    - Response size is monitored and simplified if needed
    - Text fields are truncated to 50 characters maximum

### Stock Recommendations
- **Get Stock Recommendations**: Get recommendations for Indian stocks to add based on financial metrics
  - Parameters:
    - `criteria`: Type of recommendations to get (e.g., "growth", "value", "dividend") (default: "growth")
    - `limit`: Maximum number of recommendations to return (default: 5, max: 8)
  - Notes:
    - Responses are optimized for Claude with text field truncation
    - Recommendations are filtered to exclude stocks already in portfolio
    - Response size is monitored and simplified if needed

- **Get Removal Recommendations**: Identify Indian stocks that should be removed from portfolio
  - Parameters:
    - `limit`: Maximum number of stocks to analyze (default: 5, max: 10)
  - Notes:
    - Automatically analyzes portfolio holdings for removal candidates
    - Identifies stocks with declining profits, bearish trends, or low fundamental scores
    - Response size is monitored and simplified if needed

### Market Trends
- **Get Market Trend Recommendations**: Find must-buy Indian stocks based on current market trends
  - Parameters:
    - `limit`: Maximum number of recommendations to return (default: 5, max: 8)
  - Notes:
    - Automatically excludes stocks already in your portfolio
    - Focuses on stocks with strong momentum and positive technical indicators
    - Response size is monitored and simplified if needed

### Knowledge Graph
- **Query Knowledge Graph**: Query the Indian stock knowledge graph for historical analysis and insights

### Market Data
- **Get Alpha Vantage Data**: Access Alpha Vantage API data for Indian stock market with free tier limitations 
- **Search Stock Symbol**: Search for Indian stock symbols by name or keywords

### Technical Analysis
- **Get Technical Analysis**: Get technical analysis indicators for an Indian stock (SMA, RSI)
  - Parameters:
    - `symbol`: Stock symbol to analyze (e.g., "NSE:RELIANCE")
  - Notes:
    - This tool requires multiple API calls to Alpha Vantage
    - May be rate limited if several analysis requests are made in quick succession

- **Get Optimized Technical Analysis**: Smart technical analysis that avoids rate limits
  - Parameters:
    - `symbol`: Stock symbol to analyze (e.g., "NSE:RELIANCE")
    - `indicators`: Comma-separated list of indicators to analyze (e.g., "SMA,RSI")
  - Notes:
    - Performs preflight checks to ensure API calls are available
    - Only makes necessary API calls for requested indicators
    - Provides educational content when rate limited
    - More efficient use of the 5 calls per minute limit

### API Management
- **Get Alpha Vantage API Status**: Check current status of API calls and rate limits
  - Notes:
    - Shows available API calls remaining in current minute window
    - Displays recent API call history
    - Provides recommendations on when to make calls
    - Helps Claude manage the 5 calls per minute limitation efficiently

## Knowledge Graph

The server maintains a knowledge graph in MongoDB (collection: `stock_knowledge_graph`) that stores:

- Historical analyses of Indian stocks
- Performance metrics and trends for NSE and BSE listed companies
- Portfolio inclusion/exclusion recommendations
- Technical and fundamental insights
- Indian market-specific trends and patterns

This provides Claude with persistent memory about your Indian stock portfolio and stocks of interest.

## Data Optimization for Claude

This server implements several strategies to optimize data for Claude's consumption:

1. **Automatic Data Limiting**: 
   - Default limits on query results to prevent overwhelming Claude with too much information
   - Portfolio holdings limited to 10 stocks by default (configurable up to 50)
   - Recommendations limited to 5 stocks by default
   - Portfolio analysis limited to 15 stocks maximum with 5 stocks per segment

2. **Data Simplification**:
   - Portfolio holdings simplified to essential fields only (symbol, quantity, average price)
   - Full details available when needed for analysis but hidden from direct display
   - Financial data automatically compressed to focus on essential metrics
   - Text fields truncated to prevent overwhelming Claude

3. **Parameter Controls**:
   - Tools expose parameters to allow Claude to request more or less data as needed
   - Ability to toggle between summary and detailed views
   - Control over segment size and which segment to analyze

4. **Segmented Processing**:
   - Portfolio analysis can be performed in segments to prevent large responses
   - Each segment processes a subset of stocks (default: 5 stocks per segment)
   - Allows Claude to analyze large portfolios without hitting connection timeouts
   - Automatic adjustment of segment size based on analysis type

5. **Response Size Management**:
   - Real-time monitoring of response size during processing
   - Automatic simplification when responses exceed size thresholds
   - Emergency fallback to minimal data when responses would be too large
   - Detailed logging of response sizes for troubleshooting

6. **Intelligent Internal Handling**:
   - Analysis functions use complete data internally while presenting simplified results
   - Market trend recommendations filter out stocks already in portfolio
   - Financial data compression preserves critical metrics while reducing size

These optimizations ensure Claude can process your stock data efficiently without being overwhelmed by excessive information or experiencing timeouts.

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
- `MCP_SERVER_NAME`: Server name (default: stock-analysis-mcp)
- `MCP_SERVER_VERSION`: Server version (default: 0.1.0)

### Logging Configuration
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: Log message format

### Cache Settings
- `CACHE_ENABLED`: Enable caching (default: True)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 3600)

## License

[MIT License](LICENSE) 

## Alpha Vantage API Management

This server includes sophisticated management of Alpha Vantage API calls to stay within free tier limits:

### Rate Limit Tracking
- Maintains a global counter of API calls made in each minute window
- Automatically detects and handles rate limit responses from Alpha Vantage
- Provides status information through the `get_alpha_vantage_status` tool

### Smart Call Management
- **Preflight Checks**: Before making API calls, tools check if they'll exceed rate limits
- **Cost-aware Processing**: Each API function has an assigned "cost" to track its impact
- **Graceful Degradation**: When rate limits are reached, tools provide static data or educational content
- **Targeted Calls**: Technical analysis can be configured to retrieve only specific indicators

### Fallback Mechanisms
- When rate limited, the system provides alternative content:
  - Static market data for trending stocks
  - Educational content about technical indicators
  - Historical data when available
  - Clear messaging about when to try again

### Example Usage

Here's how Claude should use the API efficiently:

1. **Check API Status First**:
   - "Let me check the Alpha Vantage API status before proceeding"
   - This helps plan which calls to make within the 5-call limit

2. **Use Optimized Tools**:
   - "I'll use optimized technical analysis to get just the SMA indicator"
   - This makes only the necessary API calls for the requested information

3. **Batch Similar Requests**:
   - "Let me collect all the stock symbols first, then query them together"
   - This helps avoid making redundant or unnecessary API calls

4. **Use Static Data When Appropriate**:
   - "Since we're rate limited, I'll use static trend data for now"
   - This provides value even when API limits are reached