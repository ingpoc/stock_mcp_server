"""
Stock Analysis MCP Server.
"""
import logging
from .config import LOG_LEVEL, LOG_FORMAT

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)

__version__ = "0.1.0" 