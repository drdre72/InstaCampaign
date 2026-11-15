#!/usr/bin/env python3
"""InstaCampaign pipeline entry point. See `python main.py --help`."""
import sys
from src.instacampaign.cli import main

if __name__ == "__main__":
    sys.exit(main())
