# -*- coding: utf-8 -*-
"""
flowerland_demo.py — 플라워랜드 시연 데모 v2 (목업 디자인 반영)
================================================================================
반영된 목업 화면
  · 홈: 2-Track AI 배너 / 4대 기능 / 인기 TOP5
  · 얼굴&MBTI: 촬영 → 얼굴 분석(메시 오버레이, 인상/분위기/매핑점수)
               → 공유 카드(사진+식물 일러스트+QR, PNG 다운로드) + 최우수 매칭 농원
  · 공간 플랜테리어 4단계: ①사진 등록 ②정밀 분석(2×2 카드, 생육난이도, 추천 식물)
               ③가상 배치 체험(식물 합성, 위치·크기 조정) ④최적 식물&농원(97% 매칭)
  · 건강 진단 / 농원 지도 / 분갈이 특화 / QR 스탬프

실행:
    pip install streamlit numpy pillow qrcode
    python -m streamlit run flowerland_demo.py
같은 폴더에 traffic_dispatch.py 필요. (dispatch.db 자동 생성)
"""

import base64
import hashlib
import io
import os
import tempfile
import random
import sqlite3
import urllib.parse
from datetime import datetime, date, timedelta

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

import traffic_dispatch as td

try:
    import gemini_api as gm
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False

# ── 페이지/스타일 ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Flower Land (플라워랜드)", page_icon="🌱",
                   layout="wide", initial_sidebar_state="collapsed")

# ── PC/모바일 콘텐츠 최대 폭 (여기 숫자만 바꾸면 전체 폭 조절됨) ──
PC_MAX_WIDTH = "960px"   # PC에서 콘텐츠가 중앙에 이 폭으로 정렬됨(넓게: 1100px, 좁게: 820px)
GREEN = "#2E7D32"
st.markdown(f"""
<style>
/* Streamlit 기본 실행표시(우상단 올림픽·자전거 아이콘) 숨김 */
[data-testid="stStatusWidget"] {{ display:none !important; }}
/* 사진 화면 중앙 원형 회전 스피너 (시계처럼 빙글빙글) */
.fl-spin-wrap {{ display:flex; flex-direction:column; align-items:center;
                 justify-content:center; padding:40px 0; }}
.fl-spinner {{ width:64px; height:64px; border-radius:50%;
               border:6px solid #e0eee0; border-top-color:{GREEN};
               animation:fl-rotate 0.9s linear infinite; }}
.fl-spin-txt {{ margin-top:14px; color:{GREEN}; font-weight:700; font-size:15px; }}
@keyframes fl-rotate {{ to {{ transform:rotate(360deg); }} }}
.block-container {{ max-width: {PC_MAX_WIDTH}; margin: 0 auto; padding-top: 2.4rem; }}
h1,h2,h3 {{ color:{GREEN}; }}
.step {{ color:{GREEN}; font-weight:800; font-size:15px; letter-spacing:.3px; }}
.big  {{ font-size:24px; font-weight:800; line-height:1.35; }}
.banner {{ border-radius:16px; padding:16px; min-height:185px; }}
.banner-fun  {{ background:linear-gradient(135deg,#fff3b0,#a7e9af,#a0d8f1); }}
.banner-util {{ background:linear-gradient(135deg,#efe6d8,#f5f0e6); }}
.chip {{ display:inline-block; background:{GREEN}; color:#fff; border-radius:12px;
        padding:2px 10px; font-size:12px; margin-bottom:6px; }}
.icon-card {{ text-align:center; background:#fff; border:1px solid #e6e6e6;
             border-radius:14px; padding:10px 4px; }}
.icon-card .e {{ font-size:30px; }} .icon-card .t {{ font-size:13px; font-weight:700; }}
.icon-card .s {{ font-size:11px; color:#777; }}
.acard {{ background:#fff; border:1.5px solid #dcecdc; border-radius:14px;
         padding:12px; min-height:118px; }}
.acard .e {{ font-size:26px; }} .acard .t {{ font-weight:800; font-size:15px; }}
.acard .s {{ font-size:12.5px; color:#555; }}
.top5 {{ background:#f7fbf7; border:1px solid #dcecdc; border-radius:12px;
        padding:8px; text-align:center; }}
.result {{ background:#f0f7f0; border-left:5px solid {GREEN}; border-radius:8px;
          padding:14px; margin-top:10px; color:#1b1b1b !important; }}
.result b {{ color:#1b3a1b !important; }}
/* ── 밝은 배경 카드 공통: 다크 테마에서 흰 글자 상속 방지 ── */
.icon-card, .acard, .top5, .nursery, .stampbn, .best {{ color:#1b1b1b !important; }}
.icon-card *, .acard *, .top5 *, .nursery *, .stampbn *, .best * {{ color:inherit; }}
.icon-card .s, .acard .s {{ color:#555 !important; }}
.best {{ background:#fffdf3; border:2px solid #e8c34a; border-radius:14px; padding:12px; }}
.best .tag {{ background:#e8c34a; color:#5b4300; font-weight:800; font-size:12px;
             border-radius:8px; padding:2px 8px; }}
.nursery {{ background:#fff; border:1px solid #cfe3cf; border-radius:10px;
           padding:8px 12px; margin-top:6px; font-size:14px; }}
.stampbn {{ background:#e9f6e9; border-radius:12px; padding:10px 14px; font-weight:700; }}

/* ── 헤더 알림 버튼: 컬럼을 채우는 흰색 둥근 박스 (스크린샷과 동일) ── */
[data-testid="stPopover"] button {{
    background:#ffffff !important; border:1px solid #e3e3e3 !important;
    border-radius:16px !important; min-height:43px !important;
    font-weight:700 !important; color:#2E5D32 !important;
    box-shadow:0 1px 3px rgba(0,0,0,.04) !important;
}}
[data-testid="stPopover"] button:hover {{
    border-color:{GREEN} !important;
    box-shadow:0 3px 10px rgba(46,125,50,.20) !important; transition:all .15s;
}}

/* ── '홈으로' 버튼 전용: 파란색 강조 + 크게 (key='home_*'만 타겟) ── */
[class*="st-key-home_"] button {{
    background: #1565C0 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    font-size: 17px !important;
    font-weight: 800 !important;
    padding: 0.7rem 1.4rem !important;
    box-shadow: 0 3px 10px rgba(21,101,192,.35) !important;
}}
[class*="st-key-home_"] button:hover {{
    background: #0D47A1 !important;
    transform: translateY(-1px);
    transition: all .15s;
}}

/* ── TOP5 일러스트 카드 이름표 ── */
.top5-name {{
    text-align: center; font-size: 12.5px; font-weight: 700;
    color: #2E5D32; margin-top: -6px; line-height: 1.3;
}}

/* ── TOP5 카드 버튼 (key='top_*') ── */
[class*="st-key-top_"] button {{
    background: #f7fbf7 !important;
    border: 1px solid #dcecdc !important;
    border-radius: 12px !important;
    min-height: 118px !important;
    padding: 10px 6px !important;
    color: #222 !important;
    white-space: pre-line !important;   /* \\n 줄바꿈 표시 */
    line-height: 1.35 !important;
    font-size: 12px !important;
}}
[class*="st-key-top_"] button p {{ white-space: pre-line !important; }}
[class*="st-key-top_"] button:hover {{
    border-color: #2E7D32 !important;
    box-shadow: 0 3px 10px rgba(46,125,50,.25) !important;
    transform: translateY(-2px);
    transition: all .15s;
}}

/* ── 반응형 컬럼 ──────────────────────────────────────────────
   PC(기본)에서는 컬럼이 넓은 화면에 정상 비율로 배치되고,
   모바일(≤640px)에서만 배너 2열·아이콘 4열·TOP5 5열을
   목업처럼 가로로 강제한다(아래 @media 블록 참조). */
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 0 !important;
    flex: 1 1 0 !important;
}}
@media (max-width: 640px) {{
    .block-container {{ padding-left: .7rem; padding-right: .7rem; padding-top: .6rem; }}
    /* 좁은 화면: 컬럼을 세로로 쌓지 말고 목업처럼 가로 유지(넘치면 스와이프) */
    [data-testid="stHorizontalBlock"] {{
        flex-wrap: nowrap !important;
        gap: 8px !important;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }}
    .big  {{ font-size: 20px; }}
    .step {{ font-size: 13px; }}
    .banner {{ min-height: 150px; padding: 12px; }}
    .icon-card .e {{ font-size: 24px; }}
    .icon-card .t {{ font-size: 11px; }}
    .icon-card .s {{ font-size: 9.5px; }}
    .top5 {{ min-width: 108px; }}      /* 카드 최소폭 확보 → 넘치면 스와이프 */
    .top5 b {{ font-size: 12px; }}
    .acard {{ min-height: 96px; padding: 9px; }}
    .acard .t {{ font-size: 13px; }}
    .acard .s {{ font-size: 11px; }}
    .nursery {{ font-size: 12.5px; }}
    .stButton button {{ padding: .45rem .5rem; font-size: 14px; }}
    h3 {{ font-size: 1.05rem !important; }}
    h4 {{ font-size: .95rem !important; }}
}}
</style>""", unsafe_allow_html=True)

USER_NAME = "정종섭"

# ── Gemini API 키 (사이드바 입력 또는 환경변수 GEMINI_API_KEY) ────────────────
with st.sidebar:
    st.markdown("### ⚙️ AI 엔진 설정")
    _default_key = gm.get_env_key() if HAS_GEMINI else ""
    if not _default_key:  # Streamlit Cloud 배포 시 Secrets에서 자동 로드
        try:
            _default_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            pass
    api_key = st.text_input("Gemini API 키", value=_default_key, type="password",
                            help="aistudio.google.com 에서 무료 발급 → 붙여넣기")
    if api_key:
        st.success("🤖 Gemini 실 AI 분석 모드")
        if st.button("🔌 연결 테스트", use_container_width=True):
            try:
                with st.spinner("Gemini 호출 중..."):
                    r = gm.ask_json(api_key, '{"ok": true} 를 그대로 반환하시오.')
                st.success(f"연결 정상 ✓ (응답: {r})")
                # 연결이 정상이면 이전 실패로 꺼둔 식물검색 AI를 다시 켠다
                st.session_state.plant_ai_off = False
                for _k in ("plant_ai_notified", "plant_ai_cache", "plant_ai_err"):
                    st.session_state.pop(_k, None)
            except Exception as e:
                st.error(f"연결 실패: {type(e).__name__}\n\n{str(e)[:300]}")
                st.caption("키는 aistudio.google.com 발급분(AIza로 시작)이어야 하며, "
                           "Secrets 형식은 GEMINI_API_KEY = \"AIza...\" 입니다.")
    else:
        st.info("키가 없으면 규칙 기반 목업 모드로 동작합니다.")
        st.caption("배포(Streamlit Cloud)에서는 Manage app → Settings → Secrets에\n"
                   'GEMINI_API_KEY = "AIza..." 형식으로 저장하세요.')
    if not any(os.path.exists(p) for p in
               ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                r"C:\Windows\Fonts\malgun.ttf")):
        st.warning("⚠️ 한글 폰트 미설치 — 결과 카드 글씨가 깨집니다. "
                   "저장소에 packages.txt(내용: fonts-nanum)를 올려주세요.")
    st.caption("모델: gemini-2.5-flash (분석)\n/ gemini-2.5-flash-image (합성)")

def gemini_on():
    return HAS_GEMINI and bool(api_key)

NAME_TO_PID = {}  # PLANT_NAMES 정의 후 아래에서 채움

# ── 데이터 ───────────────────────────────────────────────────────────────────
# 식물 마스터(최대 3,002종): plants_master_v3.csv 등을 자동 선택해 로드.
# dispatch.db 는 이 PID 체계로 traffic_dispatch.seed() 가 재고를 생성한다.
import csv as _csv

_MASTER = []                 # [{pid,korean,english_common,scientific,category}, ...]
# 마스터 CSV 자동 선택: 최신본(v3=3002종)이 있으면 우선, 없으면 v2 → 기본순.
#   파일명만 맞으면 검색·이미지·추천이 자동으로 전체 종에 적용된다.
#   (이미지는 assets/plants/{PID}.png 를 PID 그대로 찾으므로 4자리 신규 PID도 정상)
_BASE = os.path.dirname(os.path.abspath(__file__))
_MASTER_CANDIDATES = [
    "plants_master_v3.csv",        # 3,002종 (최신)
    "plants_master_v2.csv",        # 2,001종
    "plants_master.csv",           # 1,001종 (기존)
]
_MASTER_CSV = next((os.path.join(_BASE, _n)
                    for _n in _MASTER_CANDIDATES
                    if os.path.exists(os.path.join(_BASE, _n))), None)
if _MASTER_CSV:
    # utf-8-sig 로 열어 엑셀 저장(BOM) 파일도 안전하게 읽는다.
    with open(_MASTER_CSV, encoding="utf-8-sig") as _f:
        for _r in _csv.DictReader(_f):
            # 열 이름 앞뒤 공백/누락 방어
            _row = {(_k or "").strip(): (_v or "").strip() for _k, _v in _r.items()}
            if _row.get("pid"):
                _MASTER.append(_row)
if not _MASTER:
    # CSV가 없거나 비었을 때의 최소 폴백(앱이 죽지 않게)
    _MASTER = [{"pid": "P001", "korean": "몬스테라", "english_common": "Monstera",
                "scientific": "Monstera deliciosa", "category": "관엽 Foliage"}]

PLANT_NAMES = {r["pid"]: r["korean"]         for r in _MASTER}
PLANT_EN    = {r["pid"]: r["english_common"] for r in _MASTER}
PLANT_SCI   = {r["pid"]: r["scientific"]     for r in _MASTER}
PLANT_CAT   = {r["pid"]: r["category"]       for r in _MASTER}
NAME_TO_PID.update({n: p for p, n in PLANT_NAMES.items()})

def pid_of(name, fallback):
    """Gemini가 반환한 식물 이름 → PID (부분 일치 허용, 실패 시 fallback)"""
    if name in NAME_TO_PID:
        return NAME_TO_PID[name]
    for n, p in NAME_TO_PID.items():
        if name and (name in n or n in name):
            return p
    return fallback
PLANT_DESC = {
    "P416": "사계절 노지 월동이 가능하며, 여름철 화려한 군락을 형성하는 야외 특화 식물",
    "P004": "시원하게 뻗는 큰 잎으로 거실의 무드를 살리는 대형 관엽 식물",
    "P001": "구멍 뚫린 잎이 매력적인 국민 관엽. 밝은 간접광에서 잘 자람",
}
IMPRESSIONS = ["대범함 (Bold)", "세련됨 (Sophisticated)", "온화함 (Gentle)",
               "명랑함 (Cheerful)", "차분함 (Calm)", "당당함 (Confident)"]
VIBES = ["따뜻함 (Warm)", "산뜻함 (Fresh)", "포근함 (Cozy)", "싱그러움 (Vivid)"]
FACE_PLANTS = ["P004", "P001", "P010", "P227", "P011", "P416", "P003", "P006"]
FACE_COPY = {"P004": "대범하고 따뜻한 시선", "P001": "세련되고 따뜻한 조화",
             "P010": "클래식하고 차분한 품격", "P227": "다정하고 싱그러운 배려",
             "P011": "자유롭고 산뜻한 감성", "P416": "화려하고 당당한 존재감",
             "P003": "섬세하고 포근한 감수성", "P006": "실속 있고 온화한 든든함"}

# ── 성별 맞춤 인사말 ──────────────────────────────────────────────
# 얼굴 분석 결과의 성별에 따라 공유 카드 상단 인사말을 바꾼다.
GREETING_FEMALE = "아름다운 고객님"
GREETING_MALE   = "개성미 넘치는 고객님"
def greeting_for_gender(gender):
    """성별 문자열('female'/'male'/'여'/'남' 등) → 인사말. 불명확하면 기본값."""
    g = str(gender or "").strip().lower()
    if g.startswith("f") or "여" in g:
        return GREETING_FEMALE
    if g.startswith("m") or "남" in g:
        return GREETING_MALE
    return f"{USER_NAME} 님"          # 성별 불명 → 기존 기본 인사말
INDOOR_RECS  = {"거실": ["P001", "P004", "P227", "P002", "P006"],
                "침실": ["P008", "P002", "P005", "P001", "P227"],
                "사무실": ["P006", "P002", "P008", "P001", "P005"]}
OUTDOOR_RECS = {"베란다": ["P010", "P365", "P241", "P011", "P591"],
                "정원": ["P416", "P591", "P752", "P010", "P241"],
                "테라스": ["P416", "P011", "P752", "P365", "P591"]}
DIAG_CLASSES = [
    ("과습", "물주기를 절반으로 줄이고 배수 구멍 확인. 겉흙 3cm 마른 뒤 관수"),
    ("건조", "즉시 저면관수 30분. 이후 주 1~2회 규칙 관수로 전환"),
    ("광부족", "밝은 간접광 자리로 이동. 남향 창 1m 이내 권장"),
    ("응애", "잎 뒷면 물샤워 후 살비제 7일 간격 2회. 통풍 확보"),
    ("잎마름병", "감염 잎 제거·폐기, 살균제 살포. 잎에 물 닿지 않게 관수"),
    ("분갈이 필요", "뿌리가 화분을 꽉 채운 상태. 한 치수 큰 분으로 분갈이 + 새 배양토"),
]

# ── DB / 농원 ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    # 기존 DB가 있으면 스키마 버전 검사 → 옛 버전이면 삭제 후 재생성
    if os.path.exists(td.DB_PATH):
        try:
            _c = sqlite3.connect(td.DB_PATH)
            valid = td.db_is_valid(_c)
            _c.close()
        except Exception:
            valid = False
        if not valid:
            os.remove(td.DB_PATH)       # 옛 스키마 → 폐기하고 새로 생성
    fresh = not os.path.exists(td.DB_PATH)
    conn = sqlite3.connect(td.DB_PATH, check_same_thread=False)
    td.init_schema(conn)
    if fresh or conn.execute("SELECT COUNT(*) FROM nursery").fetchone()[0] == 0:
        td.seed(conn, random.Random(42))
    _ensure_admin_columns(conn)
    return conn

def _ensure_admin_columns(conn):
    """관리자 모드용 컬럼을 없으면 추가(마이그레이션). 기존 데이터 보존."""
    ncols = [r[1] for r in conn.execute("PRAGMA table_info(nursery)").fetchall()]
    if "pin" not in ncols:
        conn.execute("ALTER TABLE nursery ADD COLUMN pin TEXT")
        # 농원별 4자리 PIN 자동 발급(번호 기반, 시연용). 실서비스는 개별 재설정.
        for (nid,) in conn.execute("SELECT id FROM nursery").fetchall():
            pin = f"{(int(nid[1:]) * 7 + 1000) % 9000 + 1000:04d}"
            conn.execute("UPDATE nursery SET pin=? WHERE id=?", (pin, nid))
    if "tagline" not in ncols:
        conn.execute("ALTER TABLE nursery ADD COLUMN tagline TEXT DEFAULT ''")
    if "specialty" not in ncols:
        conn.execute("ALTER TABLE nursery ADD COLUMN specialty TEXT DEFAULT ''")
    if "address" not in ncols:
        conn.execute("ALTER TABLE nursery ADD COLUMN address TEXT DEFAULT ''")
    if "phone" not in ncols:
        conn.execute("ALTER TABLE nursery ADD COLUMN phone TEXT DEFAULT ''")
    scols = [r[1] for r in conn.execute("PRAGMA table_info(stock)").fetchall()]
    if "price_min" not in scols:
        conn.execute("ALTER TABLE stock ADD COLUMN price_min INTEGER DEFAULT 0")
    if "price_max" not in scols:
        conn.execute("ALTER TABLE stock ADD COLUMN price_max INTEGER DEFAULT 0")
    conn.commit()

conn = get_conn()

def _rebuild_db():
    """스키마 불일치(OperationalError)로 쿼리가 깨질 때 호출.
    배포된 dispatch.db를 폐기하고 현재 traffic_dispatch.py 스키마로 새로 생성한다.
    (레포에 커밋된 옛 스키마 DB가 배포되는 경우 등을 자가복구)"""
    global conn
    try:
        conn.close()
    except Exception:
        pass
    try:
        if os.path.exists(td.DB_PATH):
            os.remove(td.DB_PATH)
    except Exception:
        pass
    try:
        get_conn.clear()          # @st.cache_resource 캐시 비우기 → 다음 호출 시 재생성
    except Exception:
        pass
    conn = get_conn()
    return conn

def zone_of(nid):
    n = int(nid[1:])
    return f"{'ABCD'[n % 4]}-{n % 20 + 1:02d} 구역"

def best_nursery(pid, source):
    """실제 트래픽 분배 알고리즘으로 최우수 매칭 농원 1곳 선정"""
    try:
        ids = td.select_nurseries(conn, pid, k=1, source=source)
    except sqlite3.OperationalError:
        # dispatch.db 스키마가 traffic_dispatch.py와 어긋남 → DB 재생성 후 1회 재시도
        _rebuild_db()
        try:
            ids = td.select_nurseries(conn, pid, k=1, source=source)
        except sqlite3.OperationalError:
            return None       # 재생성 후에도 실패하면 traffic_dispatch.py 자체 수정 필요
    if not ids:
        return None
    nid = ids[0]
    try:
        row = conn.execute("SELECT name, COALESCE(address,''), COALESCE(phone,'') "
                           "FROM nursery WHERE id=?", (nid,)).fetchone()
    except sqlite3.OperationalError:      # 컬럼 없음 → 마이그레이션 후 재시도
        _ensure_admin_columns(conn)
        row = conn.execute("SELECT name, COALESCE(address,''), COALESCE(phone,'') "
                           "FROM nursery WHERE id=?", (nid,)).fetchone()
    name, address, phone = row
    qty = conn.execute("SELECT qty FROM stock WHERE nursery_id=? AND plant_id=?",
                       (nid, pid)).fetchone()
    return {"id": nid, "name": name, "address": address, "phone": phone,
            "zone": zone_of(nid), "qty": qty[0] if qty else 0,
            "recs": 2800 + int(hashlib.md5(nid.encode()).hexdigest(), 16) % 900}

def _next_nursery_id():
    """기존 최대 번호 다음의 농원ID(N### 형식)를 반환."""
    ids = [r[0] for r in conn.execute("SELECT id FROM nursery").fetchall()]
    nums = [int(i[1:]) for i in ids if len(i) > 1 and i[1:].isdigit()]
    return f"N{(max(nums) + 1) if nums else 1:03d}"

def _csv_int(v, default=0):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default

def parse_nurseries_csv(file_bytes):
    """CSV를 파싱만 한다(DB 반영 없음). 미리보기·검증용.
    반환: {'nurseries': {...}, 'stocks': {...}, 'warnings': [...],
           'headers': [...], 'encoding': str, 'delimiter': str}"""
    import io as _io, csv as _csv
    # 인코딩 자동 감지: 엑셀(UTF-8 BOM) / 한글 윈도우(CP949·EUC-KR) 모두 지원
    text, used_enc = None, "?"
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            text = file_bytes.decode(enc)
            used_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        text = file_bytes.decode("utf-8", errors="replace"); used_enc = "utf-8(강제)"
    # 엑셀이 넣는 'sep=,' 첫 줄 제거
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("sep="):
        lines = lines[1:]; text = "\n".join(lines)
    first = next((ln for ln in lines if ln.strip()), "")
    delim = max([",", ";", "\t"], key=first.count) if first else ","
    reader = _csv.DictReader(_io.StringIO(text), delimiter=delim)

    def g(row, *names):
        for k, val in row.items():
            if k and k.strip().lstrip("\ufeff") in names:
                return (val or "").strip()
        return ""

    nurseries, stocks, warns = {}, {}, []
    for i, row in enumerate(reader, start=2):
        name = g(row, "농원명", "name")
        nid = g(row, "농원ID", "id", "nursery_id")
        if not name and not nid:
            continue
        if not nid:
            nid = f"U{len(nurseries) + 1:03d}"
        nurseries[nid] = (name or nid, g(row, "구역", "zone") or "A동",
                          g(row, "PIN", "pin"), g(row, "소개문구", "tagline"),
                          g(row, "전문분야", "specialty"), g(row, "주소", "address"),
                          g(row, "대표전화", "전화번호", "phone"))
        pname = g(row, "취급식물명", "식물명", "plant_name")
        ppid = g(row, "취급식물ID", "식물ID", "plant_id")
        if pname or ppid:
            pid = ppid if ppid in PLANT_NAMES else NAME_TO_PID.get(pname)
            if not pid:
                warns.append(f"{i}행: 식물 '{pname or ppid}'을(를) 카탈로그에서 못 찾아 건너뜀")
            else:
                stocks[(nid, pid)] = (_csv_int(g(row, "재고수량", "qty")),
                                      _csv_int(g(row, "최저가", "price_min")),
                                      _csv_int(g(row, "최고가", "price_max")))
    return {"nurseries": nurseries, "stocks": stocks, "warnings": warns,
            "headers": [h.lstrip("\ufeff") for h in (reader.fieldnames or [])],
            "encoding": used_enc, "delimiter": {",": "쉼표", ";": "세미콜론", "\t": "탭"}[delim]}

def import_nurseries_csv(file_bytes, replace=False, parsed=None):
    """CSV(농원+취급식물)를 nursery/stock 테이블에 반영.
    parsed가 주어지면(미리보기 재사용) 파싱을 건너뛴다.
    반환: {'nurseries': n, 'stocks': m, 'warnings': [...]}"""
    p = parsed or parse_nurseries_csv(file_bytes)
    nurseries, stocks, warns = p["nurseries"], p["stocks"], list(p["warnings"])

    if not nurseries:
        warns.append(f"등록된 농원이 없습니다. 인식된 헤더: [{', '.join(p['headers'])}]. "
                     "'농원명'/'농원ID' 열이 있는지 확인하세요.")

    if replace:
        conn.execute("DELETE FROM stock")
        conn.execute("DELETE FROM nursery")
        conn.execute("DELETE FROM dispatch_log")
    _ensure_admin_columns(conn)   # 주소·전화 컬럼 보장(구 DB 방어)
    for nid, (name, zone, pin, tagline, specialty, address, phone) in nurseries.items():
        conn.execute(
            "INSERT INTO nursery(id,name,zone,pin,tagline,specialty,address,phone) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, zone=excluded.zone, "
            "pin=excluded.pin, tagline=excluded.tagline, specialty=excluded.specialty, "
            "address=excluded.address, phone=excluded.phone",
            (nid, name, zone, pin, tagline, specialty, address, phone))
    upd = datetime.now().strftime("%Y-%m")
    for (nid, pid), (qty, pmin, pmax) in stocks.items():
        conn.execute(
            "INSERT INTO stock(nursery_id,plant_id,qty,price_min,price_max,updated_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(nursery_id,plant_id) DO UPDATE SET "
            "qty=excluded.qty, price_min=excluded.price_min, "
            "price_max=excluded.price_max, updated_at=excluded.updated_at",
            (nid, pid, qty, pmin, pmax, upd))
    conn.commit()
    return {"nurseries": len(nurseries), "stocks": len(stocks), "warnings": warns}

# ── 폴더의 농원등록_양식.csv를 앱 시작 시 자동 반영(기본 농원 데이터·항상 참조) ──
NURSERY_CSV_PATH = os.path.join(_BASE, "농원등록_양식.csv")

@st.cache_resource
def _load_default_nursery_csv():
    """레포 폴더에 농원등록_양식.csv가 있으면 앱 시작 시 1회 자동 반영한다.
    dispatch.db는 재시작 시 초기화될 수 있지만, 레포에 커밋된 이 CSV는 유지되므로
    농원 데이터가 재시작 후에도 자동 복원된다(=항상 이 파일을 기본값으로 참조)."""
    if not os.path.exists(NURSERY_CSV_PATH):
        return None
    try:
        with open(NURSERY_CSV_PATH, "rb") as f:
            return import_nurseries_csv(f.read(), replace=False)
    except Exception as e:
        return {"error": str(e)}

_DEFAULT_CSV_RESULT = _load_default_nursery_csv()

def kakao_map_url(nursery_name, address=""):
    """농원 주소(있으면) 또는 이름+불로화훼단지로 카카오맵 검색 링크 생성.
    좌표(위경도) 없이도 동작. 앱 없어도 브라우저에서 열림."""
    q = urllib.parse.quote((address or "").strip()
                           or f"{nursery_name} 대구 동구 불로동 화훼단지")
    return f"https://map.kakao.com/?q={q}"

def best_card(b, pid):
    _loc = b.get("address") or f"{b['zone']}"
    _tel = f"<br>📞 대표전화: {b['phone']}" if b.get("phone") else ""
    st.markdown(f"""<div class='best'>
      <span class='tag'>최우수 매칭 농원</span><br>
      <b style='font-size:19px'>🌿 {b['name']}</b> <span style='color:#777'>({b['id']})</span><br>
      <span style='font-size:14px'>
      ✅ 전문성: {PLANT_NAMES.get(pid, pid)} 재배 우수<br>
      📍 위치: {_loc} (지도 보기){_tel}<br>
      🎁 특별 서비스: 현장 화분 매칭 및 무료 분갈이 가능<br>
      👍 추천 횟수: {b['recs']:,}+ · 재고 {b['qty']}개</span></div>""",
      unsafe_allow_html=True)
    # 카카오맵 길안내: st.button은 링크를 못 열므로 a태그 버튼으로 표시
    kurl = kakao_map_url(b['name'], b.get('address', ''))
    st.markdown(f"""
    <a href="{kurl}" target="_blank" style="
        display:block; text-align:center; text-decoration:none;
        background:#FEE500; color:#3A1D1D; font-weight:800; font-size:16px;
        padding:12px; border-radius:12px; margin:8px 0;">
        🗺️ 이 농원 방문하기 (카카오맵 길 안내)
    </a>""", unsafe_allow_html=True)
    c2, c3 = st.columns(2)
    c2.button("📅 방문 예약하기", use_container_width=True, key=f"rsv_{b['id']}_{pid}")
    c3.button("⭐ 내 리스트 저장", use_container_width=True, key=f"sv_{b['id']}_{pid}")

def img_hash(b: bytes) -> int:
    return int(hashlib.md5(b).hexdigest(), 16)

# ── 이미지 에셋: assets 폴더(또는 같은 폴더)에 PNG가 있으면 자동 사용 ──
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 자체 카메라 컴포넌트 (전·후면 전환 아이콘 내장) ──
_FLCAM_DIR = os.path.join(_BASE_DIR, "flcam")
HAS_FLCAM = os.path.exists(os.path.join(_FLCAM_DIR, "index.html"))
if HAS_FLCAM:
    _flcam = components.declare_component("flcam", path=_FLCAM_DIR)
def asset(name):
    for d in (os.path.join(_BASE_DIR, "assets"), _BASE_DIR):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None

@st.cache_data
def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def clickable_image(path, key, aspect="351/416", fit="100% 100%", frame=True,
                    bg=None, pad=None, pos="center", height=None, hug=False):
    """이미지 전체가 버튼으로 동작. 클릭하면 True 반환 (세션 유지됨).
    fit="contain"이면 종횡비를 유지한 채 카드 안에 맞춤 (TOP5 일러스트용).
    frame=False면 테두리·배경 없이 이미지만 (로고 등 여백 제거용).
    bg 지정 시 그 색의 둥근 박스 안에 이미지를 넣는다 (로고 회색 박스 등).
    pad=안쪽 여백, pos=이미지 정렬(예 'left center'),
    height=고정 높이(지정 시 aspect 대신 사용).
    hug=True면 컬럼을 꽉 채우지 않고 내용(=height×aspect) 폭으로 줄인다(로고 카드용)."""
    if bg is not None:                                   # 회색 등 색상 박스
        box = f"border-radius: 16px; border: 1px solid {bg}; background-color: {bg};"
        hov = "filter: brightness(.97); transform: translateY(-1px);"
    elif frame:                                          # 기본: 흰 배경 + 테두리
        box = "border-radius: 16px; border: 1px solid #e3e3e3;"
        hov = ("border-color: {g}; box-shadow: 0 3px 12px rgba(46,125,50,.30); "
               "transform: translateY(-1px);".format(g=GREEN))
    else:                                                # 테두리·배경 없음
        box = "border: none; background-color: transparent;"
        hov = "opacity: .82;"
    if hug and height:      # 내용 폭으로 축소: 높이 고정 + aspect로 폭을 명시(px)해 클릭영역 정확히 일치
        try:
            _hpx = float(str(height).replace("px", "").strip())
            _aw, _ah = (str(aspect).split("/") + ["1"])[:2]
            _wpx = _hpx * (float(_aw) / float(_ah))
            size_rule = (f"height: {height}; width: {_wpx:.0f}px; "
                         f"box-sizing: content-box;")
        except Exception:
            size_rule = f"height: {height}; aspect-ratio: {aspect}; width: auto;"
    elif height:
        size_rule = f"height: {height}; width: 100%;"
    else:
        size_rule = f"aspect-ratio: {aspect}; height: auto; width: 100%;"
    pad_rule  = f"padding: {pad}; background-origin: content-box;" if pad else ""
    bgcolor   = f" {bg}" if bg else ""
    # hug 로고는 컬럼 안에서 항상 왼쪽 고정(가운데로 밀려 좌우 틀어지는 것 방지)
    container_rule = (f".st-key-{key} {{ display:flex; justify-content:flex-start; }}"
                      if hug else "")
    st.markdown(f"""<style>
    {container_rule}
    .st-key-{key} button {{
        background: url("data:image/png;base64,{_b64(path)}") {pos} / {fit} no-repeat{bgcolor};
        {size_rule} {box} {pad_rule}
    }}
    .st-key-{key} button:hover {{ {hov} transition: all .15s; }}
    .st-key-{key} button p, .st-key-{key} button div {{ color: transparent !important; }}
    </style>""", unsafe_allow_html=True)
    return st.button("\u200b", key=key, use_container_width=(not hug))

PLANT_ILLUST = {"P001": "1_MON.png",  "P002": "2_SKIN.png", "P003": "3_Cal.png",
                "P008": "4_SANSE.png", "P026": "5_BOS_GO.png"}

def plant_illust(pid):
    """식물 일러스트 경로 탐색. assets/plants/{PID}.png 가 있으면 우선 사용
    → 없으면 TOP5 일러스트 → 그것도 없으면 None(이모지 폴백).
    새 일러스트는 assets/plants/P004.png(또는 .webp) 파일명으로만 올리면 자동 반영."""
    for ext in ("png", "webp"):
        p = asset(os.path.join("plants", f"{pid}.{ext}"))
        if p:
            return p
    f = PLANT_ILLUST.get(pid)
    return asset(f) if f else None

@st.cache_data
def _thumb(path, max_px=480):
    """대용량 일러스트를 카드용으로 축소한 PNG 경로 반환.
    원본 1~6MB PNG를 base64로 그대로 심으면 홈 화면이 20MB를 넘어
    모바일에서 느려지므로, 커패시터 용량 낮추듯 전송량을 줄인다."""
    try:
        im = Image.open(path)
        if max(im.size) <= max_px:
            return path
        im.thumbnail((max_px, max_px))
        out = os.path.join(tempfile.gettempdir(),
                           f"flthumb_{max_px}_{os.path.basename(path)}")
        if not os.path.exists(out):
            im.save(out, "PNG", optimize=True)
        return out
    except Exception:
        return path

def camera_capture(key, front_default=True):
    """촬영 버튼 옆 전환 아이콘(🔄) 하나로 전·후면을 오가는 카메라.
    전·후면 모두 동일한 3:4 프레임 크기. 촬영 결과는 BytesIO(JPEG) 반환
    — 기존 up.getvalue() 호출부와 그대로 호환."""
    if HAS_FLCAM:
        data = _flcam(front=bool(front_default), key=f"flcam_{key}", default=None)
        if data:
            try:
                return io.BytesIO(base64.b64decode(data.split(",", 1)[-1]))
            except Exception:
                return None
        return None
    # 폴백: flcam 폴더가 배포에 없으면 기본 카메라 (버튼 문구만 촬영으로)
    st.markdown("""<style>
    [data-testid="stCameraInputButton"] { font-size: 0 !important; }
    [data-testid="stCameraInputButton"] * { font-size: 0 !important; }
    [data-testid="stCameraInputButton"]::after {
        content: "📸 촬영"; font-size: 14px; font-weight: 700;
    }
    </style>""", unsafe_allow_html=True)
    return st.camera_input("촬영", key=f"cam_front_{key}",
                           label_visibility="collapsed")

# ── PIL 유틸 (일러스트/합성/카드/QR) ─────────────────────────────────────────
def find_font(size):
    """한글 TTF 탐색: 윈도우 → 저장소 동봉(assets/fonts) → 리눅스 표준 경로
    → 시스템 전체 글롭. packages.txt(fonts-nanum) 설치 시 나눔고딕이 잡힌다."""
    import glob as _glob
    cands = [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf"]
    cands += sorted(_glob.glob(os.path.join(_BASE_DIR, "assets", "fonts", "*.tt*")))
    cands += ["/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    cands += sorted(_glob.glob("/usr/share/fonts/**/*Nanum*", recursive=True))
    cands += sorted(_glob.glob("/usr/share/fonts/**/*CJK*", recursive=True))
    for path in cands:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

@st.cache_data
def _white_to_transparent(path, thr=225):
    """흰/옅은회색 배경(그림자 포함)의 밝은 저채도 픽셀을 투명 처리하여 RGBA 반환.
    합성 시 흰 사각형·바닥 그림자가 방 사진 위에 얹히는 문제 해결."""
    im = Image.open(path).convert("RGBA")
    try:
        import numpy as np
        arr = np.array(im)
        r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
        mx = arr[:, :, :3].max(axis=2)
        mn = arr[:, :, :3].min(axis=2)
        sat = mx - mn                          # 채도(색 차이)
        # ① 밝은 흰 배경: 3채널 모두 매우 밝음
        white = (r > thr) & (g > thr) & (b > thr) & (sat < 28)
        # ② 옅은 회색 그림자: 중간 밝기(190~thr)이면서 채도 거의 0(무채색)
        gray_shadow = (mx > 190) & (sat < 14)
        arr[white | gray_shadow, 3] = 0
        return Image.fromarray(arr, "RGBA")
    except Exception:
        return im

def plant_image(pid, size=380, flower=None):
    """식물 그림을 size×size RGBA 로 반환.
    assets/plants/{PID}.png(webp) 실제 일러스트가 있으면 그것을 정사각으로 맞춰 사용,
    없으면 draw_plant() 도형으로 폴백. share_card / composite_plant 공용."""
    ill = plant_illust(pid)
    if ill:
        try:
            im = _white_to_transparent(ill)   # 흰 배경 투명 처리
            # 정사각 중앙 크롭 후 리사이즈
            side = min(im.size)
            im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                          (im.width + side) // 2, (im.height + side) // 2))
            return im.resize((size, size), Image.LANCZOS)
        except Exception:
            pass
    return draw_plant(size, flower)

POT_STYLES = {
    "토분":             ((193, 121, 82), (210, 140, 100), (150, 90, 60)),
    "플라스틱(화이트)": ((236, 236, 238), (247, 247, 249), (186, 186, 190)),
    "야외용(다크)":     ((92, 98, 104), (112, 118, 124), (62, 66, 72)),
}
def draw_plant(size=300, flower=None, pot=None):
    """화분+식물 일러스트 (flower='blue'면 수국 스타일, pot으로 화분 색 변경)"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size / 300.0
    body, rim, line = POT_STYLES.get(pot, POT_STYLES["토분"])
    # 화분
    d.polygon([(105*s, 210*s), (195*s, 210*s), (180*s, 285*s), (120*s, 285*s)],
              fill=body + (255,), outline=line + (255,), width=int(3*s))
    d.rectangle([98*s, 200*s, 202*s, 216*s], fill=rim + (255,))
    # 줄기
    d.line([(150*s, 210*s), (150*s, 110*s)], fill=(60, 120, 60, 255), width=int(7*s))
    if flower == "blue":  # 수국
        rnd = random.Random(7)
        for cx, cy, r in [(150, 95, 55), (105, 120, 40), (195, 120, 40), (150, 140, 35)]:
            for _ in range(22):
                a, rr = rnd.uniform(0, 6.283), rnd.uniform(0, r)
                x, y = cx + rr*np.cos(a), cy + rr*np.sin(a)
                col = rnd.choice([(140, 170, 230), (170, 190, 240), (200, 210, 245)])
                d.ellipse([(x-9)*s, (y-9)*s, (x+9)*s, (y+9)*s], fill=col + (255,))
        for ang in (-60, -20, 20, 60):
            d.ellipse([(150+ang-22)*s, 165*s, (150+ang+22)*s, 205*s],
                      fill=(70, 140, 75, 255))
    else:  # 관엽(여인초/몬스테라 느낌)
        for ang, ln in [(-70, 95), (-35, 115), (0, 130), (35, 115), (70, 95)]:
            rad = np.radians(ang - 90)
            x2, y2 = 150 + ln*np.cos(rad), 200 + ln*np.sin(rad)
            d.line([(150*s, 200*s), (x2*s, y2*s)], fill=(60, 125, 65, 255), width=int(5*s))
            d.ellipse([(x2-30)*s, (y2-48)*s, (x2+30)*s, (y2+18)*s],
                      fill=(80, 160, 90, 255), outline=(50, 110, 60, 255), width=int(2*s))
    return im

def face_mesh_overlay(img_bytes):
    """셀카 위 얼굴 분석 메시(그리드 타원) 오버레이"""
    im = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    im.thumbnail((520, 520))
    w, h = im.size
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    cx, cy, rx, ry = w//2, int(h*0.42), int(w*0.24), int(h*0.30)
    d.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], outline=(46, 125, 50, 220), width=3)
    for i in range(1, 6):  # 그리드
        yy = cy - ry + i * (2*ry//6)
        xx = int(rx * np.sqrt(max(0, 1 - ((yy-cy)/ry)**2)))
        d.line([cx-xx, yy, cx+xx, yy], fill=(46, 125, 50, 150), width=1)
        xv = cx - rx + i * (2*rx//6)
        yv = int(ry * np.sqrt(max(0, 1 - ((xv-cx)/rx)**2)))
        d.line([xv, cy-yv, xv, cy+yv], fill=(46, 125, 50, 150), width=1)
    return Image.alpha_composite(im, ov)

def run_face_analysis():
    """셀카를 분석해 ss.face_res / ss.face_copy 를 채운다.
    2단계 화면을 없앴으므로, 1단계 '다음' 직후 호출해 바로 3단계 카드로 넘어간다.
    Gemini on이면 실분석, 아니면 목업. 같은 사진은 캐시로 재호출 방지."""
    h = img_hash(ss.face_img)
    if gemini_on() and ss.get("face_ai_h") != h:
        spot = st.empty()   # 중앙 원형 스피너 표시용 placeholder
        spot.markdown(
            "<div class='fl-spin-wrap'><div class='fl-spinner'></div>"
            "<div class='fl-spin-txt'>🤖 얼굴을 분석하는 중...</div></div>",
            unsafe_allow_html=True)
        try:
            mbti = None if ss.get("mbti", "선택 안 함") == "선택 안 함" else ss.mbti
            res = gm.analyze_face(api_key, ss.face_img,
                                  list(PLANT_NAMES.values()), mbti)
            ss.face_ai, ss.face_ai_h = res, h
        except Exception as e:
            st.warning(f"Gemini 호출 실패 — 목업 모드로 대체 ({type(e).__name__})")
            ss.face_ai = None; ss.face_ai_h = h
        finally:
            spot.empty()
    ai = ss.get("face_ai") if ss.get("face_ai_h") == h else None

    if ai:
        pid = pid_of(ai.get("plant", ""), FACE_PLANTS[h % len(FACE_PLANTS)])
        imp = f"{ai.get('impression','온화함')} ({ai.get('impression_en','Gentle')})"
        vib = f"{ai.get('vibe','따뜻함')} ({ai.get('vibe_en','Warm')})"
        score = int(ai.get("score", 95))
        ss.face_copy = ai.get("copy", FACE_COPY.get(pid, "따뜻한 조화"))
        gender = ai.get("gender", "")          # Gemini가 성별을 주면 사용
    else:
        pid = FACE_PLANTS[h % len(FACE_PLANTS)]
        imp, vib = IMPRESSIONS[h % 6], VIBES[h % 4]
        score = 91 + h % 9
        ss.face_copy = FACE_COPY[pid]
        gender = "female" if h % 2 == 0 else "male"   # 목업: 사진 해시로 데모용 결정
    ss.face_gender = gender
    ss.face_greeting = greeting_for_gender(gender)     # 성별 맞춤 인사말
    ss.face_res = (pid, imp, vib, score)

def make_qr(text, size=140):
    if HAS_QR:
        q = qrcode.make(text).resize((size, size))
        return q.convert("RGBA")
    im = Image.new("RGBA", (size, size), "white")   # 의사 QR(라이브러리 없을 때)
    d = ImageDraw.Draw(im)
    rnd = random.Random(text)
    c = size // 21
    for i in range(21):
        for j in range(21):
            if rnd.random() < 0.45:
                d.rectangle([i*c, j*c, (i+1)*c, (j+1)*c], fill="black")
    return im

def composite_plant(bg_bytes, pid, x_pct, y_pct, scale_pct, label):
    """3단계 가상 배치: 공간 사진 위 식물 합성"""
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    bg.thumbnail((720, 720))
    w, h = bg.size
    ps = int(min(w, h) * scale_pct / 100)
    pl = plant_image(pid, ps, "blue" if pid == "P416" else None)
    x = int(w * x_pct / 100 - ps/2)
    y = int(h * y_pct / 100 - ps/2)
    out = bg.copy()
    out.paste(pl, (x, y), pl)
    d = ImageDraw.Draw(out)
    d.rectangle([x-4, y-4, x+ps+4, y+ps+4], outline=(255, 255, 255, 230), width=3)
    f = find_font(22)
    tw = d.textlength(label, font=f)
    d.rounded_rectangle([x+ps/2-tw/2-10, y+ps+8, x+ps/2+tw/2+10, y+ps+44],
                        radius=10, fill=(255, 255, 255, 235))
    d.text((x+ps/2-tw/2, y+ps+14), label, font=f, fill=(30, 60, 30))
    return out

def place_stage(pid, key="stage", height=None):
    """공간 사진 위에 식물을 얹어, 핀치(크기)·드래그로 실시간 배치해보는 미리보기.
    별도 '확정' 버튼 없이 화면에서 바로 체험한다(2손가락=크기+위치, 1손가락=스크롤)."""
    bg_b64 = base64.b64encode(ss.sp_img).decode()
    # 사진 실제 비율로 iframe 높이 추정 → 로드 후 JS가 실제 높이에 맞춰 더 조여 빈 공간 제거
    try:
        _w, _h = Image.open(io.BytesIO(ss.sp_img)).size
        _aspect = (_w / _h) if _h else 1.4
    except Exception:
        _aspect = 1.4
    if height is None:                       # 모바일 실제 폭(~400px) 기준 추정 → JS가 실제값으로 재조정
        height = int(min(720, max(150, 400 / _aspect + 16)))
    ill = plant_illust(pid)
    _pi = _white_to_transparent(ill) if ill else \
        draw_plant(400, "blue" if pid == "P416" else None, pot=ss.get("pot_style"))
    _buf = io.BytesIO(); _pi.save(_buf, "PNG")
    plant_b64 = base64.b64encode(_buf.getvalue()).decode()
    components.html(f"""
    <style>html,body{{margin:0;padding:0;overflow:hidden;height:100%;}}</style>
    <div id="{key}" style="position:relative; width:100%; height:100%; max-width:640px; margin:0 auto;
         touch-action:pan-y; user-select:none; border-radius:12px; overflow:hidden;
         box-shadow:0 2px 10px rgba(0,0,0,.15);">
      <img src="data:image/jpeg;base64,{bg_b64}"
           style="width:100%; height:100%; object-fit:cover; display:block; pointer-events:none;">
      <img id="{key}_p" src="data:image/png;base64,{plant_b64}"
           style="position:absolute; left:60%; top:62%; width:40%; height:auto;
                  transform:translate(-50%,-50%); cursor:grab;
                  filter:drop-shadow(0 6px 10px rgba(0,0,0,.35));">
      <div style="position:absolute; left:8px; bottom:8px; background:rgba(46,125,50,.85);
           color:#fff; font-size:12px; padding:3px 9px; border-radius:8px;">
        {PLANT_NAMES.get(pid,'')} — 두 손가락으로 크기·위치 · 한 손가락은 스크롤</div>
    </div>
    <script>
    (function(){{
      const stage=document.getElementById('{key}'), plant=document.getElementById('{key}_p');
      let px=60, py=62, scale=40, dragging=false, ox=0, oy=0;
      function apply(){{ plant.style.left=px+'%'; plant.style.top=py+'%'; plant.style.width=scale+'%'; }}
      function rect(){{ return stage.getBoundingClientRect(); }}
      function sd(cx,cy){{ dragging=true; plant.style.cursor='grabbing'; const r=rect();
        ox=cx-r.left-(px/100*r.width); oy=cy-r.top-(py/100*r.height); }}
      function mv(cx,cy){{ if(!dragging)return; const r=rect();
        px=Math.min(95,Math.max(5,((cx-r.left-ox)/r.width)*100));
        py=Math.min(95,Math.max(5,((cy-r.top-oy)/r.height)*100)); apply(); }}
      function ed(){{ dragging=false; plant.style.cursor='grab'; }}
      plant.addEventListener('mousedown',e=>{{sd(e.clientX,e.clientY);e.preventDefault();}});
      window.addEventListener('mousemove',e=>mv(e.clientX,e.clientY));
      window.addEventListener('mouseup',ed);
      stage.addEventListener('wheel',e=>{{ scale=Math.min(90,Math.max(10,
        scale-Math.sign(e.deltaY)*3)); apply(); e.preventDefault(); }},{{passive:false}});
      let pinch=0, s0=40, px0=0, py0=0, mx0=0, my0=0;
      function dist(t){{ const dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY; return Math.hypot(dx,dy); }}
      function mid(t){{ return {{x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2}}; }}
      stage.addEventListener('touchstart',e=>{{
        if(e.touches.length===2){{ const r=rect(), m=mid(e.touches);
          dragging=false; pinch=dist(e.touches); s0=scale;
          px0=px; py0=py; mx0=(m.x-r.left)/r.width*100; my0=(m.y-r.top)/r.height*100;
          e.preventDefault(); }}
      }},{{passive:false}});
      stage.addEventListener('touchmove',e=>{{
        if(e.touches.length===2 && pinch>0){{ const r=rect(), m=mid(e.touches);
          scale=Math.min(90,Math.max(10, s0*(dist(e.touches)/pinch)));
          const mx=(m.x-r.left)/r.width*100, my=(m.y-r.top)/r.height*100;
          px=Math.min(95,Math.max(5, px0+(mx-mx0))); py=Math.min(95,Math.max(5, py0+(my-my0)));
          apply(); e.preventDefault(); }}
      }},{{passive:false}});
      stage.addEventListener('touchend',e=>{{ if(e.touches.length<2){{ pinch=0; }} }});
      // ── iframe + 상위 래퍼 높이를 사진 실제 높이에 맞춰 축소(사진 아래 빈 공간 제거) ──
      function fitFrame(){{
        try{{
          const fh=Math.ceil(stage.getBoundingClientRect().height);
          if(fh>0 && window.frameElement){{
            let el=window.frameElement;
            for(let i=0;i<5 && el && el.style;i++){{      // iframe→래퍼 상위 몇 단계까지
              el.style.height=fh+'px'; el.style.minHeight='0px';
              el=el.parentElement;
            }}
          }}
        }}catch(e){{}}
      }}
      const _bg=stage.querySelector('img');
      if(_bg && _bg.complete) fitFrame(); else if(_bg) _bg.addEventListener('load',fitFrame);
      window.addEventListener('resize',fitFrame);
      try{{ new ResizeObserver(fitFrame).observe(stage); }}catch(e){{}}
      [60,200,500,1000,2000].forEach(t=>setTimeout(fitFrame,t));
      apply();
    }})();
    </script>
    """, height=height)

def plant_picker(recs, key):
    """추천 식물 타일(가로 나열). 탭하면 선택되어 색이 진해지고 ss.sp_pid가 바뀌며,
    사진(배치 스테이지)에 즉시 반영된다."""
    sel = ss.get("sp_pid")
    if sel not in recs:
        sel = recs[0]; ss.sp_pid = sel
    cols = st.columns(len(recs))
    for i, (col, rp) in enumerate(zip(cols, recs)):
        with col:
            ill = plant_illust(rp)
            if ill:
                st.image(_thumb(ill, 200), use_container_width=True)
            else:
                st.markdown("<div style='text-align:center;font-size:36px'>🌿</div>",
                            unsafe_allow_html=True)
            if st.button(("✅ " if rp == sel else "") + PLANT_NAMES[rp],
                         key=f"{key}_{i}_{rp}", use_container_width=True,
                         type="primary" if rp == sel else "secondary"):
                ss.sp_pid = rp; st.rerun()
    return sel

def interactive_card(img_bytes, pid, copy_text, score, greeting,
                     init_x=72, init_y=50, init_s=44):
    """공유 카드 자체를 조작 가능한 HTML로 렌더한다.
    별도 편집 화면 없이, 카드 위에서 식물을 바로 끌어 옮기고(드래그)
    두 손가락/휠로 크기를 조절하며, 카드 전체를 PNG로 저장한다.
    한글은 브라우저 폰트로 렌더되어 폰트 파일 없이도 깨지지 않는다."""
    # 셀카를 정사각으로 크롭(브라우저 object-fit 의존 없이 정사각 소스 사용)
    ph = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    side = min(ph.size)
    ph = ph.crop(((ph.width-side)//2, (ph.height-side)//2,
                  (ph.width+side)//2, (ph.height+side)//2)).resize((440, 440))
    _b = io.BytesIO(); ph.save(_b, "JPEG", quality=88)
    selfie_b64 = base64.b64encode(_b.getvalue()).decode()
    # 식물 일러스트(흰 배경 투명)
    ill = plant_illust(pid)
    if ill:
        _pi = _white_to_transparent(ill); _bb = io.BytesIO(); _pi.save(_bb, "PNG")
    else:
        _pl = draw_plant(400, "blue" if pid == "P416" else None)
        _bb = io.BytesIO(); _pl.save(_bb, "PNG")
    plant_b64 = base64.b64encode(_bb.getvalue()).decode()
    pname = PLANT_NAMES.get(pid, pid)
    fname = f"flowerland_{pname}.png"
    components.html(f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <div id="card" style="width:100%; max-width:430px; margin:0 auto; background:#e8f5e9;
         border-radius:14px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,.18);
         font-family:'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif;">
      <div style="background:#2E7D32; color:#fff; padding:14px 18px; font-size:19px; font-weight:800;">
        🌱 Flower Land (플라워랜드)</div>
      <div id="canvas" style="position:relative; width:100%; height:300px; background:#e8f5e9;
           touch-action:pan-y; user-select:none; overflow:hidden;">
        <img id="selfie" src="data:image/jpeg;base64,{selfie_b64}"
             style="position:absolute; left:5%; top:50%; transform:translateY(-50%);
                    width:40%; height:auto; border-radius:6px; pointer-events:none;">
        <img id="plant" src="data:image/png;base64,{plant_b64}"
             style="position:absolute; left:{init_x}%; top:{init_y}%; width:{init_s}%; height:auto;
                    transform:translate(-50%,-50%); cursor:grab;
                    filter:drop-shadow(0 6px 10px rgba(0,0,0,.28));">
      </div>
      <div style="padding:14px 18px 18px;">
        <div style="font-size:20px; font-weight:800; color:#173d1b; line-height:1.35;">
           {greeting} &amp; {pname} :</div>
        <div style="font-size:20px; font-weight:800; color:#173d1b; line-height:1.35;">{copy_text}</div>
        <div style="font-size:13px; color:#5a6e5a; margin-top:10px;">
           매핑 점수 {score}% · 나와 닮은 반려식물 카드</div>
      </div>
      <div style="background:#2E7D32; height:14px;"></div>
    </div>
    <div style="text-align:center; margin-top:12px;
                font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;">
      <button id="save" style="background:#ff5a5f; color:#fff; border:none; width:100%; max-width:430px;
         font-size:17px; font-weight:800; padding:13px; border-radius:12px; cursor:pointer;">
         📤 결과 공유하기 (카드 PNG 저장)</button>
      <div style="color:#888; font-size:12px; margin-top:7px;">
         ✌️ 두 손가락으로 크기·위치 조절 · 한 손가락은 화면 스크롤 &nbsp;(PC: 드래그 이동·휠 크기)</div>
    </div>
    <script>
    (function(){{
      const canvas=document.getElementById('canvas');
      const plant=document.getElementById('plant');
      let px={init_x}, py={init_y}, scale={init_s};
      function apply(){{ plant.style.left=px+'%'; plant.style.top=py+'%'; plant.style.width=scale+'%'; }}
      function rect(){{ return canvas.getBoundingClientRect(); }}
      let dragging=false, ox=0, oy=0;
      function sd(cx,cy){{ dragging=true; plant.style.cursor='grabbing'; const r=rect();
        ox=cx-r.left-(px/100*r.width); oy=cy-r.top-(py/100*r.height); }}
      function mv(cx,cy){{ if(!dragging)return; const r=rect();
        px=Math.min(98,Math.max(2,((cx-r.left-ox)/r.width)*100));
        py=Math.min(98,Math.max(2,((cy-r.top-oy)/r.height)*100)); apply(); }}
      function ed(){{ dragging=false; plant.style.cursor='grab'; }}
      plant.addEventListener('mousedown',e=>{{sd(e.clientX,e.clientY);e.preventDefault();}});
      window.addEventListener('mousemove',e=>mv(e.clientX,e.clientY));
      window.addEventListener('mouseup',ed);
      canvas.addEventListener('wheel',e=>{{ scale=Math.min(95,Math.max(12,
        scale-Math.sign(e.deltaY)*3)); apply(); e.preventDefault(); }},{{passive:false}});
      let pinch=0, s0={init_s}, px0=0, py0=0, mx0=0, my0=0;
      function dist(t){{ const dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
        return Math.hypot(dx,dy); }}
      function mid(t){{ return {{x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2}}; }}
      canvas.addEventListener('touchstart',e=>{{
        if(e.touches.length===2){{                          // 두 손가락: 크기+위치 조작
          const r=rect(), m=mid(e.touches);
          dragging=false; pinch=dist(e.touches); s0=scale;
          px0=px; py0=py; mx0=(m.x-r.left)/r.width*100; my0=(m.y-r.top)/r.height*100;
          e.preventDefault();
        }}                                                  // 한 손가락은 가로채지 않음 → 페이지 스크롤
      }},{{passive:false}});
      canvas.addEventListener('touchmove',e=>{{
        if(e.touches.length===2 && pinch>0){{
          const r=rect(), m=mid(e.touches);
          scale=Math.min(95,Math.max(12, s0*(dist(e.touches)/pinch)));
          const mx=(m.x-r.left)/r.width*100, my=(m.y-r.top)/r.height*100;
          px=Math.min(98,Math.max(2, px0+(mx-mx0)));
          py=Math.min(98,Math.max(2, py0+(my-my0)));
          apply(); e.preventDefault();
        }}                                                  // 한 손가락은 스크롤
      }},{{passive:false}});
      canvas.addEventListener('touchend',e=>{{ if(e.touches.length<2){{ pinch=0; }} }});
      apply();
      document.getElementById('save').addEventListener('click',function(){{
        const btn=document.getElementById('save'); btn.textContent='⏳ 카드 생성 중...';
        html2canvas(document.getElementById('card'),
          {{backgroundColor:'#e8f5e9', scale:2, useCORS:true}}).then(function(cv){{
          cv.toBlob(function(blob){{
            const url=URL.createObjectURL(blob);
            const a=document.createElement('a'); a.href=url; a.download='{fname}';
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(()=>URL.revokeObjectURL(url),5000);
            btn.textContent='📤 결과 공유하기 (카드 PNG 저장)';
          }}, 'image/png');
        }}).catch(function(err){{
          btn.textContent='📤 결과 공유하기 (카드 PNG 저장)';
          alert('이미지 저장 중 문제가 발생했습니다. 화면을 캡처해 주세요.');
        }});
      }});
    }})();
    </script>
    """, height=560)

def pinch_image(pid, init_size=62, height=340):
    """DB(카탈로그) 식물 이미지를 핀치/휠로 크기 조절 + 드래그로 이동해서 보는 뷰어.
    assets/plants/{PID}.png 일러스트가 있으면 사용, 없으면 도형 폴백."""
    ill = plant_illust(pid)
    _pi = _white_to_transparent(ill) if ill else draw_plant(400, "blue" if pid == "P416" else None)
    _b = io.BytesIO(); _pi.save(_b, "PNG")
    img_b64 = base64.b64encode(_b.getvalue()).decode()
    components.html(f"""
    <div id="box" style="position:relative; width:100%; height:{height-46}px;
         background:#f5faf5; border:1px solid #dcecdc; border-radius:12px;
         touch-action:pan-y; user-select:none; overflow:hidden;">
      <img id="img" src="data:image/png;base64,{img_b64}"
           style="position:absolute; left:50%; top:50%; width:{init_size}%; height:auto;
                  transform:translate(-50%,-50%); cursor:grab;
                  filter:drop-shadow(0 4px 8px rgba(0,0,0,.2));">
    </div>
    <div style="text-align:center; color:#888; font-size:12px; margin-top:7px;
         font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;">
       ✌️ 두 손가락으로 크기·위치 조절 · 한 손가락은 화면 스크롤 &nbsp;(PC: 드래그 이동·휠 크기)</div>
    <script>
    (function(){{
      const box=document.getElementById('box'), img=document.getElementById('img');
      let px=50, py=50, scale={init_size};
      function apply(){{ img.style.left=px+'%'; img.style.top=py+'%'; img.style.width=scale+'%'; }}
      function rect(){{ return box.getBoundingClientRect(); }}
      let dragging=false, ox=0, oy=0;
      function sd(cx,cy){{ dragging=true; img.style.cursor='grabbing'; const r=rect();
        ox=cx-r.left-(px/100*r.width); oy=cy-r.top-(py/100*r.height); }}
      function mv(cx,cy){{ if(!dragging)return; const r=rect();
        px=Math.min(98,Math.max(2,((cx-r.left-ox)/r.width)*100));
        py=Math.min(98,Math.max(2,((cy-r.top-oy)/r.height)*100)); apply(); }}
      function ed(){{ dragging=false; img.style.cursor='grab'; }}
      img.addEventListener('mousedown',e=>{{sd(e.clientX,e.clientY);e.preventDefault();}});
      window.addEventListener('mousemove',e=>mv(e.clientX,e.clientY));
      window.addEventListener('mouseup',ed);
      box.addEventListener('wheel',e=>{{ scale=Math.min(170,Math.max(15,
        scale-Math.sign(e.deltaY)*4)); apply(); e.preventDefault(); }},{{passive:false}});
      let pinch=0, s0={init_size}, px0=0, py0=0, mx0=0, my0=0;
      function dist(t){{ const dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
        return Math.hypot(dx,dy); }}
      function mid(t){{ return {{x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2}}; }}
      box.addEventListener('touchstart',e=>{{
        if(e.touches.length===2){{
          const r=rect(), m=mid(e.touches);
          dragging=false; pinch=dist(e.touches); s0=scale;
          px0=px; py0=py; mx0=(m.x-r.left)/r.width*100; my0=(m.y-r.top)/r.height*100;
          e.preventDefault();
        }}                                                  // 한 손가락 → 페이지 스크롤
      }},{{passive:false}});
      box.addEventListener('touchmove',e=>{{
        if(e.touches.length===2 && pinch>0){{
          const r=rect(), m=mid(e.touches);
          scale=Math.min(170,Math.max(15, s0*(dist(e.touches)/pinch)));
          const mx=(m.x-r.left)/r.width*100, my=(m.y-r.top)/r.height*100;
          px=Math.min(98,Math.max(2, px0+(mx-mx0)));
          py=Math.min(98,Math.max(2, py0+(my-my0)));
          apply(); e.preventDefault();
        }}
      }},{{passive:false}});
      box.addEventListener('touchend',e=>{{ if(e.touches.length<2){{ pinch=0; }} }});
      apply();
    }})();
    </script>
    """, height=height)

# ── 라우팅 ───────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("page", "home")
ss.setdefault("face_step", 1); ss.setdefault("space_step", 1)
def go(p): ss.page = p; st.rerun()

def show_plant_intro(name, registered):
    """식물 소개. Gemini 키가 있고 정상이면 AI 분석, 실패하거나 키가 없으면
    plants_master.csv(단지 카탈로그) 정보로 폴백한다.
    · 같은 이름은 세션 캐시로 재호출하지 않음(반복 실패/지연 방지)
    · 한 번 실패하면 이후 검색은 AI를 생략하고 조용히 카탈로그로 표시."""
    ai_available = gemini_on() and not ss.get("plant_ai_off")
    info = None
    if ai_available:
        cache = ss.setdefault("plant_ai_cache", {})
        if name in cache:
            info = cache[name]                          # 이미 조회한 이름 → 재호출 안 함
        else:
            names = "、".join(PLANT_NAMES.values())
            prompt = (
                f"너는 원예 전문가다. 식물 '{name}'을 소개한다.\n"
                f"아래 JSON만 출력(마크다운·설명 금지):\n"
                '{"exists": true/false, "sci":"학명", "type":"분류(관엽/다육/화초/허브 등)", '
                '"summary":"특징 한줄(45자내)", "light":"광 요구", "water":"물주기", '
                '"level":"난이도(초보/중급/고수)", "similar":["유사품종 최대3개"]}\n'
                f"'similar'는 반드시 이 목록에서만: {names}\n"
                f"'{name}'이 식물이 아니면 exists=false.")
            try:
                with st.spinner(f"'{name}' 식물 정보를 AI로 분석 중..."):
                    info = gm.ask_json(api_key, prompt)
            except Exception as e:
                info = None
                ss.plant_ai_off = True                  # 이후 검색은 AI 생략(스팸 방지)
                ss.plant_ai_err = type(e).__name__
            cache[name] = info                          # None도 캐시 → 같은 이름 재시도 방지
        if info and info.get("exists"):
            ss.last_similar = info.get("similar", [])
            st.markdown(
                f"<div class='result'><b style='font-size:19px'>{name}</b> "
                f"<span style='color:#888'>{info.get('sci','')}</span> "
                f"<span class='chip'>🤖 Gemini</span><br>"
                f"<b>유형</b>: {info.get('type','-')} · <b>난이도</b>: {info.get('level','-')}<br>"
                f"{info.get('summary','')}<br>"
                f"☀️ {info.get('light','-')} &nbsp; 💧 {info.get('water','-')}</div>",
                unsafe_allow_html=True)
            return

    # AI가 꺼졌다면(실패 이력) 세션당 1번만 안내
    if ss.get("plant_ai_off") and not ss.get("plant_ai_notified"):
        st.caption(f"ℹ️ AI 상세 분석을 불러오지 못해 단지 카탈로그 정보로 표시합니다. "
                   f"(원인: {ss.get('plant_ai_err','오류')} · 사이드바에서 Gemini 키/모델 확인)")
        ss.plant_ai_notified = True

    # ── 폴백: 마스터 카탈로그(plants_master.csv) 기반 실제 식물 정보 ──
    if name in NAME_TO_PID:
        pid = NAME_TO_PID[name]
        en, sci, cat = PLANT_EN.get(pid, ""), PLANT_SCI.get(pid, ""), PLANT_CAT.get(pid, "")
        desc = PLANT_DESC.get(pid, "")
        care = ""
        try:  # care 컬럼이 있는 DB면 덤으로 표시(없어도 무방)
            row = conn.execute("SELECT care_level, light_need, water_cycle "
                               "FROM plant WHERE id=?", (pid,)).fetchone()
            if row:
                care = f"<br>난이도 {row[0]} · ☀️ {row[1]} · 💧 {row[2]}일 주기"
        except Exception:
            pass
        st.markdown(
            f"<div class='result'><b style='font-size:19px'>{name}</b> "
            + (f"<span style='color:#888'>{sci}</span> " if sci else "")
            + f"<span class='chip'>단지 카탈로그</span><br>"
            + (f"<b>영문명</b>: {en}<br>" if en else "")
            + (f"<b>분류</b>: {cat}<br>" if cat else "")
            + (f"{desc}<br>" if desc else "")
            + "불로화훼단지에서 취급 중인 품종입니다. 아래에서 취급 농원·재고를 확인하세요."
            + care + "</div>",
            unsafe_allow_html=True)
        return
    st.info(f"'{name}'은(는) 단지 카탈로그(1,001종)에 없는 품종입니다. "
            "사이드바에서 Gemini 키를 연결하면 AI 소개를 볼 수 있습니다.")

def show_stock_nurseries(pid, compact=False):
    """DB에서 해당 품종 취급 농원·재고 표시 + 트래픽 분배 추천 회원사."""
    try:
        rows = conn.execute("""
            SELECT s.nursery_id, n.name, s.qty, s.updated_at,
                   n.zone, COALESCE(n.address,''), COALESCE(n.phone,'')
            FROM stock s JOIN nursery n ON n.id = s.nursery_id
            WHERE s.plant_id = ? AND s.qty > 0
            ORDER BY s.qty DESC""", (pid,)).fetchall()
    except sqlite3.OperationalError:          # 구 DB: 주소·전화 컬럼 없음 → 추가 후 재시도
        _ensure_admin_columns(conn)
        rows = conn.execute("""
            SELECT s.nursery_id, n.name, s.qty, s.updated_at,
                   n.zone, COALESCE(n.address,''), COALESCE(n.phone,'')
            FROM stock s JOIN nursery n ON n.id = s.nursery_id
            WHERE s.plant_id = ? AND s.qty > 0
            ORDER BY s.qty DESC""", (pid,)).fetchall()
    if not rows:
        st.error(f"현재 '{PLANT_NAMES.get(pid,'')}' 재고 보유 농원이 없습니다.")
        st.caption("💡 관리자 모드에서 농원에 이 품종의 재고를 등록하면 여기에 표시됩니다.")
        return
    total = sum(r[2] for r in rows)
    st.markdown(f"<div class='nursery'>취급 농원 <b>{len(rows)}곳</b> · "
                f"단지 총 재고 <b>{total}개</b></div>", unsafe_allow_html=True)
    for nid, name, qty, upd, zone, addr, phone in (rows if not compact else rows[:2]):
        fresh = "🟢" if (upd and upd >= "2026") else "🟡"
        kurl = kakao_map_url(name, addr)
        loc = addr or zone                    # 주소가 있으면 주소, 없으면 실제 구역
        tel = (f"<a href='tel:{phone}' style='color:#e91e63; text-decoration:none; "
               f"font-weight:700;'>📞 {phone}</a>" if phone else "")
        st.markdown(
            f"<div class='nursery'>🏪 <b>{name}</b> ({nid}) · {loc}"
            f"<br>재고 <b>{qty}개</b> {fresh} · "
            f"<a href='{kurl}' target='_blank' style='color:#1a73e8; "
            f"text-decoration:none; font-weight:700;'>📍 지도</a>"
            + (f" · {tel}" if tel else "") + "</div>",
            unsafe_allow_html=True)
    if not compact:
        st.caption("🟢 재고 최근 갱신 · 🟡 갱신 필요(72h 기준)")
        b = best_nursery(pid, "search")
        if b:
            st.markdown("#### ⭐ 오늘의 추천 회원사 (트래픽 분배)")
            best_card(b, pid)
NOTICES = [
    ("🎉", "봄맞이 분갈이 이벤트 — 이번 주말 현장 무료 분갈이"),
    ("📅", "예약 확정 — 3/16(토) 14:00 대형 몬스테라 상담"),
    ("🌸", "신규 입고 — 올리브나무·아레카야자 대형목"),
]

def header():
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)  # 로고 상단 여백
    c1, c2 = st.columns([1, 1], vertical_alignment="center")  # 로고↔알림 세로 가운데
    logo = asset("Flower_land.png")
    with c1:
        # Flower_land.png 로고 = 홈 버튼. 내용 폭에 맞춘 컴팩트 회색 카드(왼쪽 배치)
        if logo:
            if clickable_image(logo, f"logohome_{page}", aspect="300/96",
                               fit="contain", bg="#EFF1EF", pad="8px 14px",
                               pos="left center", height="43px", hug=True):
                go("home")
        else:
            if st.button("🌱 Flower Land (홈)", key=f"logohome_{page}"):
                go("home")
    with c2:
        # 🔔 알림 벨 — 컬럼을 채우는 넓은 흰 박스 (스크린샷과 동일)
        with st.popover(f"🔔 알림 {len(NOTICES)}", use_container_width=True):
            st.markdown("**📣 새 소식 · 예약 알림**")
            for ico, txt in NOTICES:
                st.markdown(f"{ico} {txt}")

def home_button(page):
    pass   # 홈 버튼 제거: 이제 헤더의 Flower_land.png 로고 자체가 홈 버튼

page = ss.page

# ══════════════ 홈 ══════════════
if page == "home":
    header()
    b1, b2 = st.columns(2)
    with b1:
        if asset("MBTI.png"):
            if clickable_image(asset("MBTI.png"), "imgbtn_face", "351/415"):
                ss.face_step = 1; go("face")
        else:
            st.markdown("""<div class='banner banner-fun'><span class='chip'>재미 레이어</span><br>
            <b style='font-size:16px'>나와 닮은 식물 찾기<br>(얼굴 & MBTI)</b><br>
            <span style='font-size:12px'>셀카로 분석하는 나의 식물 유형 카드 공유!</span></div>""",
            unsafe_allow_html=True)
            if st.button("📷 사진 찍고 추천받기", use_container_width=True, type="primary"):
                ss.face_step = 1; go("face")
    with b2:
        if asset("TERA.png"):
            if clickable_image(asset("TERA.png"), "imgbtn_space", "351/418"):
                ss.space_step = 1; go("space")
        else:
            st.markdown("""<div class='banner banner-util'><span class='chip'>실용 레이어</span><br>
            <b style='font-size:16px'>내 방·정원 맞춤<br>플랜테리어</b><br>
            <span style='font-size:12px'>공간 사진을 찍어보세요. 최적의 식물과 배치 제안!</span></div>""",
            unsafe_allow_html=True)
            if st.button("🖼️ 공간 분석 시작", use_container_width=True, type="primary"):
                ss.space_step = 1; go("space")
    st.write("")
    # ── 식물 검색 ──
    sc1, sc2 = st.columns([3, 1])
    q = sc1.text_input("식물 검색", placeholder="🔎 식물 이름으로 검색 (예: 몬스테라, 수국)",
                       label_visibility="collapsed")
    if sc2.button("검색", use_container_width=True, type="primary") or q:
        if q.strip():
            ss.search_q = q.strip(); go("search")
    cols = st.columns(4)
    ICON_FILES = ["MAP.png", "Port.png", "TREE.png", "CARE.png"]
    ICON_ASPECT = ["165/222", "172/222", "172/222", "172/222"]
    for col, e, ic, asp, t, s, tgt in zip(cols, "🗺️🪴🔍💧", ICON_FILES, ICON_ASPECT,
            ["농원 지도", "분갈이·화분 특화", "식물 건강 진단", "내 식물 관리"],
            ["40개 농원 안내", "특화 농원 보기", "시든 식물 처방", "물·영양 알림"],
            ["map", "repot", "diag", "care"]):
        with col:
            if asset(ic):
                if clickable_image(asset(ic), f"imgbtn_{tgt}", asp):
                    go(tgt)
            else:
                st.markdown(f"<div class='icon-card'><div class='e'>{e}</div>"
                            f"<div class='t'>{t}</div><div class='s'>{s}</div></div>",
                            unsafe_allow_html=True)
                if st.button("열기", key=f"b_{tgt}", use_container_width=True):
                    go(tgt)
    st.write("")
    st.markdown("#### 실시간 단지 인기 식물 TOP 5")
    # 고해상도 일러스트 이미지 카드 (PNG 없는 식물은 이모지 카드로 자동 폴백)
    cols = st.columns(5)
    for rank, (pid, em, col) in enumerate(zip(
            ["P001", "P002", "P003", "P008", "P026"], "🌿🍃🌱🪴🌿", cols), 1):
        with col:
            img = plant_illust(pid)
            if img:
                if clickable_image(_thumb(img), f"imgbtn_top_{pid}", "2/3", fit="contain"):
                    ss.plant_pid = pid
                    go("plant")
                st.markdown(f"<div class='top5-name'>{rank}. {PLANT_NAMES[pid]}</div>",
                            unsafe_allow_html=True)
            else:
                label = f"{em}\n{rank}. {PLANT_NAMES[pid]}"
                if st.button(label, key=f"top_{pid}", use_container_width=True):
                    ss.plant_pid = pid
                    go("plant")
    st.caption("※ 초기 시연 — AI 분석은 규칙 기반 목업, 농원 선정은 실제 가중 랜덤 알고리즘 동작")
    st.write("")
    with st.expander("🔑 회원사 · 상인회 로그인"):
        st.caption("농원주는 자기 농원의 추천 식물을 직접 등록·편집할 수 있습니다.")
        if st.button("회원사 관리자 모드 들어가기", use_container_width=True):
            go("admin")

# ══════════════ 식물 상세 (TOP5 등에서 진입) ══════════════
elif page == "plant":
    header()
    home_button(page)
    pid = ss.get("plant_pid")
    if not pid or pid not in PLANT_NAMES:
        st.warning("식물 정보를 찾을 수 없습니다.")
        st.stop()
    name = PLANT_NAMES[pid]
    st.markdown(f"## 🌿 {name}")

    # ⓪ 일러스트 (있는 식물만) — 핀치/휠로 크기 조절 · 끌어서 이동
    ill = plant_illust(pid)
    if ill:
        pinch_image(pid)

    # ① API(제미나이): 식물 유형·소개
    st.markdown("### 식물 소개")
    show_plant_intro(name, registered=True)

    # ② DB: 취급 농원·재고
    st.markdown("### 🏪 어느 농원에 있나요")
    show_stock_nurseries(pid)

    st.write("")
    if st.button("🔎 다른 식물 검색하기", use_container_width=True):
        ss.search_q = ""
        go("search")

# ══════════════ 얼굴 & MBTI (3단계) ══════════════
elif page == "face":
    header()
    step = ss.face_step
    if step == 1:
        home_button(page)
        st.markdown(
            "<div class='step' style='padding-top:4px'>"
            "1단계 : 분석할 셀카를 찍어주세요</div>",
            unsafe_allow_html=True)
    else:
        home_button(page)

    if step == 1:
        ss.mbti = st.selectbox("MBTI (선택)", ["선택 안 함"] + [
            a+b+c+d for a in "EI" for b in "SN" for c in "TF" for d in "JP"])
        t1, t2 = st.tabs(["📷 직접 촬영하기", "🖼️ 갤러리에서 선택"])
        with t1: cam = camera_capture("face", front_default=True)  # ◀ 촬영 한글화 + 전·후면 전환
        with t2: fil = st.file_uploader("파일", type=["jpg", "jpeg", "png"],
                                        label_visibility="collapsed")
        up = cam or fil
        st.markdown(
            "<div style='background:#eef6ff; border-radius:8px; padding:7px 10px; "
            "font-size:12.5px; color:#2b3a4a; white-space:nowrap; overflow:hidden; "
            "text-overflow:ellipsis;'>💡 팁: 얼굴이 잘 보이도록 찍으면 더 정확해요!</div>",
            unsafe_allow_html=True)
        if up and st.button("다음", type="primary", use_container_width=True):
            ss.face_img = up.getvalue()
            run_face_analysis()          # ◀ 분석 즉시 실행
            ss.face_step = 3             # ◀ 2단계 건너뛰고 바로 3단계 카드 출력
            st.rerun()

    else:
        if not ss.get("face_res") or not ss.get("face_img"):
            st.warning("셀카 정보가 없어 처음 단계로 돌아갑니다.")
            ss.face_step = 1; st.rerun()
        pid, imp, vib, score = ss.face_res
        copy = ss.get("face_copy") or FACE_COPY.get(pid, "따뜻한 조화")
        greeting = ss.get("face_greeting") or f"{USER_NAME} 님"   # 성별 맞춤 인사말
        st.markdown("<div class='step'>3단계: 유형 카드 공유 & 매칭 농원</div>",
                    unsafe_allow_html=True)

        # 카드 자체에서 바로 조작: 식물을 끌어 이동 · 핀치/휠로 크기 → 카드 PNG 저장
        interactive_card(ss.face_img, pid, copy, score, greeting)

        st.markdown("#### 40개 전체 농원 노출 · 최우수 매칭")
        b = best_nursery(pid, "fun01")
        if b: best_card(b, pid)
        if st.button("처음부터 다시", use_container_width=True):
            ss.face_step = 1; st.rerun()

# ══════════════ 공간 플랜테리어 (4단계) ══════════════
elif page == "space":
    header()
    home_button(page)
    step = ss.space_step
    st.progress(step / 3, text=f"{step}단계 / 3단계")

    if step == 1:
        st.markdown("<div class='step'>1단계: 공간 사진 등록</div>", unsafe_allow_html=True)
        st.markdown("<div class='big'>분석할 정원이나 거실 사진을 올려주세요.</div>",
                    unsafe_allow_html=True)
        st.caption("(A single, best photo is recommended)")
        ss.room = st.selectbox("공간 유형",
                               list(INDOOR_RECS.keys()) + list(OUTDOOR_RECS.keys()))
        t1, t2 = st.tabs(["📷 직접 촬영하기", "🖼️ 갤러리에서 선택"])
        with t1: cam = camera_capture("space", front_default=False)  # ◀ 공간 촬영은 후면 기본
        with t2: fil = st.file_uploader("파일", type=["jpg", "jpeg", "png"],
                                        label_visibility="collapsed")
        up = cam or fil
        st.info("팁: 하늘(창문)과 바닥면이 잘 보이도록 찍으면 더 정확해요!")
        if up and st.button("다음", type="primary", use_container_width=True):
            ss.sp_img = up.getvalue(); ss.space_step = 2; st.rerun()

    elif step == 2:
        h = img_hash(ss.sp_img)
        outdoor = ss.room in OUTDOOR_RECS
        # ── Gemini 실분석 ──
        if gemini_on() and ss.get("sp_ai_h") != h:
            try:
                with st.spinner(f"🤖 Flowerland가 {ss.room} 사진을 분석하는 중..."):
                    res = gm.analyze_space(api_key, ss.sp_img, ss.room,
                                           list(PLANT_NAMES.values()))
                ss.sp_ai, ss.sp_ai_h = res, h
            except Exception as e:
                st.warning(f"AI 분석 실패 — 기본 분석으로 대체 ({type(e).__name__})")
                ss.sp_ai = None; ss.sp_ai_h = h
        ai = ss.get("sp_ai") if ss.get("sp_ai_h") == h else None

        st.markdown("<div class='step'>2단계: 정밀 분석 & 가상 배치"
                    + (" · 🤖 Flowerland" if ai else " · 기본 분석") + "</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='big'>AI가 당신의 {ss.room}을 분석했습니다!</div>",
                    unsafe_allow_html=True)
        icons = ["☀️", "🌱", "❄️", "📐"] if outdoor else ["🪟", "💡", "🎨", "📏"]
        if ai and ai.get("cards"):
            cards = [(icons[i % 4], c.get("title", ""),
                      f"{c.get('value','')}|/|{c.get('detail','')}".replace("|/|", "<br>"))
                     for i, c in enumerate(ai["cards"][:4])]
            stars = int(ai.get("stars", 4))
            _fallback = (OUTDOOR_RECS if outdoor else INDOOR_RECS)[ss.room]
            recs = [pid_of(n, fb) for n, fb in zip(ai.get("plants", []), _fallback)]
            # 유효하지 않은 PID(마스터에 없음)는 기본 추천으로 교체
            recs = [(p if p in PLANT_NAMES else fb)
                    for p, fb in zip(recs + _fallback, _fallback)][:5]
            if not recs:
                recs = _fallback
            ss.sp_match = int(ai.get("match", 97))
            ss.sp_reason = ai.get("reason", "")
        else:
            if outdoor:
                cards = [("☀️", "일조량 분석", f"직사광 노출 (일 평균 {4+h % 4}시간 이상 야외 환경)"),
                         ("🌱", "바닥 재질", "잔디 및 토양 구역 (일부 데크 영역 감지)"),
                         ("❄️", "월동 여부", "겨울철 영하 기온 (노지 월동 식물 필수)"),
                         ("📐", "공간 규모", "대형 화분 및 군락 식재 영역 보유")]
            else:
                cards = [("🪟", "창문 방향", ["남향", "동향", "남동향"][h % 3]),
                         ("💡", "광량", f"평균 {2500 + h % 2000:,} Lux (간접광 풍부)"),
                         ("🎨", "인테리어 톤", "우드 & 화이트"),
                         ("📏", "여백", "거실장 옆 (대형 식물 추천)")]
            stars = 4 + h % 2
            recs = (OUTDOOR_RECS if outdoor else INDOOR_RECS)[ss.room]
            ss.sp_match = 95 + h % 5
            ss.sp_reason = ""
        # ── 추천 식물 5종 준비 + 배치할 식물 확정 ──
        # 중복 PID 제거(순서 유지) → plant_picker 버튼 키 충돌 방지
        _seen = set(); recs = [p for p in recs if not (p in _seen or _seen.add(p))]
        _fb_all = (OUTDOOR_RECS if outdoor else INDOOR_RECS)[ss.room]
        for p in _fb_all:                        # 5종 미만이면 기본 추천으로 보충
            if len(recs) >= 5:
                break
            if p not in _seen:
                recs.append(p); _seen.add(p)
        recs = recs[:5] or _fb_all[:5]
        ss.sp_recs = recs
        if ss.get("sp_pid") not in recs:
            ss.sp_pid = recs[0]
        pid = ss.sp_pid

        # ── 가상 배치 (기존 3단계를 여기로 병합) ──
        st.markdown("##### 🪴 가상 배치 체험")
        mode = st.radio("합성 방식", ["🎚️ 수동 배치", "🤖 AI 실사 합성 (Flowerland)"],
                        horizontal=True, index=0)   # 수동 배치가 기본
        if mode.startswith("🎚️"):
            st.caption("✌️ 두 손가락으로 크기·위치 조절 · 한 손가락은 화면 스크롤 "
                       "(PC는 드래그 이동, 휠로 크기)")
            place_stage(pid, key="st2")             # 확정 버튼 없이 실시간 배치
        else:
            if not gemini_on():
                st.warning("AI 실사 합성을 쓰려면 사이드바에서 AI 키를 입력하세요.")
            else:
                cache_key = (h, pid)
                if ss.get("comp_key") != cache_key:
                    try:
                        with st.spinner(f"🤖 Flowerland가 {PLANT_NAMES[pid]}을(를) "
                                        f"{ss.room}에 합성하는 중... (10~20초)"):
                            ss.comp_img = gm.composite_plant_ai(
                                api_key, ss.sp_img, PLANT_NAMES[pid], ss.room)
                        ss.comp_key = cache_key; ss.comp_err = None
                    except Exception as e:
                        ss.comp_img = None; ss.comp_key = cache_key
                        ss.comp_err = f"{type(e).__name__}: {e}"
                if ss.get("comp_img"):
                    st.image(ss.comp_img, use_container_width=True,
                             caption=f"{PLANT_NAMES[pid]} 실사 합성 결과 (Flowerland)")
                    if st.button("🔄 다시 합성하기", use_container_width=True):
                        ss.comp_key = None; st.rerun()
                elif ss.get("comp_err"):
                    _err = ss.comp_err
                    if "429" in _err:
                        st.warning("무료 AI 이미지 생성 한도를 초과했어요 (429). 잠시 후 다시 "
                                   "시도하거나, 아래 **수동 배치**를 이용해 주세요.")
                    else:
                        st.warning("AI 실사 합성에 실패했어요 — 아래 **수동 배치**를 사용해 주세요.")
                    with st.expander("오류 상세 보기 (관리자용)"):
                        st.code(_err)
                    place_stage(pid, key="st2")     # 실패 시 수동 배치로 자동 대체

        # ── 사진 아래: 분석 라인(창문방향…여백) + 종합 추천 지표 (첨부 이미지 순서) ──
        chips = " &nbsp;·&nbsp; ".join(
            f"{e} <b>{t}</b> {s.split('<br>')[0]}" for (e, t, s) in cards)
        st.markdown(f"<div class='acard' style='text-align:left; font-size:14px; "
                    f"line-height:1.9'>{chips}</div>", unsafe_allow_html=True)
        st.markdown(f"### 종합 추천 지표 · 생육 난이도 최적: {'⭐' * stars}")

        # ── 추천 식물 5종: 사진 아래에서 탭하면 사진에 올라옵니다 ──
        st.markdown("#### 🌿 추천 식물 5종 · 탭하면 사진에 올라옵니다")
        plant_picker(recs, "pick2")
        if mode.startswith("🎚️"):
            _pot = ["토분", "플라스틱(화이트)", "야외용(다크)"]
            ss.pot_style = st.selectbox("🏺 화분 스타일", _pot,
                                        index=_pot.index(ss.get("pot_style", "토분")),
                                        help="일러스트가 도형인 식물의 화분 색에 반영됩니다.")
        st.button("🛒 장바구니 담기", use_container_width=True)
        if st.button("다음 →", type="primary", use_container_width=True):
            ss.space_step = 3; st.rerun()

    else:
        pid = ss.sp_pid
        recs = ss.get("sp_recs") or [pid]
        h = img_hash(ss.sp_img)
        match = ss.get("sp_match", 95 + h % 5)
        st.markdown("<div class='step'>3단계: 나의 최적 식물 & 농원</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='big'>{USER_NAME}님! 이 식물이 당신의 {ss.room}과 "
                    f"{match}% 어울립니다!</div>", unsafe_allow_html=True)

        # 사진 위에 식물 배치 미리보기 (핀치=크기·위치, 요청 8)
        place_stage(pid, key="st4")
        st.markdown("##### 🌿 다른 식물로 바꿔보기 · 탭하면 사진에 올라옵니다")
        plant_picker(recs, "pick4")

        reason = ss.get("sp_reason") or PLANT_DESC.get(
            pid, "이 공간의 채광·규모에 최적화된 추천 식물")
        st.markdown(f"<div class='result'><b style='font-size:20px'>{PLANT_NAMES[pid]}</b><br>"
                    f"{reason}<br>단지 평균가 / 건강 장수 수명 ⭐ 4.9</div>",
                    unsafe_allow_html=True)

        st.markdown("#### 이 식물을 가장 잘 키우고 조경 자재를 보유한 농원")
        b = best_nursery(pid, "fun02")
        if b: best_card(b, pid)
        if st.button("처음부터 다시", use_container_width=True):
            ss.space_step = 1; st.rerun()

# ══════════════ 식물 검색 (취급 회원사 찾기) ══════════════
elif page == "search":
    header()
    home_button(page)
    st.markdown("## 🔎 식물 검색")
    st.caption("① AI가 식물 유형·특징을 소개하고 ② DB에서 취급 농원(재고)을 안내합니다.")

    # 홈에서 넘어온 검색어를 아래 입력창(세션)에 반영
    if ss.get("search_q") and ss.get("_last_sq") != ss.get("search_q"):
        ss._last_sq = ss.search_q
        ss.search_box = ss.search_q
    ss.setdefault("search_box", "")
    term = ss.search_box.strip()

    pid = None
    disp_name = term
    hit_pids = []
    if term:
        hits = [(p, nm) for p, nm in PLANT_NAMES.items() if term in nm]
        hit_pids = [h[0] for h in hits]
        # 새 검색어면 품종 선택 초기화(옵션 불일치 방지)
        if ss.get("search_term_seen") != term:
            ss.search_term_seen = term
            ss.pop("variety_pick", None)
        if hit_pids:
            cur = ss.get("variety_pick")
            pid = cur if cur in hit_pids else hit_pids[0]
            disp_name = PLANT_NAMES[pid]
            # ── 카탈로그 이미지: 식물 검색 아래 · 식물 이름 위 ──
            st.markdown("### 🖼️ 카탈로그 이미지")
            pinch_image(pid)
            # ── 품종 선택 ──
            if len(hit_pids) > 1:
                pid = st.radio("품종 선택", hit_pids,
                               format_func=lambda p: PLANT_NAMES[p],
                               horizontal=True, key="variety_pick")
                disp_name = PLANT_NAMES[pid]

    # ── 식물 이름 (검색 입력) — 카탈로그 이미지 아래 ──
    st.text_input("식물 이름", key="search_box",
                  placeholder="예: 몬스테라, 수국, 필로덴드론 버킨")

    if term:
        # ── ① API(제미나이): 식물 유형·소개 ──────────────────────
        st.markdown("### 🌿 식물 소개")
        show_plant_intro(disp_name, registered=bool(pid))

        # ── ② DB: 취급 농원·재고 ────────────────────────────────
        st.markdown("### 🏪 어느 농원에 있나요")
        if pid:
            show_stock_nurseries(pid)
        else:
            # 미등록 품종 → AI가 뽑은 유사 품종의 농원 안내
            sim = [s for s in ss.get("last_similar", []) if s in NAME_TO_PID][:3]
            if sim:
                st.caption(f"'{term}'은(는) 아직 단지 미취급 품종입니다. "
                           "AI가 추천한 유사 품종의 취급 농원을 안내합니다.")
                for snm in sim:
                    st.markdown(f"**🌿 {snm}** (유사 품종)")
                    show_stock_nurseries(NAME_TO_PID[snm], compact=True)
            else:
                st.info("단지 내 취급 농원 정보가 없습니다. 농원에 직접 문의해 보세요.")

# ══════════════ 회원사 관리자 모드 ══════════════
elif page == "admin":
    header()
    home_button(page)
    st.markdown("## 🔑 회원사 관리자 모드")

    # ── 로그인 상태 관리 ──
    if "admin_nid" not in ss: ss.admin_nid = None
    if "is_master" not in ss: ss.is_master = False

    MASTER_PIN = "0000"   # 상인회 마스터 (시연용)

    # ── 로그아웃 ──
    if ss.admin_nid or ss.is_master:
        who = "상인회 관리자" if ss.is_master else \
              conn.execute("SELECT name FROM nursery WHERE id=?", (ss.admin_nid,)).fetchone()[0]
        c1, c2 = st.columns([3,1])
        c1.success(f"로그인: {who}")
        if c2.button("로그아웃"):
            ss.admin_nid = None; ss.is_master = False; st.rerun()

    # ── 로그인 폼 ──
    if not ss.admin_nid and not ss.is_master:
        st.info("농원을 선택하고 PIN 4자리를 입력하세요. (상인회 관리자는 농원='상인회 관리자' 선택)")
        nlist = conn.execute("SELECT id, name FROM nursery ORDER BY id").fetchall()
        opts = ["(상인회 관리자)"] + [f"{n} ({i})" for i, n in nlist]
        sel = st.selectbox("농원 선택", opts)
        pin = st.text_input("PIN 4자리", max_chars=4, type="password")
        cc1, cc2 = st.columns([1,3])
        if cc1.button("로그인", type="primary"):
            if sel == "(상인회 관리자)":
                if pin == MASTER_PIN:
                    ss.is_master = True; st.rerun()
                else:
                    st.error("마스터 PIN이 올바르지 않습니다.")
            else:
                nid = sel.split("(")[-1].rstrip(")")
                real = conn.execute("SELECT pin FROM nursery WHERE id=?", (nid,)).fetchone()
                if real and pin == real[0]:
                    ss.admin_nid = nid; st.rerun()
                else:
                    st.error("PIN이 올바르지 않습니다.")
        with cc2:
            with st.expander("PIN을 모르나요? (시연용 안내)"):
                st.caption("시연 편의를 위해 각 농원 PIN은 아래에서 확인 가능합니다. "
                           "실서비스에서는 상인회가 개별 발급합니다.")
                if st.checkbox("전체 PIN 표시"):
                    rows = conn.execute("SELECT id, name, pin FROM nursery ORDER BY id LIMIT 100").fetchall()
                    st.dataframe({"농원ID":[r[0] for r in rows],
                                  "이름":[r[1] for r in rows],
                                  "PIN":[r[2] for r in rows]}, height=200)
                st.caption("상인회 관리자 마스터 PIN: 0000")

    # ══ 개별 농원 콘솔 ══
    elif ss.admin_nid:
        nid = ss.admin_nid
        info = conn.execute("SELECT name, tagline, specialty FROM nursery WHERE id=?", (nid,)).fetchone()
        st.markdown(f"### 🏪 {info[0]} 콘솔  ·  {zone_of(nid)}")

        tab1, tab2, tab3 = st.tabs(["🌿 추천 식물 관리", "🏷️ 농원 정보", "📊 내 노출 현황"])

        # --- 추천 식물(재고) 관리 ---
        with tab1:
            st.markdown("#### 현재 등록된 추천 식물")
            rows = conn.execute("""SELECT plant_id, qty, price_min, price_max, updated_at
                FROM stock WHERE nursery_id=? ORDER BY qty DESC""", (nid,)).fetchall()
            if not rows:
                st.caption("아직 등록된 식물이 없습니다. 아래에서 추가하세요.")
            for pid, qty, pmin, pmax, upd in rows:
                pname = PLANT_NAMES.get(pid, pid)
                with st.container():
                    cc = st.columns([3,2,2,2,1.4])
                    cc[0].markdown(f"**{pname}**")
                    nq = cc[1].number_input("재고", 0, 9999, int(qty), key=f"q_{pid}")
                    npmin = cc[2].number_input("최저가", 0, 999999, int(pmin or 0),
                                               step=1000, key=f"pmin_{pid}")
                    npmax = cc[3].number_input("최고가", 0, 999999, int(pmax or 0),
                                               step=1000, key=f"pmax_{pid}")
                    if cc[4].button("💾", key=f"sv_{pid}", help="저장"):
                        conn.execute("""UPDATE stock SET qty=?, price_min=?, price_max=?,
                            updated_at=? WHERE nursery_id=? AND plant_id=?""",
                            (nq, npmin, npmax, datetime.now().isoformat(), nid, pid))
                        conn.commit(); st.toast(f"{pname} 저장됨"); st.rerun()
                    if cc[4].button("🗑", key=f"del_{pid}", help="삭제"):
                        conn.execute("DELETE FROM stock WHERE nursery_id=? AND plant_id=?", (nid, pid))
                        conn.commit(); st.toast(f"{pname} 삭제됨"); st.rerun()

            st.divider()
            st.markdown("#### ➕ 추천 식물 추가")
            have = {r[0] for r in rows}
            avail = [(p, n) for p, n in PLANT_NAMES.items() if p not in have]
            ac = st.columns([3,2,2,2])
            newp = ac[0].selectbox("품종", [p for p, _ in avail],
                                   format_func=lambda p: PLANT_NAMES[p], key="newp")
            newq = ac[1].number_input("재고", 1, 9999, 10, key="newq")
            newmin = ac[2].number_input("최저가", 0, 999999, 15000, step=1000, key="newmin")
            newmax = ac[3].number_input("최고가", 0, 999999, 45000, step=1000, key="newmax")
            if st.button("추가하기", type="primary"):
                conn.execute("""INSERT INTO stock(nursery_id, plant_id, qty, price_min, price_max, updated_at)
                    VALUES(?,?,?,?,?,?)""",
                    (nid, newp, newq, newmin, newmax, datetime.now().isoformat()))
                conn.commit(); st.toast(f"{PLANT_NAMES[newp]} 추가됨"); st.rerun()

        # --- 농원 정보 ---
        with tab2:
            tl = st.text_input("대표 문구 (앱에 노출)", value=info[1] or "",
                               placeholder="예: 30년 전통 대형 관엽 전문")
            sp = st.text_input("전문 분야", value=info[2] or "",
                               placeholder="예: 관엽/분갈이")
            if st.button("농원 정보 저장", type="primary"):
                conn.execute("UPDATE nursery SET tagline=?, specialty=? WHERE id=?",
                             (tl, sp, nid)); conn.commit()
                st.success("저장되었습니다.")
            st.divider()
            newpin = st.text_input("PIN 변경 (4자리)", max_chars=4, type="password")
            if st.button("PIN 변경") and len(newpin) == 4 and newpin.isdigit():
                conn.execute("UPDATE nursery SET pin=? WHERE id=?", (newpin, nid))
                conn.commit(); st.success("PIN이 변경되었습니다.")

        # --- 내 노출 현황 ---
        with tab3:
            n_nur = conn.execute("SELECT COUNT(*) FROM nursery").fetchone()[0] or 1
            mine = conn.execute("SELECT COALESCE(SUM(cnt),0) FROM dispatch_log WHERE nursery_id=?",
                                (nid,)).fetchone()[0]
            allc = conn.execute("SELECT COALESCE(SUM(cnt),0) FROM dispatch_log").fetchone()[0]
            avg = allc / n_nur if allc else 0
            mystock = conn.execute("SELECT COUNT(DISTINCT plant_id) FROM stock WHERE nursery_id=?",
                                   (nid,)).fetchone()[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("누적 추천 노출", f"{mine}회")
            c2.metric("단지 평균 대비", f"{(mine/avg*100 if avg else 0):.0f}%")
            c3.metric("등록 식물 수", f"{mystock}종")
            st.caption("재고를 많이·자주 등록할수록 추천 노출 기회가 늘어납니다. "
                       "추천 분배는 재고량과 최근 배정 이력으로 실시간 계산됩니다.")

    # ══ 상인회 마스터 대시보드 ══
    elif ss.is_master:
        st.markdown("### 📊 상인회 통합 대시보드")
        counts = dict(conn.execute(
            "SELECT nursery_id, COALESCE(SUM(cnt),0) FROM dispatch_log GROUP BY nursery_id"
            ).fetchall())
        allids = [r[0] for r in conn.execute("SELECT id FROM nursery").fetchall()]
        vals = [counts.get(i, 0) for i in allids]
        import numpy as _np
        def _gini(x):
            x = _np.sort(_np.array(x, float)); n = len(x)
            if n == 0 or x.sum() == 0: return 0.0
            cum = _np.cumsum(x); return float((n + 1 - 2*(cum/cum[-1]).sum())/n)
        g = _gini(vals)
        cov = sum(1 for v in vals if v > 0) / len(allids)
        c1, c2, c3 = st.columns(3)
        c1.metric("지니계수", f"{g:.3f}", "목표 ≤0.35 " + ("✅" if g <= 0.35 else "⚠️"))
        c2.metric("커버리지", f"{cov*100:.0f}%", "목표 ≥85% " + ("✅" if cov >= 0.85 else "⚠️"))
        c3.metric("누적 추천 노출", f"{sum(vals)}회")
        st.divider()
        st.markdown("#### 농원별 노출 · 등록 식물 수 (상위/하위)")
        stat = conn.execute("""SELECT n.id, n.name, COUNT(DISTINCT s.plant_id) plants,
            COALESCE(SUM(s.qty),0) stock FROM nursery n
            LEFT JOIN stock s ON s.nursery_id=n.id GROUP BY n.id""").fetchall()
        stat = sorted(stat, key=lambda r: counts.get(r[0], 0), reverse=True)
        rows_show = stat[:8] + [("...","...","...","...")] + stat[-5:]
        st.dataframe({
            "농원":[f"{r[1]}" if r[0]!="..." else "..." for r in rows_show],
            "등록식물":[r[2] for r in rows_show],
            "총재고":[r[3] for r in rows_show],
            "추천노출":[counts.get(r[0],0) if r[0]!="..." else "..." for r in rows_show],
        }, height=430)
        st.caption("미등록·저노출 농원을 파악해 재고 등록을 독려하세요. "
                   "노출 편중이 심하면(지니↑) 알고리즘이 자동 보정합니다.")

        # ── 🏪 농원 직접 등록·편집 (이름·주소 등 수기 입력) ──
        st.divider()
        st.markdown("#### 🏪 농원 직접 등록·편집")
        ZONE_OPTS = ["A동", "B동", "C동", "D동", "E동", "노지구역"]
        _ensure_admin_columns(conn)   # 주소·전화 컬럼 보장(구 DB 방어)

        # ── 📄 CSV 일괄 등록·수정 (폴더의 농원등록_양식.csv를 항상 기본값으로 참조) ──
        with st.expander("📄 CSV 파일로 일괄 등록·수정 (엑셀)", expanded=False):
            # 폴더 CSV 자동 반영 상태
            if _DEFAULT_CSV_RESULT and "error" not in _DEFAULT_CSV_RESULT:
                st.success(f"✅ 폴더의 **농원등록_양식.csv**를 기본값으로 자동 반영 중 "
                           f"(농원 {_DEFAULT_CSV_RESULT['nurseries']}곳 · "
                           f"취급식물 {_DEFAULT_CSV_RESULT['stocks']}건). 재시작해도 자동 복원됩니다.")
            elif _DEFAULT_CSV_RESULT and "error" in _DEFAULT_CSV_RESULT:
                st.warning(f"폴더 농원등록_양식.csv 읽기 오류: {_DEFAULT_CSV_RESULT['error']}")
            else:
                st.info("폴더에 **농원등록_양식.csv**가 아직 없습니다. 아래에서 업로드하면 "
                        "이 이름으로 저장되어 항상 기본값으로 참조됩니다. (영구 보관은 레포 커밋)")
            st.caption("엑셀에서 농원·취급식물을 표로 작성해 한 번에 등록/수정합니다. "
                       "같은 농원은 취급식물별로 여러 줄로 적으세요. "
                       "(한글 인코딩·쉼표/탭 자동 인식, 농원ID 비우면 자동 생성)")
            _sample = (
                "농원명,농원ID,구역,PIN,주소,대표전화,전문분야,소개문구,취급식물명,재고수량,최저가,최고가\n"
                "행복농원,N901,A동,1234,대구 동구 불로동 123-4,053-111-2222,관엽,30년 전통 관엽 전문,몬스테라,20,15000,45000\n"
                "행복농원,N901,A동,1234,대구 동구 불로동 123-4,053-111-2222,관엽,30년 전통 관엽 전문,스킨답서스,15,8000,20000\n"
                "초록뜰,N902,B동,5678,대구 동구 불로동 200-1,053-333-4444,다육,다육·선인장 전문,금전수,12,10000,30000\n"
            ).encode("utf-8-sig")
            _dl_bytes, _dl_label = _sample, "⬇️ 빈 양식(템플릿) CSV 내려받기"
            if os.path.exists(NURSERY_CSV_PATH):     # 폴더에 파일 있으면 그걸 편집용으로 제공
                try:
                    with open(NURSERY_CSV_PATH, "rb") as _f:
                        _dl_bytes = _f.read()
                    _dl_label = "⬇️ 현재 폴더의 농원등록_양식.csv 내려받기(편집용)"
                except Exception:
                    pass
            st.download_button(_dl_label, _dl_bytes, file_name="농원등록_양식.csv",
                               mime="text/csv", use_container_width=True)
            up = st.file_uploader("작성한 CSV 업로드", type=["csv"], key="nur_csv_up")
            if up is not None:
                raw = up.getvalue()
                try:
                    parsed = parse_nurseries_csv(raw)
                except Exception as e:
                    st.error(f"CSV를 읽지 못했습니다: {e}"); parsed = None
                if parsed is not None:
                    st.info(f"인식 결과 — 농원 {len(parsed['nurseries'])}곳 · "
                            f"취급식물 {len(parsed['stocks'])}건 · "
                            f"인코딩 {parsed['encoding']} · 구분자 {parsed['delimiter']}")
                    if parsed["headers"]:
                        st.caption("인식된 열: " + ", ".join(parsed["headers"]))
                    for w in parsed["warnings"][:8]:
                        st.warning(w)
                    if parsed["nurseries"]:
                        _prev = list(parsed["nurseries"].items())[:12]
                        st.dataframe({
                            "농원ID": [k for k, _ in _prev],
                            "농원명": [v[0] for _, v in _prev],
                            "구역":  [v[1] for _, v in _prev],
                            "주소":  [v[5] for _, v in _prev],
                        }, use_container_width=True)
                    repl = st.checkbox("⚠️ 기존 농원·재고 전체 삭제 후 이 파일로 교체",
                                       value=False, key="nur_csv_replace")
                    _save = st.checkbox("💾 이 파일을 폴더의 농원등록_양식.csv로 저장(항상 기본값 참조)",
                                        value=True, key="nur_csv_save")
                    if st.button("📥 이 CSV로 등록/수정 실행", type="primary",
                                 use_container_width=True, key="nur_csv_import"):
                        res = import_nurseries_csv(raw, replace=repl, parsed=parsed)
                        saved = False
                        if _save:
                            try:
                                with open(NURSERY_CSV_PATH, "wb") as _f:
                                    _f.write(raw)
                                _load_default_nursery_csv.clear()   # 다음 시작 시 재로드
                                saved = True
                            except Exception as e:
                                st.warning(f"폴더 저장 실패(읽기전용 환경일 수 있음): {e}")
                        st.success(f"✅ 완료 — 농원 {res['nurseries']}곳, "
                                   f"취급식물 {res['stocks']}건 반영"
                                   + (" · 농원등록_양식.csv 저장됨" if saved else ""))
                        if saved:
                            st.info("영구 보관하려면 이 **농원등록_양식.csv**를 GitHub 레포에 커밋하세요. "
                                    "(Streamlit Cloud는 재시작 시 임시 파일이 사라질 수 있어, "
                                    "레포에 커밋해야 재배포 후에도 유지됩니다.)")
                        for w in res["warnings"][:8]:
                            st.warning(w)
                        st.rerun()

        with st.expander("➕ 새 농원 등록", expanded=False):
            with st.form("new_nursery", clear_on_submit=True):
                fc = st.columns([2, 1])
                nn_name = fc[0].text_input("농원명 *")
                nn_id = fc[1].text_input("농원ID(비우면 자동)", placeholder="자동")
                fc1 = st.columns([2, 1])
                nn_addr = fc1[0].text_input("주소", placeholder="예: 대구 동구 불로동 000-0")
                nn_phone = fc1[1].text_input("대표 전화번호", placeholder="예: 053-000-0000")
                fc2 = st.columns(3)
                nn_zone = fc2[0].selectbox("구역", ZONE_OPTS)
                nn_pin = fc2[1].text_input("PIN(4자리)", max_chars=4)
                nn_spec = fc2[2].text_input("전문분야", placeholder="예: 관엽")
                nn_tag = st.text_input("소개문구", placeholder="예: 30년 전통 관엽 전문")
                if st.form_submit_button("등록", type="primary"):
                    if not nn_name.strip():
                        st.error("농원명은 필수입니다.")
                    else:
                        nid = nn_id.strip() or _next_nursery_id()
                        conn.execute(
                            "INSERT INTO nursery(id,name,zone,pin,tagline,specialty,"
                            "address,phone) VALUES(?,?,?,?,?,?,?,?) "
                            "ON CONFLICT(id) DO UPDATE SET "
                            "name=excluded.name, zone=excluded.zone, pin=excluded.pin, "
                            "tagline=excluded.tagline, specialty=excluded.specialty, "
                            "address=excluded.address, phone=excluded.phone",
                            (nid, nn_name.strip(), nn_zone, nn_pin.strip(),
                             nn_tag.strip(), nn_spec.strip(), nn_addr.strip(),
                             nn_phone.strip()))
                        conn.commit()
                        ss.reg_msg = f"✅ '{nn_name.strip()}' ({nid}) 등록 완료"
                        st.rerun()
        if ss.get("reg_msg"):
            st.success(ss.pop("reg_msg"))

        # 기존 농원 편집 / 삭제
        nlist = conn.execute("SELECT id, name FROM nursery ORDER BY id").fetchall()
        if nlist:
            esel = st.selectbox("편집할 농원 선택", [f"{n} ({i})" for i, n in nlist],
                                key="edit_nur_sel")
            enid = esel.split("(")[-1].rstrip(")")
            cur = conn.execute(
                "SELECT name, COALESCE(address,''), zone, COALESCE(pin,''), "
                "COALESCE(tagline,''), COALESCE(specialty,''), COALESCE(phone,'') "
                "FROM nursery WHERE id=?", (enid,)).fetchone()
            ec = st.columns([2, 1])
            e_name = ec[0].text_input("농원명", value=cur[0], key=f"en_{enid}")
            e_zone = ec[1].selectbox("구역", ZONE_OPTS,
                                     index=ZONE_OPTS.index(cur[2]) if cur[2] in ZONE_OPTS else 0,
                                     key=f"ez_{enid}")
            ec1 = st.columns([2, 1])
            e_addr = ec1[0].text_input("주소", value=cur[1], key=f"ea_{enid}")
            e_phone = ec1[1].text_input("대표 전화번호", value=cur[6], key=f"eph_{enid}")
            ec2 = st.columns(2)
            e_spec = ec2[0].text_input("전문분야", value=cur[5], key=f"es_{enid}")
            e_pin = ec2[1].text_input("PIN(4자리)", value=cur[3], max_chars=4, key=f"ep_{enid}")
            e_tag = st.text_input("소개문구", value=cur[4], key=f"et_{enid}")
            bc = st.columns(2)
            if bc[0].button("💾 저장", type="primary", key=f"esave_{enid}",
                            use_container_width=True):
                conn.execute("UPDATE nursery SET name=?, address=?, phone=?, zone=?, "
                             "pin=?, tagline=?, specialty=? WHERE id=?",
                             (e_name.strip(), e_addr.strip(), e_phone.strip(), e_zone,
                              e_pin.strip(), e_tag.strip(), e_spec.strip(), enid))
                conn.commit(); st.success("저장되었습니다."); st.rerun()
            if bc[1].button("🗑 이 농원 삭제", key=f"edel_{enid}", use_container_width=True):
                conn.execute("DELETE FROM stock WHERE nursery_id=?", (enid,))
                conn.execute("DELETE FROM nursery WHERE id=?", (enid,))
                conn.commit(); st.warning(f"{enid} 삭제됨"); st.rerun()

            # ── 이 농원에 재고(취급 식물) 바로 등록 → 검색과 즉시 매칭 ──
            st.markdown("##### 🌿 이 농원의 취급 식물(재고) 등록")
            st.caption("여기서 재고를 넣어야 식물 검색 결과에 이 농원이 표시됩니다.")
            my_stock = conn.execute(
                "SELECT plant_id, qty FROM stock WHERE nursery_id=? ORDER BY qty DESC",
                (enid,)).fetchall()
            if my_stock:
                st.caption("현재 등록: " + " · ".join(
                    f"{PLANT_NAMES.get(p, p)} {q}개" for p, q in my_stock[:8])
                    + (" 외" if len(my_stock) > 8 else ""))
            sc = st.columns([3, 1.4, 1.6, 1.6, 1.2])
            sp_pid2 = sc[0].selectbox("품종", list(PLANT_NAMES.keys()),
                                      format_func=lambda p: PLANT_NAMES[p],
                                      key=f"mstk_p_{enid}")
            sp_q = sc[1].number_input("재고", 0, 9999, 10, key=f"mstk_q_{enid}")
            sp_min = sc[2].number_input("최저가", 0, 999999, 15000, step=1000,
                                        key=f"mstk_min_{enid}")
            sp_max = sc[3].number_input("최고가", 0, 999999, 45000, step=1000,
                                        key=f"mstk_max_{enid}")
            if sc[4].button("등록", key=f"mstk_add_{enid}", type="primary"):
                conn.execute(
                    "INSERT INTO stock(nursery_id,plant_id,qty,price_min,price_max,"
                    "updated_at) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(nursery_id,plant_id) DO UPDATE SET qty=excluded.qty, "
                    "price_min=excluded.price_min, price_max=excluded.price_max, "
                    "updated_at=excluded.updated_at",
                    (enid, sp_pid2, sp_q, sp_min, sp_max,
                     datetime.now().strftime("%Y-%m")))
                conn.commit()
                st.toast(f"{PLANT_NAMES[sp_pid2]} {sp_q}개 등록"); st.rerun()

        # ── 💾 현재 DB 백업(CSV) — 앱 재시작 시 데이터 소실 대비 ──
        st.divider()
        st.markdown("#### 💾 현재 농원·재고 백업")
        st.caption("배포 환경은 앱 재시작 시 DB가 초기화될 수 있습니다. "
                   "수정 후 이 백업 CSV를 내려받아 두면, 초기화돼도 그대로 다시 업로드해 복구할 수 있습니다.")
        import io as _io2, csv as _csv2
        _buf = _io2.StringIO()
        _w = _csv2.writer(_buf)
        _w.writerow(["농원ID", "농원명", "주소", "대표전화", "구역", "소개문구",
                     "전문분야", "PIN", "취급식물명", "취급식물ID", "재고수량",
                     "최저가", "최고가"])
        _ensure_admin_columns(conn)
        for r in conn.execute("""
            SELECT n.id, n.name, COALESCE(n.address,''), COALESCE(n.phone,''), n.zone,
                   COALESCE(n.tagline,''), COALESCE(n.specialty,''), COALESCE(n.pin,''),
                   s.plant_id, s.qty, COALESCE(s.price_min,0), COALESCE(s.price_max,0)
            FROM nursery n LEFT JOIN stock s ON s.nursery_id = n.id
            ORDER BY n.id, s.qty DESC""").fetchall():
            _w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                         PLANT_NAMES.get(r[8], "") if r[8] else "",
                         r[8] or "", r[9] or "", r[10] or "", r[11] or ""])
        st.download_button("⬇️ 현재 농원·재고 전체 CSV 내려받기",
                           ("\ufeff" + _buf.getvalue()).encode("utf-8"),
                           file_name=f"농원백업_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                           mime="text/csv", use_container_width=True)

        # ── 📁 농원·재고 CSV 일괄 업로드 ──
        st.divider()
        st.markdown("#### 📁 농원·재고 CSV 업로드")
        st.caption("양식을 채워 올리면 농원과 취급 식물이 한 번에 등록됩니다. "
                   "같은 농원ID의 여러 줄은 한 농원의 여러 취급식물로 묶입니다.")
        _tmpl = ("농원ID,농원명,주소,대표전화,구역,소개문구,전문분야,PIN,취급식물명,취급식물ID,재고수량,최저가,최고가\n"
                 "N001,불로원예,대구 동구 불로동 12-3,053-111-2222,A동,50년 전통 관엽·대형목 전문,관엽·대형목,1234,몬스테라,P001,12,25000,80000\n"
                 "N001,불로원예,대구 동구 불로동 12-3,053-111-2222,A동,50년 전통 관엽·대형목 전문,관엽·대형목,1234,올리브나무,,5,120000,300000\n"
                 "N002,그린가든,대구 동구 불로동 45,053-333-4444,B동,다육·선인장 특화,다육·선인장,5678,스투키,,30,8000,20000\n")
        st.download_button("⬇️ 빈 양식(CSV) 내려받기", ("\ufeff" + _tmpl).encode("utf-8"),
                           file_name="농원_취급식물_양식.csv", mime="text/csv",
                           use_container_width=True)
        up_csv = st.file_uploader("작성한 CSV 파일 선택", type=["csv"], key="nur_csv")
        parsed = None
        if up_csv is not None:
            # ── 파일을 고르면 즉시 파싱 미리보기 (DB 반영 전) ──
            try:
                parsed = parse_nurseries_csv(up_csv.getvalue())
                st.info(f"🔎 미리보기 — 인코딩: {parsed['encoding']} · "
                        f"구분자: {parsed['delimiter']} · "
                        f"농원 **{len(parsed['nurseries'])}곳** · "
                        f"취급식물 **{len(parsed['stocks'])}건** 인식됨")
                st.caption("인식된 헤더: " + ", ".join(parsed["headers"]))
                if parsed["nurseries"]:
                    prev = [(nid, v[0], v[5], v[6]) for nid, v
                            in list(parsed["nurseries"].items())[:5]]
                    st.dataframe({"농원ID": [p[0] for p in prev],
                                  "농원명": [p[1] for p in prev],
                                  "주소": [p[2] for p in prev],
                                  "대표전화": [p[3] for p in prev]},
                                 use_container_width=True, height=len(prev)*38+40)
                else:
                    st.warning("⚠️ 농원이 0곳 인식됐습니다. '농원명' 또는 '농원ID' "
                               "열 이름이 정확한지 위 헤더 목록과 비교해 보세요.")
                if parsed["warnings"]:
                    with st.expander(f"⚠️ 파싱 경고 {len(parsed['warnings'])}건"):
                        for w in parsed["warnings"][:80]:
                            st.caption("· " + w)
            except Exception as e:
                import traceback as _tb
                st.error(f"파일 읽기 실패: {type(e).__name__} — {e}")
                st.code(_tb.format_exc()[-600:])
        rep = st.checkbox("기존 농원·재고를 모두 지우고 새로 등록(전체 교체)", value=False,
                          help="체크하면 시연용 데모 농원 전체를 포함해 전부 삭제 후 등록합니다.")
        if parsed and parsed["nurseries"] and st.button(
                "업로드 실행 (DB 반영)", type="primary", use_container_width=True):
            try:
                ss.last_import = import_nurseries_csv(up_csv.getvalue(),
                                                      replace=rep, parsed=parsed)
            except Exception as e:
                import traceback as _tb
                ss.last_import = {"error": f"{type(e).__name__} — {str(e)[:300]}",
                                  "trace": _tb.format_exc()[-800:]}
            st.rerun()   # 대시보드 지표·표를 새 데이터로 갱신
        li = ss.get("last_import")
        if li:
            if li.get("error"):
                st.error(f"업로드 실패: {li['error']}")
                if li.get("trace"):
                    st.code(li["trace"])
            elif li["nurseries"] == 0:
                st.warning("⚠️ 등록된 농원이 없습니다. 파일 형식(CSV UTF-8)과 헤더를 확인하세요.")
            else:
                st.success(f"✅ 농원 {li['nurseries']}곳 · 취급식물 {li['stocks']}건 등록 완료")
            if li.get("warnings"):
                with st.expander(f"⚠️ 안내·경고 {len(li['warnings'])}건"):
                    for w in li["warnings"][:80]:
                        st.caption("· " + w)
        st.caption("※ 배포 환경(Streamlit Cloud)은 앱 재시작 시 DB가 초기화될 수 있으니, "
                   "영구 보관은 CSV 원본을 별도 보관하세요. 한글 윈도우 엑셀은 "
                   "‘다른 이름으로 저장 → CSV UTF-8’로 저장하면 가장 안전합니다.")

# ══════════════ 건강 진단 ══════════════
elif page == "diag":
    header()
    home_button(page)
    st.markdown("## 🔍 식물 건강 진단")
    t1, t2 = st.tabs(["📷 카메라로 촬영", "📁 파일 업로드"])
    with t1:
        st.caption("잎 부분을 가까이 대고 찍어주세요")
        cam = camera_capture("diag", front_default=False)  # ◀ 잎 촬영은 후면 기본
    with t2: fil = st.file_uploader("시든 식물 사진", type=["jpg", "jpeg", "png"])
    up = cam or fil
    if up and st.button("🩺 진단하기", type="primary", use_container_width=True):
        b = up.getvalue(); st.image(b, width=230)
        ai = None
        if gemini_on():
            try:
                with st.spinner("🤖 Gemini가 식물 상태를 진단하는 중..."):
                    ai = gm.diagnose(api_key, b)
            except Exception as e:
                st.warning(f"Gemini 호출 실패 — 목업 모드로 대체 ({type(e).__name__})")
        if ai:
            cls = ai.get("diagnosis", "정상")
            conf = int(ai.get("confidence", 70))
            rx = (f"[즉시] {ai.get('prescription_now','')}<br>"
                  f"[1주 관리] {ai.get('prescription_week','')}<br>"
                  f"[필요 자재] {ai.get('materials','')}")
            guess = ai.get("plant_guess", "")
            need_repot = bool(ai.get("needs_repotting"))
            tag = " · 🤖 Gemini"
        else:
            cls, rx = DIAG_CLASSES[img_hash(b) % len(DIAG_CLASSES)]
            conf = 62 + img_hash(b) % 33
            guess = ""; need_repot = (cls == "분갈이 필요"); tag = " · 목업"
        st.markdown(f"<div class='result'><b style='font-size:18px'>진단: {cls}</b> "
                    f"<span style='color:#777'>(신뢰도 {conf}%{tag})</span>"
                    + (f"<br>추정 식물: {guess}" if guess else "")
                    + f"<br><br><b>💊 처방</b><br>{rx}</div>", unsafe_allow_html=True)
        if need_repot:
            nb = best_nursery("P241", "fun03")
            if nb:
                st.info("🪴 분갈이·화분 특화 농원과 연결해 드립니다.")
                best_card(nb, "P241")
        if conf < 70:
            st.warning("신뢰도가 낮습니다. 단지 내 전문가 상담을 권장합니다.")
        st.caption("※ 본 진단은 참고용이며 실제 상태와 다를 수 있습니다.")

# ══════════════ 농원 지도 ══════════════
elif page == "map":
    header()
    home_button(page)
    st.markdown("## 🗺️ 농원 지도 (불로화훼단지)")
    try:
        rows = conn.execute("SELECT id, name, COALESCE(address,''), COALESCE(phone,''), zone "
                            "FROM nursery ORDER BY id").fetchall()
    except sqlite3.OperationalError:
        _ensure_admin_columns(conn)
        rows = conn.execute("SELECT id, name, COALESCE(address,''), COALESCE(phone,''), zone "
                            "FROM nursery ORDER BY id").fetchall()
    if not rows:
        st.info("등록된 농원이 없습니다.")
    else:
        # 농원별 '고정' 좌표(ID 해시 기반) — 재렌더에도 자리가 안 흔들림
        def _coord(nid):
            h = int(hashlib.md5(nid.encode()).hexdigest(), 16)
            return (35.9258 + ((h % 1000) / 1000 - 0.5) * 0.004,
                    128.6390 + (((h // 997) % 1000) / 1000 - 0.5) * 0.006)
        info = {i: (n, a, p, z) for i, n, a, p, z in rows}

        # 먼저 선택 → 그 값으로 지도를 그린다(선택이 지도에 반영되도록 순서 중요)
        sel = st.selectbox("농원 선택", [f"{n} ({i})" for i, n, *_ in rows], key="map_sel")
        sel_id = sel.split("(")[-1].rstrip(")")
        slat, slon = _coord(sel_id)

        pts = []
        for i, n, a, p, z in rows:
            la, lo = _coord(i)
            is_sel = (i == sel_id)
            pts.append({"name": n, "id": i, "lat": la, "lon": lo,
                        "color": [231, 76, 60] if is_sel else [46, 125, 50],
                        "rad": 34 if is_sel else 15})
        try:
            import pydeck as pdk
            layer = pdk.Layer(
                "ScatterplotLayer", data=pts, get_position="[lon, lat]",
                get_fill_color="color", get_radius="rad",
                radius_min_pixels=6, radius_max_pixels=40, pickable=True,
                stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1)
            view = pdk.ViewState(latitude=slat, longitude=slon, zoom=16, pitch=0)
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                layers=[layer], initial_view_state=view,
                tooltip={"text": "{name} ({id})"}), use_container_width=True)
        except Exception:
            # pydeck 미지원 환경 폴백: 선택 농원을 빨간 큰 점으로 강조한 기본 지도
            import pandas as _pd
            df = _pd.DataFrame({"lat": [p["lat"] for p in pts],
                                "lon": [p["lon"] for p in pts],
                                "color": [p["color"] for p in pts],
                                "size": [p["rad"] for p in pts]})
            st.map(df, latitude="lat", longitude="lon", color="color", size="size")

        n, a, p, z = info[sel_id]
        addr = a or f"{z} · 불로화훼단지"
        tel = f"📞 <a href='tel:{p}' style='color:#e91e63;text-decoration:none;font-weight:700'>{p}</a>" if p else "📞 053-000-0000"
        st.markdown(f"<div class='nursery'>🌿 <b>{n}</b> ({sel_id})<br>"
                    f"📍 {addr} · {tel}<br>영업 09:00~18:00 · QR 스탬프 입구 부착</div>",
                    unsafe_allow_html=True)

# ══════════════ 분갈이 특화 ══════════════
elif page == "repot":
    header()
    home_button(page)
    st.markdown("## 🪴 분갈이·화분 특화 농원")
    for nid, name in conn.execute(
            "SELECT id, name FROM nursery ORDER BY RANDOM() LIMIT 6").fetchall():
        st.markdown(f"<div class='nursery'>🪴 <b>{name}</b> ({nid}) · {zone_of(nid)}<br>"
                    f"분갈이 서비스 5,000원~ · 수제 토분 취급 · 📞 예약 문의</div>",
                    unsafe_allow_html=True)

# ══════════════ 내 식물 관리 (물·영양) ══════════════
elif page == "care":
    header()
    home_button(page)
    st.markdown("## 💧 내 식물 관리")
    st.caption("우리 집 식물의 물 주기·영양제 일정을 관리하세요.")

    # 데모용 초기 식물 2개 (세션 유지)
    if "myplants" not in ss:
        ss.myplants = [
            {"name": "거실 몬스테라", "pid": "P001", "water_cycle": 7,  "feed_cycle": 30,
             "last_water": date.today() - timedelta(days=6),
             "last_feed":  date.today() - timedelta(days=25)},
            {"name": "베란다 다육이", "pid": "P241", "water_cycle": 14, "feed_cycle": 45,
             "last_water": date.today() - timedelta(days=3),
             "last_feed":  date.today() - timedelta(days=10)},
        ]

    # ── 새 식물 등록 ──
    with st.expander("➕ 새 식물 등록"):
        nm = st.text_input("별명 (예: 안방 스투키)", key="care_nm")
        sp = st.selectbox("품종", list(PLANT_NAMES.values()), key="care_sp")
        wc = st.slider("물 주기 (일)", 3, 30, 7, key="care_wc")
        fc = st.slider("영양제 주기 (일)", 14, 90, 30, key="care_fc")
        if st.button("등록", type="primary", key="care_add") and nm:
            ss.myplants.append({"name": nm, "pid": pid_of(sp, "P001"),
                                "water_cycle": wc, "feed_cycle": fc,
                                "last_water": date.today(), "last_feed": date.today()})
            st.success(f"'{nm}' 등록 완료!")
            st.rerun()

    st.write("")
    today = date.today()
    for i, pl in enumerate(ss.myplants):
        d_w = (today - pl["last_water"]).days
        d_f = (today - pl["last_feed"]).days
        left_w = pl["water_cycle"] - d_w
        left_f = pl["feed_cycle"] - d_f
        w_stat = ("🔴 오늘 물 주세요!" if left_w <= 0 else
                  f"💧 물까지 {left_w}일 남음")
        f_stat = ("🟠 영양제 줄 때!" if left_f <= 0 else
                  f"🧪 영양까지 {left_f}일 남음")
        st.markdown(f"""<div class='acard'>
            <span class='t'>🪴 {pl['name']}</span>
            <span style='color:#888;font-size:12px'> · {PLANT_NAMES.get(pl['pid'],'')}</span><br>
            <span class='s'>{w_stat} (주기 {pl['water_cycle']}일) &nbsp;|&nbsp; {f_stat} (주기 {pl['feed_cycle']}일)</span>
            </div>""", unsafe_allow_html=True)
        st.progress(min(max(d_w / pl["water_cycle"], 0.0), 1.0),
                    text=f"마지막 물: {pl['last_water']} ({d_w}일 전)")
        c1, c2, c3 = st.columns(3)
        if c1.button("💧 물 줬어요", key=f"w_{i}", use_container_width=True):
            pl["last_water"] = today; st.rerun()
        if c2.button("🧪 영양제 줬어요", key=f"f_{i}", use_container_width=True):
            pl["last_feed"] = today; st.rerun()
        if c3.button("🗑 삭제", key=f"d_{i}", use_container_width=True):
            ss.myplants.pop(i); st.rerun()
        st.write("")

    # 물/영양 관련 자재 → 단지 농원 연결 (트래픽 분배)
    st.markdown("#### 🏪 영양제·급수 용품이 필요하면")
    b = best_nursery("P241", "care") if 'best_nursery' in dir() else None
    pairs = pick_nurseries("P241", 2, "care")
    show_nurseries(pairs, "P241")

