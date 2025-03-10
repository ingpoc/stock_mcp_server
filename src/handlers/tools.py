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
                "properties": {}, 
                "additionalProperties": False
            },
            category="Portfolio Analysis",
            displayName="Get Portfolio Holdings"
        ),
        types.Tool(
            name="portfolio_analysis",
            description="Analyze the current Indian stock portfolio holdings including latest earnings, metrics, and provide recommendations. Stores analysis in knowledge graph.",
            inputSchema={
                "type": "object", 
                "properties": {}, 
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

async def handle_call_tool(
    name: str, 
    arguments: Optional[Dict[str, Any]] = None
) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests.
    
    Args:
        name: Tool name
        arguments: Tool arguments
        
    Returns:
        Tool results
        
    Raises:
        ValueError: If the tool name is not supported
    """
    logger.info(f"Tool call: {name} with arguments {arguments}")
    if arguments is None:
        arguments = {}
    
    try:
        db = await connect_to_mongodb()
        if not db:
            return [types.TextContent(text=json.dumps({"error": "Failed to connect to database"}, indent=2))]
        
        # Portfolio Holdings
        if name == "get_portfolio_holdings":
            holdings_data = await get_portfolio_holdings()
            
            # Transform data to be LLM-friendly
            simplified_holdings = []
            for holding in holdings_data:
                simplified_holdings.append({
                    "symbol": holding.get("symbol", ""),
                    "company_name": holding.get("company_name", ""),
                    "quantity": holding.get("quantity", 0),
                    "average_price": holding.get("average_price", 0),
                    "asset_type": holding.get("asset_type", "stock"),
                    "purchase_date": holding.get("purchase_date")
                })
            
            return [types.TextContent(text=json.dumps(simplified_holdings, default=handle_mongo_object, indent=2))]
            
        # Portfolio Analysis
        elif name == "portfolio_analysis":
            # 1. Get portfolio holdings
            holdings = await get_portfolio_holdings()
            
            # 2. For each holding, get detailed financials
            analysis_results = []
            for holding in holdings:
                symbol = holding.get("symbol", "")
                
                # Get most recent financial data
                financials = await get_detailed_financials(symbol)
                
                if financials:
                    # Find the most recent quarter from financial metrics
                    latest_metrics = None
                    if financials.get("financial_metrics") and len(financials["financial_metrics"]) > 0:
                        # Sort by quarter if available
                        metrics_list = sorted(
                            financials["financial_metrics"],
                            key=lambda x: x.get("quarter", ""),
                            reverse=True
                        )
                        latest_metrics = metrics_list[0] if metrics_list else None
                    
                    # Create condensed analysis
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
                    
                    analysis_results.append(analysis)
                    
                    # Store analysis in knowledge graph for future reference
                    knowledge_entry = {
                        "symbol": symbol,
                        "company_name": holding.get("company_name", ""),
                        "analysis_date": datetime.now(),
                        "latest_quarter": latest_metrics.get("quarter", "Unknown") if latest_metrics else "Unknown",
                        "metrics": analysis["metrics"],
                        "strengths": analysis["strengths"],
                        "weaknesses": analysis["weaknesses"],
                        "technicals": analysis["technicals"],
                        "fundamental_insights": analysis["fundamental_insights"],
                        "portfolio": {
                            "quantity": holding.get("quantity", 0),
                            "average_price": holding.get("average_price", 0),
                            "in_portfolio": True
                        }
                    }
                    
                    # Add Alpha Vantage API data if available
                    alpha_vantage_data = await get_stock_data(symbol)
                    if alpha_vantage_data:
                        knowledge_entry["alpha_vantage"] = alpha_vantage_data
                    
                    # Update or insert knowledge graph entry
                    await update_knowledge_graph(symbol, knowledge_entry)
            
            return [types.TextContent(text=json.dumps(analysis_results, default=handle_mongo_object, indent=2))]
            
        # Stock Recommendations
        elif name == "get_stock_recommendations":
            criteria = arguments.get("criteria")
            
            # Get portfolio symbols to exclude them from recommendations
            holdings = await get_portfolio_holdings()
            exclude_symbols = [h.get("symbol", "") for h in holdings]
            
            # Get recommendations
            recommendations = await get_stock_recommendations(exclude_symbols, criteria)
            
            # Store recommendations in knowledge graph
            for recommendation in recommendations:
                symbol = recommendation.get("symbol", "")
                if symbol:
                    knowledge_entry = {
                        "symbol": symbol,
                        "company_name": recommendation.get("company_name", ""),
                        "analysis_date": datetime.now(),
                        "metrics": recommendation.get("metrics", {}),
                        "strengths": recommendation.get("strengths", ""),
                        "weaknesses": recommendation.get("weaknesses", ""),
                        "technicals": recommendation.get("technicals", ""),
                        "fundamental_insights": recommendation.get("fundamental_insights", ""),
                        "portfolio": {
                            "in_portfolio": False,
                            "recommendation": "Consider Adding"
                        }
                    }
                    await update_knowledge_graph(symbol, knowledge_entry)
            
            return [types.TextContent(text=json.dumps(recommendations, default=handle_mongo_object, indent=2))]
            
        # Portfolio Removal Recommendations
        elif name == "get_removal_recommendations":
            # Get holdings
            holdings = await get_portfolio_holdings()
            
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
            
            return [types.TextContent(text=json.dumps(removal_candidates, default=handle_mongo_object, indent=2))]
            
        # Market Trend Recommendations
        elif name == "get_market_trend_recommendations":
            # Get current portfolio symbols
            holdings = await get_portfolio_holdings()
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
            
            return [types.TextContent(text=json.dumps(trending_stocks, default=handle_mongo_object, indent=2))]
            
        # Knowledge Graph Query
        elif name == "query_knowledge_graph":
            symbol = arguments.get("symbol")
            criteria = arguments.get("criteria")
            
            # Query knowledge graph
            entries = await query_knowledge_graph(symbol, criteria)
            
            if symbol and not entries:
                return [types.TextContent(text=json.dumps({"message": f"No knowledge graph data found for {symbol}"}, indent=2))]
            
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
            
            return [types.TextContent(text=json.dumps(simplified_knowledge, default=handle_mongo_object, indent=2))]
            
        # Alpha Vantage Data
        elif name == "get_alpha_vantage_data":
            symbol = arguments.get("symbol")
            if not symbol:
                return [types.TextContent(text=json.dumps({"error": "Missing required parameter: symbol"}, indent=2))]
            
            function = arguments.get("function", "GLOBAL_QUOTE")
            
            # Add a note about rate limits
            rate_limit_notice = (
                "Note: Running on Alpha Vantage free tier API which has rate limits (5 calls/minute, 500 calls/day). "
                "This request may be delayed if rate limits are being approached."
            )
            
            # Handle different functions
            if function == "GLOBAL_QUOTE":
                data = await get_stock_data(symbol)
                return [types.TextContent(text=f"{rate_limit_notice}\n\n{json.dumps(data, indent=2)}")]
            elif function in ["TIME_SERIES_DAILY", "OVERVIEW", "SYMBOL_SEARCH"]:
                from ..utils.alpha_vantage import fetch_alpha_vantage_data
                
                # For SYMBOL_SEARCH, handle search parameters differently
                if function == "SYMBOL_SEARCH":
                    data = await fetch_alpha_vantage_data(function, "", keywords=symbol)
                else:
                    data = await fetch_alpha_vantage_data(function, symbol)
                    
                if data:
                    return [types.TextContent(text=f"{rate_limit_notice}\n\n{json.dumps(data, indent=2)}")]
                else:
                    return [types.TextContent(text=json.dumps({"error": "Failed to fetch data. Rate limit may have been exceeded."}, indent=2))]
            else:
                return [types.TextContent(text=json.dumps({"error": f"Function '{function}' not supported in free tier or invalid"}, indent=2))]
                
        # Technical Analysis
        elif name == "get_technical_analysis":
            symbol = arguments.get("symbol")
            if not symbol:
                return [types.TextContent(text=json.dumps({"error": "Missing required parameter: symbol"}, indent=2))]
                
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
            
            return [types.TextContent(text=json.dumps(analysis, indent=2))]
            
        # Symbol Search
        elif name == "search_stock_symbol":
            keywords = arguments.get("keywords")
            if not keywords:
                return [types.TextContent(text=json.dumps({"error": "Missing required parameter: keywords"}, indent=2))]
                
            # Search for symbols
            results = await search_stock_symbol(keywords)
            return [types.TextContent(text=json.dumps(results, indent=2))]
            
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(text=json.dumps({"error": str(e)}, indent=2))] 