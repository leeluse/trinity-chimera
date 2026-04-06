#!/usr/bin/env python3
"""Run LLM Arbiter API Server.

Usage:
    python run_arbiter_server.py [--port 8000] [--host localhost]
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ai_trading.arbiter.api import start_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run LLM Arbiter API Server')
    parser.add_argument(
        '--host',
        default='localhost',
        help='Server host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Server port (default: 8000)'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Run without LLM (for testing)'
    )

    args = parser.parse_args()

    # Check API key
    if not args.no_llm and not os.environ.get('ANTHROPIC_API_KEY'):
        logger.warning("ANTHROPIC_API_KEY not set. Running in test mode.")
        os.environ['ANTHROPIC_API_KEY'] = 'test-key'

    logger.info(f"Starting LLM Arbiter API Server on {args.host}:{args.port}")
    logger.info("Endpoints:")
    logger.info(f"  - REST API: http://{args.host}:{args.port}/api/v1/")
    logger.info(f"  - WebSocket: ws://{args.host}:{args.port}/ws")
    logger.info("")
    logger.info("Press Ctrl+C to stop")

    try:
        asyncio.run(start_server(host=args.host, port=args.port))
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
