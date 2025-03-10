"""
Prompt handlers for MCP server.
"""
import json
import logging
from typing import Dict, List, Optional, Any
import mcp.types as types

from ..utils.database import (
    connect_to_mongodb, 
    handle_mongo_object,
    HOLDINGS_COLLECTION,
    DETAILED_FINANCIALS_COLLECTION,
    KNOWLEDGE_GRAPH_COLLECTION
)

# Setup logging
logger = logging.getLogger("stock_mcp_server.handlers.prompts")

async def handle_list_prompts() -> List[types.Prompt]:
    """
    List available prompts for stock analysis.
    
    Returns:
        List of available prompts
    """
    return [
        types.Prompt(
            name="portfolio-recommendation",
            description="Generate recommendations for your stock portfolio",
            arguments=[],
        ),
        types.Prompt(
            name="market-overview",
            description="Provide a market overview for a specific quarter",
            arguments=[
                types.PromptArgument(
                    name="quarter",
                    description="Financial quarter (e.g., 'Q2 FY24-25')",
                    required=False,
                )
            ],
        ),
    ]

async def handle_get_prompt(
    name: str, 
    arguments: Optional[Dict[str, str]] = None
) -> types.GetPromptResult:
    """
    Generate a prompt for stock analysis.
    
    Args:
        name: Prompt name
        arguments: Prompt arguments
        
    Returns:
        Prompt result
        
    Raises:
        ValueError: If the prompt name is not supported
    """
    db = await connect_to_mongodb()
    if not db:
        return types.GetPromptResult(
            description="Error connecting to database",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text="I tried to analyze my portfolio but encountered an error connecting to the database. Please help me troubleshoot this issue."
                    ),
                )
            ],
        )
    
    if name == "portfolio-recommendation":
        # Get holdings from MongoDB directly
        holdings = await db[HOLDINGS_COLLECTION].find({}).to_list(length=15)
        
        # Get knowledge graph data for context
        knowledge_graph = await db[KNOWLEDGE_GRAPH_COLLECTION].find({"portfolio.in_portfolio": True}).to_list(length=15)
        
        return types.GetPromptResult(
            description="Generate portfolio recommendations",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""Please analyze my portfolio and provide recommendations:

1. Here are my current holdings:
{json.dumps(holdings, default=handle_mongo_object, indent=2)}

2. Additional knowledge graph analysis:
{json.dumps(knowledge_graph, default=handle_mongo_object, indent=2)}

Based on this information, please:
- Analyze the performance of my portfolio as a whole
- Identify strengths and weaknesses in my portfolio allocation
- Recommend which stocks I should consider selling
- Suggest potential new stocks to add to diversify or improve returns
- Consider current market trends and future outlooks in your recommendation
""",
                    ),
                )
            ],
        )
    elif name == "market-overview":
        quarter = (arguments or {}).get("quarter", None)
        
        # Get quarters from MongoDB directly
        pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$group": {"_id": "$financial_metrics.quarter"}},
            {"$sort": {"_id": -1}},
            {"$limit": 5}
        ]
        quarters_data = await db[DETAILED_FINANCIALS_COLLECTION].aggregate(pipeline).to_list(length=5)
        quarters = [q["_id"] for q in quarters_data if q["_id"]]
        
        # Find the specified quarter or use the latest one
        target_quarter = quarter if quarter else (quarters[0] if quarters else None)
        
        # Get market data for the specified quarter
        pipeline = [
            {"$unwind": "$financial_metrics"},
            {"$match": {"financial_metrics.quarter": target_quarter}},
            {"$project": {
                "symbol": 1,
                "company_name": 1,
                "metrics": "$financial_metrics"
            }},
            {"$limit": 20}
        ]
        market_data = await db[DETAILED_FINANCIALS_COLLECTION].aggregate(pipeline).to_list(length=20)
        
        return types.GetPromptResult(
            description="Generate market overview",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"""Please provide a comprehensive market overview based on the following data:

1. Target Quarter: {target_quarter or "Latest"}

2. Available Quarters:
{json.dumps(quarters, indent=2)}

3. Market Data:
{json.dumps(market_data, default=handle_mongo_object, indent=2)}

Please include:
- Summary of overall market performance for {target_quarter or "the latest quarter"}
- Analysis of top performing sectors
- Notable stock movements
- Analysis of market trends
- Outlook for upcoming quarters
""",
                    ),
                )
            ],
        )
    else:
        raise ValueError(f"Unknown prompt: {name}") 