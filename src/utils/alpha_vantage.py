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

# Global API usage tracking
class AlphaVantageStatus:
    def __init__(self):
        self.calls_this_minute = 0
        self.last_reset = datetime.now()
        self.available_calls = 5
        self.is_rate_limited = False
        self.reset_time = None
        self.recent_calls = []  # Track recent call details
        
    def update(self, function: str, symbol: str, success: bool):
        """Update status with a new API call"""
        now = datetime.now()
        
        # Check if we should reset the minute counter
        if (now - self.last_reset).total_seconds() >= 60:
            self.calls_this_minute = 0
            self.last_reset = now
            self.available_calls = 5
            if not self.is_rate_limited:
                logger.info("Minute window reset, available calls reset to 5")
        
        # Record this call
        if success:
            self.calls_this_minute += 1
            self.available_calls = max(0, 5 - self.calls_this_minute)
            
            # Record call details (keep last 10)
            self.recent_calls.append({
                "timestamp": now.strftime("%H:%M:%S"),
                "function": function,
                "symbol": symbol,
                "success": success
            })
            if len(self.recent_calls) > 10:
                self.recent_calls.pop(0)
    
    def set_rate_limited(self, duration_minutes=1):
        """Mark API as rate limited"""
        self.is_rate_limited = True
        self.reset_time = datetime.now() + timedelta(minutes=duration_minutes)
        self.available_calls = 0
        logger.warning(f"Alpha Vantage API marked as rate limited until {self.reset_time.strftime('%H:%M:%S')}")
    
    def check_reset(self):
        """Check if rate limit has been reset"""
        if self.is_rate_limited and self.reset_time and datetime.now() >= self.reset_time:
            self.is_rate_limited = False
            self.available_calls = 5
            self.calls_this_minute = 0
            self.last_reset = datetime.now()
            logger.info("Rate limit reset, available calls reset to 5")
            return True
        return False
    
    def get_status(self) -> dict:
        """Get current API status"""
        self.check_reset()  # Check if we should reset
        
        now = datetime.now()
        time_since_reset = (now - self.last_reset).total_seconds()
        time_to_next_reset = max(0, 60 - time_since_reset)
        
        status = {
            "available_calls": self.available_calls,
            "calls_made_this_minute": self.calls_this_minute,
            "is_rate_limited": self.is_rate_limited,
            "seconds_to_next_reset": round(time_to_next_reset),
            "recent_calls": self.recent_calls
        }
        
        if self.is_rate_limited and self.reset_time:
            status["rate_limit_reset_in_seconds"] = max(0, round((self.reset_time - now).total_seconds()))
            
        return status

# Create global instance
av_status = AlphaVantageStatus()

# Rate limiting for Alpha Vantage free tier
class RateLimiter:
    def __init__(self, calls_per_minute=5, calls_per_day=500):
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        self.minute_calls = deque(maxlen=calls_per_minute)
        self.day_calls = deque(maxlen=calls_per_day)
        self.reset_time = None  # Track when the rate limit will reset
        self.is_rate_limited = False
        self.last_request_time = None
        
    async def wait_if_needed(self):
        """Wait if rate limits would be exceeded"""
        now = datetime.now()
        
        # If we're currently rate limited, check if enough time has passed
        if self.is_rate_limited and self.reset_time:
            if now < self.reset_time:
                wait_time = (self.reset_time - now).total_seconds()
                logger.warning(f"API is rate limited. Need to wait {wait_time:.1f} seconds until reset.")
                # Update global status
                av_status.set_rate_limited(duration_minutes=wait_time/60)
                return False
            else:
                # Reset has occurred
                logger.info("Rate limit reset timer expired, clearing rate limited status")
                self.is_rate_limited = False
                self.minute_calls.clear()
                self.day_calls.clear()
                av_status.check_reset()  # Update global status
        
        # Enforce minimum delay between requests (12 seconds for free tier to be safe)
        if self.last_request_time:
            elapsed = (now - self.last_request_time).total_seconds()
            if elapsed < 12:  # 12 second minimum between requests for free tier
                delay = 12 - elapsed
                logger.info(f"Enforcing minimum delay between requests: waiting {delay:.1f} seconds")
                await asyncio.sleep(delay)
                now = datetime.now()  # Update now after sleep
        
        # Clean up old timestamps
        while self.minute_calls and now - self.minute_calls[0] > timedelta(minutes=1):
            self.minute_calls.popleft()
        
        while self.day_calls and now - self.day_calls[0] > timedelta(days=1):
            self.day_calls.popleft()
        
        # Check if we need to wait for rate limits
        if len(self.minute_calls) >= self.calls_per_minute:
            # We've hit the minute limit
            self.is_rate_limited = True
            self.reset_time = self.minute_calls[0] + timedelta(minutes=1, seconds=5)  # Add 5 sec buffer
            wait_time = 60 - (now - self.minute_calls[0]).total_seconds()
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                av_status.set_rate_limited(duration_minutes=1)  # Update global status
                return False
        
        if len(self.day_calls) >= self.calls_per_day:
            # We've hit the daily limit
            self.is_rate_limited = True
            self.reset_time = self.day_calls[0] + timedelta(days=1, seconds=300)  # Add 5 min buffer
            logger.warning("Daily API call limit reached for Alpha Vantage")
            av_status.set_rate_limited(duration_minutes=60)  # Update global status
            return False
        
        # Track this call
        self.minute_calls.append(now)
        self.day_calls.append(now)
        self.last_request_time = now
        
        # Update available calls
        av_status.calls_this_minute = len(self.minute_calls)
        av_status.available_calls = max(0, self.calls_per_minute - av_status.calls_this_minute)
        
        return True

    def mark_rate_limited(self):
        """Mark the API as rate limited after getting a rate limit response"""
        self.is_rate_limited = True
        # Set reset time to 1 minute from now to be safe
        self.reset_time = datetime.now() + timedelta(minutes=1)
        logger.warning(f"API explicitly returned rate limit error, will avoid calls until {self.reset_time}")
        av_status.set_rate_limited(duration_minutes=1)  # Update global status

# Create a global rate limiter with more conservative limits for free tier
rate_limiter = RateLimiter(
    calls_per_minute=4,  # Use 4 instead of 5 to be safe
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
        av_status.update(function, symbol, False)  # Track failed call
        return {"error": "Alpha Vantage API key not configured"}
    
    # Skip validation for SYMBOL_SEARCH function which doesn't require a symbol
    if function != "SYMBOL_SEARCH" and symbol:
        # Ensure proper formatting for Indian stocks
        formatted_symbol = format_indian_stock_symbol(symbol)
        
        # Verify it's an Indian stock
        if not is_indian_stock(formatted_symbol):
            logger.error(f"Non-Indian stock symbol requested: {symbol}")
            av_status.update(function, symbol, False)  # Track failed call
            return {"error": "Only Indian stock symbols (NSE/BSE) are supported"}
    else:
        formatted_symbol = symbol
    
    # Check if we're currently rate limited
    if rate_limiter.is_rate_limited:
        logger.warning("Rate limiter active, skipping API call")
        av_status.update(function, symbol, False)  # Track failed call
        return {"error": "Failed to fetch data. Rate limit exceeded. Try again later."}
        
    # Apply rate limiting
    can_proceed = await rate_limiter.wait_if_needed()
    if not can_proceed:
        logger.warning("Rate limit would be exceeded, skipping API call")
        av_status.update(function, symbol, False)  # Track failed call
        return {"error": "Failed to fetch data. Rate limit would be exceeded. Try again later."}
        
    request_params = {
        "function": function,
        "symbol": formatted_symbol if function != "SYMBOL_SEARCH" else "",
        "apikey": ALPHA_VANTAGE_API_KEY,
        **params
    }
    
    logger.info(f"Fetching Alpha Vantage data for {formatted_symbol if function != 'SYMBOL_SEARCH' else 'symbol search'} with function {function}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ALPHA_VANTAGE_BASE_URL, params=request_params, timeout=30) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                    except aiohttp.ContentTypeError:
                        # Sometimes Alpha Vantage returns HTML for error pages
                        text_response = await response.text()
                        if "API call frequency" in text_response:
                            rate_limiter.mark_rate_limited()
                            logger.warning("Rate limit exceeded (detected from HTML response)")
                            av_status.update(function, symbol, False)  # Track failed call
                            return {"error": "Failed to fetch data. Rate limit exceeded."}
                        else:
                            logger.error(f"Failed to parse response as JSON: {text_response[:100]}...")
                            av_status.update(function, symbol, False)  # Track failed call
                            return {"error": "Failed to parse API response"}
                    
                    # Check for error messages from Alpha Vantage
                    if "Error Message" in data:
                        logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                        av_status.update(function, symbol, False)  # Track failed call
                        return {"error": f"API Error: {data['Error Message']}"}
                    
                    # Check for rate limit note
                    if "Note" in data:
                        note = data["Note"]
                        if "API call frequency" in note:
                            rate_limiter.mark_rate_limited()
                            logger.warning(f"Rate limit note received: {note}")
                            av_status.update(function, symbol, False)  # Track failed call
                            return {"error": "Failed to fetch data. Rate limit exceeded."}
                        logger.info(f"API Note: {note}")
                    
                    # Check for information note - may be a valid response
                    if "Information" in data:
                        info = data["Information"]
                        logger.info(f"API Information: {info}")
                    
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
                    
                    # Track successful call
                    av_status.update(function, symbol, True)
                    return data
                elif response.status == 403:
                    # Invalid API key or other auth issue
                    logger.error("Alpha Vantage API authentication error (403)")
                    av_status.update(function, symbol, False)  # Track failed call
                    return {"error": "API authentication failed. Check your API key."}
                elif response.status == 429:
                    # Too many requests - explicit rate limit
                    rate_limiter.mark_rate_limited()
                    logger.warning("Alpha Vantage rate limit exceeded (429 response)")
                    av_status.update(function, symbol, False)  # Track failed call
                    return {"error": "Failed to fetch data. Rate limit exceeded."}
                else:
                    logger.error(f"Alpha Vantage API error: Status {response.status}")
                    av_status.update(function, symbol, False)  # Track failed call
                    return {"error": f"API request failed with status {response.status}"}
    except asyncio.TimeoutError:
        logger.error("Request to Alpha Vantage API timed out")
        av_status.update(function, symbol, False)  # Track failed call
        return {"error": "Request timed out"}
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage data: {e}")
        av_status.update(function, symbol, False)  # Track failed call
        return {"error": f"Failed to fetch data: {str(e)}"}

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
    
    # Check if we're currently rate limited
    if rate_limiter.is_rate_limited:
        return {
            "symbol": formatted_symbol,
            "error": "Failed to fetch data. Rate limit exceeded. Try again later."
        }
    
    # For the free tier, we'll prioritize getting quote data only
    # This is more likely to succeed than getting all data points
    quote = await get_stock_quote(formatted_symbol)
    
    # Check for error in quote
    if quote and isinstance(quote, dict) and "error" in quote:
        return {
            "symbol": formatted_symbol,
            "error": quote["error"]
        }
    
    # If we got a valid quote, see if we can get overview next
    if quote and "Global Quote" in quote and not rate_limiter.is_rate_limited:
        overview = await get_stock_overview(formatted_symbol)
    else:
        overview = None
    
    # At this point, we might be hitting rate limits, so skip daily data
    # to prevent overwhelming the free tier limit
    daily = None
    if not rate_limiter.is_rate_limited and quote and overview:
        daily = await get_daily_time_series(formatted_symbol)
    
    # Combine whatever data we got
    result = {
        "symbol": formatted_symbol,
        "overview": overview or {},
        "quote": quote or {}, 
        "daily_data": daily or {},
        "market": "Indian" if formatted_symbol.startswith(("NSE:", "BSE:")) else "Other"
    }
    
    # Check if we got anything meaningful
    if (not quote or "Global Quote" not in quote) and (not overview) and (not daily):
        result["error"] = "Failed to fetch data. Rate limit may have been exceeded."
    
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
    
    # Check if we're currently rate limited
    if rate_limiter.is_rate_limited:
        return {
            "symbol": formatted_symbol,
            "error": "Failed to fetch data. Rate limit exceeded. Try again later."
        }
    
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
    
    # Check for error in response
    if sma_data and "error" in sma_data:
        return {
            "symbol": formatted_symbol,
            "error": sma_data["error"]
        }
    
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
    
    # If we already have one indicator, we may want to skip RSI to conserve API calls
    # This is a tradeoff between complete data and staying within rate limits
    if rate_limiter.is_rate_limited:
        # Return partial results rather than nothing
        if "SMA" in result["indicators"]:
            logger.info("Skipping RSI due to rate limits, returning partial technical analysis")
            return result
    
    # Get RSI (Relative Strength Index)
    rsi_data = await fetch_alpha_vantage_data(
        "RSI", 
        formatted_symbol, 
        time_period=14, 
        series_type="close"
    )
    
    # Check for error in response
    if rsi_data and "error" in rsi_data:
        # If we already have SMA data, return that instead of an error
        if "SMA" in result["indicators"]:
            logger.info("RSI request failed but returning SMA data")
            return result
        return {
            "symbol": formatted_symbol,
            "error": rsi_data["error"]
        }
    
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
    # Check if we're currently rate limited
    if rate_limiter.is_rate_limited:
        logger.warning("Rate limiter active, using static trending stocks fallback")
        return get_static_trending_stocks(limit)
    
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
    rate_limited = False
    symbols_to_try = min(limit * 2, len(major_indian_stocks))
    
    for symbol in major_indian_stocks[:symbols_to_try]:  # Get more than needed to account for potential failures
        # Check if rate limited during processing
        if rate_limiter.is_rate_limited:
            rate_limited = True
            logger.warning(f"Rate limit hit after processing {len(trending_stocks)} stocks")
            break
            
        # Get quote data
        quote_data = await get_stock_quote(symbol)
        
        # Check for error in response
        if quote_data and isinstance(quote_data, dict) and "error" in quote_data:
            logger.warning(f"Error getting quote for {symbol}: {quote_data['error']}")
            if "rate limit" in quote_data["error"].lower():
                rate_limited = True
                break
            continue
        
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
                trend_strength = "STRONG" if abs(change_value) > 3 else "MEDIUM" if abs(change_value) > 1 else "WEAK"
            except (ValueError, TypeError):
                trend = "NEUTRAL"
                trend_strength = "WEAK"
                
            # Create a simplified trend object
            trending_stocks.append({
                "symbol": symbol,
                "company_name": symbol.split(':')[1],  # Simplified
                "price": price,
                "change_percentage": change_percent,
                "sector": get_sector_for_symbol(symbol),  # Use a helper function
                "trend_strength": trend_strength,
                "price_momentum": trend,
                "trend_insights": f"Stock has shown {trend_strength.lower()} {trend.lower()} momentum recently with {change_percent} change.",
                "market": symbol.split(':')[0]  # NSE or BSE
            })
            
            # If we have enough stocks, stop querying to preserve rate limits
            if len(trending_stocks) >= limit:
                break
                
            # Respect rate limits by waiting between calls
            await asyncio.sleep(12)  # Being cautious with free tier limit
    
    # If we didn't get enough stocks or hit rate limits, use fallback data
    if rate_limited or len(trending_stocks) < limit:
        logger.warning(f"Using static fallback data to supplement {len(trending_stocks)} trending stocks")
        # Fill in remaining slots with static data
        trending_stocks.extend(get_static_trending_stocks(limit - len(trending_stocks)))
    
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

def get_sector_for_symbol(symbol: str) -> str:
    """
    Get sector for an Indian stock symbol.
    Simple implementation with common sectors for major stocks.
    
    Args:
        symbol: Stock symbol with exchange prefix
        
    Returns:
        Sector name or "Unknown"
    """
    # Remove exchange prefix if present
    if ":" in symbol:
        ticker = symbol.split(":", 1)[1]
    else:
        ticker = symbol
    
    # Map of tickers to sectors for major Indian stocks
    sector_map = {
        # Banks
        "HDFCBANK": "Banking",
        "ICICIBANK": "Banking",
        "SBIN": "Banking",
        "KOTAKBANK": "Banking",
        "AXISBANK": "Banking",
        
        # IT
        "TCS": "IT Services",
        "INFY": "IT Services",
        "WIPRO": "IT Services",
        "HCLTECH": "IT Services",
        "TECHM": "IT Services",
        
        # Oil & Gas
        "RELIANCE": "Oil & Gas",
        "ONGC": "Oil & Gas",
        
        # Pharma
        "SUNPHARMA": "Pharmaceuticals",
        "DRREDDY": "Pharmaceuticals",
        "DIVISLAB": "Pharmaceuticals",
        
        # Auto
        "MARUTI": "Automobile",
        "M&M": "Automobile",
        "HEROMOTOCO": "Automobile",
        "TATAMOTOR": "Automobile",
        
        # Consumer Goods
        "HINDUNILVR": "Consumer Goods",
        "ITC": "Consumer Goods",
        "TITAN": "Consumer Goods",
        
        # Energy & Power
        "POWERGRID": "Power",
        "NTPC": "Power",
        
        # Metals
        "TATASTEEL": "Metals",
        "JSWSTEEL": "Metals",
        "COAL": "Metals",
        
        # Telecom
        "BHARTIARTL": "Telecommunications",
        
        # Others
        "ASIANPAINT": "Paints",
        "LT": "Construction",
        "APOLLOHOSP": "Healthcare",
        "ADANIPORTS": "Infrastructure",
        "BAJFINANCE": "Financial Services",
        "BAJAJFINSV": "Financial Services",
        "HDFCLIFE": "Insurance",
    }
    
    # Map BSE codes to tickers for common stocks
    bse_to_ticker = {
        "500325": "RELIANCE",
        "532540": "TCS",
        "500180": "HDFCBANK",
        "500209": "INFY",
    }
    
    # Convert BSE code to ticker if needed
    if ticker.isdigit() and ticker in bse_to_ticker:
        ticker = bse_to_ticker[ticker]
    
    return sector_map.get(ticker, "Unknown")

def get_static_trending_stocks(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get static trending stocks data when rate limits are hit.
    
    Args:
        limit: Maximum number of stocks to return
        
    Returns:
        List of trending stocks with static data
    """
    # Static data for top Indian stocks
    static_trending = [
        {
            "symbol": "NSE:RELIANCE",
            "company_name": "RELIANCE",
            "price": "2,856.15",
            "change_percentage": "1.5%",
            "sector": "Oil & Gas",
            "trend_strength": "MEDIUM",
            "price_momentum": "BULLISH",
            "trend_insights": "Reliance has shown medium bullish momentum recently with steady buying interest.",
            "market": "NSE",
            "is_fallback_data": True  # Mark as static data
        },
        {
            "symbol": "NSE:TCS",
            "company_name": "TCS",
            "price": "3,567.80",
            "change_percentage": "0.8%",
            "sector": "IT Services",
            "trend_strength": "WEAK",
            "price_momentum": "BULLISH",
            "trend_insights": "TCS has shown weak bullish momentum with moderate trading volumes.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:HDFCBANK",
            "company_name": "HDFCBANK",
            "price": "1,678.25",
            "change_percentage": "2.1%",
            "sector": "Banking",
            "trend_strength": "STRONG",
            "price_momentum": "BULLISH",
            "trend_insights": "HDFC Bank has shown strong bullish momentum with increasing volumes.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:INFY",
            "company_name": "INFY",
            "price": "1,489.50",
            "change_percentage": "-0.7%",
            "sector": "IT Services",
            "trend_strength": "WEAK",
            "price_momentum": "BEARISH",
            "trend_insights": "Infosys has shown weak bearish momentum with limited selling pressure.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:HINDUNILVR",
            "company_name": "HINDUNILVR",
            "price": "2,742.30",
            "change_percentage": "0.4%",
            "sector": "Consumer Goods",
            "trend_strength": "WEAK",
            "price_momentum": "BULLISH",
            "trend_insights": "Hindustan Unilever has shown weak bullish momentum recently.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:ICICIBANK",
            "company_name": "ICICIBANK",
            "price": "1,056.75",
            "change_percentage": "1.8%",
            "sector": "Banking",
            "trend_strength": "MEDIUM",
            "price_momentum": "BULLISH",
            "trend_insights": "ICICI Bank has shown medium bullish momentum with good buying support.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:SBIN",
            "company_name": "SBIN",
            "price": "789.60",
            "change_percentage": "3.2%",
            "sector": "Banking",
            "trend_strength": "STRONG",
            "price_momentum": "BULLISH",
            "trend_insights": "SBI has shown strong bullish momentum with high volumes.",
            "market": "NSE",
            "is_fallback_data": True
        },
        {
            "symbol": "NSE:BAJFINANCE",
            "company_name": "BAJFINANCE",
            "price": "7,124.50",
            "change_percentage": "-1.2%",
            "sector": "Financial Services",
            "trend_strength": "MEDIUM",
            "price_momentum": "BEARISH",
            "trend_insights": "Bajaj Finance has shown medium bearish momentum with some selling pressure.",
            "market": "NSE",
            "is_fallback_data": True
        }
    ]
    
    # Return requested number of stocks
    return static_trending[:limit]

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

async def get_alpha_vantage_status() -> Dict[str, Any]:
    """
    Get current status of Alpha Vantage API usage.
    
    Returns:
        Status dictionary with available calls and rate limit info
    """
    return av_status.get_status()

async def preflight_check(function: str, symbol: str = "") -> Dict[str, Any]:
    """
    Check if an API call is likely to succeed before making it.
    
    Args:
        function: Alpha Vantage function to check
        symbol: Symbol to query (if applicable)
        
    Returns:
        Status dictionary with go/no-go recommendation
    """
    status = av_status.get_status()
    
    # Define API call costs (some functions require multiple internal calls)
    function_costs = {
        "GLOBAL_QUOTE": 1,
        "OVERVIEW": 1,
        "TIME_SERIES_DAILY": 1,
        "SYMBOL_SEARCH": 1,
        "SMA": 1,
        "RSI": 1,
        "get_technical_analysis": 2,  # Requires SMA and RSI
        "get_stock_data": 1,          # Prioritize just quote data
        "get_india_trending_stocks": 5,  # High cost, better to use fallback
    }
    
    # Get cost of this function
    cost = function_costs.get(function, 1)
    
    # Check if we have enough calls available
    can_proceed = status["available_calls"] >= cost and not status["is_rate_limited"]
    
    result = {
        "function": function,
        "symbol": symbol,
        "cost": cost,
        "can_proceed": can_proceed,
        "status": status,
        "recommendation": "proceed" if can_proceed else "wait",
        "fallback_available": function in ["get_india_trending_stocks", "get_technical_analysis"]
    }
    
    if not can_proceed:
        if status["is_rate_limited"]:
            result["reason"] = "API is currently rate limited"
            result["wait_seconds"] = status.get("rate_limit_reset_in_seconds", 60)
        else:
            result["reason"] = f"Not enough available calls ({status['available_calls']} available, {cost} required)"
            result["wait_seconds"] = status["seconds_to_next_reset"]
    
    return result 