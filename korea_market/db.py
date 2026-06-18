"""
Korea Market DB - SQLite schema and helpers
누적 데이터 저장 (일간/월간/분기/반기 리포트 기반)
"""

import sqlite3
import os
from datetime import datetime
DB_PATH = os.environ.get("DB_PATH",
          os.path.join(os.path.dirname(__file__), "../data/korea_market.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── 거래대금 TOP300 ──────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS trading_volume (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,          -- YYYY-MM-DD
        rank        INTEGER NOT NULL,
        ticker      TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        market      TEXT,                      -- KOSPI/KOSDAQ
        sector      TEXT,
        close       REAL,
        change_pct  REAL,                      -- 등락률(%)
        volume      INTEGER,                   -- 거래량
        amount      REAL,                      -- 거래대금(억원)
        market_cap  REAL,                      -- 시가총액(억원)
        UNIQUE(date, ticker)
    )""")

    # ── 신고가 종목 ──────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS high_price (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        ticker      TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        market      TEXT,
        sector      TEXT,
        close       REAL,
        change_pct  REAL,
        high_52w    REAL,
        UNIQUE(date, ticker)
    )""")

    # ── 상한가 종목 ──────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS upper_limit (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        ticker      TEXT    NOT NULL,
        name        TEXT    NOT NULL,
        market      TEXT,
        sector      TEXT,
        close       REAL,
        UNIQUE(date, ticker)
    )""")

    # ── 일간 섹터 집계 ───────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS sector_daily (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT    NOT NULL,
        sector          TEXT    NOT NULL,
        total_amount    REAL    DEFAULT 0,    -- 섹터 총 거래대금(억)
        stock_count     INTEGER DEFAULT 0,    -- 편입 종목 수
        high_count      INTEGER DEFAULT 0,    -- 신고가 수
        upper_count     INTEGER DEFAULT 0,    -- 상한가 수
        avg_change_pct  REAL    DEFAULT 0,    -- 평균 등락률
        sector_score    REAL    DEFAULT 0,    -- 섹터 강도 점수
        UNIQUE(date, sector)
    )""")

    # ── 주도섹터 / 순환매 기록 ───────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS sector_leadership (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        date            TEXT    NOT NULL UNIQUE,
        top_sectors     TEXT,                 -- JSON: [{"sector":"반도체","score":87.3}, ...]
        rotation_signal TEXT,                 -- 순환매 신호 텍스트
        market_summary  TEXT                  -- 시장 총평
    )""")

    # ── 수집 로그 ────────────────────────────────────────────────
    c.execute("""
    CREATE TABLE IF NOT EXISTS collection_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        source      TEXT    NOT NULL,          -- ricco/naver_high/naver_upper
        status      TEXT    NOT NULL,          -- success/error
        count       INTEGER DEFAULT 0,
        message     TEXT,
        created_at  TEXT    DEFAULT (datetime('now','localtime'))
    )""")

    conn.commit()
    conn.close()
    print(f"[DB] Initialized: {DB_PATH}")


if __name__ == "__main__":
    init_db()
