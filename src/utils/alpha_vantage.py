"""
Alpha Vantage API utility functions.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import deque
import aiohttp

from ..config import (
    ALPHA_VANTAGE_API_KEY, 
    ALPHA_VANTAGE_BASE_URL,
    ALPHA_VANTAGE_RATE_LIMIT_MINUTE,
    ALPHA_VANTAGE_RATE_LIMIT_DAY,
    ALPHA_VANTAGE_DEFAULT_EXCHANGE
)

# Setup logging
logger = logging.getLogger("stock_mcp_server.alpha_vantage")

# Rate limiting for Alpha Vantage free tier
class RateLimiter:
    def __init__(self, calls_per_minute=5, calls_per_day=500):
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        self.minute_calls = deque(maxlen=calls_per_minute)
        self.day_calls = deque(maxlen=calls_per_day)
        
    async def wait_if_needed(self):
        """Wait if rate limits would be exceeded"""
        now = datetime.now()
        
        # Clean up old timestamps
        while self.minute_calls and now - self.minute_calls[0] > timedelta(minutes=1):
            self.minute_calls.popleft()
        
        while self.day_calls and now - self.day_calls[0] > timedelta(days=1):
            self.day_calls.popleft()
        
        # Check if we need to wait for rate limits
        if len(self.minute_calls) >= self.calls_per_minute:
            wait_time = 60 - (now - self.minute_calls[0]).total_seconds()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time + 1)  # Add a buffer second
        
        if len(self.day_calls) >= self.calls_per_day:
            # We've hit the daily limit
            logger.warning("Daily API call limit reached for Alpha Vantage")
            return False
        
        # Track this call
        self.minute_calls.append(now)
        self.day_calls.append(now)
        return True

# Create a global rate limiter
rate_limiter = RateLimiter(
    calls_per_minute=ALPHA_VANTAGE_RATE_LIMIT_MINUTE,
    calls_per_day=ALPHA_VANTAGE_RATE_LIMIT_DAY
)

def format_indian_stock_symbol(symbol: str) -> str:
    """
    Format a stock symbol for Indian markets (NSE/BSE).
    
    Args:
        symbol: The stock symbol to format
        
    Returns:
        Formatted symbol with exchange prefix if needed
    """
    # If symbol already has an exchange prefix, verify it's Indian
    if ':' in symbol:
        exchange, ticker = symbol.split(':', 1)
        if exchange.upper() in ['NSE', 'BSE']:
            return f"{exchange.upper()}:{ticker}"
        else:
            # Replace with NSE as default if non-Indian exchange was specified
            logger.warning(f"Non-Indian exchange specified: {exchange}. Defaulting to NSE.")
            return f"NSE:{ticker}"
        
    # If it's a numerical code, it's likely a BSE symbol
    if symbol.isdigit():
        return f"BSE:{symbol}"
        
    # Default to NSE for other cases
    return f"{ALPHA_VANTAGE_DEFAULT_EXCHANGE}:{symbol}"

def is_indian_stock(symbol: str) -> bool:
    """
    Verify if a stock symbol is from Indian exchanges (NSE/BSE).
    
    Args:
        symbol: Stock symbol to check
        
    Returns:
        True if Indian stock, False otherwise
    """
    if ':' in symbol:
        exchange = symbol.split(':', 1)[0].upper()
        return exchange in ['NSE', 'BSE']
    
    # If no exchange specified, we're treating it as Indian by default
    return True

async def fetch_alpha_vantage_data(
    function: str, 
    symbol: str, 
    **params
) -> Optional[Dict[str, Any]]:
    """
    Fetch data from Alpha Vantage API with rate limiting.
    
    Args:
        function: Alpha Vantage function (e.g., GLOBAL_QUOTE, TIME_SERIES_DAILY)
        symbol: Stock symbol (can include exchange prefix like NSE:RELIANCE)
        **params: Additional parameters for the API call
        
    Returns:
        API response data or None if error
    """
    if not ALPHA_VANTAGE_API_KEY:
        logger.warning("Alpha Vantage API key not set")
        return None
    
    # Skip validation for SYMBOL_SEARCH function which doesn't require a symbol
    if function != "SYMBOL_SEARCH" and symbol:
        # Ensure proper formatting for Indian stocks
        formatted_symbol = format_indian_stock_symbol(symbol)
        
        # Verify it's an Indian stock
        if not is_indian_stock(formatted_symbol):
            logger.error(f"Non-Indian stock symbol requested: {symbol}")
            return None
    else:
        formatted_symbol = symbol
        
    # Apply rate limiting
    can_proceed = await rate_limiter.wait_if_needed()
    if not can_proceed:
        logger.warning("Daily API call limit reached for Alpha Vantage")
        return None
        
    request_params = {
        "function": function,
        "symbol": formatted_symbol if function != "SYMBOL_SEARCH" else "",
        "apikey": ALPHA_VANTAGE_API_KEY,
        **params
    }
    
    logger.info(f"Fetching Alpha Vantage data for {formatted_symbol if function != 'SYMBOL_SEARCH' else 'symbol search'} with function {function}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ALPHA_VANTAGE_BASE_URL, params=request_params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for error messages from Alpha Vantage
                    if "Error Message" in data:
                        logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                        return None
                    
                    # Check if the response is about an Indian stock (when applicable)
                    if function == "SYMBOL_SEARCH" and "bestMatches" in data:
                        # Filter to only include Indian stock results
                        indian_results = []
                        for match in data["bestMatches"]:
                            region = match.get("4. region", "")
                            name = match.get("2. name", "")
                            if "India" in region or any(x in name for x in ["NSE", "BSE"]):
                                indian_results.append(match)
                        
                        # Replace the results with only Indian stocks
                        data["bestMatches"] = indian_results
                    
                    # Check for Note (usually indicates rate limiting)
                    if "Note" in data and "API call frequency" in data["Note"]:
                        logger.warning(f"Alpha Vantage rate limit warning: {data['Note']}")
                    
                    return data
                else:
                    logger.error(f"Alpha Vantage API error: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage data: {e}")
        return None

async def get_stock_overview(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get stock overview data.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Stock overview data or None if error
    """
    return await fetch_alpha_vantage_data("OVERVIEW", symbol)

async def get_stock_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get stock quote data.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Stock quote data or None if error
    """
    return await fetch_alpha_vantage_data("GLOBAL_QUOTE", symbol)

async def get_daily_time_series(symbol: str, outputsize: str = "compact") -> Optional[Dict[str, Any]]:
    """
    Get daily time series data.
    
    Args:
        symbol: Stock symbol
        outputsize: 'compact' (100 data points) or 'full' (20+ years of data)
        
    Returns:
        Daily time series data or None if error
    """
    return await fetch_alpha_vantage_data(
        "TIME_SERIES_DAILY", 
        symbol,
        outputsize=outputsize
    )

async def get_stock_data(symbol: str) -> Dict[str, Any]:
    """
    Get comprehensive stock data combining multiple endpoints.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Combined stock data
    """
    # Format symbol for Indian market if needed
    formatted_symbol = format_indian_stock_symbol(symbol)
    
    # Get overview data
    overview = await get_stock_overview(formatted_symbol)
    
    # Get global quote
    quote = await get_stock_quote(formatted_symbol)
    
    # Get daily data (compact = last 100 trading days)
    daily = await get_daily_time_series(formatted_symbol)
    
    # Combine data
    result = {
        "symbol": formatted_symbol,
        "overview": overview or {},
        "quote": quote or {}, 
        "daily_data": daily or {},
        "market": "Indian" if formatted_symbol.startswith(("NSE:", "BSE:")) else "Other"
    }
    
    return result

async def get_technical_analysis(symbol: str) -> Dict[str, Any]:
    """
    Get basic technical analysis for a stock
    
    Args:
        symbol: Stock symbol (e.g., NSE:RELIANCE)
        
    Returns:
        Dictionary with technical indicators
    """
    formatted_symbol = format_indian_stock_symbol(symbol)
    
    result = {
        "symbol": formatted_symbol,
        "indicators": {}
    }
    
    # Get SMA (Simple Moving Average)
    sma_data = await fetch_alpha_vantage_data(
        "SMA", 
        formatted_symbol, 
        time_period=20, 
        series_type="close"
    )
    
    if sma_data and "Technical Analysis: SMA" in sma_data:
        # Get the most recent SMA value
        dates = sorted(sma_data["Technical Analysis: SMA"].keys(), reverse=True)
        if dates:
            latest_date = dates[0]
            result["indicators"]["SMA"] = {
                "value": sma_data["Technical Analysis: SMA"][latest_date]["SMA"],
                "time_period": 20,
                "date": latest_date
            }
    
    # Get RSI (Relative Strength Index)
    rsi_data = await fetch_alpha_vantage_data(
        "RSI", 
        formatted_symbol, 
        time_period=14, 
        series_type="close"
    )
    
    if rsi_data and "Technical Analysis: RSI" in rsi_data:
        # Get the most recent RSI value
        dates = sorted(rsi_data["Technical Analysis: RSI"].keys(), reverse=True)
        if dates:
            latest_date = dates[0]
            result["indicators"]["RSI"] = {
                "value": rsi_data["Technical Analysis: RSI"][latest_date]["RSI"],
                "time_period": 14,
                "date": latest_date
            }
    
    return result

async def get_india_trending_stocks(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Gets trending Indian stocks based on basic data.
    
    Args:
        limit: Maximum number of stocks to return
        
    Returns:
        List of trending stocks with basic data
    """
    # Predefined list of major Indian stocks - expanded list
    major_indian_stocks = [
        # Large Cap
        "NSE:RELIANCE",  # Reliance Industries
        "NSE:TCS",       # Tata Consultancy Services
        "NSE:HDFCBANK",  # HDFC Bank
        "NSE:INFY",      # Infosys
        "NSE:HINDUNILVR", # Hindustan Unilever
        "NSE:ICICIBANK", # ICICI Bank
        "NSE:SBIN",      # State Bank of India
        "NSE:BAJFINANCE", # Bajaj Finance
        "NSE:BHARTIARTL", # Bharti Airtel
        "NSE:KOTAKBANK", # Kotak Mahindra Bank
        "NSE:LT",        # Larsen & Toubro
        "NSE:ITC",       # ITC Limited
        "NSE:AXISBANK",  # Axis Bank
        "NSE:ASIANPAINT", # Asian Paints
        "NSE:MARUTI",    # Maruti Suzuki
        "NSE:HCLTECH",   # HCL Technologies
        
        # Mid Cap
        "NSE:TITAN",     # Titan Company
        "NSE:ADANIPORTS", # Adani Ports
        "NSE:BAJAJFINSV", # Bajaj Finserv
        "NSE:WIPRO",     # Wipro
        "NSE:HDFCLIFE",  # HDFC Life Insurance
        "NSE:TECHM",     # Tech Mahindra
        
        # Pharma & Healthcare
        "NSE:SUNPHARMA", # Sun Pharmaceutical
        "NSE:DRREDDY",   # Dr. Reddy's Laboratories
        "NSE:DIVISLAB",  # Divi's Laboratories
        "NSE:APOLLOHOSP", # Apollo Hospitals
        
        # Auto
        "NSE:M&M",       # Mahindra & Mahindra
        "NSE:HEROMOTOCO", # Hero MotoCorp
        "NSE:TATAMOTOR", # Tata Motors
        
        # Energy & Metals
        "NSE:ONGC",      # Oil and Natural Gas Corporation
        "NSE:POWERGRID", # Power Grid Corporation
        "NSE:NTPC",      # NTPC Limited
        "NSE:COAL",      # Coal India
        "NSE:TATASTEEL", # Tata Steel
        "NSE:JSWSTEEL",  # JSW Steel
        
        # BSE examples
        "BSE:500325",    # Reliance Industries (BSE)
        "BSE:532540",    # TCS (BSE)
        "BSE:500180",    # HDFC Bank (BSE)
        "BSE:500209",    # Infosys (BSE)
    ]
    
    trending_stocks = []
    
    for symbol in major_indian_stocks[:limit*2]:  # Get more than needed to account for potential failures
        # Get quote data
        quote_data = await get_stock_quote(symbol)
        
        if quote_data and "Global Quote" in quote_data:
            data = quote_data["Global Quote"]
            price = data.get("05. price", "N/A")
            change_percent = data.get("10. change percent", "0%")
            
            # Skip if we don't get valid data
            if price == "N/A" or change_percent == "0%":
                continue
            
            # Clean up the change percentage for processing
            if isinstance(change_percent, str):
                change_percent_cleaned = change_percent.strip("%").strip()
            else:
                change_percent_cleaned = change_percent
                
            try:
                change_value = float(change_percent_cleaned)
                trend = "BULLISH" if change_value > 0 else "BEARISH"
            except (ValueError, TypeError):
                trend = "NEUTRAL"
                
            # Create a simplified trend object
            trending_stocks.append({
                "symbol": symbol,
                "company_name": symbol.split(':')[1],  # Simplified
                "price": price,
                "change_percentage": change_percent,
                "source": "Alpha Vantage API",
                "volume": data.get("06. volume", "N/A"),
                "technical_trend": trend,
                "market": symbol.split(':')[0]  # NSE or BSE
            })
            
            # Respect rate limits by waiting between calls
            await asyncio.sleep(12)  # Being cautious with free tier limit
            
        if len(trending_stocks) >= limit:
            break
    
    # Sort by absolute change percentage (either positive or negative)        
    try:
        trending_stocks.sort(
            key=lambda x: abs(float(x["change_percentage"].strip("%").strip())) 
                if isinstance(x["change_percentage"], str) else 0, 
            reverse=True
        )
    except (ValueError, TypeError):
        pass
            
    return trending_stocks[:limit]

async def search_stock_symbol(keywords: str) -> List[Dict[str, Any]]:
    """
    Search for stock symbols using Alpha Vantage SYMBOL_SEARCH endpoint.
    
    Args:
        keywords: Search keywords
        
    Returns:
        List of matching stock symbols
    """
    data = await fetch_alpha_vantage_data("SYMBOL_SEARCH", "", keywords=keywords)
    
    if not data or "bestMatches" not in data:
        return []
        
    results = []
    for match in data["bestMatches"]:
        # Filter for Indian stocks (NSE or BSE)
        exchange = match.get("4. region", "")
        if "India" in exchange or any(x in match.get("2. name", "") for x in ["NSE", "BSE"]):
            results.append({
                "symbol": match.get("1. symbol", ""),
                "name": match.get("2. name", ""),
                "type": match.get("3. type", ""),
                "region": exchange,
                "market_close": match.get("5. marketClose", ""),
                "market_open": match.get("6. marketOpen", ""),
                "timezone": match.get("7. timezone", ""),
                "currency": match.get("8. currency", "")
            })
    
    return results

async def get_trending_stocks(exclude_symbols: List[str] = None) -> List[Dict[str, Any]]:
    """
    Get trending stocks from Alpha Vantage.
    For free tier, use basic Indian stock market trending method.
    
    Args:
        exclude_symbols: List of symbols to exclude
        
    Returns:
        List of trending stocks
    """
    if exclude_symbols is None:
        exclude_symbols = []

    # For Indian market with free tier, use our custom implementation
    stocks = await get_india_trending_stocks(limit=5)
    
    # Filter out excluded symbols
    return [s for s in stocks if s.get("symbol") not in exclude_symbols] 