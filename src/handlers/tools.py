"""
Tool handlers for MCP server.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import mcp.types as types

from ..utils.database import (
    connect_to_mongodb,
    handle_mongo_object,
    get_portfolio_holdings,
    get_detailed_financials,
    get_latest_financial_metrics, 
    update_knowledge_graph,
    query_knowledge_graph,
    get_stock_recommendations
)
from ..utils.alpha_vantage import (
    get_stock_data,
    get_trending_stocks,
    get_technical_analysis,
    get_india_trending_stocks,
    search_stock_symbol
)

# Setup logging
logger = logging.getLogger("stock_mcp_server.handlers.tools")

async def handle_list_tools() -> List[types.Tool]:
    """
    List available tools for Indian stock market analysis.
    
    Returns:
        List of available tools
    """
    return [
        types.Tool(
            name="get_portfolio_holdings",
            description="Get a list of Indian stocks in the user's portfolio with basic information",
            inputSchema={
                "type": "object", 
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of holdings to return (default: 10)",
                        "minimum": 1,
                        "maximum": 50
                    },
                    "summary": {
                        "type": "boolean",
                        "description": "If true, returns a simplified view with fewer fields (default: true)"
                    }
                }, 
                "additionalProperties": False
            },
            category="Portfolio Analysis",
            displayName="Get Portfolio Holdings"
        ),
        types.Tool(
            name="get_portfolio_summary",
            description="Get a high-level summary of the portfolio including count of stocks by sector and the total number of stocks",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            },
            category="Portfolio Analysis",
            displayName="Get Portfolio Summary"
        ),
        types.Tool(
            name="portfolio_analysis",
            description="Analyze the current Indian stock portfolio holdings including latest earnings, metrics, and provide recommendations. Stores analysis in knowledge graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of stocks to analyze (default: 10)",
                        "minimum": 1,
                        "maximum": 30
                    },
                    "include_details": {
                        "type": "boolean",
                        "description": "Whether to include detailed analysis for each stock (default: false)"
                    },
                    "segment": {
                        "type": "integer",
                        "description": "Which segment/page of stocks to analyze (1-based, default: 1)",
                        "minimum": 1
                    },
                    "segment_size": {
                        "type": "integer",
                        "description": "Number of stocks per segment (default: 5)",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "additionalProperties": False
            },
            category="Portfolio Analysis",
            displayName="Analyze Portfolio"
        ),
        types.Tool(
            name="get_stock_recommendations",
            description="Get recommendations for Indian stocks (NSE/BSE) to add to the portfolio based on financial metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "string", 
                        "description": "Criteria for recommendations (e.g., 'growth', 'value', 'dividend')"
                    }
                },
                "additionalProperties": False
            },
            category="Stock Recommendations",
            displayName="Get Stock Recommendations"
        ),
        types.Tool(
            name="get_removal_recommendations",
            description="Identify Indian stocks that should be removed from portfolio",
            inputSchema={
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "string",
                        "description": "Criteria for removal (e.g., 'underperforming', 'high risk')"
                    }
                },
                "additionalProperties": False
            },
            category="Stock Recommendations",
            displayName="Get Removal Recommendations"
        ),
        types.Tool(
            name="get_market_trend_recommendations",
            description="Find must-buy Indian stocks based on current market trends (NSE/BSE only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recommendations to return"
                    }
                },
                "additionalProperties": False
            },
            category="Market Trends",
            displayName="Get Market Trend Recommendations"
        ),
        types.Tool(
            name="query_knowledge_graph",
            description="Query the Indian stock knowledge graph for historical analysis and insights",
            inputSchema={
                "type": "object", 
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Indian stock symbol to query (optional, e.g., 'RELIANCE' or 'NSE:RELIANCE')"
                    },
                    "criteria": {
                        "type": "string",
                        "description": "Search criteria (e.g., 'bullish', 'bearish', 'high growth')"
                    }
                },
                "additionalProperties": False
            },
            category="Knowledge Graph",
            displayName="Query Knowledge Graph"
        ),
        types.Tool(
            name="get_alpha_vantage_data",
            description="Access Alpha Vantage API data for Indian stock market (NSE/BSE only) with free tier limitations (rate limited to 5 calls/minute)",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string", 
                        "description": "Indian stock symbol (e.g., 'RELIANCE' or 'NSE:RELIANCE' or 'BSE:500325')"
                    },
                    "function": {
                        "type": "string",
                        "description": "Alpha Vantage function (defaults to GLOBAL_QUOTE, supported free tier functions: GLOBAL_QUOTE, TIME_SERIES_DAILY, OVERVIEW, SYMBOL_SEARCH)"
                    }
                },
                "required": ["symbol"],
                "additionalProperties": False
            },
            category="Market Data",
            displayName="Get Alpha Vantage Data"
        ),
        types.Tool(
            name="get_technical_analysis",
            description="Get technical analysis indicators for an Indian stock (SMA, RSI)",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Indian stock symbol (e.g., 'RELIANCE' or 'NSE:RELIANCE')"
                    }
                },
                "required": ["symbol"],
                "additionalProperties": False
            },
            category="Technical Analysis",
            displayName="Get Technical Analysis"
        ),
        types.Tool(
            name="search_stock_symbol",
            description="Search for Indian stock symbols by name or keywords (NSE/BSE only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords for Indian stocks (e.g., 'Reliance', 'HDFC', 'TCS')"
                    }
                },
                "required": ["keywords"],
                "additionalProperties": False
            },
            category="Market Data",
            displayName="Search Stock Symbol"
        ),
    ]

async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle a tool call.
    
    Args:
        name: Name of the tool
        arguments: Tool arguments
        
    Returns:
        List of Content objects with the tool result
    """
    logger.info(f"Tool call: {name} with arguments {arguments}")
    
    # Get db connection
    db = await connect_to_mongodb()
    
    # Check if the database connection is successful
    if db is None:
        logger.error("Database connection failed")
        # Return a properly formatted error message that follows MCP protocol
        return [types.TextContent(
            text=json.dumps({"error": "Failed to connect to MongoDB database"}, indent=2),
            type="text"
        )]
    
    # Get Portfolio Holdings
    if name == "get_portfolio_holdings":
        try:
            limit = arguments.get("limit", 10)
            summary = arguments.get("summary", True)
            holdings = await get_portfolio_holdings(limit=limit, summary=summary)
            return [types.TextContent(
                text=json.dumps(holdings, default=handle_mongo_object, indent=2),
                type="text"
            )]
        except Exception as e:
            logger.error(f"Error fetching portfolio holdings: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error fetching portfolio holdings: {str(e)}"}, indent=2),
                type="text"
            )]
    
    # Get Portfolio Summary
    elif name == "get_portfolio_summary":
        try:
            # Get all portfolio holdings
            holdings = await get_portfolio_holdings(limit=100, summary=True)
            
            if not holdings:
                return [types.TextContent(
                    text=json.dumps({"message": "No holdings found in portfolio"}, indent=2),
                    type="text"
                )]
            
            # Count stocks by sector
            sectors = {}
            for holding in holdings:
                sector = holding.get("sector", "Other")
                if sector not in sectors:
                    sectors[sector] = 0
                sectors[sector] += 1
            
            # Sort sectors by count
            sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
            
            # Calculate total value and allocations
            total_value = sum(holding.get("quantity", 0) * holding.get("average_price", 0) for holding in holdings)
            
            # Create summary with recommendations for segmented analysis
            segment_size = 5  # Recommended segment size
            total_segments = (len(holdings) + segment_size - 1) // segment_size
            
            summary = {
                "total_stocks": len(holdings),
                "total_segments": total_segments,
                "recommended_segment_size": segment_size,
                "sectors": dict(sorted_sectors),
                "segment_guide": [
                    f"Segment {i+1}: Stocks {i*segment_size+1}-{min((i+1)*segment_size, len(holdings))} of {len(holdings)}"
                    for i in range(total_segments)
                ],
                "analysis_tip": "For best results, analyze one segment at a time using: portfolio_analysis with segment=1, segment_size=5"
            }
            
            return [types.TextContent(
                text=json.dumps(summary, indent=2),
                type="text"
            )]
        except Exception as e:
            logger.error(f"Error generating portfolio summary: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error generating portfolio summary: {str(e)}"}, indent=2),
                type="text"
            )]
        
    # Portfolio Analysis
    elif name == "portfolio_analysis":
        try:
            # Extract parameters with defaults
            limit = arguments.get("limit", 10)  # Default reduced to 10 stocks instead of processing all
            include_details = arguments.get("include_details", False)
            segment = arguments.get("segment", 1)  # Default to first segment
            segment_size = arguments.get("segment_size", 5)  # Default to 5 stocks per segment
            
            # Apply safety limits to prevent timeouts
            if limit > 30:
                limit = 30  # Maximum cap at 30 stocks to prevent timeouts
            if segment_size > 10:
                segment_size = 10  # Maximum cap at 10 stocks per segment
            
            logger.info(f"Starting portfolio analysis with limit={limit}, include_details={include_details}, segment={segment}, segment_size={segment_size}")
            
            # 1. Get all portfolio holdings first
            all_holdings = await get_portfolio_holdings(limit=limit, summary=False)
            logger.info(f"Retrieved {len(all_holdings)} holdings from portfolio")
            
            if not all_holdings:
                logger.warning("No holdings found in portfolio")
                return [types.TextContent(text=json.dumps({"message": "No holdings found in portfolio"}, indent=2), type="text")]
            
            # 2. Calculate pagination for segments
            start_idx = (segment - 1) * segment_size
            end_idx = min(start_idx + segment_size, len(all_holdings))
            
            # Check if segment is valid
            if start_idx >= len(all_holdings):
                logger.warning(f"Segment {segment} is out of range for {len(all_holdings)} holdings")
                return [types.TextContent(
                    text=json.dumps({
                        "error": f"Segment {segment} is out of range. There are only {(len(all_holdings) + segment_size - 1) // segment_size} segments available for {len(all_holdings)} holdings with segment_size={segment_size}"
                    }, indent=2),
                    type="text"
                )]
            
            # Get current segment of holdings
            segment_holdings = all_holdings[start_idx:end_idx]
            logger.info(f"Analyzing segment {segment} with {len(segment_holdings)} holdings (stocks {start_idx+1}-{end_idx} of {len(all_holdings)})")
            
            # 3. For each holding in the segment, get detailed financials
            analysis_results = []
            for i, holding in enumerate(segment_holdings):
                symbol = holding.get("symbol", "")
                logger.info(f"Analyzing holding {i+1}/{len(segment_holdings)} in segment {segment}: {symbol}")
                
                # Get most recent financial data
                financials = await get_detailed_financials(symbol)
                
                if not financials:
                    logger.warning(f"No financial data found for {symbol}")
                    continue
                
                # Find the most recent quarter from financial metrics
                latest_metrics = None
                if financials.get("financial_metrics") and len(financials["financial_metrics"]) > 0:
                    logger.debug(f"Processing financial metrics for {symbol}")
                    # Sort by quarter if available
                    metrics_list = sorted(
                        financials["financial_metrics"],
                        key=lambda x: x.get("quarter", ""),
                        reverse=True
                    )
                    latest_metrics = metrics_list[0] if metrics_list else None
                else:
                    logger.warning(f"No financial metrics found for {symbol}")
                
                # Create condensed or detailed analysis based on parameter
                if include_details and latest_metrics:
                    logger.debug(f"Creating detailed analysis for {symbol}")
                    analysis = {
                        "symbol": symbol,
                        "company_name": holding.get("company_name", ""),
                        "quantity": holding.get("quantity", 0),
                        "average_price": holding.get("average_price", 0),
                        "latest_quarter": latest_metrics.get("quarter", "Unknown") if latest_metrics else "Unknown",
                        "metrics": {
                            "pe_ratio": latest_metrics.get("ttm_pe", "N/A") if latest_metrics else "N/A",
                            "revenue_growth": latest_metrics.get("revenue_growth", "N/A") if latest_metrics else "N/A",
                            "profit_growth": latest_metrics.get("net_profit_growth", "N/A") if latest_metrics else "N/A",
                            "piotroski_score": latest_metrics.get("piotroski_score", "N/A") if latest_metrics else "N/A",
                            "market_cap": latest_metrics.get("market_cap", "N/A") if latest_metrics else "N/A",
                            "book_value": latest_metrics.get("book_value", "N/A") if latest_metrics else "N/A"
                        },
                        "strengths": latest_metrics.get("strengths", "") if latest_metrics else "",
                        "weaknesses": latest_metrics.get("weaknesses", "") if latest_metrics else "",
                        "technicals": latest_metrics.get("technicals_trend", "") if latest_metrics else "",
                        "fundamental_insights": latest_metrics.get("fundamental_insights", "") if latest_metrics else ""
                    }
                else:
                    # Create simplified analysis with only essential information
                    logger.debug(f"Creating simplified analysis for {symbol}")
                    analysis = {
                        "symbol": symbol,
                        "company_name": holding.get("company_name", ""),
                        "quantity": holding.get("quantity", 0),
                        "average_price": holding.get("average_price", 0),
                        "key_metrics": {
                            "pe_ratio": latest_metrics.get("ttm_pe", "N/A") if latest_metrics else "N/A",
                            "profit_growth": latest_metrics.get("net_profit_growth", "N/A") if latest_metrics else "N/A",
                        },
                        "recommendation": latest_metrics.get("recommendation", "Hold") if latest_metrics else "Hold",
                    }
                
                analysis_results.append(analysis)
                logger.debug(f"Analysis for {symbol} completed and added to results")
                
                # Only store detailed analysis in knowledge graph to save time
                if include_details and latest_metrics:
                    # Store analysis in knowledge graph for future reference
                    knowledge_entry = {
                        "symbol": symbol,
                        "company_name": holding.get("company_name", ""),
                        "analysis_date": datetime.now(),
                        "latest_quarter": latest_metrics.get("quarter", "Unknown") if latest_metrics else "Unknown",
                        "analysis": analysis
                    }
                    
                    await update_knowledge_graph(symbol, knowledge_entry)
                    logger.debug(f"Knowledge graph updated for {symbol}")
            
            logger.info(f"Completed analysis for {len(analysis_results)} stocks in segment {segment}")
            
            # Add a summary for the segment
            if analysis_results:
                total_segments = (len(all_holdings) + segment_size - 1) // segment_size
                portfolio_summary = {
                    "portfolio_size": len(all_holdings),  # Total portfolio size
                    "segment": segment,  # Current segment number
                    "total_segments": total_segments,  # Total number of segments
                    "segment_stocks": len(analysis_results),  # How many we analyzed in this segment
                    "stocks_range": f"{start_idx+1}-{end_idx} of {len(all_holdings)}",  # Range of stocks in this segment
                    "analysis_date": datetime.now().isoformat(),
                    "holdings": analysis_results
                }
                logger.info(f"Returning segment {segment}/{total_segments} portfolio analysis results")
                return [types.TextContent(text=json.dumps(portfolio_summary, default=handle_mongo_object, indent=2), type="text")]
            else:
                logger.warning(f"No analysis results generated for segment {segment}")
                return [types.TextContent(text=json.dumps({"message": f"No analysis results could be generated for segment {segment}"}, indent=2), type="text")]
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error analyzing portfolio: {str(e)}"}, indent=2),
                type="text"
            )]
    
    # Stock Recommendations
    elif name == "get_stock_recommendations":
        try:
            criteria = arguments.get("criteria", "growth")
            recommendations = await get_stock_recommendations(criteria)
            return [types.TextContent(
                text=json.dumps(recommendations, default=handle_mongo_object, indent=2),
                type="text"
            )]
        except Exception as e:
            logger.error(f"Error getting stock recommendations: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error getting stock recommendations: {str(e)}"}, indent=2),
                type="text"
            )]
        
    # Portfolio Removal Recommendations
    elif name == "get_removal_recommendations":
        # Get all holdings for analysis
        holdings = await get_portfolio_holdings(limit=50, summary=False)
        
        # Analyze each holding for potential removal
        removal_candidates = []
        for holding in holdings:
            symbol = holding.get("symbol", "")
            
            # Get latest financial metrics
            latest_metrics = await get_latest_financial_metrics(symbol)
            
            if latest_metrics:
                # Determine if stock should be removed
                reasons = []
                
                # Check for declining profits using string comparison (since values might be like "-23%")
                if latest_metrics.get("net_profit_growth") and "-" in str(latest_metrics["net_profit_growth"]):
                    reasons.append("Declining profits")
                    
                # Check for technical trend
                if latest_metrics.get("technicals_trend") and "BEARISH" in latest_metrics["technicals_trend"]:
                    reasons.append("Bearish technical trend")
                    
                # Check for low piotroski score
                piotroski_score = latest_metrics.get("piotroski_score", "0")
                try:
                    if piotroski_score != "NA" and float(str(piotroski_score).replace("NA", "0")) < 3:
                        reasons.append("Low fundamental strength (Piotroski score)")
                except (ValueError, TypeError):
                    pass
                
                # Add if we have reasons for removal
                if reasons:
                    removal_candidates.append({
                        "symbol": symbol,
                        "company_name": holding.get("company_name", ""),
                        "quantity": holding.get("quantity", 0),
                        "average_price": holding.get("average_price", 0),
                        "reasons": reasons,
                        "metrics": {
                            "pe_ratio": latest_metrics.get("ttm_pe", "N/A"),
                            "profit_growth": latest_metrics.get("net_profit_growth", "N/A"),
                            "piotroski_score": latest_metrics.get("piotroski_score", "N/A"),
                        },
                        "weaknesses": latest_metrics.get("weaknesses", ""),
                        "technicals": latest_metrics.get("technicals_trend", "")
                    })
                    
                    # Update knowledge graph
                    await update_knowledge_graph(symbol, {
                        "portfolio.recommendation": "Consider Removing",
                        "portfolio.removal_reasons": reasons,
                        "analysis_date": datetime.now()
                    })
        
        return [types.TextContent(text=json.dumps(removal_candidates, default=handle_mongo_object, indent=2), type="text")]
        
    # Market Trend Recommendations
    elif name == "get_market_trend_recommendations":
        # Get current portfolio symbols
        holdings = await get_portfolio_holdings(limit=50, summary=True)
        exclude_symbols = [h.get("symbol", "") for h in holdings]
        
        # Get limit parameter
        limit = int(arguments.get("limit", 5))
        
        # Use our specialized India trending stocks function
        trending_stocks = await get_india_trending_stocks(limit=limit)
        
        # Store recommendations in knowledge graph
        for stock in trending_stocks:
            symbol = stock.get("symbol", "")
            if symbol and symbol not in exclude_symbols:
                knowledge_entry = {
                    "symbol": symbol,
                    "company_name": stock.get("company_name", symbol.split(':')[1] if ':' in symbol else symbol),
                    "analysis_date": datetime.now(),
                    "metrics": {
                        "price": stock.get("price", "N/A"),
                        "change_percentage": stock.get("change_percentage", "N/A"),
                        "volume": stock.get("volume", "N/A")
                    },
                    "technicals": stock.get("technical_trend", ""),
                    "source": "Alpha Vantage API (Indian Market Trends)",
                    "portfolio": {
                        "in_portfolio": False,
                        "recommendation": "Indian Market Trend Buy"
                    }
                }
                await update_knowledge_graph(symbol, knowledge_entry)
        
        return [types.TextContent(text=json.dumps(trending_stocks, default=handle_mongo_object, indent=2), type="text")]
        
    # Knowledge Graph Query
    elif name == "query_knowledge_graph":
        symbol = arguments.get("symbol")
        criteria = arguments.get("criteria")
        
        # Query knowledge graph
        entries = await query_knowledge_graph(symbol, criteria)
        
        if symbol and not entries:
            return [types.TextContent(text=json.dumps({"message": f"No knowledge graph data found for {symbol}"}, indent=2), type="text")]
        
        # Format for LLM (simplified)
        simplified_knowledge = []
        for entry in entries:
            simplified = {
                "symbol": entry.get("symbol", ""),
                "company_name": entry.get("company_name", ""),
                "analysis_date": entry.get("analysis_date", ""),
                "latest_quarter": entry.get("latest_quarter", ""),
                "metrics": entry.get("metrics", {}),
                "portfolio": entry.get("portfolio", {}),
                "technicals": entry.get("technicals", ""),
                "fundamental_insights": entry.get("fundamental_insights", "")
            }
            simplified_knowledge.append(simplified)
        
        return [types.TextContent(text=json.dumps(simplified_knowledge, default=handle_mongo_object, indent=2), type="text")]
        
    # Alpha Vantage Data
    elif name == "get_alpha_vantage_data":
        symbol = arguments.get("symbol")
        if not symbol:
            return [types.TextContent(text=json.dumps({"error": "Missing required parameter: symbol"}, indent=2), type="text")]
        
        function = arguments.get("function", "GLOBAL_QUOTE")
        
        # Add a note about rate limits
        rate_limit_notice = (
            "Note: Running on Alpha Vantage free tier API which has rate limits (5 calls/minute, 500 calls/day). "
            "This request may be delayed if rate limits are being approached."
        )
        
        # Handle different functions
        if function == "GLOBAL_QUOTE":
            data = await get_stock_data(symbol)
            return [types.TextContent(text=f"{rate_limit_notice}\n\n{json.dumps(data, indent=2)}", type="text")]
        elif function in ["TIME_SERIES_DAILY", "OVERVIEW", "SYMBOL_SEARCH"]:
            from ..utils.alpha_vantage import fetch_alpha_vantage_data
            
            # For SYMBOL_SEARCH, handle search parameters differently
            if function == "SYMBOL_SEARCH":
                data = await fetch_alpha_vantage_data(function, "", keywords=symbol)
            else:
                data = await fetch_alpha_vantage_data(function, symbol)
                
            if data:
                return [types.TextContent(text=f"{rate_limit_notice}\n\n{json.dumps(data, indent=2)}", type="text")]
            else:
                return [types.TextContent(text=json.dumps({"error": "Failed to fetch data. Rate limit may have been exceeded."}, indent=2), type="text")]
        else:
            return [types.TextContent(text=json.dumps({"error": f"Function '{function}' not supported in free tier or invalid"}, indent=2), type="text")]
            
    # Technical Analysis
    elif name == "get_technical_analysis":
        symbol = arguments.get("symbol")
        if not symbol:
            return [types.TextContent(text=json.dumps({"error": "Missing required parameter: symbol"}, indent=2), type="text")]
            
        # Get technical analysis
        analysis = await get_technical_analysis(symbol)
        
        # Store in knowledge graph
        knowledge_entry = {
            "symbol": analysis.get("symbol", symbol),
            "analysis_date": datetime.now(),
            "technicals": analysis.get("indicators", {}),
            "source": "Alpha Vantage API (Technical Analysis)"
        }
        await update_knowledge_graph(symbol, knowledge_entry)
        
        return [types.TextContent(text=json.dumps(analysis, indent=2), type="text")]
        
    # Symbol Search
    elif name == "search_stock_symbol":
        keywords = arguments.get("keywords")
        if not keywords:
            return [types.TextContent(text=json.dumps({"error": "Missing required parameter: keywords"}, indent=2), type="text")]
            
        # Search for symbols
        results = await search_stock_symbol(keywords)
        return [types.TextContent(text=json.dumps(results, indent=2), type="text")]
        
    else:
        # Unsupported tool
        error_message = f"Unsupported tool: {name}"
        logger.error(error_message)
        return [types.TextContent(
            text=json.dumps({"error": error_message}, indent=2),
            type="text"
        )] 