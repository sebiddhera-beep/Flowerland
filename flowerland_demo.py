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
                   layout="centered", initial_sidebar_state="collapsed")
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
.block-container {{ max-width: 480px; padding-top: 1.0rem; }}
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

/* ── 모바일 대응 (갤럭시 S24: 뷰포트 약 384px) ─────────────────────
   Streamlit은 좁은 화면에서 컬럼을 세로로 쌓아버리므로,
   배너 2열·아이콘 4열·TOP5 5열이 목업처럼 가로로 유지되게 강제한다. */
[data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
    gap: 8px !important;
    overflow-x: auto;              /* TOP5 등은 좌우 스와이프 */
    -webkit-overflow-scrolling: touch;
}}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    min-width: 0 !important;
    flex: 1 1 0 !important;
}}
@media (max-width: 640px) {{
    .block-container {{ padding-left: .7rem; padding-right: .7rem; padding-top: .6rem; }}
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
# 식물 마스터 1001종: plants_master.csv (PID·한글명·영문명·학명) 을 로드.
# dispatch.db 는 이 PID 체계로 traffic_dispatch.seed() 가 재고를 생성한다.
import csv as _csv

_MASTER = []                 # [{pid,korean,english_common,scientific,category}, ...]
_MASTER_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plants_master.csv")
try:
    with open(_MASTER_CSV, encoding="utf-8") as _f:
        for _r in _csv.DictReader(_f):
            _MASTER.append(_r)
except FileNotFoundError:
    # CSV가 없을 때의 최소 폴백(앱이 죽지 않게)
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
INDOOR_RECS  = {"거실": ["P001", "P004", "P227"], "침실": ["P008", "P002", "P005"],
                "사무실": ["P006", "P002", "P008"]}
OUTDOOR_RECS = {"베란다": ["P010", "P365", "P241"], "정원": ["P416", "P591", "P752"],
                "테라스": ["P416", "P011", "P752"]}
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
    scols = [r[1] for r in conn.execute("PRAGMA table_info(stock)").fetchall()]
    if "price_min" not in scols:
        conn.execute("ALTER TABLE stock ADD COLUMN price_min INTEGER DEFAULT 0")
    if "price_max" not in scols:
        conn.execute("ALTER TABLE stock ADD COLUMN price_max INTEGER DEFAULT 0")
    conn.commit()

conn = get_conn()

def zone_of(nid):
    n = int(nid[1:])
    return f"{'ABCD'[n % 4]}-{n % 20 + 1:02d} 구역"

def best_nursery(pid, source):
    """실제 트래픽 분배 알고리즘으로 최우수 매칭 농원 1곳 선정"""
    ids = td.select_nurseries(conn, pid, k=1, source=source)
    if not ids:
        return None
    nid = ids[0]
    name = conn.execute("SELECT name FROM nursery WHERE id=?", (nid,)).fetchone()[0]
    qty = conn.execute("SELECT qty FROM stock WHERE nursery_id=? AND plant_id=?",
                       (nid, pid)).fetchone()
    return {"id": nid, "name": name, "zone": zone_of(nid),
            "qty": qty[0] if qty else 0,
            "recs": 2800 + int(hashlib.md5(nid.encode()).hexdigest(), 16) % 900}

def kakao_map_url(nursery_name):
    """농원 이름 + 불로화훼단지 주소로 카카오맵 검색 링크 생성.
    좌표(위경도) 없이도 동작. 앱 없어도 브라우저에서 열림.
    나중에 nursery 테이블에 lat/lng 컬럼을 넣으면
    https://map.kakao.com/link/to/{이름},{위도},{경도} 방식으로 교체 가능."""
    q = urllib.parse.quote(f"{nursery_name} 대구 동구 불로동 화훼단지")
    return f"https://map.kakao.com/?q={q}"

def best_card(b, pid):
    st.markdown(f"""<div class='best'>
      <span class='tag'>최우수 매칭 농원</span><br>
      <b style='font-size:19px'>🌿 {b['name']}</b> <span style='color:#777'>({b['id']})</span><br>
      <span style='font-size:14px'>
      ✅ 전문성: {PLANT_NAMES.get(pid, pid)} 재배 우수<br>
      📍 위치: {b['zone']} (지도 보기)<br>
      🎁 특별 서비스: 현장 화분 매칭 및 무료 분갈이 가능<br>
      👍 추천 횟수: {b['recs']:,}+ · 재고 {b['qty']}개</span></div>""",
      unsafe_allow_html=True)
    # 카카오맵 길안내: st.button은 링크를 못 열므로 a태그 버튼으로 표시
    kurl = kakao_map_url(b['name'])
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

def clickable_image(path, key, aspect="351/416", fit="100% 100%"):
    """이미지 전체가 버튼으로 동작. 클릭하면 True 반환 (세션 유지됨).
    fit="contain"이면 종횡비를 유지한 채 카드 안에 맞춤 (TOP5 일러스트용)."""
    st.markdown(f"""<style>
    .st-key-{key} button {{
        background: url("data:image/png;base64,{_b64(path)}") center / {fit} no-repeat;
        width: 100%; aspect-ratio: {aspect}; height: auto;
        border-radius: 16px; border: 1px solid #e3e3e3;
    }}
    .st-key-{key} button:hover {{
        border-color: {GREEN}; box-shadow: 0 3px 12px rgba(46,125,50,.30);
        transform: translateY(-1px); transition: all .15s;
    }}
    .st-key-{key} button p, .st-key-{key} button div {{ color: transparent !important; }}
    </style>""", unsafe_allow_html=True)
    return st.button("\u200b", key=key, use_container_width=True)

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

def plant_image(pid, size=380, flower=None):
    """식물 그림을 size×size RGBA 로 반환.
    assets/plants/{PID}.png(webp) 실제 일러스트가 있으면 그것을 정사각으로 맞춰 사용,
    없으면 draw_plant() 도형으로 폴백. share_card / composite_plant 공용."""
    ill = plant_illust(pid)
    if ill:
        try:
            im = Image.open(ill).convert("RGBA")
            # 정사각 중앙 크롭 후 리사이즈
            side = min(im.size)
            im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                          (im.width + side) // 2, (im.height + side) // 2))
            return im.resize((size, size), Image.LANCZOS)
        except Exception:
            pass
    return draw_plant(size, flower)

def draw_plant(size=300, flower=None):
    """화분+식물 일러스트 (flower='blue'면 수국 스타일)"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size / 300.0
    # 화분
    d.polygon([(105*s, 210*s), (195*s, 210*s), (180*s, 285*s), (120*s, 285*s)],
              fill=(193, 121, 82, 255), outline=(150, 90, 60, 255), width=int(3*s))
    d.rectangle([98*s, 200*s, 202*s, 216*s], fill=(210, 140, 100, 255))
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
    else:
        pid = FACE_PLANTS[h % len(FACE_PLANTS)]
        imp, vib = IMPRESSIONS[h % 6], VIBES[h % 4]
        score = 91 + h % 9
        ss.face_copy = FACE_COPY[pid]
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

def share_card(img_bytes, pid, copy_text, score):
    """공유 카드 PNG 생성 (사진 + 식물 일러스트 + 문구)"""
    W, H = 840, 1030
    card = Image.new("RGBA", (W, H), (232, 245, 233, 255))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, W, 110], fill=(46, 125, 50, 255))
    d.text((30, 30), "🌱 Flower Land (플라워랜드)", font=find_font(40), fill="white")
    # 셀카는 기존 크기, 식물은 더 크게 (비대칭)
    SELF_PS = 360        # 셀카 크기
    PLANT_PS = 520       # 식물 크기(더 크게)
    y_top = 150
    # 식물(우) — 크게. 오른쪽 정렬
    _pl = plant_image(pid, PLANT_PS, "blue" if pid == "P416" else None)
    x_plant = W - PLANT_PS - 15
    y_plant = y_top
    card.paste(_pl, (x_plant, y_plant), _pl)
    # 셀카(좌) — 식물과 세로 중앙 맞춤
    ph = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    side = min(ph.size)
    ph = ph.crop(((ph.width-side)//2, (ph.height-side)//2,
                  (ph.width+side)//2, (ph.height+side)//2)).resize((SELF_PS, SELF_PS))
    y_self = y_top + (PLANT_PS - SELF_PS) // 2      # 식물과 세로 중앙 정렬
    card.paste(ph, (25, y_self))
    # 텍스트 (사진 아래로)
    ty = y_top + PLANT_PS + 45
    f_big, f_mid = find_font(46), find_font(30)
    d.text((35, ty), f"{USER_NAME} 님 & {PLANT_NAMES[pid]} :", font=f_big, fill=(27, 60, 30))
    d.text((35, ty + 62), copy_text, font=f_big, fill=(27, 60, 30))
    d.text((35, ty + 150), f"매핑 점수 {score}%  ·  나와 닮은 반려식물 카드",
           font=f_mid, fill=(90, 110, 90))
    d.rectangle([0, H-40, W, H], fill=(46, 125, 50, 255))
    return card

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

# ── 라우팅 ───────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("page", "home")
ss.setdefault("face_step", 1); ss.setdefault("space_step", 1)
def go(p): ss.page = p; st.rerun()

def show_plant_intro(name, registered):
    """API(제미나이)로 식물 유형·특징·관리법 소개. 키 없으면 DB 기본정보 폴백."""
    tag = "🤖 Gemini" if gemini_on() else "기본 정보"
    if gemini_on():
        with st.spinner(f"'{name}' 식물 정보를 AI로 분석 중..."):
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
                info = gm.ask_json(api_key, prompt)
            except Exception as e:
                st.error(f"AI 조회 실패: {type(e).__name__} — 기본 정보로 대체")
                info = None
        if info and info.get("exists"):
            ss.last_similar = info.get("similar", [])
            st.markdown(
                f"<div class='result'><b style='font-size:19px'>{name}</b> "
                f"<span style='color:#888'>{info.get('sci','')}</span> "
                f"<span class='chip'>{tag}</span><br>"
                f"<b>유형</b>: {info.get('type','-')} · <b>난이도</b>: {info.get('level','-')}<br>"
                f"{info.get('summary','')}<br>"
                f"☀️ {info.get('light','-')} &nbsp; 💧 {info.get('water','-')}</div>",
                unsafe_allow_html=True)
            return
    # ── 폴백: DB 마스터의 기본 정보 (plant 테이블 있으면 사용) ──
    if name in NAME_TO_PID:
        try:
            pid = NAME_TO_PID[name]
            row = conn.execute("SELECT care_level, light_need, water_cycle "
                               "FROM plant WHERE id=?", (pid,)).fetchone()
        except Exception:
            row = None
        if row:
            st.markdown(
                f"<div class='result'><b style='font-size:19px'>{name}</b> "
                f"<span class='chip'>{tag}</span><br>"
                f"난이도 {row[0]} · ☀️ {row[1]} · 💧 {row[2]}일 주기</div>",
                unsafe_allow_html=True)
            return
        st.markdown(
            f"<div class='result'><b style='font-size:19px'>{name}</b> "
            f"<span class='chip'>단지 취급 품종</span><br>"
            "이 품종은 단지에서 취급 중입니다. 아래에서 취급 농원을 확인하세요.</div>",
            unsafe_allow_html=True)
        return
    st.info(f"'{name}'의 상세 정보가 준비되지 않았습니다. "
            "(사이드바에서 Gemini 키를 연결하면 AI 소개가 표시됩니다)")

def show_stock_nurseries(pid, compact=False):
    """DB에서 해당 품종 취급 농원·재고 표시 + 트래픽 분배 추천 회원사."""
    rows = conn.execute("""
        SELECT s.nursery_id, n.name, s.qty, s.updated_at
        FROM stock s JOIN nursery n ON n.id = s.nursery_id
        WHERE s.plant_id = ? AND s.qty > 0
        ORDER BY s.qty DESC""", (pid,)).fetchall()
    if not rows:
        st.error(f"현재 '{PLANT_NAMES.get(pid,'')}' 재고 보유 농원이 없습니다.")
        return
    total = sum(r[2] for r in rows)
    st.markdown(f"<div class='nursery'>취급 농원 <b>{len(rows)}곳</b> · "
                f"단지 총 재고 <b>{total}개</b></div>", unsafe_allow_html=True)
    for nid, name, qty, upd in (rows if not compact else rows[:2]):
        fresh = "🟢" if (upd and upd >= "2026") else "🟡"
        kurl = kakao_map_url(name)
        st.markdown(
            f"<div class='nursery'>🏪 <b>{name}</b> ({nid}) · {zone_of(nid)}"
            f"<br>재고 <b>{qty}개</b> {fresh} · "
            f"<a href='{kurl}' target='_blank' style='color:#1a73e8; "
            f"text-decoration:none; font-weight:700;'>📍 지도</a> · 📞 전화</div>",
            unsafe_allow_html=True)
    if not compact:
        st.caption("🟢 재고 최근 갱신 · 🟡 갱신 필요(72h 기준)")
        b = best_nursery(pid, "search")
        if b:
            st.markdown("#### ⭐ 오늘의 추천 회원사 (트래픽 분배)")
            best_card(b, pid)
def header():
    c1, c2 = st.columns([3, 1])
    if asset("FL_Land.png"):
        c1.image(asset("FL_Land.png"), width=260)
    else:
        c1.markdown("### 🌱 Flower Land <span style='font-size:13px;color:#777'>(플라워랜드)</span>",
                    unsafe_allow_html=True)
    c2.markdown(f"<div style='text-align:right;padding-top:14px'>{USER_NAME}님 🌿</div>",
                unsafe_allow_html=True)

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
            ["80개 농원 안내", "특화 농원 보기", "시든 식물 처방", "물·영양 알림"],
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
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    pid = ss.get("plant_pid")
    if not pid or pid not in PLANT_NAMES:
        st.warning("식물 정보를 찾을 수 없습니다.")
        st.stop()
    name = PLANT_NAMES[pid]
    st.markdown(f"## 🌿 {name}")

    # ⓪ 일러스트 (있는 식물만 — assets/plants/{PID}.png 로 추가 가능)
    ill = plant_illust(pid)
    if ill:
        _c = st.columns([1, 2, 1])[1]
        _c.image(_thumb(ill, 640), use_container_width=True)

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
        hc1, hc2 = st.columns([1, 3])
        with hc1:
            if st.button("← 홈으로", key=f"home_{page}", use_container_width=True): go("home")
        with hc2:
            st.markdown(
                "<div class='step' style='padding-top:8px'>"
                "1단계 : 분석할 셀카를 찍어주세요</div>",
                unsafe_allow_html=True)
    else:
        if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")

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
        st.markdown("<div class='step'>3단계: 유형 카드 공유 & 매칭 농원</div>",
                    unsafe_allow_html=True)
        card = share_card(ss.face_img, pid, copy, score)
        st.image(card, use_container_width=True) # ◀ 결과 카드 화면 폭에 꽉 차게 확대
        buf = io.BytesIO(); card.convert("RGB").save(buf, "PNG")
        st.download_button("📤 결과 공유하기 (카드 PNG 저장)", buf.getvalue(),
                           file_name=f"flowerland_{PLANT_NAMES[pid]}.png",
                           mime="image/png", type="primary", use_container_width=True)
        st.markdown("#### 80개 전체 농원 노출 · 최우수 매칭")
        b = best_nursery(pid, "fun01")
        if b: best_card(b, pid)
        if st.button("처음부터 다시", use_container_width=True):
            ss.face_step = 1; st.rerun()

# ══════════════ 공간 플랜테리어 (4단계) ══════════════
elif page == "space":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    step = ss.space_step
    st.progress(step / 4, text=f"{step}단계 / 4단계")

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
                with st.spinner(f"🤖 Gemini가 {ss.room} 사진을 분석하는 중..."):
                    res = gm.analyze_space(api_key, ss.sp_img, ss.room,
                                           list(PLANT_NAMES.values()))
                ss.sp_ai, ss.sp_ai_h = res, h
            except Exception as e:
                st.warning(f"Gemini 호출 실패 — 목업 모드로 대체 ({type(e).__name__})")
                ss.sp_ai = None; ss.sp_ai_h = h
        ai = ss.get("sp_ai") if ss.get("sp_ai_h") == h else None

        st.markdown("<div class='step'>2단계: 공간 정밀 분석"
                    + (" · 🤖 Gemini" if ai else " · 목업") + "</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='big'>AI가 당신의 {ss.room}을 분석했습니다!</div>",
                    unsafe_allow_html=True)
        st.image(ss.sp_img, use_container_width=True)
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
                    for p, fb in zip(recs + _fallback, _fallback)][:3]
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
        for r in range(2):
            c1, c2 = st.columns(2)
            for col, (e, t, s) in zip((c1, c2), cards[r*2:r*2+2]):
                col.markdown(f"<div class='acard'><span class='e'>{e}</span><br>"
                             f"<span class='t'>{t}</span><br><span class='s'>{s}</span></div>",
                             unsafe_allow_html=True)
        st.markdown(f"### 종합 추천 지표 · 생육 난이도 최적: {'⭐' * stars}")
        st.markdown("#### 추천 식물들")
        cols = st.columns(3)
        for col, pid in zip(cols, recs):
            ill = plant_illust(pid)
            if ill:
                col.image(_thumb(ill, 240), use_container_width=True)
                col.markdown(f"<div style='text-align:center'><b>{PLANT_NAMES[pid]}</b> 👍</div>",
                             unsafe_allow_html=True)
            else:
                col.markdown(f"<div class='top5'><div style='font-size:34px'>🌿</div>"
                             f"<b>{PLANT_NAMES[pid]}</b> 👍</div>", unsafe_allow_html=True)
        ss.sp_recs = recs      # 4단계에서 3종 추천 재사용
        ss.sp_pid = st.radio("가상 배치할 식물 선택",
                             recs, format_func=lambda p: PLANT_NAMES[p], horizontal=True)
        if st.button("다음", type="primary", use_container_width=True):
            ss.space_step = 3; st.rerun()

    elif step == 3:
        pid = ss.sp_pid
        st.markdown("<div class='step'>3단계: 가상 플랜테리어 체험</div>", unsafe_allow_html=True)
        mode = st.radio("합성 방식", ["🤖 AI 실사 합성 (Gemini)", "🎚️ 수동 배치 (슬라이더)"],
                        horizontal=True, index=0 if gemini_on() else 1)
        if mode.startswith("🤖"):
            if not gemini_on():
                st.warning("사이드바에 Gemini API 키를 입력하면 실사 합성이 가능합니다.")
            else:
                cache_key = (img_hash(ss.sp_img), pid)
                if ss.get("comp_key") != cache_key:
                    try:
                        with st.spinner(f"🤖 Gemini가 {PLANT_NAMES[pid]}을(를) "
                                        f"{ss.room}에 합성하는 중... (10~20초)"):
                            ss.comp_img = gm.composite_plant_ai(
                                api_key, ss.sp_img, PLANT_NAMES[pid], ss.room)
                        ss.comp_key = cache_key
                    except Exception as e:
                        st.warning(f"합성 실패 — 수동 배치를 사용하세요 ({type(e).__name__})")
                        ss.comp_img = None; ss.comp_key = cache_key
                if ss.get("comp_img"):
                    st.image(ss.comp_img, use_container_width=True,
                             caption=f"{PLANT_NAMES[pid]} 실사 합성 결과 (Gemini)")
                    if st.button("🔄 다시 합성하기", use_container_width=True):
                        ss.comp_key = None; st.rerun()
        else:
            st.caption("👆 식물을 손가락으로 끌어 옮기고, 두 손가락으로 크기를 조절한 뒤 "
                       "‘이 위치로 확정’을 누르세요. (마우스는 드래그 이동, 휠로 크기)")
            # 서버가 이전에 확정한 값이 있으면 초기 위치로 사용
            init_x = ss.get("mx", 50); init_y = ss.get("my", 60); init_s = ss.get("msc", 38)
            # 배경(공간 사진) + 식물 이미지를 base64로 브라우저에 전달 → 실시간 조작
            bg_b64 = base64.b64encode(ss.sp_img).decode()
            ill = plant_illust(pid)
            if ill:
                _pi = Image.open(ill).convert("RGBA")
                _buf = io.BytesIO(); _pi.save(_buf, "PNG")
                plant_b64 = base64.b64encode(_buf.getvalue()).decode()
            else:
                _pl = draw_plant(400, "blue" if pid == "P416" else None)
                _buf = io.BytesIO(); _pl.save(_buf, "PNG")
                plant_b64 = base64.b64encode(_buf.getvalue()).decode()

            components.html(f"""
            <div id="stage" style="position:relative; width:100%; max-width:700px;
                 margin:0 auto; touch-action:none; user-select:none; border-radius:12px;
                 overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.15);">
              <img id="bg" src="data:image/jpeg;base64,{bg_b64}"
                   style="width:100%; display:block; pointer-events:none;">
              <img id="plant" src="data:image/png;base64,{plant_b64}"
                   style="position:absolute; left:{init_x}%; top:{init_y}%; width:{init_s}%;
                          transform:translate(-50%,-50%); cursor:grab;
                          filter:drop-shadow(0 6px 10px rgba(0,0,0,.35));">
              <div style="position:absolute; left:8px; bottom:8px; background:rgba(46,125,50,.85);
                   color:#fff; font-size:12px; padding:3px 9px; border-radius:8px;">
                {PLANT_NAMES[pid]} — 끌어서 이동 · 두 손가락/휠로 크기</div>
            </div>
            <div style="text-align:center; margin-top:10px;">
              <button id="confirm" style="background:#2e7d32; color:#fff; border:none;
                 font-size:16px; font-weight:700; padding:11px 28px; border-radius:10px;
                 cursor:pointer;">✅ 이 위치로 확정</button>
              <span id="pos" style="margin-left:10px; color:#666; font-size:13px;"></span>
            </div>
            <script>
            (function(){{
              const stage=document.getElementById('stage');
              const plant=document.getElementById('plant');
              let px={init_x}, py={init_y}, scale={init_s};       // % 단위
              function apply(){{
                plant.style.left=px+'%'; plant.style.top=py+'%'; plant.style.width=scale+'%';
                document.getElementById('pos').textContent =
                  '좌우 '+Math.round(px)+'% · 상하 '+Math.round(py)+'% · 크기 '+Math.round(scale)+'%';
              }}
              function rect(){{ return stage.getBoundingClientRect(); }}
              let dragging=false, ox=0, oy=0;
              function startDrag(cx,cy){{ dragging=true; plant.style.cursor='grabbing';
                const r=rect(); ox=cx-r.left-(px/100*r.width); oy=cy-r.top-(py/100*r.height); }}
              function moveDrag(cx,cy){{ if(!dragging)return; const r=rect();
                px=Math.min(95,Math.max(5,((cx-r.left-ox)/r.width)*100));
                py=Math.min(95,Math.max(5,((cy-r.top-oy)/r.height)*100)); apply(); }}
              function endDrag(){{ dragging=false; plant.style.cursor='grab'; }}
              plant.addEventListener('mousedown',e=>{{startDrag(e.clientX,e.clientY);e.preventDefault();}});
              window.addEventListener('mousemove',e=>moveDrag(e.clientX,e.clientY));
              window.addEventListener('mouseup',endDrag);
              stage.addEventListener('wheel',e=>{{ scale=Math.min(90,Math.max(10,
                scale - Math.sign(e.deltaY)*3)); apply(); e.preventDefault(); }},{{passive:false}});
              let pinchStart=0, scaleStart={init_s};
              function dist(t){{ const dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
                return Math.hypot(dx,dy); }}
              stage.addEventListener('touchstart',e=>{{
                if(e.touches.length===1){{ startDrag(e.touches[0].clientX,e.touches[0].clientY); }}
                else if(e.touches.length===2){{ dragging=false; pinchStart=dist(e.touches);
                  scaleStart=scale; }}
                e.preventDefault();
              }},{{passive:false}});
              stage.addEventListener('touchmove',e=>{{
                if(e.touches.length===1){{ moveDrag(e.touches[0].clientX,e.touches[0].clientY); }}
                else if(e.touches.length===2 && pinchStart>0){{
                  scale=Math.min(90,Math.max(10, scaleStart*(dist(e.touches)/pinchStart))); apply(); }}
                e.preventDefault();
              }},{{passive:false}});
              stage.addEventListener('touchend',e=>{{ if(e.touches.length===0){{endDrag();pinchStart=0;}} }});
              // ── 확정: 부모(Streamlit) URL에 값 실어 새로고침 → 서버가 읽어 합성 ──
              document.getElementById('confirm').addEventListener('click',function(){{
                const p = window.parent;
                const url = new URL(p.location.href);
                url.searchParams.set('mx', Math.round(px));
                url.searchParams.set('my', Math.round(py));
                url.searchParams.set('msc', Math.round(scale));
                p.location.href = url.toString();
              }});
              apply();
            }})();
            </script>
            """, height=590)

            # ── 서버: URL 쿼리파라미터로 넘어온 확정값을 읽어 합성 ──
            qp = st.query_params
            if "mx" in qp and "my" in qp and "msc" in qp:
                try:
                    ss.mx = int(qp["mx"]); ss.my = int(qp["my"]); ss.msc = int(qp["msc"])
                except ValueError:
                    pass
                st.query_params.clear()   # 값 소비 후 URL 정리(무한루프 방지)
            if "mx" in ss:
                st.success(f"확정 위치: 좌우 {ss.mx}% · 상하 {ss.my}% · 크기 {ss.msc}%")
                ss.comp_img = composite_plant(ss.sp_img, pid, ss.mx, ss.my, ss.msc,
                                              f"{PLANT_NAMES[pid]} 대형 화분")
                st.image(ss.comp_img, use_container_width=True,
                         caption="확정한 위치로 합성된 결과 (저장됩니다)")
        b1, b2, b3 = st.columns(3)
        b1.button("🔄 식물 변경", use_container_width=True,
                  on_click=lambda: ss.update(space_step=2))
        b2.button("🛒 장바구니 담기", use_container_width=True)
        b3.button("🏺 화분 스타일 (토분/야외용)", use_container_width=True)
        if st.button("다음", type="primary", use_container_width=True):
            ss.space_step = 4; st.rerun()

    else:
        pid = ss.sp_pid
        h = img_hash(ss.sp_img)
        match = ss.get("sp_match", 95 + h % 5)
        st.markdown("<div class='step'>4단계: 나의 최적 식물 & 농원</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='big'>{USER_NAME}님! 이 식물이 당신의 {ss.room}과 "
                    f"{match}% 어울립니다!</div>", unsafe_allow_html=True)
        pc1, pc2 = st.columns([1, 2])
        if ss.get("comp_img"):
            pc1.image(ss.comp_img)
        else:
            pc1.image(plant_image(pid, 220, "blue" if pid == "P416" else None))
        reason = ss.get("sp_reason") or PLANT_DESC.get(
            pid, "이 공간의 채광·규모에 최적화된 추천 식물")
        pc2.markdown(f"""<div class='result'><b style='font-size:20px'>{PLANT_NAMES[pid]}</b><br>
            {reason}<br>단지 평균가 / 건강 장수 수명 ⭐ 4.9</div>""", unsafe_allow_html=True)

        # ── 사진 바로 아래: 이 공간에 어울리는 3가지 추천 식물 ──
        recs = ss.get("sp_recs") or [pid]
        st.markdown("#### 🌿 이 공간에 어울리는 추천 식물 3가지")
        rcols = st.columns(3)
        for col, rp in zip(rcols, recs[:3]):
            ill = plant_illust(rp)
            if ill:
                col.image(_thumb(ill, 240), use_container_width=True)
            else:
                col.markdown("<div style='text-align:center;font-size:48px'>🌿</div>",
                             unsafe_allow_html=True)
            _mark = " ✅" if rp == pid else ""
            col.markdown(f"<div style='text-align:center'><b>{PLANT_NAMES[rp]}</b>{_mark}</div>",
                         unsafe_allow_html=True)

        st.markdown("#### 이 식물을 가장 잘 키우고 조경 자재를 보유한 농원")
        b = best_nursery(pid, "fun02")
        if b: best_card(b, pid)
        if st.button("처음부터 다시", use_container_width=True):
            ss.space_step = 1; st.rerun()

# ══════════════ 식물 검색 (취급 회원사 찾기) ══════════════
elif page == "search":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    st.markdown("## 🔎 식물 검색")
    st.caption("① AI가 식물 유형·특징을 소개하고 ② DB에서 취급 농원(재고)을 안내합니다.")
    q = st.text_input("식물 이름", value=ss.get("search_q", ""),
                      placeholder="예: 몬스테라, 수국, 필로덴드론 버킨")

    if q.strip():
        term = q.strip()
        hits = [(pid, nm) for pid, nm in PLANT_NAMES.items() if term in nm]

        # 품종 확정: DB 매칭 우선, 없으면 None(=미등록)
        pid = None
        if hits:
            pid = (st.radio("품종 선택", [h[0] for h in hits],
                            format_func=lambda p: PLANT_NAMES[p], horizontal=True)
                   if len(hits) > 1 else hits[0][0])
            disp_name = PLANT_NAMES[pid]
        else:
            disp_name = term

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
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
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
                    rows = conn.execute("SELECT id, name, pin FROM nursery ORDER BY id LIMIT 80").fetchall()
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
            since = (datetime.now() - timedelta(days=7)).isoformat()
            mine = conn.execute("SELECT COUNT(*) FROM exposure_log WHERE nursery_id=? AND ts>=?",
                                (nid, since)).fetchone()[0]
            allc = conn.execute("SELECT COUNT(*) FROM exposure_log WHERE ts>=?", (since,)).fetchone()[0]
            avg = allc / 80 if allc else 0
            ef = conn.execute("SELECT expo_factor FROM nursery WHERE id=?", (nid,)).fetchone()[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("주간 추천 노출", f"{mine}회")
            c2.metric("단지 평균 대비", f"{(mine/avg*100 if avg else 0):.0f}%")
            c3.metric("현재 노출 가중치", f"{ef:.2f}")
            st.caption("재고를 자주 갱신할수록(신선도 유지) 노출 가중치가 올라갑니다. "
                       "가중치는 매일 04시 자동 재계산됩니다.")

    # ══ 상인회 마스터 대시보드 ══
    elif ss.is_master:
        st.markdown("### 📊 상인회 통합 대시보드")
        since = (datetime.now() - timedelta(days=7)).isoformat()
        counts = dict(conn.execute(
            "SELECT nursery_id, COUNT(*) FROM exposure_log WHERE ts>=? GROUP BY nursery_id",
            (since,)).fetchall())
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
        c3.metric("주간 총 노출", f"{sum(vals)}회")
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
            "주간노출":[counts.get(r[0],0) if r[0]!="..." else "..." for r in rows_show],
        }, height=430)
        st.caption("미등록·저노출 농원을 파악해 재고 등록을 독려하세요. "
                   "노출 편중이 심하면(지니↑) 알고리즘이 자동 보정합니다.")

# ══════════════ 건강 진단 ══════════════
elif page == "diag":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
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
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    st.markdown("## 🗺️ 농원 지도 (불로화훼단지)")
    rows = conn.execute("SELECT id, name FROM nursery").fetchall()
    rng = np.random.RandomState(7)
    st.map({"lat": 35.9258 + rng.uniform(-0.002, 0.002, len(rows)),
            "lon": 128.6390 + rng.uniform(-0.003, 0.003, len(rows))},
           size=8, color="#2E7D32")
    sel = st.selectbox("농원 선택", [f"{n} ({i}) · {zone_of(i)}" for i, n in rows])
    st.markdown(f"<div class='nursery'>🌿 <b>{sel}</b><br>영업 09:00~18:00 · 취급: 관엽/다육 "
                f"· 📞 053-98X-XXXX · 📱 QR 스탬프 입구 부착</div>", unsafe_allow_html=True)

# ══════════════ 분갈이 특화 ══════════════
elif page == "repot":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    st.markdown("## 🪴 분갈이·화분 특화 농원")
    for nid, name in conn.execute(
            "SELECT id, name FROM nursery ORDER BY RANDOM() LIMIT 6").fetchall():
        st.markdown(f"<div class='nursery'>🪴 <b>{name}</b> ({nid}) · {zone_of(nid)}<br>"
                    f"분갈이 서비스 5,000원~ · 수제 토분 취급 · 📞 예약 문의</div>",
                    unsafe_allow_html=True)

# ══════════════ 내 식물 관리 (물·영양) ══════════════
elif page == "care":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
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

