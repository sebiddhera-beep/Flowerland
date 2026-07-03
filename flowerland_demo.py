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
import random
import sqlite3

import numpy as np
import streamlit as st
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
          padding:14px; margin-top:10px; }}
.best {{ background:#fffdf3; border:2px solid #e8c34a; border-radius:14px; padding:12px; }}
.best .tag {{ background:#e8c34a; color:#5b4300; font-weight:800; font-size:12px;
             border-radius:8px; padding:2px 8px; }}
.nursery {{ background:#fff; border:1px solid #cfe3cf; border-radius:10px;
           padding:8px 12px; margin-top:6px; font-size:14px; }}
.stampbn {{ background:#e9f6e9; border-radius:12px; padding:10px 14px; font-weight:700; }}

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
    else:
        st.info("키가 없으면 규칙 기반 목업 모드로 동작합니다.")
    st.caption("모델: gemini-2.5-flash (분석)\n/ gemini-2.5-flash-image (합성)")

def gemini_on():
    return HAS_GEMINI and bool(api_key)

NAME_TO_PID = {}  # PLANT_NAMES 정의 후 아래에서 채움

# ── 데이터 ───────────────────────────────────────────────────────────────────
# 식물 마스터 60종 (dispatch.db의 P001~P060과 1:1 매핑 — 검색 대상)
_NAMES = [
    "몬스테라", "스킨답서스", "칼라데아", "여인초", "스투키", "금전수", "홍콩야자",
    "테이블야자", "산세베리아", "아레카야자", "고무나무", "올리브나무", "유칼립투스",
    "라벤더", "로즈마리", "다육 에케베리아", "필로덴드론", "알로카시아", "행운목",
    "수국", "남천나무", "에메랄드그린", "관음죽", "파키라", "벵갈고무나무",
    "떡갈잎고무나무", "몬스테라 아단소니", "안스리움", "스파티필름", "디펜바키아",
    "아글라오네마", "호야", "립살리스", "틸란드시아", "박쥐란", "보스턴고사리",
    "아디안텀", "페페로미아", "필레아", "칼랑코에", "제라늄", "베고니아",
    "시클라멘", "포인세티아", "호접란", "덴파레", "심비디움", "동양란",
    "풍란", "석곡", "장미", "국화", "카네이션", "거베라", "튤립 구근",
    "수선화 구근", "무늬산세베리아", "황금죽", "커피나무", "레몬나무",
]
PLANT_NAMES = {f"P{i:03d}": n for i, n in enumerate(_NAMES, 1)}
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
    "P020": "사계절 노지 월동이 가능하며, 여름철 화려한 군락을 형성하는 야외 특화 식물",
    "P004": "시원하게 뻗는 큰 잎으로 거실의 무드를 살리는 대형 관엽 식물",
    "P001": "구멍 뚫린 잎이 매력적인 국민 관엽. 밝은 간접광에서 잘 자람",
}
IMPRESSIONS = ["대범함 (Bold)", "세련됨 (Sophisticated)", "온화함 (Gentle)",
               "명랑함 (Cheerful)", "차분함 (Calm)", "당당함 (Confident)"]
VIBES = ["따뜻함 (Warm)", "산뜻함 (Fresh)", "포근함 (Cozy)", "싱그러움 (Vivid)"]
FACE_PLANTS = ["P004", "P001", "P012", "P010", "P013", "P020", "P003", "P006"]
FACE_COPY = {"P004": "대범하고 따뜻한 시선", "P001": "세련되고 따뜻한 조화",
             "P012": "클래식하고 차분한 품격", "P010": "다정하고 싱그러운 배려",
             "P013": "자유롭고 산뜻한 감성", "P020": "화려하고 당당한 존재감",
             "P003": "섬세하고 포근한 감수성", "P006": "실속 있고 온화한 든든함"}
INDOOR_RECS  = {"거실": ["P001", "P004", "P010"], "침실": ["P009", "P002", "P005"],
                "사무실": ["P006", "P002", "P009"]}
OUTDOOR_RECS = {"베란다": ["P012", "P015", "P016"], "정원": ["P020", "P021", "P022"],
                "테라스": ["P020", "P013", "P022"]}
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
    fresh = not os.path.exists(td.DB_PATH)
    conn = sqlite3.connect(td.DB_PATH, check_same_thread=False)
    td.init_schema(conn)
    if fresh or conn.execute("SELECT COUNT(*) FROM nursery").fetchone()[0] == 0:
        td.seed(conn, random.Random(42))
    return conn

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
    c1, c2, c3 = st.columns([1.4, 1, 1])
    c1.button("🗺️ 이 농원 방문하기 (길 안내)", use_container_width=True, type="primary",
              key=f"go_{b['id']}_{pid}")
    c2.button("📅 방문 예약하기", use_container_width=True, key=f"rsv_{b['id']}_{pid}")
    c3.button("⭐ 내 리스트 저장", use_container_width=True, key=f"sv_{b['id']}_{pid}")
    st.markdown("<div class='stampbn'>🎟️ 불로단지 스탬프 투어 참여 (방문 시 QR 스캔) ▶</div>",
                unsafe_allow_html=True)

def img_hash(b: bytes) -> int:
    return int(hashlib.md5(b).hexdigest(), 16)

# ── 이미지 에셋: assets 폴더(또는 같은 폴더)에 PNG가 있으면 자동 사용 ──
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

def clickable_image(path, key, aspect="351/416"):
    """이미지 전체가 버튼으로 동작. 클릭하면 True 반환 (세션 유지됨)."""
    st.markdown(f"""<style>
    .st-key-{key} button {{
        background: url("data:image/png;base64,{_b64(path)}") center / 100% 100% no-repeat;
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

# ── PIL 유틸 (일러스트/합성/카드/QR) ─────────────────────────────────────────
def find_font(size):
    for path in [r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf",
                 "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

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
    """공유 카드 PNG 생성 (사진 + 식물 일러스트 + 문구 + QR)"""
    W, H = 840, 1050
    card = Image.new("RGBA", (W, H), (232, 245, 233, 255))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, W, 110], fill=(46, 125, 50, 255))
    d.text((30, 30), "🌱 Flower Land (플라워랜드)", font=find_font(40), fill="white")
    # 셀카(좌) — 중앙 정사각 크롭
    ph = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    side = min(ph.size)
    ph = ph.crop(((ph.width-side)//2, (ph.height-side)//2,
                  (ph.width+side)//2, (ph.height+side)//2)).resize((380, 380))
    card.paste(ph, (35, 150))
    card.paste(draw_plant(380, "blue" if pid == "P020" else None), (425, 150), 
               draw_plant(380, "blue" if pid == "P020" else None))
    f_big, f_mid = find_font(44), find_font(30)
    d.text((35, 575), f"{USER_NAME} 님 & {PLANT_NAMES[pid]} :", font=f_big, fill=(27, 60, 30))
    d.text((35, 635), copy_text, font=f_big, fill=(27, 60, 30))
    d.text((35, 720), f"매핑 점수 {score}%  ·  나와 닮은 반려식물 카드", font=f_mid, fill=(90, 110, 90))
    qr = make_qr(f"https://flowerland.demo/share/{pid}/{score}", 200)
    card.paste(qr, (W-240, H-260), qr)
    d.text((35, H-230), "QR을 스캔하면 나의 식물 유형을\n확인할 수 있어요!", font=f_mid, fill=(90, 110, 90))
    d.rectangle([0, H-40, W, H], fill=(46, 125, 50, 255))
    return card

def composite_plant(bg_bytes, pid, x_pct, y_pct, scale_pct, label):
    """3단계 가상 배치: 공간 사진 위 식물 합성"""
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    bg.thumbnail((720, 720))
    w, h = bg.size
    ps = int(min(w, h) * scale_pct / 100)
    pl = draw_plant(ps, "blue" if pid == "P020" else None)
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
def header():
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 🌱 Flower Land <span style='font-size:13px;color:#777'>(플라워랜드)</span>",
                unsafe_allow_html=True)
    c2.markdown(f"<div style='text-align:right;padding-top:14px'>{USER_NAME}님 🌿</div>",
                unsafe_allow_html=True)

page = ss.page

# ══════════════ 홈 ══════════════
if page == "home":
    header()
    st.markdown("#### 2-Track AI 배너")
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
    ICON_FILES = ["MAP.png", "Port.png", "QR.png", "TREE.png"]
    ICON_ASPECT = ["165/222", "172/222", "172/222", "172/222"]
    for col, e, ic, asp, t, s, tgt in zip(cols, "🗺️🪴📱🔍", ICON_FILES, ICON_ASPECT,
            ["농원 지도", "분갈이·화분 특화", "QR 스탬프 투어", "식물 건강 진단"],
            ["80개 농원 안내", "특화 농원 보기", "단지 방문 인증", "시든 식물 처방"],
            ["map", "repot", "stamp", "diag"]):
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
    cols = st.columns(5)
    for rank, (pid, em, col) in enumerate(zip(
            ["P001", "P002", "P003", "P009", "P006"], "🌿🍃🌱🪴🌳", cols), 1):
        with col:
            b = best_nursery(pid, "fun07")
            st.markdown(f"<div class='top5'><div style='font-size:32px'>{em}</div>"
                        f"<b>{rank}. {PLANT_NAMES[pid]}</b><br>"
                        f"<span style='font-size:11px;color:#777'>{b['name'] if b else '-'}"
                        f"<br>💬 {random.randint(8, 15)}개</span></div>",
                        unsafe_allow_html=True)
    st.caption("※ 초기 시연 — AI 분석은 규칙 기반 목업, 농원 선정은 실제 가중 랜덤 알고리즘 동작")

# ══════════════ 얼굴 & MBTI (3단계) ══════════════
elif page == "face":
    header()
    if st.button("← 홈으로"): go("home")
    step = ss.face_step

    if step == 1:
        st.markdown("<div class='step'>1단계: 셀카 등록</div>", unsafe_allow_html=True)
        st.markdown("<div class='big'>분석할 셀카를 찍어주세요</div>", unsafe_allow_html=True)
        st.caption("(A single, best photo is recommended)")
        t1, t2 = st.tabs(["📷 직접 촬영하기", "🖼️ 갤러리에서 선택"])
        with t1: cam = st.camera_input("노트북 카메라", label_visibility="collapsed")
        with t2: fil = st.file_uploader("파일", type=["jpg", "jpeg", "png"],
                                        label_visibility="collapsed")
        up = cam or fil
        ss.mbti = st.selectbox("MBTI (선택)", ["선택 안 함"] + [
            a+b+c+d for a in "EI" for b in "SN" for c in "TF" for d in "JP"])
        st.info("팁: 정면 얼굴이 잘 보이도록 찍으면 더 정확해요!")
        if up and st.button("다음", type="primary", use_container_width=True):
            ss.face_img = up.getvalue(); ss.face_step = 2; st.rerun()

    elif step == 2:
        h = img_hash(ss.face_img)
        # ── Gemini 실분석 (캐시: 같은 사진 재호출 방지) ──
        if gemini_on() and ss.get("face_ai_h") != h:
            try:
                with st.spinner("🤖 Gemini가 얼굴을 분석하는 중..."):
                    mbti = None if ss.mbti == "선택 안 함" else ss.mbti
                    res = gm.analyze_face(api_key, ss.face_img,
                                          list(PLANT_NAMES.values()), mbti)
                ss.face_ai, ss.face_ai_h = res, h
            except Exception as e:
                st.warning(f"Gemini 호출 실패 — 목업 모드로 대체 ({type(e).__name__})")
                ss.face_ai = None; ss.face_ai_h = h
        ai = ss.get("face_ai") if ss.get("face_ai_h") == h else None

        if ai:
            pid = pid_of(ai.get("plant", ""), FACE_PLANTS[h % len(FACE_PLANTS)])
            imp = f"{ai.get('impression','온화함')} ({ai.get('impression_en','Gentle')})"
            vib = f"{ai.get('vibe','따뜻함')} ({ai.get('vibe_en','Warm')})"
            score = int(ai.get("score", 95))
            ss.face_copy = ai.get("copy", FACE_COPY.get(pid, "따뜻한 조화"))
            reason = ai.get("reason", "")
        else:
            pid = FACE_PLANTS[h % len(FACE_PLANTS)]
            imp, vib = IMPRESSIONS[h % 6], VIBES[h % 4]
            score = 91 + h % 9
            ss.face_copy = FACE_COPY[pid]
            reason = ""
        ss.face_res = (pid, imp, vib, score)
        st.markdown("<div class='step'>2단계: 얼굴 분석"
                    + (" · 🤖 Gemini" if ai else " · 목업") + "</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div class='big'>나와 닮은 반려식물: '{PLANT_NAMES[pid]}'</div>",
                    unsafe_allow_html=True)
        st.image(face_mesh_overlay(ss.face_img), use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("인상", imp.split(" ")[0], imp.split(" ")[1] if " " in imp else "")
        c2.metric("분위기", vib.split(" ")[0], vib.split(" ")[1] if " " in vib else "")
        c3.metric("매핑 점수", f"{score}%")
        if reason:
            st.markdown(f"<div class='result'>💬 {reason}</div>", unsafe_allow_html=True)
        if ss.mbti != "선택 안 함":
            st.caption(f"MBTI {ss.mbti} 반영됨")
        if st.button("다음 (유형 카드 만들기)", type="primary", use_container_width=True):
            ss.face_step = 3; st.rerun()

    else:
        pid, imp, vib, score = ss.face_res
        copy = ss.get("face_copy") or FACE_COPY.get(pid, "따뜻한 조화")
        st.markdown("<div class='step'>3단계: 유형 카드 공유 & 매칭 농원</div>",
                    unsafe_allow_html=True)
        card = share_card(ss.face_img, pid, copy, score)
        st.image(card, use_container_width=True)
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
    if st.button("← 홈으로"): go("home")
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
        with t1: cam = st.camera_input("카메라", label_visibility="collapsed")
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
            recs = [pid_of(n, r) for n, r in zip(
                ai.get("plants", []),
                (OUTDOOR_RECS if outdoor else INDOOR_RECS)[ss.room])] or \
                (OUTDOOR_RECS if outdoor else INDOOR_RECS)[ss.room]
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
            col.markdown(f"<div class='top5'><div style='font-size:34px'>🌿</div>"
                         f"<b>{PLANT_NAMES[pid]}</b> 👍</div>", unsafe_allow_html=True)
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
            st.caption("원하는 위치에 식물을 놓아보세요. (슬라이더로 위치·크기 조정)")
            c1, c2, c3 = st.columns(3)
            x = c1.slider("좌우 위치", 10, 90, 50)
            y = c2.slider("상하 위치", 10, 90, 62)
            sc = c3.slider("크기", 15, 60, 34)
            st.image(composite_plant(ss.sp_img, pid, x, y, sc,
                                     f"{PLANT_NAMES[pid]} 대형 화분"),
                     use_container_width=True)
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
            pc1.image(draw_plant(220, "blue" if pid == "P020" else None))
        reason = ss.get("sp_reason") or PLANT_DESC.get(
            pid, "이 공간의 채광·규모에 최적화된 추천 식물")
        pc2.markdown(f"""<div class='result'><b style='font-size:20px'>{PLANT_NAMES[pid]}</b><br>
            {reason}<br>단지 평균가 / 건강 장수 수명 ⭐ 4.9</div>""", unsafe_allow_html=True)
        st.markdown("#### 이 식물을 가장 잘 키우고 조경 자재를 보유한 농원")
        b = best_nursery(pid, "fun02")
        if b: best_card(b, pid)
        if st.button("처음부터 다시", use_container_width=True):
            ss.space_step = 1; st.rerun()

# ══════════════ 식물 검색 (취급 회원사 찾기) ══════════════
elif page == "search":
    header()
    if st.button("← 홈으로"): go("home")
    st.markdown("## 🔎 식물 검색")
    st.caption("찾는 식물이 단지 내 어느 회원사(농원)에 있는지 검색합니다.")
    q = st.text_input("식물 이름", value=ss.get("search_q", ""),
                      placeholder="예: 몬스테라, 수국, 호접란")
    if q.strip():
        term = q.strip()
        hits = [(pid, nm) for pid, nm in PLANT_NAMES.items() if term in nm]
        if not hits:
            st.warning(f"'{term}'와(과) 일치하는 품종이 없습니다. 다른 이름으로 검색해 보세요.")
        else:
            if len(hits) > 1:
                pid = st.radio("품종 선택", [h[0] for h in hits],
                               format_func=lambda p: PLANT_NAMES[p], horizontal=True)
            else:
                pid = hits[0][0]
            rows = conn.execute("""
                SELECT s.nursery_id, n.name, s.qty, s.updated_at
                FROM stock s JOIN nursery n ON n.id = s.nursery_id
                WHERE s.plant_id = ? AND s.qty > 0
                ORDER BY s.qty DESC""", (pid,)).fetchall()
            if not rows:
                st.error(f"현재 '{PLANT_NAMES[pid]}' 재고를 보유한 회원사가 없습니다.")
            else:
                total = sum(r[2] for r in rows)
                st.markdown(f"<div class='result'><b style='font-size:19px'>🌿 "
                            f"{PLANT_NAMES[pid]}</b><br>취급 회원사 <b>{len(rows)}곳</b> · "
                            f"단지 총 재고 <b>{total}개</b></div>", unsafe_allow_html=True)
                fb = st.checkbox("재고 많은 순 정렬", value=True)
                if not fb:
                    rows = sorted(rows, key=lambda r: r[0])
                for nid, name, qty, upd in rows:
                    fresh = "🟢" if (upd and upd >= "2026") else "🟡"
                    st.markdown(
                        f"<div class='nursery'>🏪 <b>{name}</b> ({nid}) · {zone_of(nid)}"
                        f"<br>재고 <b>{qty}개</b> {fresh} · 📍 지도 보기 · 📞 전화 연결</div>",
                        unsafe_allow_html=True)
                st.caption("🟢 재고 최근 갱신 · 🟡 갱신 필요 (실서비스: 72시간 기준)")
                b = best_nursery(pid, "fun07")
                if b:
                    st.markdown("#### 오늘의 추천 회원사 (트래픽 분배 적용)")
                    best_card(b, pid)

# ══════════════ 건강 진단 ══════════════
elif page == "diag":
    header()
    if st.button("← 홈으로"): go("home")
    st.markdown("## 🔍 식물 건강 진단")
    t1, t2 = st.tabs(["📷 카메라로 촬영", "📁 파일 업로드"])
    with t1: cam = st.camera_input("잎 부분을 가까이 대고 찍어주세요")
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
            nb = best_nursery("P016", "fun03")
            if nb:
                st.info("🪴 분갈이·화분 특화 농원과 연결해 드립니다.")
                best_card(nb, "P016")
        if conf < 70:
            st.warning("신뢰도가 낮습니다. 단지 내 전문가 상담을 권장합니다.")
        st.caption("※ 본 진단은 참고용이며 실제 상태와 다를 수 있습니다.")

# ══════════════ 농원 지도 ══════════════
elif page == "map":
    header()
    if st.button("← 홈으로"): go("home")
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
    if st.button("← 홈으로"): go("home")
    st.markdown("## 🪴 분갈이·화분 특화 농원")
    for nid, name in conn.execute(
            "SELECT id, name FROM nursery ORDER BY RANDOM() LIMIT 6").fetchall():
        st.markdown(f"<div class='nursery'>🪴 <b>{name}</b> ({nid}) · {zone_of(nid)}<br>"
                    f"분갈이 서비스 5,000원~ · 수제 토분 취급 · 📞 예약 문의</div>",
                    unsafe_allow_html=True)

# ══════════════ QR 스탬프 ══════════════
elif page == "stamp":
    header()
    if st.button("← 홈으로"): go("home")
    st.markdown("## 📱 QR 스탬프 투어")
    ss.setdefault("stamps", 3)
    n = ss.stamps
    st.progress(min(n / 20, 1.0), text=f"현재 스탬프 {n}개 / 20개")
    c1, c2, c3 = st.columns(3)
    c1.metric("5곳", "화분 할인쿠폰", "✅" if n >= 5 else f"{5-n}곳 남음")
    c2.metric("10곳", "미니 다육 증정", "✅" if n >= 10 else f"{10-n}곳 남음")
    c3.metric("20곳", "시즌 굿즈", "✅" if n >= 20 else f"{20-n}곳 남음")
    if st.button("📷 QR 스캔 (시연: 랜덤 농원 인증)", type="primary", use_container_width=True):
        row = conn.execute("SELECT name FROM nursery ORDER BY RANDOM() LIMIT 1").fetchone()
        ss.stamps += 1
        st.success(f"✅ {row[0]} 방문 인증 완료! (GPS 반경 150m 검증 통과)")
        st.rerun()
    st.caption("K-2 첫 출격지 등 역사 포인트 3곳은 보너스 스탬프 2개 적립")
