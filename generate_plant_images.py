"""
generate_plant_images.py — 플라워랜드 식물 일러스트 일괄 생성 (Nano Banana)
──────────────────────────────────────────────────────────────────────────
plants_master(_v2).csv 를 읽어 각 식물 이미지를 생성하고
assets/plants/{PID}.png 로 저장한다. 앱(flowerland_demo.py)의 illust() 가
이 경로를 자동 인식하므로, 생성만 하면 바로 반영된다.

★ 이번 버전 변경점 — 배경 '투명(알파)' 이 기본
    - TRANSPARENT_BG=True : 배경을 투명 PNG(또는 WEBP)로 저장
    - 배경 제거 방식 2단계
        rembg 설치돼 있으면 rembg 로 정밀 제거,
        없으면 흰배경 '플러드필 키잉'(모서리에서 연결된 흰색만 제거)
        → 흰색 화분 '안쪽'은 지워지지 않는다.
    - autocrop 이 알파를 인식하고 투명 캔버스에 배치(예전엔 흰 캔버스라
      투명이 도로 흰색으로 덮이는 버그가 있었음)

■ 사전 준비
    pip install google-genai pillow numpy      # (스크립트가 자동 설치도 시도함)
    (정밀 배경 제거를 쓰려면)  pip install rembg onnxruntime

    ★ API 키 넣는 법 (둘 중 하나)
      ① [가장 쉬움] 이 스크립트와 같은 폴더에 'gemini_key.txt' 파일 생성 →
         발급받은 키 한 줄만 붙여넣어 저장. (F5로 실행해도 유지됨)
      ② 환경변수:  set GEMINI_API_KEY=키값   (cmd)  /  setx GEMINI_API_KEY "키값" (영구)
      ※ IDLE 셸에서 os.environ 로 넣는 방식은 F5(RESTART) 시 지워지므로 비권장.

★ 카테고리별 화분 유무 자동 분기
    - 실내 화분식물(관엽·다육·선인장·난초·허브·식충·야자) → 화분에 심긴 모습
    - 정원 식물(조경수·관목·침엽수·자생초·그라스·꽃 등) → 화분 없이 '전체 수형'
    - 수생식물(수생) → 물 위/물속 자연스러운 모습(화분 없음)
    매핑은 코드 상단 POT_CATEGORIES / AQUATIC_CATEGORIES 에서 자유롭게 조정.

■ 실행
    python generate_plant_images.py                 # 전체 생성(투명 배경, 카테고리별 화분 자동)
    python generate_plant_images.py --limit 20      # 앞 20종만(테스트)
    python generate_plant_images.py --only P001,P227 # 특정 PID만
    python generate_plant_images.py --cat 조경수,관목,침엽수  # 특정 카테고리만
    python generate_plant_images.py --style garden  # 전부 화분 없이 강제(auto|pot|garden|aquatic)
    python generate_plant_images.py --force         # 이미 있어도 다시 생성
    python generate_plant_images.py --opaque        # 투명 대신 흰 배경으로 저장
    python generate_plant_images.py --bg rembg      # 배경제거 방식 강제(auto|rembg|whitekey)
    python generate_plant_images.py --model nano2   # Nano Banana 2 사용

■ 팁
    - 흰색/아주 밝은 화분은 whitekey 로는 경계가 아쉬울 수 있음 → rembg 권장.
    - 무료 티어 하루 500장 한도 → --limit 로 나눠 실행 권장.
"""
import os
import csv
import sys
import time
import argparse
import subprocess
from io import BytesIO


# ══════════════════════════════════════════════════════════════
# 의존 패키지 자동 설치(부트스트랩)
#   실행하는 바로 그 파이썬(sys.executable)에 설치하므로
#   'pip 따로 설치했는데 계속 미설치' 문제를 방지한다.
#   IDLE(F5)로 돌려도 동작. --no-autoinstall 로 끌 수 있음.
# ══════════════════════════════════════════════════════════════
# (import이름, pip설치이름)
REQUIRED = [("google.genai", "google-genai"), ("PIL", "pillow"), ("numpy", "numpy")]
OPTIONAL = [("rembg", "rembg"), ("onnxruntime", "onnxruntime")]  # 정밀 배경제거(선택)


def _installed(import_name):
    import importlib.util
    try:
        return importlib.util.find_spec(import_name) is not None
    except Exception:
        return False


def _pip_install(pkgs):
    print(f"    설치 시도: {' '.join(pkgs)}")
    return subprocess.call(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *pkgs]
    ) == 0


def ensure_packages(auto=True, with_optional=False):
    """필수(+선택) 패키지를 확인하고 없으면 설치. 성공 여부 반환."""
    need = [pip for imp, pip in REQUIRED if not _installed(imp)]
    if with_optional:
        need += [pip for imp, pip in OPTIONAL if not _installed(imp)]
    if not need:
        return True
    if not auto:
        print("필요한 패키지가 없습니다: " + ", ".join(need))
        print("설치:  \"%s\" -m pip install %s" % (sys.executable, " ".join(need)))
        return False
    print("-" * 60)
    print(f"파이썬: {sys.executable}")
    print(f"누락 패키지 자동 설치: {', '.join(need)}")
    ok = _pip_install(need)
    # pip 자체가 없으면 ensurepip 로 부트스트랩 후 재시도
    if not ok:
        print("    pip 준비 시도(ensurepip)…")
        subprocess.call([sys.executable, "-m", "ensurepip", "--upgrade"])
        ok = _pip_install(need)
    # 설치 후 재확인
    still = [pip for imp, pip in REQUIRED if not _installed(imp)]
    if still:
        print("-" * 60)
        print("⚠️ 자동 설치가 실패했습니다: " + ", ".join(still))
        print("   파이썬 3.14 등 최신 버전은 일부 패키지 설치파일(wheel)이 아직 없을 수 있습니다.")
        print("   해결책 ①  아래 명령을 명령프롬프트(cmd)에 직접 실행:")
        print('        "%s" -m pip install %s' % (sys.executable, " ".join(still)))
        print("   해결책 ②  파이썬 3.12 를 설치한 뒤 그 파이썬으로 실행(가장 안정적)")
        return False
    print("설치 완료. 계속 진행합니다.")
    print("-" * 60)
    return True

# ── 프롬프트 : 흰 배경 + 그림자 없이(투명 키잉이 깔끔하게) ──
#   카테고리에 따라 세 가지 중 하나를 자동 선택한다. (아래 STYLE_* 매핑 참고)
#     pot     : 화분에 심긴 실내 화분식물
#     garden  : 화분 없이 전체 수형(나무는 뿌리목~수관, 풀·지피는 한 포기)
#     aquatic : 물 위/물속 자연스러운 수생식물(화분 없음)
PROMPT_POTTED = (
    "{ko}({en}, 학명 {sci})를 촬영한 사진. "
    "화면 중앙에 단 하나의 화분에 심긴 식물 딱 한 그루만. "
    "실물과 완전히 동일한 사실적(photorealistic) 스튜디오 제품 사진, "
    "동일한 정면 각도·조명·촬영 스타일로 통일, 정사각형 1:1 구도. "
    "배경은 순수한 흰색(#FFFFFF) 심리스 배경, 그림자 없이 균일한 조명. "
    "식물과 화분만 중앙에 크게 배치. "
    "절대 금지: 여러 그루, 격자(grid)·타일·콜라주 배열, 이미지 분할, "
    "같은 식물 반복, 텍스트나 라벨, 액자·테두리, 바닥 그림자."
)

PROMPT_GARDEN = (
    "{ko}({en}, 학명 {sci})를 촬영한 사진. "
    "화분·화병·용기 없이, 식물 한 그루의 '전체 수형(자연 형태)'만. "
    "나무·관목은 뿌리목부터 수관까지 한 그루 전체, "
    "풀·지피·그라스·자생초는 자연스러운 한 포기 전체. "
    "실물과 완전히 동일한 사실적(photorealistic) 식물도감식 사진, "
    "정면·통일된 조명·촬영 스타일, 정사각형 1:1 구도. "
    "배경은 순수한 흰색(#FFFFFF) 심리스 배경, 그림자 없이 균일한 조명. "
    "식물만 중앙에 크게 배치. "
    "절대 금지: 화분·화병·용기·받침, 흙더미, 배경 풍경·정원·하늘, "
    "여러 그루, 격자(grid)·타일·콜라주 배열, 이미지 분할, "
    "텍스트나 라벨, 액자·테두리, 바닥 그림자."
)

PROMPT_AQUATIC = (
    "{ko}({en}, 학명 {sci})를 촬영한 사진. "
    "화분·용기 없이, 물 위 또는 물속에서 자라는 자연스러운 한 포기 모습. "
    "실물과 완전히 동일한 사실적(photorealistic) 식물도감식 사진, "
    "정면·통일된 조명, 정사각형 1:1 구도. "
    "배경은 순수한 흰색(#FFFFFF) 심리스 배경, 그림자 없이 균일한 조명. "
    "식물(과 최소한의 물)만 중앙에 크게 배치. "
    "절대 금지: 화분·화병·용기·어항, 배경 연못·풍경, 여러 포기, "
    "격자·타일·콜라주, 이미지 분할, 텍스트·라벨, 액자·테두리, 바닥 그림자."
)

# ── 카테고리 → 스타일 매핑 ─────────────────────────────────────
#   원하는 대로 카테고리를 옮기면 된다(부분 문자열로 매칭 → "관엽 Foliage" 는 "관엽"만 써도 됨).
POT_CATEGORIES = [      # 화분 O (실내 화분식물)
    "관엽", "다육", "선인장", "난초", "허브", "식충", "야자",
]
AQUATIC_CATEGORIES = [  # 물 (화분 X)
    "수생",
]
# 그 외 전부 garden(화분 X, 전체 수형)로 처리한다:
#   조경수·관목·침엽수·대나무·장미·과실수·열대과실·자생초·그라스·지피·구근·덩굴·양치·꽃 …
DEFAULT_STYLE = "garden"


def resolve_style(category, forced=None):
    """카테고리 문자열로 pot/garden/aquatic 결정. forced 가 있으면 그대로 사용."""
    if forced and forced != "auto":
        return forced
    cat = category or ""
    for key in AQUATIC_CATEGORIES:
        if key in cat:
            return "aquatic"
    for key in POT_CATEGORIES:
        if key in cat:
            return "pot"
    return DEFAULT_STYLE


PROMPTS = {"pot": PROMPT_POTTED, "garden": PROMPT_GARDEN, "aquatic": PROMPT_AQUATIC}

MODELS = {
    "nano":  "gemini-2.5-flash-image",   # Nano Banana (안정)
    "nano2": "gemini-3.1-flash-image",   # Nano Banana 2 (최신)
}

HERE = os.path.dirname(os.path.abspath(__file__))
# 확장본이 있으면 그걸, 없으면 원본을 사용
MASTER_CSV = os.path.join(HERE, "plants_master_v2.csv")
if not os.path.exists(MASTER_CSV):
    MASTER_CSV = os.path.join(HERE, "plants_master.csv")
OUT_DIR = os.path.join(HERE, "assets", "plants")

# ── 리사이즈 / 압축 설정 ────────────────────────────────────────
RESIZE_PX = 768          # 저장할 정사각 한 변 픽셀 (0=원본 유지)
SAVE_FORMAT = "PNG"      # "PNG" 또는 "WEBP" (둘 다 투명 지원 / JPG는 투명 불가)
WEBP_QUALITY = 90        # WEBP 품질(0~100)
PNG_OPTIMIZE = True      # PNG 무손실 최적화

# ── 배경 투명 처리 ─────────────────────────────────────────────
TRANSPARENT_BG = True    # True=배경 투명(알파) / False=흰 배경 유지
BG_METHOD = "auto"       # "auto"(rembg 있으면 rembg, 없으면 whitekey) | "rembg" | "whitekey"
WHITE_TOL = 32           # whitekey: 배경 흰색으로 볼 허용 오차(클수록 더 많이 제거)
EDGE_FEATHER = 0.8       # 알파 경계 부드럽게(가우시안 반경 px, 0=끔)

# ── 자동 여백 제거(auto-crop) ──────────────────────────────────
AUTOCROP = True          # 식물+화분만 남기고 여백 제거해 꽉 차게
CROP_BRIGHTNESS = 235    # (알파 없을 때) 이 밝기보다 어두우면 '식물'로 간주
CROP_PADDING = 0.05      # 둘레 여백 비율(0.05=5%)
ALPHA_SUBJECT = 12       # 알파가 이 값보다 크면 subject 로 간주(크롭 기준)


# ══════════════════════════════════════════════════════════════
# 배경 투명화
# ══════════════════════════════════════════════════════════════
def _rembg_available():
    try:
        import rembg  # noqa: F401
        return True
    except Exception:
        return False


def whitekey(img):
    """흰 '배경'만 투명하게. 네 모서리에서 연결된 흰 영역만 제거하므로
    화분/식물 내부의 흰색은 보존된다."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    rgb = img.convert("RGB")
    w, h = rgb.size
    KEY = (255, 0, 255)                       # 배경 표식용 마젠타
    work = rgb.copy()
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
                 (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        # 씨앗 픽셀이 이미 표식색이면 건너뜀
        if work.getpixel(seed) != KEY:
            ImageDraw.floodfill(work, seed, KEY, thresh=WHITE_TOL)
    arr = np.asarray(work)
    bg_mask = np.all(arr == np.array(KEY, dtype=np.uint8), axis=2)
    alpha = np.where(bg_mask, 0, 255).astype("uint8")
    alpha_img = Image.fromarray(alpha, "L")
    if EDGE_FEATHER and EDGE_FEATHER > 0:
        alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(EDGE_FEATHER))
    out = rgb.convert("RGBA")
    out.putalpha(alpha_img)
    return out


def make_transparent(img):
    """BG_METHOD 에 따라 배경을 투명하게 만든 RGBA 이미지 반환."""
    method = BG_METHOD
    if method == "auto":
        method = "rembg" if _rembg_available() else "whitekey"
    if method == "rembg":
        try:
            from rembg import remove
            return remove(img.convert("RGBA"))
        except Exception as e:
            print(f"    [rembg 실패→whitekey] {type(e).__name__}: {str(e)[:60]}")
    return whitekey(img)


# ══════════════════════════════════════════════════════════════
# 자동 크롭(알파 인식) + 저장
# ══════════════════════════════════════════════════════════════
def autocrop(img):
    """subject 영역만 잘라 정사각 캔버스 중앙에 padding 주어 배치.
    알파가 있으면 알파로, 없으면 밝기로 subject 를 판정한다.
    캔버스 배경은 TRANSPARENT_BG 에 따라 투명/흰색."""
    import numpy as np
    from PIL import Image
    img = img.convert("RGBA")
    arr = np.asarray(img)
    a = arr[..., 3]
    if a.min() < 255:                          # 알파가 실제로 쓰이는 경우
        mask = a > ALPHA_SUBJECT
    else:                                      # 불투명 → 밝기로 판정
        mask = arr[..., :3].min(axis=2) < CROP_BRIGHTNESS
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = img.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))
    w, h = crop.size
    side = max(w, h)
    pad = int(side * CROP_PADDING)
    canvas = side + pad * 2
    bg = (255, 255, 255, 0) if TRANSPARENT_BG else (255, 255, 255, 255)
    out = Image.new("RGBA", (canvas, canvas), bg)
    out.paste(crop, ((canvas - w) // 2, (canvas - h) // 2), crop)
    return out


def save_optimized(img, out_dir, pid):
    """(투명화)→크롭→리사이즈→저장. 저장 경로 반환."""
    from PIL import Image
    img = img.convert("RGBA")
    if TRANSPARENT_BG:
        img = make_transparent(img)
    if AUTOCROP:
        img = autocrop(img)
    if RESIZE_PX and RESIZE_PX > 0:
        img = img.resize((RESIZE_PX, RESIZE_PX), Image.LANCZOS)
    if not TRANSPARENT_BG:
        # 흰 배경으로 평탄화(투명 픽셀을 흰색 위에 합성)
        flat = Image.new("RGBA", img.size, (255, 255, 255, 255))
        flat.paste(img, (0, 0), img)
        img = flat.convert("RGB")
    if SAVE_FORMAT.upper() == "WEBP":
        out_path = os.path.join(out_dir, f"{pid}.webp")
        img.save(out_path, "WEBP", quality=WEBP_QUALITY, method=6)
    else:
        out_path = os.path.join(out_dir, f"{pid}.png")
        img.save(out_path, "PNG", optimize=PNG_OPTIMIZE)
    return out_path


# ══════════════════════════════════════════════════════════════
# 생성 파이프라인
# ══════════════════════════════════════════════════════════════
def load_master():
    with open(MASTER_CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_prompt(row, forced_style=None):
    style = resolve_style(row.get("category", ""), forced_style)
    tmpl = PROMPTS[style]
    return style, tmpl.format(
        ko=row["korean"], en=row["english_common"], sci=row["scientific"])


def generate_one(client, model, prompt):
    """이미지 1장 생성 → PIL.Image 반환. 실패 시 예외."""
    from google.genai import types
    resp = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            from PIL import Image
            return Image.open(BytesIO(part.inline_data.data))
    raise RuntimeError("이미지 파트 없음(안전필터 차단 가능)")


def read_key_file():
    """스크립트 폴더의 키 파일에서 API 키를 읽는다(환경변수 대안).
    gemini_key.txt 또는 api_key.txt 에 키 한 줄만 넣어두면 된다.
    F5(재시작)에도 지워지지 않아 가장 편하다."""
    for name in ("gemini_key.txt", "api_key.txt", "GEMINI_API_KEY.txt"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8-sig") as f:
                    for line in f:
                        k = line.strip().strip('"').strip("'")
                        if k and not k.startswith("여기에") and not k.startswith("#"):
                            return k
            except Exception:
                pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="앞 N종만 생성(0=전체)")
    ap.add_argument("--only", type=str, default="", help="특정 PID 목록(쉼표구분)")
    ap.add_argument("--cat", type=str, default="", help="특정 카테고리만(부분문자열, 쉼표구분) 예: 조경수,관목,침엽수")
    ap.add_argument("--style", choices=["auto", "pot", "garden", "aquatic"], default="auto",
                    help="프롬프트 스타일 강제(기본 auto=카테고리 매핑)")
    ap.add_argument("--force", action="store_true", help="이미 있어도 재생성")
    ap.add_argument("--opaque", action="store_true", help="투명 대신 흰 배경으로 저장")
    ap.add_argument("--bg", choices=["auto", "rembg", "whitekey"], default=None,
                    help="배경제거 방식(기본 auto)")
    ap.add_argument("--remove-bg", action="store_true",
                    help="(호환용) 배경 투명 처리 — 이제 기본값이라 안 줘도 됨")
    ap.add_argument("--model", choices=list(MODELS), default="nano", help="사용 모델")
    ap.add_argument("--sleep", type=float, default=1.0, help="호출 간 대기(초)")
    ap.add_argument("--no-autoinstall", action="store_true", help="누락 패키지 자동설치 끄기")
    args = ap.parse_args()

    # 전역 설정 반영
    global TRANSPARENT_BG, BG_METHOD
    if args.opaque:
        TRANSPARENT_BG = False
    if args.bg:
        BG_METHOD = args.bg

    # ── 패키지 확인/자동 설치 (키보다 먼저: 키 없어도 설치는 진행) ──
    want_optional = (args.bg == "rembg")
    if not ensure_packages(auto=not args.no_autoinstall, with_optional=want_optional):
        sys.exit(1)

    # ── API 키 ─────────────────────────────────────────────────
    # ⚠️ 보안: 코드에 키를 하드코딩하지 말 것.
    #    (이전 파일에 노출됐던 키는 즉시 폐기하고 새로 발급하세요.)
    #    우선순위: 환경변수 → 키 파일(gemini_key.txt)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = read_key_file()
    if not api_key:
        print("\n패키지는 준비됐습니다. 이제 API 키만 넣으면 됩니다.")
        print("★ 가장 쉬운 방법(F5로 실행해도 유지됨):")
        print("   이 스크립트와 같은 폴더에 'gemini_key.txt' 파일을 만들고,")
        print("   그 안에 발급받은 키 한 줄만 붙여넣어 저장하세요.")
        print("   폴더: %s" % HERE)
        print("")
        print("  ※ IDLE에서 os.environ 로 키를 넣었다면, F5를 누르는 순간")
        print("     인터프리터가 RESTART 되면서 그 키가 지워집니다. 그래서 키 파일 방식을 권장합니다.")
        print("")
        print("  (대안) 환경변수 영구설정 후 cmd/IDLE 새로 열기:")
        print("     setx GEMINI_API_KEY \"발급받은키\"")
        sys.exit(1)

    from google import genai

    client = genai.Client(api_key=api_key)
    model = MODELS[args.model]
    os.makedirs(OUT_DIR, exist_ok=True)

    rows = load_master()
    if args.only:
        want = {p.strip() for p in args.only.split(",")}
        rows = [r for r in rows if r["pid"] in want]
    if args.cat:
        keys = [c.strip() for c in args.cat.split(",") if c.strip()]
        rows = [r for r in rows if any(k in r.get("category", "") for k in keys)]
    if args.limit > 0:
        rows = rows[:args.limit]

    method_now = BG_METHOD
    if method_now == "auto":
        method_now = "rembg" if _rembg_available() else "whitekey"
    bg_desc = "투명(" + method_now + ")" if TRANSPARENT_BG else "흰 배경"

    total = len(rows)
    done = skipped = failed = 0
    from collections import Counter
    style_counts = Counter(resolve_style(r.get("category", ""), args.style) for r in rows)
    style_desc = " · ".join(f"{k} {v}" for k, v in style_counts.items())
    print(f"대상 {total}종 · 모델 {model} · 배경 {bg_desc} · 저장 {OUT_DIR}")
    print(f"마스터 CSV: {MASTER_CSV}")
    print(f"스타일 분포: {style_desc}  (강제={args.style})")
    print("-" * 60)

    for i, row in enumerate(rows, 1):
        pid = row["pid"]
        exists = (os.path.exists(os.path.join(OUT_DIR, f"{pid}.png")) or
                  os.path.exists(os.path.join(OUT_DIR, f"{pid}.webp")))
        if exists and not args.force:
            skipped += 1
            continue

        style, prompt = build_prompt(row, args.style)
        label = f"[{i}/{total}] {pid} {row['korean']}({style})"

        for attempt in range(1, 4):            # 재시도 3회(지수 백오프)
            try:
                img = generate_one(client, model, prompt)
                out_path = save_optimized(img, OUT_DIR, pid)
                kb = os.path.getsize(out_path) // 1024
                done += 1
                print(f"{label} ✓  ({RESIZE_PX or '원본'}px, {kb}KB)")
                break
            except Exception as e:
                wait = 2 ** attempt
                msg = str(e)[:80]
                if attempt < 3:
                    print(f"{label} … 재시도 {attempt}/3 ({type(e).__name__}: {msg}) {wait}s 대기")
                    time.sleep(wait)
                else:
                    failed += 1
                    print(f"{label} ✗ 실패: {type(e).__name__}: {msg}")

        time.sleep(args.sleep)

    print("-" * 60)
    print(f"완료  생성 {done} · 건너뜀(기존) {skipped} · 실패 {failed}")
    if failed:
        print("실패분은 같은 명령을 다시 실행하면 이어서 재시도합니다.")


# ── IDLE(F5) 실행 설정 ───────────────────────────────────────
IDLE_LIMIT  = 0        # 몇 종 생성? 20=테스트, 0=전체
IDLE_MODEL  = "nano"   # "nano"(2.5) 또는 "nano2"(3.1)
IDLE_OPAQUE = False    # True면 흰 배경, False면 투명 배경(기본)

if __name__ == "__main__":
    if len(sys.argv) == 1:                     # IDLE 등 인자 없이 실행 시
        sys.argv += ["--limit", str(IDLE_LIMIT), "--model", IDLE_MODEL]
        if IDLE_OPAQUE:
            sys.argv += ["--opaque"]
    main()
