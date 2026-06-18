#!/usr/bin/env python3
"""
Korea Market Daily Pipeline
매일 16:05 자동 실행 → 수집 → 분석 → 리포트 생성

사용법:
  python run_daily.py              # 오늘 날짜로 실행
  python run_daily.py 2025-06-18  # 특정 날짜
  python run_daily.py --demo       # 데모 데이터로 테스트
"""

import sys
import os
import json
import random
import sqlite3
from datetime import datetime, date, timedelta

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from db import init_db, get_conn
from collector import collect_all, save_trading_volume, save_high_price, save_upper_limit
from analyzer import run_analysis
from reporter import generate_report

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reports")


# ── 데모 데이터 생성 ──────────────────────────────────────────────────────────

DEMO_SECTORS = [
    ("반도체", "KOSPI"), ("2차전지", "KOSPI"), ("바이오/제약", "KOSDAQ"),
    ("AI/소프트웨어", "KOSDAQ"), ("자동차", "KOSPI"), ("금융", "KOSPI"),
    ("방산/우주", "KOSPI"), ("조선/해운", "KOSPI"), ("철강/화학", "KOSPI"),
    ("소비재/유통", "KOSPI"), ("통신", "KOSPI"), ("에너지", "KOSPI"),
]

DEMO_STOCKS = {
    "반도체": [("005930", "삼성전자"), ("000660", "SK하이닉스"), ("042700", "한미반도체"),
                ("078020", "이오테크닉스"), ("240810", "원익IPS")],
    "2차전지": [("373220", "LG에너지솔루션"), ("006400", "삼성SDI"), ("247540", "에코프로비엠"),
                ("086520", "에코프로"), ("003670", "포스코퓨처엠")],
    "바이오/제약": [("207940", "삼성바이오로직스"), ("068270", "셀트리온"), ("128940", "한미약품"),
                   ("009420", "한올바이오파마"), ("196170", "알테오젠")],
    "AI/소프트웨어": [("035420", "NAVER"), ("035720", "카카오"), ("293490", "카카오게임즈"),
                    ("259960", "크래프톤")],
    "자동차": [("005380", "현대차"), ("000270", "기아"), ("012330", "현대모비스"),
               ("060980", "한온시스템")],
    "금융": [("105560", "KB금융"), ("055550", "신한지주"), ("086790", "하나금융지주"),
             ("316140", "우리금융지주")],
    "방산/우주": [("012450", "한화에어로스페이스"), ("079550", "LIG넥스원"),
                 ("047810", "한국항공우주"), ("064350", "현대로템")],
    "조선/해운": [("009540", "HD한국조선해양"), ("010140", "삼성중공업"),
                 ("042660", "한화오션"), ("011200", "HMM")],
    "철강/화학": [("005490", "POSCO홀딩스"), ("051910", "LG화학"), ("011170", "롯데케미칼")],
    "소비재/유통": [("002790", "아모레퍼시픽"), ("030000", "제일기획"), ("139480", "이마트")],
    "통신": [("017670", "SK텔레콤"), ("030200", "KT"), ("032640", "LG유플러스")],
    "에너지": [("015760", "한국전력"), ("034220", "LG디스플레이"), ("096770", "SK이노베이션")],
}


def generate_demo_data(target_date: str) -> dict:
    """현실적인 데모 데이터 생성 (실제 API 접근 불가 시)"""
    random.seed(int(target_date.replace("-", "")))

    # 오늘의 '주도 테마' 랜덤 선택
    hot_sectors = random.sample(list(DEMO_STOCKS.keys()), k=3)
    cold_sectors = random.sample([s for s in DEMO_STOCKS.keys() if s not in hot_sectors], k=2)

    volume_data = []
    rank = 1

    for sector, stocks in DEMO_STOCKS.items():
        market = DEMO_SECTORS[[s[0] for s in DEMO_SECTORS].index(sector)][1] if sector in [s[0] for s in DEMO_SECTORS] else "KOSPI"
        is_hot = sector in hot_sectors
        is_cold = sector in cold_sectors

        base_amount = random.uniform(2000, 8000) if is_hot else random.uniform(200, 2000)

        for ticker, name in stocks:
            change = random.gauss(3.5 if is_hot else -1.2 if is_cold else 0.5, 2.5)
            amount = base_amount * random.uniform(0.7, 1.4) / len(stocks)
            base_price = random.randint(10000, 80000)

            volume_data.append({
                "rank": rank,
                "ticker": ticker,
                "name": name,
                "market": market,
                "sector": sector,
                "close": base_price,
                "change_pct": round(change, 2),
                "volume": random.randint(500000, 10000000),
                "amount": round(amount, 1),
                "market_cap": round(base_price * random.randint(100000000, 5000000000) / 1e8, 1),
            })
            rank += 1

    # 거래대금 기준 정렬 + 순위 재부여
    volume_data.sort(key=lambda x: x["amount"], reverse=True)
    for i, v in enumerate(volume_data, 1):
        v["rank"] = i

    # 신고가 데이터 (주도 섹터 위주)
    high_data = []
    for sector in hot_sectors:
        stocks = DEMO_STOCKS.get(sector, [])
        for ticker, name in random.sample(stocks, k=min(2, len(stocks))):
            close = random.randint(15000, 150000)
            high_data.append({
                "ticker": ticker,
                "name": name,
                "market": "KOSPI",
                "sector": sector,
                "close": close,
                "change_pct": round(random.uniform(1.5, 8.0), 2),
                "high_52w": close,
            })

    # 상한가 데이터
    upper_data = []
    n_upper = random.randint(3, 15)
    all_stocks = [(t, n, s) for s, stocks in DEMO_STOCKS.items() for t, n in stocks]
    upper_candidates = random.sample(all_stocks, k=min(n_upper, len(all_stocks)))
    for ticker, name, sector in upper_candidates:
        upper_data.append({
            "ticker": ticker,
            "name": name,
            "market": "KOSDAQ" if random.random() > 0.4 else "KOSPI",
            "sector": sector,
            "close": random.randint(5000, 80000),
        })

    return {
        "volume": volume_data[:300],
        "high": high_data,
        "upper": upper_data,
    }


# ── 메인 파이프라인 ───────────────────────────────────────────────────────────

def run_pipeline(target_date: str = None, demo: bool = False) -> str:
    """
    전체 파이프라인 실행
    1. 데이터 수집 (or 데모)
    2. 분석
    3. HTML 리포트 생성
    Returns: 생성된 HTML 파일 경로
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    print(f"\n{'='*65}")
    print(f"  🇰🇷 Korea Market Daily Pipeline")
    print(f"  Date: {target_date}  |  Mode: {'DEMO' if demo else 'LIVE'}")
    print(f"{'='*65}\n")

    # DB 초기화
    init_db()
    conn = get_conn()

    # ── Step 1: 데이터 수집 ──────────────────────────────────────
    if demo:
        print("[Step 1] Generating demo data...")
        demo_data = generate_demo_data(target_date)
        save_trading_volume(conn, target_date, demo_data["volume"])
        save_high_price(conn, target_date, demo_data["high"])
        save_upper_limit(conn, target_date, demo_data["upper"])
        print(f"  Volume: {len(demo_data['volume'])}  High: {len(demo_data['high'])}  Upper: {len(demo_data['upper'])}")
    else:
        print("[Step 1] Collecting live data...")
        result = collect_all(target_date)
        print(f"  Volume: {result['volume_count']}  High: {result['high_count']}  Upper: {result['upper_count']}")

    conn.close()

    # ── Step 2: 분석 ─────────────────────────────────────────────
    print("\n[Step 2] Running sector analysis...")
    analysis = run_analysis(target_date)
    if not analysis:
        raise RuntimeError(f"Analysis failed for {target_date}")

    print(f"  Leading sectors: {[s['sector'] for s in analysis['leading_sectors'][:3]]}")
    print(f"  Rotation: {analysis['rotation']['signal']}")

    # ── Step 3: 리포트 생성 ──────────────────────────────────────
    print("\n[Step 3] Generating HTML report...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = generate_report(analysis, OUTPUT_DIR)

    print(f"\n{'='*65}")
    print(f"  ✅ Report ready: {filepath}")
    print(f"{'='*65}\n")

    return filepath


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    demo_mode = "--demo" in args
    args = [a for a in args if not a.startswith("--")]
    target = args[0] if args else None

    try:
        path = run_pipeline(target_date=target, demo=demo_mode)
        print(f"Output: {path}")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
