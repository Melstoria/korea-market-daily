#!/usr/bin/env python3
"""
Cron/Scheduler Setup
매일 16:05 자동 실행 설정

사용법:
  python setup_cron.py install    # cron 등록
  python setup_cron.py remove     # cron 제거
  python setup_cron.py status     # 현재 상태 확인
  python setup_cron.py run        # 즉시 실행 (테스트)
"""

import sys
import os
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.absolute()
PYTHON = sys.executable
RUNNER = PROJECT_DIR / "run_daily.py"
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "daily_run.log"

CRON_COMMENT = "# Korea Market Daily Report"
# 평일 16:05 (월-금)
CRON_SCHEDULE = "5 16 * * 1-5"
CRON_CMD = f'{PYTHON} {RUNNER} >> {LOG_FILE} 2>&1'
CRON_LINE = f"{CRON_SCHEDULE} {CRON_CMD} {CRON_COMMENT}"


def get_current_crontab() -> list[str]:
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.splitlines()
    except FileNotFoundError:
        pass
    return []


def install_cron():
    LOG_DIR.mkdir(exist_ok=True)
    lines = get_current_crontab()

    # 기존 항목 제거
    lines = [l for l in lines if CRON_COMMENT not in l]
    lines.append(CRON_LINE)

    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"✅ Cron installed: {CRON_LINE}")
        print(f"   Log: {LOG_FILE}")
    else:
        print(f"❌ Cron install failed: {proc.stderr}")
        print(f"\n수동 설치: crontab -e 에 아래 줄 추가:")
        print(f"  {CRON_LINE}")


def remove_cron():
    lines = get_current_crontab()
    filtered = [l for l in lines if CRON_COMMENT not in l]
    if len(filtered) == len(lines):
        print("ℹ️  Korea Market cron entry not found")
        return
    new_crontab = "\n".join(filtered) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print("✅ Cron entry removed")


def status():
    lines = get_current_crontab()
    found = [l for l in lines if CRON_COMMENT in l]
    if found:
        print(f"✅ Active cron: {found[0]}")
    else:
        print("❌ No cron entry found")

    # DB 상태
    db_path = PROJECT_DIR / "korea_market.db"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        try:
            c.execute("SELECT COUNT(DISTINCT date) FROM sector_daily")
            days = c.fetchone()[0]
            c.execute("SELECT MAX(date) FROM sector_daily")
            last = c.fetchone()[0]
            print(f"📊 DB: {days}거래일 누적, 최근: {last}")
        except:
            print("📊 DB: 초기화 전")
        conn.close()
    else:
        print("📊 DB: 없음 (최초 실행 전)")


def run_now():
    os.chdir(PROJECT_DIR)
    os.system(f"{PYTHON} {RUNNER} --demo")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {
        "install": install_cron,
        "remove": remove_cron,
        "status": status,
        "run": run_now,
    }.get(cmd, status)()
