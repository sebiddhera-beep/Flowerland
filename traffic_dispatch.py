"""
traffic_dispatch.py — 플라워랜드 농원 재고 DB + 트래픽 분산 모듈
────────────────────────────────────────────────────────────────
flowerland_demo.py 가 import 하여 사용한다. 인터페이스:
  - DB_PATH                : sqlite 파일 경로
  - init_schema(conn)      : 테이블 생성(nursery, stock, dispatch_log)
  - seed(conn, rng)        : 데모 농원 + 마스터 전체(v3=3002종) 재고를 랜덤 생성
  - select_nurseries(conn, plant_id, k, source)
                           : 특정 식물 재고 보유 농원 중 k곳을 가중랜덤 선택

재고는 실 재고가 아니라 데모용으로 재현 가능(seed 고정)하게 생성한다.
식물 마스터는 같은 폴더의 plants_master_v3.csv(없으면 v2·기본) PID 목록을 읽는다.
트래픽 분산은 Efraimidis-Spirakis 가중 무작위 추출(A-Res)로,
재고량과 최근 배정 빈도를 함께 반영해 방문객을 농원에 고르게 흩뿌린다.
"""
import os
import csv
import math
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch.db")

# 마스터 CSV 자동 선택: 최신본(v3=3002종) 우선 → v2 → 기본. 앱과 동일 규칙.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MASTER_CANDIDATES = ["plants_master_v3.csv", "plants_master_v2.csv", "plants_master.csv"]
_MASTER_CSV = next((os.path.join(_BASE_DIR, _n)
                    for _n in _MASTER_CANDIDATES
                    if os.path.exists(os.path.join(_BASE_DIR, _n))),
                   os.path.join(_BASE_DIR, "plants_master.csv"))

# 스키마 버전: 구조가 바뀌면 이 숫자를 올린다.
# 앱은 DB의 버전이 이 값과 다르면 DB를 통째로 재생성한다.
SCHEMA_VERSION = 5      # v5: dispatch_log 구조 검증 강화 + 옛 PK DB 강제 재생성


def db_is_valid(conn):
    """현재 DB가 최신 스키마인지 확인.
    테이블 존재 + user_version + dispatch_log의 컬럼/PK 구조까지 검증한다.
    (옛 버전은 dispatch_log의 PK 구성이 달라 ON CONFLICT 쿼리가 깨졌음)"""
    try:
        tabs = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if not {"nursery", "stock", "dispatch_log"} <= tabs:
            return False
        if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            return False
        # dispatch_log 구조: source 컬럼 + PK가 정확히 (plant_id, nursery_id, source)
        dl = conn.execute("PRAGMA table_info(dispatch_log)").fetchall()
        dl_cols = {r[1] for r in dl}
        dl_pk   = {r[1] for r in dl if r[5]}     # r[5]=pk 순번(0이면 PK 아님)
        if not {"plant_id", "nursery_id", "source", "cnt"} <= dl_cols:
            return False
        if dl_pk != {"plant_id", "nursery_id", "source"}:
            return False
        # stock 필수 컬럼
        stk = {r[1] for r in conn.execute("PRAGMA table_info(stock)").fetchall()}
        if not {"nursery_id", "plant_id", "qty"} <= stk:
            return False
        return True
    except Exception:
        return False

# ── 농원 생성 파라미터 ──────────────────────────────────────────
N_NURSERY = 40                      # 불로화훼단지 농원 수(데모)
ZONES = ["A동", "B동", "C동", "D동", "E동", "노지구역"]


# ── 반드시 재고를 넣을 PID(안전장치) ───────────────────────────
# CSV 로딩이 옛 버전이어도 아래 종은 항상 시드되도록 보장한다.
#   P657 금목서 · P3002 은목서
GUARANTEED_PIDS = ["P657", "P3002"]


def _load_plant_ids():
    """마스터 CSV 에서 PID 목록을 읽는다(v3 우선). 없으면 P001만.
    GUARANTEED_PIDS 는 누락 시 뒤에 덧붙여 항상 포함한다."""
    ids = []
    try:
        # utf-8-sig: 엑셀 저장(BOM) CSV도 안전하게 읽는다.
        with open(_MASTER_CSV, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pid = (r.get("pid") or "").strip()
                if pid:
                    ids.append(pid)
    except FileNotFoundError:
        pass
    if not ids:
        ids = ["P001"]
    # 보장 PID 보강(중복 없이)
    seen = set(ids)
    for pid in GUARANTEED_PIDS:
        if pid not in seen:
            ids.append(pid); seen.add(pid)
    return ids


# ── 스키마 ──────────────────────────────────────────────────────
def init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS nursery (
        id       TEXT PRIMARY KEY,
        name     TEXT NOT NULL,
        zone     TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS stock (
        nursery_id TEXT NOT NULL,
        plant_id   TEXT NOT NULL,
        qty        INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT '2026-01',
        PRIMARY KEY (nursery_id, plant_id)
    );
    CREATE TABLE IF NOT EXISTS dispatch_log (
        plant_id   TEXT NOT NULL,
        nursery_id TEXT NOT NULL,
        source     TEXT DEFAULT '',
        cnt        INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (plant_id, nursery_id, source)
    );
    CREATE INDEX IF NOT EXISTS idx_stock_plant ON stock(plant_id);
    """)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


# ── 시드(데모 재고 생성) ────────────────────────────────────────
def seed(conn, rng):
    """농원 N_NURSERY개 + 각 식물의 재고를 랜덤 생성. rng=random.Random(고정seed)."""
    plant_ids = _load_plant_ids()

    # 1) 농원
    nurseries = []
    for i in range(1, N_NURSERY + 1):
        nid = f"N{i:03d}"
        zone = ZONES[i % len(ZONES)]
        name = f"{zone[:-1] if zone.endswith('동') else zone} {i}번 농원"
        nurseries.append((nid, name, zone))
    conn.executemany("INSERT OR REPLACE INTO nursery(id,name,zone) VALUES (?,?,?)", nurseries)

    # 2) 재고: 각 식물을 취급하는 농원 수를 다양화(인기종은 많은 농원, 희귀종은 소수)
    rows = []
    nid_list = [n[0] for n in nurseries]
    for idx, pid in enumerate(plant_ids):
        # 취급 농원 수: 8~40곳 사이에서 랜덤(앞쪽 인기종일수록 많게 약한 경향)
        base = 40 - int(28 * (idx / max(len(plant_ids) - 1, 1)))
        n_hold = max(6, rng.randint(max(6, base - 8), base + 4))
        holders = rng.sample(nid_list, min(n_hold, len(nid_list)))
        for nid in holders:
            qty = rng.randint(3, 60)
            upd = rng.choice(["2026-01", "2026-02", "2025-11", "2025-12"])
            rows.append((nid, pid, qty, upd))
    conn.executemany(
        "INSERT OR REPLACE INTO stock(nursery_id,plant_id,qty,updated_at) VALUES (?,?,?,?)",
        rows)
    conn.commit()


# ── 트래픽 분산: 가중 무작위 추출(A-Res / Efraimidis-Spirakis) ──
def _weight(qty, dispatched):
    """재고 많을수록↑, 최근 많이 배정된 곳일수록↓. 로그 스케일로 완만하게."""
    inv = 1.0 / (1.0 + dispatched)          # 공정성: 배정 적은 곳 우대
    return math.log1p(max(qty, 0) + 1) * (0.4 + 0.6 * inv)


def select_nurseries(conn, plant_id, k=1, source=""):
    """plant_id 재고 보유 농원 중 k곳을 가중랜덤으로 선택하고 배정로그를 남긴다."""
    import random
    rng = random.Random()

    rows = conn.execute(
        "SELECT nursery_id, qty FROM stock WHERE plant_id=? AND qty>0", (plant_id,)
    ).fetchall()
    if not rows:
        return []

    # 현재까지의 배정 횟수 로드
    dmap = {}
    for nid, cnt in conn.execute(
        "SELECT nursery_id, cnt FROM dispatch_log WHERE plant_id=? AND source=?",
        (plant_id, source)
    ).fetchall():
        dmap[nid] = cnt

    # A-Res: key = u^(1/w), 상위 k개 선택
    scored = []
    for nid, qty in rows:
        w = _weight(qty, dmap.get(nid, 0))
        u = rng.random()
        key = u ** (1.0 / w) if w > 0 else 0.0
        scored.append((key, nid))
    scored.sort(reverse=True)
    chosen = [nid for _, nid in scored[:k]]

    # 배정 로그 갱신(공정성 반영용)
    for nid in chosen:
        conn.execute(
            "INSERT INTO dispatch_log(plant_id,nursery_id,source,cnt) VALUES (?,?,?,1) "
            "ON CONFLICT(plant_id,nursery_id,source) DO UPDATE SET cnt=cnt+1",
            (plant_id, nid, source))
    conn.commit()
    return chosen


# ── 단독 실행 시: DB 새로 만들기 ───────────────────────────────
if __name__ == "__main__":
    import random
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"기존 {DB_PATH} 삭제")
    conn = sqlite3.connect(DB_PATH)
    init_schema(conn)
    seed(conn, random.Random(42))
    n_nur = conn.execute("SELECT COUNT(*) FROM nursery").fetchone()[0]
    n_stk = conn.execute("SELECT COUNT(*) FROM stock").fetchone()[0]
    n_pl = conn.execute("SELECT COUNT(DISTINCT plant_id) FROM stock").fetchone()[0]
    print(f"생성 완료: 농원 {n_nur}개, 재고 레코드 {n_stk:,}건, 식물 {n_pl}종")
    conn.close()
