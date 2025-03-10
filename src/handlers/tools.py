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
            
            # Calculate basic statistics
            avg_price = round(sum(holding.get("average_price", 0) for holding in holdings) / len(holdings), 2)
            
            # Create a compact symbol list (just 5 examples per sector)
            sector_examples = {}
            for holding in holdings:
                sector = holding.get("sector", "Other")
                if sector not in sector_examples:
                    sector_examples[sector] = []
                if len(sector_examples[sector]) < 5:  # Limit to 5 stocks per sector
                    sector_examples[sector].append(holding.get("symbol", ""))
            
            # Count stocks by performance category (if available)
            performance = {"Strong Performer": 0, "Neutral": 0, "Underperforming": 0, "Unknown": 0}
            for holding in holdings:
                perf = holding.get("performance", "Unknown")
                if perf in performance:
                    performance[perf] += 1
                else:
                    performance["Unknown"] += 1
            
            # Calculate segmentation strategy
            total_stocks = len(holdings)
            segment_size = 5  # Recommended segment size
            total_segments = (total_stocks + segment_size - 1) // segment_size
            
            # Create a very concise summary
            summary = {
                "portfolio_stats": {
                    "total_stocks": total_stocks,
                    "average_price": avg_price,
                    "sectors_count": len(sectors),
                },
                "segments": {
                    "total_segments": total_segments,
                    "recommended_size": segment_size,
                    "segment_ranges": [f"Segment {i+1}: Stocks {i*segment_size+1}-{min((i+1)*segment_size, total_stocks)}" for i in range(total_segments)]
                },
                "sector_distribution": dict(sorted_sectors),
                "analysis_tip": "For best results, analyze one segment at a time using: portfolio_analysis with segment=1, segment_size=5"
            }
            
            logger.info(f"Generated portfolio summary with {total_stocks} stocks across {len(sectors)} sectors")
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
            # Parse parameters with lower limits to reduce response size
            limit = 10
            segment = 1
            segment_size = 5  # Default to smaller segment size (was 10)
            include_details = False
            max_limit = 15    # Lower maximum limit (was 20)
            
            parameters = arguments
            
            # Parse limit parameter - how many stocks to analyze
            if "limit" in parameters:
                try:
                    limit = int(parameters["limit"])
                    # Cap to reasonable size to prevent timeouts
                    limit = min(max(1, limit), max_limit)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid limit value: {parameters.get('limit')}, using default: {limit}")
            
            # Parse segment parameter - which segment of the portfolio to analyze
            if "segment" in parameters:
                try:
                    segment = int(parameters["segment"])
                    # Ensure segment is at least 1
                    segment = max(1, segment)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid segment value: {parameters.get('segment')}, using default: {segment}")
            
            # Parse segment_size parameter - how many stocks per segment
            if "segment_size" in parameters:
                try:
                    segment_size = int(parameters["segment_size"])
                    # Cap to reasonable size to prevent timeouts
                    segment_size = min(max(1, segment_size), 5)  # Maximum segment size reduced to 5 (was 10)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid segment_size value: {parameters.get('segment_size')}, using default: {segment_size}")
            
            # Parse include_details parameter
            if "include_details" in parameters:
                include_details_param = parameters["include_details"]
                if isinstance(include_details_param, bool):
                    include_details = include_details_param
                elif isinstance(include_details_param, str):
                    include_details = include_details_param.lower() in ["true", "yes", "1"]
            
            # If detailed analysis is requested, reduce segment size to prevent timeouts
            if include_details:
                # For detailed analysis, use even smaller segment size
                original_segment_size = segment_size
                segment_size = min(segment_size, 3)  # No more than 3 detailed stocks at once
                logger.info(f"Detailed analysis requested, reducing segment size from {original_segment_size} to {segment_size}")
            
            # Get portfolio holdings
            holdings = await get_portfolio_holdings()
            if not holdings:
                return [types.TextContent(
                    text=json.dumps({"error": "Unable to retrieve portfolio holdings"}, indent=2),
                    type="text"
                )]
            
            # Calculate start and end indices for requested segment
            start_idx = (segment - 1) * segment_size
            end_idx = min(start_idx + segment_size, len(holdings))
            
            # Check if segment is valid
            if start_idx >= len(holdings):
                return [types.TextContent(
                    text=json.dumps({
                        "error": f"Segment {segment} is out of range. Portfolio has {len(holdings)} stocks, "
                                 f"with segment_size {segment_size}, max segment is {(len(holdings) // segment_size) + 1}."
                    }, indent=2),
                    type="text"
                )]
            
            # Get segment of holdings
            segment_holdings = holdings[start_idx:end_idx]
            logger.info(f"Analyzing segment {segment} with {len(segment_holdings)} stocks (indices {start_idx}-{end_idx-1})")
            
            # Prepare response data
            analysis_results = []
            total_investment = 0
            total_current_value = 0
            
            # Keep track of response size to avoid timeouts
            response_size_estimate = 0
            max_response_size = 15000  # Characters (conservative estimate)
            
            for holding in segment_holdings:
                symbol = holding.get("symbol")
                if not symbol:
                    logger.warning(f"Holding missing symbol: {holding}")
                    continue
                
                logger.info(f"Processing {symbol}...")
                
                # Get stock details and financials
                stock_data = {
                        "symbol": symbol,
                    "company_name": holding.get("company_name", symbol),
                        "quantity": holding.get("quantity", 0),
                    "purchase_price": holding.get("purchase_price", 0),
                    "current_price": holding.get("current_price", 0),
                    "sector": holding.get("sector", ""),
                    "security_type": holding.get("security_type", "Equity"),
                }
                
                # Calculate basic metrics
                purchase_value = stock_data["quantity"] * stock_data["purchase_price"]
                current_value = stock_data["quantity"] * stock_data["current_price"]
                stock_data["purchase_value"] = purchase_value
                stock_data["current_value"] = current_value
                
                profit_loss = current_value - purchase_value
                stock_data["profit_loss"] = profit_loss
                
                if purchase_value > 0:
                    profit_loss_percent = (profit_loss / purchase_value) * 100
                    stock_data["profit_loss_percent"] = round(profit_loss_percent, 2)
                else:
                    stock_data["profit_loss_percent"] = 0
                
                # Update totals
                total_investment += purchase_value
                total_current_value += current_value
                
                # If detailed analysis is requested, get financial metrics
                if include_details:
                    try:
                        # Get detailed financials for the stock
                        financials = await get_detailed_financials(symbol)
                        
                        if financials and "financial_metrics" in financials and financials["financial_metrics"]:
                            # Use only the most recent financial metrics
                            metrics = financials.get("financial_metrics", [])
                            if metrics:
                                # Drastically reduce the metrics to avoid large responses
                                latest_metrics = metrics[0] if metrics else {}
                                
                                # Include only essential metrics and truncate text fields
                                essential_metrics = {
                                    "quarter": latest_metrics.get("quarter", ""),
                                    "pe_ratio": latest_metrics.get("pe_ratio", ""),
                                    "piotroski_score": latest_metrics.get("piotroski_score", ""),
                                }
                                
                                # Only include short versions of textual analyses to reduce size
                                for field in ["strengths", "weaknesses", "fundamental_insights"]:
                                    if field in latest_metrics:
                                        value = latest_metrics[field]
                                        if isinstance(value, str):
                                            # Drastically truncate text to 50 chars max
                                            essential_metrics[field] = (value[:50] + "...") if len(value) > 50 else value
                                
                                stock_data["financials"] = essential_metrics
                            else:
                                stock_data["financials"] = {"note": "No recent financial metrics available"}
                        else:
                            stock_data["financials"] = {"note": "No financial data available"}
                    except Exception as e:
                        logger.error(f"Error fetching detailed financials for {symbol}: {e}")
                        stock_data["financials"] = {"error": "Failed to retrieve financial data"}
                
                # Add to results and estimate response size
                analysis_results.append(stock_data)
                current_entry_size = len(json.dumps(stock_data))
                response_size_estimate += current_entry_size
                
                logger.debug(f"Added {symbol} to results. Entry size: {current_entry_size} chars. Total estimate: {response_size_estimate}")
                
                # Emergency size check - if we're getting too large, stop adding details
                if response_size_estimate > max_response_size:
                    logger.warning(f"Response size estimate ({response_size_estimate}) exceeds limit ({max_response_size}). Truncating results.")
                    break
            
            # Calculate portfolio metrics
            portfolio_metrics = {
                "total_stocks_in_portfolio": len(holdings),
                "stocks_in_segment": len(analysis_results),
                "segment": segment,
                "segment_size": segment_size,
                "total_segments": (len(holdings) + segment_size - 1) // segment_size,
                "total_investment": round(total_investment, 2),
                "total_current_value": round(total_current_value, 2),
                "total_profit_loss": round(total_current_value - total_investment, 2),
            }
            
            if total_investment > 0:
                portfolio_metrics["total_profit_loss_percent"] = round(
                    ((total_current_value - total_investment) / total_investment) * 100, 2
                )
            else:
                portfolio_metrics["total_profit_loss_percent"] = 0
            
            # Create the final response payload
            response_data = {
                "portfolio_metrics": portfolio_metrics,
                "holdings": analysis_results,
            }
            
            # Final size check - if still too large, create a simplified response
            final_response_size = len(json.dumps(response_data))
            if final_response_size > max_response_size:
                logger.warning(f"Final response still too large ({final_response_size} chars). Creating simplified summary.")
                
                # Create a simplified holdings list with minimal information
                simplified_holdings = []
                for holding in analysis_results:
                    simplified_holdings.append({
                        "symbol": holding["symbol"],
                        "company_name": holding["company_name"],
                        "quantity": holding["quantity"],
                        "current_value": holding["current_value"],
                        "profit_loss_percent": holding["profit_loss_percent"],
                    })
                
                response_data = {
                    "portfolio_metrics": portfolio_metrics,
                    "holdings": simplified_holdings,
                    "note": "Response was simplified due to size constraints. Use segment_size=1 or request fewer stocks for detailed analysis."
                }
            
            # Convert to JSON and return response
            try:
                response_json = json.dumps(response_data)
                logger.info(f"Returning analysis for segment {segment} with {len(analysis_results)} stocks. Response size: {len(response_json)} chars")
                return [types.TextContent(text=response_json, type="text")]
            except Exception as e:
                logger.error(f"Error serializing portfolio analysis response: {e}")
                return [types.TextContent(
                    text=json.dumps({"error": f"Failed to create portfolio analysis: {str(e)}"}, indent=2),
                    type="text"
                )]
        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error analyzing portfolio: {str(e)}"}, indent=2),
                type="text"
            )]
            
        # Stock Recommendations
        elif name == "get_stock_recommendations":
        try:
            # Get parameters with sensible defaults
            criteria = arguments.get("criteria", "growth")
            limit = int(arguments.get("limit", 5))  # Default to 5 recommendations
            limit = min(max(1, limit), 8)  # Cap between 1-8 recommendations
            
            logger.info(f"Getting stock recommendations with criteria={criteria}, limit={limit}")
            
            # Get recommendations with limit applied
            recommendations = await get_stock_recommendations(criteria, limit=limit)
            
            # Compress and simplify the recommendations
            simplified_recommendations = []
            response_size_estimate = 0
            max_response_size = 10000
            
            for rec in recommendations:
                # Create simplified recommendation with essential fields only
                simple_rec = {
                    "symbol": rec.get("symbol", ""),
                    "company_name": rec.get("company_name", ""),
                    "exchange": rec.get("exchange", "NSE"),
                    "sector": rec.get("sector", ""),
                    "metrics": {
                        "pe_ratio": rec.get("pe_ratio", "N/A"),
                        "growth_rate": rec.get("growth_rate", "N/A"),
                        "piotroski_score": rec.get("piotroski_score", "N/A")
                    },
                    "recommendation_reason": rec.get("recommendation_reason", "")
                }
                
                # Truncate any long text fields
                if "recommendation_reason" in simple_rec and isinstance(simple_rec["recommendation_reason"], str):
                    text = simple_rec["recommendation_reason"]
                    if len(text) > 100:
                        simple_rec["recommendation_reason"] = text[:100] + "..."
                
                simplified_recommendations.append(simple_rec)
                
                # Track response size
                current_size = len(json.dumps(simple_rec))
                response_size_estimate += current_size
                
                # Stop if we hit size limit
                if response_size_estimate > max_response_size:
                    logger.warning(f"Response size exceeds limit ({max_response_size}). Truncating recommendations.")
                    break
            
            # Create final response
            response_data = {
                "criteria": criteria,
                "recommendations_count": len(simplified_recommendations),
                "recommendations": simplified_recommendations
            }
            
            # Convert to JSON and return
            response_json = json.dumps(response_data, default=handle_mongo_object)
            logger.info(f"Returning {len(simplified_recommendations)} stock recommendations. Response size: {len(response_json)} chars")
            
            return [types.TextContent(text=response_json, type="text")]
        except Exception as e:
            logger.error(f"Error getting stock recommendations: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error getting stock recommendations: {str(e)}"}, indent=2),
                type="text"
            )]
            
        # Portfolio Removal Recommendations
        elif name == "get_removal_recommendations":
        try:
            # Parse parameters with limits
            limit = int(arguments.get("limit", 5))  # Default to just 5 stocks
            max_limit = 10  # Cap at 10 stocks maximum
            limit = min(max(1, limit), max_limit)
            
            logger.info(f"Getting removal recommendations with limit={limit}")
            
            # Get all holdings for analysis, but limiting to what we need
            holdings = await get_portfolio_holdings(limit=30, summary=False)
            if not holdings:
                return [types.TextContent(
                    text=json.dumps({"error": "No portfolio holdings found"}, indent=2),
                    type="text"
                )]
            
            logger.info(f"Found {len(holdings)} holdings to analyze for removal")
            
            # Track response size
            response_size_estimate = 0
            max_response_size = 10000  # Smaller limit since this is a more complex analysis
            
            # Analyze each holding for potential removal
            removal_candidates = []
            for holding in holdings:
                symbol = holding.get("symbol", "")
                if not symbol:
                    continue
                
                logger.info(f"Analyzing {symbol} for potential removal...")
                
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
                        # Create a simplified candidate record with minimal data
                        candidate = {
                            "symbol": symbol,
                            "company_name": holding.get("company_name", ""),
                            "quantity": holding.get("quantity", 0),
                            "purchase_price": holding.get("purchase_price", 0),
                            "reasons": reasons,
                            "metrics": {
                                "pe_ratio": latest_metrics.get("ttm_pe", "N/A"),
                                "profit_growth": latest_metrics.get("net_profit_growth", "N/A"),
                                "piotroski_score": latest_metrics.get("piotroski_score", "N/A"),
                            }
                        }
                        
                        # Truncate any text fields to prevent large responses
                        if "weaknesses" in latest_metrics and latest_metrics["weaknesses"]:
                            weakness_text = str(latest_metrics["weaknesses"])
                            candidate["weaknesses"] = (weakness_text[:50] + "...") if len(weakness_text) > 50 else weakness_text
                        
                        # Add the compressed candidate to our results
                        removal_candidates.append(candidate)
                        
                        # Estimate response size
                        current_size = len(json.dumps(candidate))
                        response_size_estimate += current_size
                        logger.debug(f"Added {symbol} to removal candidates. Entry size: {current_size} chars. Total: {response_size_estimate}")
                        
                        # Update knowledge graph in background
                        await update_knowledge_graph(symbol, {
                            "portfolio.recommendation": "Consider Removing",
                            "portfolio.removal_reasons": reasons,
                            "analysis_date": datetime.now()
                        })
            
                        # Check if we've reached our limit or size threshold
                        if len(removal_candidates) >= limit or response_size_estimate > max_response_size:
                            logger.info(f"Reached limit ({len(removal_candidates)} stocks) or size threshold. Stopping analysis.")
                            break
            
            # If response is still too large, further simplify
            if response_size_estimate > max_response_size:
                logger.warning(f"Response size ({response_size_estimate}) exceeds limit. Creating simplified version.")
                simplified_candidates = []
                for candidate in removal_candidates:
                    simplified_candidates.append({
                        "symbol": candidate["symbol"],
                        "company_name": candidate["company_name"],
                        "reasons": candidate["reasons"],
                        "metrics": {
                            "profit_growth": candidate["metrics"]["profit_growth"],
                            "piotroski_score": candidate["metrics"]["piotroski_score"]
                        }
                    })
                removal_candidates = simplified_candidates
            
            # Create the final response
            response_data = {
                "removal_candidates": removal_candidates,
                "total_analyzed": len(holdings),
                "removal_candidates_count": len(removal_candidates)
            }
            
            # Convert to JSON and return
            response_json = json.dumps(response_data, default=handle_mongo_object)
            logger.info(f"Returning {len(removal_candidates)} removal recommendations. Response size: {len(response_json)} chars")
            
            return [types.TextContent(text=response_json, type="text")]
        except Exception as e:
            logger.error(f"Error getting removal recommendations: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error getting removal recommendations: {str(e)}"}, indent=2),
                type="text"
            )]
            
        # Market Trend Recommendations
        elif name == "get_market_trend_recommendations":
        try:
            # Get current portfolio symbols
            holdings = await get_portfolio_holdings(limit=30, summary=True)
            exclude_symbols = [h.get("symbol", "") for h in holdings]
            
            # Get parameters with sensible defaults
            limit = int(arguments.get("limit", 5))
            limit = min(max(1, limit), 8)  # Cap between 1-8 recommendations
            
            logger.info(f"Getting market trend recommendations with limit={limit}, excluding {len(exclude_symbols)} portfolio stocks")
            
            # Use our specialized India trending stocks function
            trending_stocks = await get_india_trending_stocks(limit=limit)
            
            # Track response size
            simplified_recommendations = []
            response_size_estimate = 0
            max_response_size = 10000
            
            # Process each stock
            for stock in trending_stocks:
                symbol = stock.get("symbol", "")
                if not symbol or symbol in exclude_symbols:
                    continue
                
                # Create simplified stock data
                simple_stock = {
                        "symbol": symbol,
                    "company_name": stock.get("company_name", ""),
                    "sector": stock.get("sector", ""),
                    "trend_strength": stock.get("trend_strength", "MEDIUM"),
                    "price_momentum": stock.get("price_momentum", "N/A"),
                }
                
                # Add truncated insights if available
                if "trend_insights" in stock and stock["trend_insights"]:
                    insights = str(stock["trend_insights"])
                    simple_stock["trend_insights"] = (insights[:100] + "...") if len(insights) > 100 else insights
                
                # Add to recommendations and update size estimate
                simplified_recommendations.append(simple_stock)
                
                # Store in knowledge graph (don't await to avoid slowing down response)
                await update_knowledge_graph(symbol, {
                    "market_trends.trending": True,
                    "market_trends.strength": stock.get("trend_strength", "MEDIUM"),
                    "market_trends.insights": stock.get("trend_insights", ""),
                    "analysis_date": datetime.now()
                })
                
                # Track response size
                current_size = len(json.dumps(simple_stock))
                response_size_estimate += current_size
                
                # Stop if we hit limit or size threshold
                if len(simplified_recommendations) >= limit or response_size_estimate > max_response_size:
                    break
            
            # Create final response
            response_data = {
                "trending_stocks_count": len(simplified_recommendations),
                "trending_stocks": simplified_recommendations,
                "excluded_portfolio_symbols": len(exclude_symbols)
            }
            
            # Convert to JSON and return
            response_json = json.dumps(response_data, default=handle_mongo_object)
            logger.info(f"Returning {len(simplified_recommendations)} trending stocks. Response size: {len(response_json)} chars")
            
            return [types.TextContent(text=response_json, type="text")]
        except Exception as e:
            logger.error(f"Error getting market trend recommendations: {e}")
            return [types.TextContent(
                text=json.dumps({"error": f"Error getting market trend recommendations: {str(e)}"}, indent=2),
                type="text"
            )]
            
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