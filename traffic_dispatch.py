# -*- coding: utf-8 -*-
"""
traffic_dispatch.py — 플라워랜드 농원 트래픽 분배 알고리즘 (개발사양서 6장 구현)
================================================================================
기능
  1) 가중 랜덤 비복원 추출로 추천 노출 농원 1~3곳 선정
     가중치 w = 1.0 × min(√재고량, 2.0) × 노출보정계수(0.5~2.0) × 신선도페널티(0.5|1.0)
  2) 노출 이력 기록(exposure_log) → 일배치로 노출보정계수 재산출
  3) 형평성 KPI: 지니계수 G, 커버리지, 재고 신선도 산출
  4) 시뮬레이션 모드: 80개 농원 × N일 가상 운영으로 KPI 목표 검증
     (목표: G ≤ 0.35, 커버리지 ≥ 85%)

사용법
  python traffic_dispatch.py simulate --days 28 --daily-requests 300
  python traffic_dispatch.py select  --plant P013 -k 3
  python traffic_dispatch.py report
데이터는 SQLite(dispatch.db)에 저장. 실서비스에서는 PostgreSQL로 교체(SQL 동일 계열).
"""

import argparse
import math
import random
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

DB_PATH = "dispatch.db"

# ── 운영 파라미터 (사양서 6장) ────────────────────────────────────────────────
STOCK_CAP        = 2.0      # 재고계수 상한  min(sqrt(stock), 2.0)
EXPO_MIN         = 0.5      # 노출보정계수 하한
EXPO_MAX         = 2.0      # 노출보정계수 상한
STALE_HOURS      = 72       # 재고 신선도 기준(시간)
STALE_PENALTY    = 0.5      # 미갱신 농원 가중치 페널티
GINI_TARGET      = 0.35     # 지니계수 운영 목표
COVERAGE_TARGET  = 0.85     # 커버리지 운영 목표
WINDOW_DAYS      = 7        # KPI 산출 이동窓(일)

N_NURSERY = 80              # 불로화훼단지 농원 수
N_PLANT   = 60              # 식물 마스터 품종 수(시뮬레이션용)


# ── DB ───────────────────────────────────────────────────────────────────────
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS nursery(
        id TEXT PRIMARY KEY, name TEXT, size_factor REAL,
        expo_factor REAL DEFAULT 1.0);
    CREATE TABLE IF NOT EXISTS stock(
        nursery_id TEXT, plant_id TEXT, qty INTEGER, updated_at TEXT,
        PRIMARY KEY(nursery_id, plant_id));
    CREATE TABLE IF NOT EXISTS exposure_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nursery_id TEXT, plant_id TEXT, source TEXT, ts TEXT);
    CREATE INDEX IF NOT EXISTS ix_expo_ts ON exposure_log(ts);
    CREATE INDEX IF NOT EXISTS ix_expo_n  ON exposure_log(nursery_id);
    """)
    conn.commit()


# ── 시드 데이터 (시뮬레이션) ──────────────────────────────────────────────────
def seed(conn, rng):
    """80개 농원. 현실 반영: 대형 20% / 중형 50% / 소형 30%로 재고량 비대칭 생성."""
    conn.execute("DELETE FROM nursery")
    conn.execute("DELETE FROM stock")
    conn.execute("DELETE FROM exposure_log")
    now = datetime.now()

    for i in range(1, N_NURSERY + 1):
        r = rng.random()
        size = 3.0 if r < 0.2 else (1.5 if r < 0.7 else 0.7)   # 대/중/소
        conn.execute("INSERT INTO nursery VALUES(?,?,?,1.0)",
                     (f"N{i:03d}", f"농원{i:03d}", size))

    # 품종별 취급 농원: 평균 18곳(대형 농원일수록 취급 확률·재고량 ↑)
    nurseries = conn.execute("SELECT id, size_factor FROM nursery").fetchall()
    for pi in range(1, N_PLANT + 1):
        pid = f"P{pi:03d}"
        for nid, size in nurseries:
            if rng.random() < 0.15 + 0.06 * size:           # 취급 여부
                qty = max(1, int(rng.gauss(8 * size, 4)))
                # 30% 농원은 재고 갱신 게으름 → 신선도 페널티 대상
                upd = now - timedelta(hours=rng.choice([6, 24, 48, 96, 120]))
                conn.execute("INSERT INTO stock VALUES(?,?,?,?)",
                             (nid, pid, qty, upd.isoformat()))
    conn.commit()


# ── 핵심 1: 농원 선정 ─────────────────────────────────────────────────────────
def select_nurseries(conn, plant_id, k=3, source="fun01", ts=None, log=True):
    """추천 식물 취급 농원 중 가중 랜덤 비복원 추출로 k곳 선정."""
    ts = ts or datetime.now()
    rows = conn.execute("""
        SELECT s.nursery_id, s.qty, s.updated_at, n.expo_factor
        FROM stock s JOIN nursery n ON n.id = s.nursery_id
        WHERE s.plant_id = ? AND s.qty > 0""", (plant_id,)).fetchall()
    if not rows:
        return []

    ids, weights = [], []
    for nid, qty, upd, ef in rows:
        stale = (ts - datetime.fromisoformat(upd)) > timedelta(hours=STALE_HOURS)
        w = 1.0 * min(math.sqrt(qty), STOCK_CAP) * ef * (STALE_PENALTY if stale else 1.0)
        ids.append(nid)
        weights.append(w)

    w = np.asarray(weights, dtype=float)
    k = min(k, len(ids))
    # 비복원 가중 추출: Efraimidis-Spirakis (key = u^(1/w))
    u = np.random.random(len(ids))
    keys = u ** (1.0 / np.maximum(w, 1e-12))
    picked = [ids[i] for i in np.argsort(-keys)[:k]]

    if log:
        conn.executemany(
            "INSERT INTO exposure_log(nursery_id, plant_id, source, ts) VALUES(?,?,?,?)",
            [(nid, plant_id, source, ts.isoformat()) for nid in picked])
        conn.commit()
    return picked


# ── 핵심 2: 일배치 — 노출보정계수 재산출 ──────────────────────────────────────
def recalc_exposure_factors(conn, ts=None):
    """최근 7일 노출량 기준. 평균 대비 적게 노출된 농원 ↑, 많이 노출된 농원 ↓.
       factor = clip( (평균노출 / 개별노출)^0.5 , 0.5, 2.0 )  — 완만한 보정."""
    ts = ts or datetime.now()
    since = (ts - timedelta(days=WINDOW_DAYS)).isoformat()
    counts = dict(conn.execute(
        "SELECT nursery_id, COUNT(*) FROM exposure_log WHERE ts >= ? GROUP BY nursery_id",
        (since,)).fetchall())
    all_ids = [r[0] for r in conn.execute("SELECT id FROM nursery").fetchall()]
    vals = np.array([counts.get(i, 0) for i in all_ids], dtype=float)
    mean = vals.mean() if vals.sum() > 0 else 0.0

    for nid, c in zip(all_ids, vals):
        if mean <= 0:
            f = 1.0
        else:
            f = (mean / max(c, 0.5)) ** 0.5          # 미노출(0회)은 0.5로 간주 → 강한 부스트
            f = float(np.clip(f, EXPO_MIN, EXPO_MAX))
        conn.execute("UPDATE nursery SET expo_factor=? WHERE id=?", (f, nid))
    conn.commit()


# ── 핵심 3: KPI ──────────────────────────────────────────────────────────────
def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    cum = np.cumsum(x)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def kpi(conn, ts=None):
    ts = ts or datetime.now()
    since = (ts - timedelta(days=WINDOW_DAYS)).isoformat()
    counts = dict(conn.execute(
        "SELECT nursery_id, COUNT(*) FROM exposure_log WHERE ts >= ? GROUP BY nursery_id",
        (since,)).fetchall())
    all_ids = [r[0] for r in conn.execute("SELECT id FROM nursery").fetchall()]
    vals = [counts.get(i, 0) for i in all_ids]

    fresh = conn.execute("""
        SELECT AVG(CASE WHEN (julianday(?) - julianday(updated_at)) * 24 <= ?
                        THEN 1.0 ELSE 0.0 END) FROM stock""",
        (ts.isoformat(), STALE_HOURS)).fetchone()[0] or 0.0

    return {
        "gini":     gini(vals),
        "coverage": sum(1 for v in vals if v > 0) / len(all_ids),
        "fresh":    fresh,
        "total":    int(sum(vals)),
        "min_max":  (int(min(vals)), int(max(vals))),
    }


def print_kpi(m, label=""):
    ok_g = "OK" if m["gini"] <= GINI_TARGET else "미달"
    ok_c = "OK" if m["coverage"] >= COVERAGE_TARGET else "미달"
    print(f"[{label}] 지니계수 G={m['gini']:.3f} (목표≤{GINI_TARGET}, {ok_g}) | "
          f"커버리지={m['coverage']*100:.1f}% (목표≥{COVERAGE_TARGET*100:.0f}%, {ok_c}) | "
          f"재고신선도={m['fresh']*100:.1f}% | 주간노출 합={m['total']} "
          f"min/max={m['min_max'][0]}/{m['min_max'][1]}")


# ── 시뮬레이션 ────────────────────────────────────────────────────────────────
def simulate(days=28, daily_requests=300, seed_val=42):
    rng = random.Random(seed_val)
    np.random.seed(seed_val)
    conn = db()
    init_schema(conn)
    seed(conn, rng)

    # 인기 편중 반영: 상위 품종에 요청 몰림 (Zipf)
    plant_ids = [f"P{i:03d}" for i in range(1, N_PLANT + 1)]
    zipf_w = np.array([1.0 / (r + 1) for r in range(N_PLANT)])
    zipf_w /= zipf_w.sum()

    start = datetime.now() - timedelta(days=days)
    print(f"=== 시뮬레이션: 농원 {N_NURSERY}곳 × {days}일 × 일 {daily_requests}건 추천 ===\n")

    for d in range(days):
        day_ts = start + timedelta(days=d)
        for _ in range(daily_requests):
            pid = np.random.choice(plant_ids, p=zipf_w)
            t = day_ts + timedelta(seconds=random.randint(0, 86399))
            select_nurseries(conn, pid, k=3,
                             source=random.choice(["fun01", "fun02", "fun03", "fun07"]),
                             ts=t)
        recalc_exposure_factors(conn, ts=day_ts + timedelta(days=1))  # 매일 04시 배치 가정
        if (d + 1) % 7 == 0:
            print_kpi(kpi(conn, ts=day_ts + timedelta(days=1)), label=f"{d+1:2d}일차")

    print()
    m = kpi(conn, ts=start + timedelta(days=days))
    print_kpi(m, label="최종")
    verdict = ("합격" if m["gini"] <= GINI_TARGET and m["coverage"] >= COVERAGE_TARGET
               else "불합격 — 파라미터(EXPO_MAX, 보정지수) 조정 필요")
    print(f"\n검수 판정: {verdict}")

    # 상/하위 노출 농원 표
    since = (start + timedelta(days=days - WINDOW_DAYS)).isoformat()
    rows = conn.execute("""
        SELECT n.id, n.size_factor, n.expo_factor, COUNT(e.id) c
        FROM nursery n LEFT JOIN exposure_log e
             ON e.nursery_id = n.id AND e.ts >= ?
        GROUP BY n.id ORDER BY c DESC""", (since,)).fetchall()
    print("\n주간 노출 상위 5 / 하위 5 (규모, 보정계수, 노출수):")
    for nid, sz, ef, c in rows[:5]:
        print(f"  {nid}  규모x{sz:.1f}  보정 {ef:.2f}  노출 {c}")
    print("  ...")
    for nid, sz, ef, c in rows[-5:]:
        print(f"  {nid}  규모x{sz:.1f}  보정 {ef:.2f}  노출 {c}")
    conn.close()


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="플라워랜드 트래픽 분배 알고리즘")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("simulate", help="가상 운영 시뮬레이션 + KPI 검증")
    s1.add_argument("--days", type=int, default=28)
    s1.add_argument("--daily-requests", type=int, default=300)
    s1.add_argument("--seed", type=int, default=42)

    s2 = sub.add_parser("select", help="단건 선정 테스트")
    s2.add_argument("--plant", required=True)
    s2.add_argument("-k", type=int, default=3)

    sub.add_parser("report", help="현재 DB 기준 KPI 출력")

    a = ap.parse_args()
    if a.cmd == "simulate":
        simulate(a.days, a.daily_requests, a.seed)
    elif a.cmd == "select":
        conn = db(); init_schema(conn)
        picked = select_nurseries(conn, a.plant, k=a.k)
        print(f"{a.plant} 취급 노출 농원 → {picked if picked else '재고 보유 농원 없음'}")
        conn.close()
    elif a.cmd == "report":
        conn = db(); init_schema(conn)
        print_kpi(kpi(conn), label="현재")
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
