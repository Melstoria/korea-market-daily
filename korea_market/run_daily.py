#!/usr/bin/env python3
"""
Korea Market Daily Pipeline
"""

import sys
import os
import json
import random
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, get_conn
from collector import collect_all, save_trading_volume, save_high_price, save_upper_limit
from analyzer import run_analysis
from reporter import generate_report

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.getcwd(), "docs", "reports"))

def run_pipeline(target_date=None, demo=False):
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n{'='*65}")
    print(f"  Korea Market Daily Pipeline")
    print(f"  Date: {target_date}  |  Mode: {'DEMO' if demo else 'LIVE'}")
    print(f"{'='*65}\n")

    init_db()

    print("[Step 1] Collecting live data...")
    result = collect_all(target_date)
    print(f"  Volume: {result['volume_count']}  High: {result['high_count']}  Upper: {result['upper_count']}")

    print("\n[Step 2] Running sector analysis...")
    analysis = run_analysis(target_date)
    if not analysis:
        raise RuntimeError(f"Analysis failed for {target_date}")

    print(f"  Leading sectors: {[s['sector'] for s in analysis['leading_sectors'][:3]]}")

    print("\n[Step 3] Generating HTML report...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = generate_report(analysis, OUTPUT_DIR)

    print(f"\n{'='*65}")
    print(f"  Report ready: {filepath}")
    print(f"{'='*65}\n")
    return filepath

if __name__ == "__main__":
    args = sys.argv[1:]
    target = args[0] if args else None
    path = run_pipeline(target_date=target)
    print(f"Output: {path}")