# -*- coding: utf-8 -*-
"""
gemini_api.py — 구글 제미나이(Gemini) API 연동 모듈
================================================================================
플라워랜드 데모의 AI 3종(얼굴 분석/공간 분석/건강 진단)과 가상 배치 이미지 합성을
Gemini API로 처리한다. REST 직접 호출 방식(requests)이라 별도 SDK가 필요 없다.

API 키 발급 (무료):
  1) https://aistudio.google.com 접속 → 구글 계정 로그인
  2) 좌측 "Get API key" → "Create API key" → 키 복사
  3) 앱 사이드바에 붙여넣기 (또는 환경변수 GEMINI_API_KEY 설정)

사용 모델:
  - 비전/텍스트 분석: gemini-2.5-flash            (사진 이해 → JSON 응답)
  - 이미지 합성/생성 : gemini-2.5-flash-image     (공간 사진에 식물 합성)
"""

import base64
import json
import os
import re

import requests

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_TEXT = "gemini-2.5-flash"
MODEL_IMAGE = "gemini-2.5-flash-image"
TIMEOUT = 60


def get_env_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _parts(prompt, images):
    parts = []
    for img in images or []:
        parts.append({"inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(img).decode()}})
    parts.append({"text": prompt})
    return parts


def _post(key, model, body):
    r = requests.post(f"{BASE}/{model}:generateContent",
                      params={"key": key},
                      json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def ask_json(key, prompt, images=None, model=MODEL_TEXT):
    """이미지+프롬프트 → JSON dict. 프롬프트에서 JSON-only를 강제하고 방어적으로 파싱."""
    body = {
        "contents": [{"parts": _parts(
            prompt + "\n\n반드시 유효한 JSON 객체 하나만 출력하고, "
                     "설명·마크다운 코드펜스는 절대 붙이지 마시오.", images)}],
        "generationConfig": {"temperature": 0.4,
                             "response_mime_type": "application/json"},
    }
    data = _post(key, model, body)
    text = ""
    for p in data["candidates"][0]["content"]["parts"]:
        text += p.get("text", "")
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def make_image(key, prompt, images=None, model=MODEL_IMAGE):
    """이미지 합성/생성 → PNG bytes (첫 번째 이미지 파트). 실패 시 예외."""
    body = {
        "contents": [{"parts": _parts(prompt, images)}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    data = _post(key, model, body)
    for p in data["candidates"][0]["content"]["parts"]:
        inline = p.get("inline_data") or p.get("inlineData")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("응답에 이미지가 없습니다: " + json.dumps(data)[:300])


# ── 플라워랜드 전용 프롬프트 ─────────────────────────────────────────────────
def analyze_face(key, img_bytes, plant_list, mbti=None):
    """셀카 → {impression, vibe, plant, score, copy}  (plant는 목록 내 이름)"""
    prompt = f"""당신은 화훼단지 앱의 '나와 닮은 식물 찾기' AI다.
사진 속 인물의 인상과 분위기를 긍정적으로 분석하고, 아래 식물 목록에서
가장 잘 어울리는 식물 1종을 골라라. 외모 평가나 부정적 표현은 금지.
{"MBTI는 " + mbti + "이다. 성격 특성도 반영하라." if mbti else ""}
식물 목록: {", ".join(plant_list)}
JSON 스키마: {{"impression": "한 단어 (예: 대범함)", "impression_en": "영어 한 단어",
"vibe": "한 단어 (예: 따뜻함)", "vibe_en": "영어 한 단어",
"plant": "목록 내 식물 이름 그대로", "score": 90~99 정수,
"copy": "'대범하고 따뜻한 시선' 같은 8자 내외 감성 문구",
"reason": "이 식물과 닮은 이유 한 문장"}}"""
    return ask_json(key, prompt, [img_bytes])


def analyze_space(key, img_bytes, room, plant_list):
    """공간 사진 → 분석 카드 4개 + 추천 식물 3종"""
    outdoor = room in ("정원", "테라스", "베란다")
    axes = ("일조량 분석/바닥 재질/월동 여부/공간 규모" if outdoor
            else "창문 방향/광량(Lux 추정)/인테리어 톤/여백(배치 추천 위치)")
    prompt = f"""당신은 화훼단지 앱의 플랜테리어 분석 AI다. 사진은 사용자의 {room}이다.
사진을 근거로 다음 4개 축을 분석하라: {axes}
그리고 아래 목록에서 이 공간에 가장 적합한 식물 3종을 골라라.
식물 목록: {", ".join(plant_list)}
JSON 스키마: {{"cards": [{{"title": "축 이름", "value": "핵심 결과 (짧게)",
"detail": "근거 한 문장"}}, ...4개],
"stars": 3~5 정수 (생육 난이도 최적 점수),
"plants": ["목록 내 이름", "이름", "이름"],
"match": 90~99 정수 (1순위 식물 어울림 %),
"reason": "1순위 식물 추천 이유 한 문장"}}"""
    return ask_json(key, prompt, [img_bytes])


def diagnose(key, img_bytes):
    """식물 사진 → 진단/처방"""
    prompt = """당신은 화훼단지 앱의 식물 건강 진단 AI다. 사진 속 식물의 상태를 진단하라.
가능한 진단: 과습, 건조, 광부족, 광과다, 냉해, 응애, 깍지벌레, 진딧물,
잎마름병, 무름병, 뿌리썩음, 분갈이 필요, 정상
JSON 스키마: {"plant_guess": "추정 식물 이름", "diagnosis": "진단명 1개",
"confidence": 50~99 정수, "prescription_now": "즉시 조치 한 문장",
"prescription_week": "1주 관리 한 문장", "needs_repotting": true/false,
"materials": "필요 자재 (예: 배양토, 살비제)"}"""
    return ask_json(key, prompt, [img_bytes])


def composite_plant_ai(key, space_bytes, plant_name, room):
    """공간 사진에 식물을 자연스럽게 합성한 이미지 생성"""
    prompt = (f"이 {room} 사진의 빈 공간에 '{plant_name}' 화분을 실사처럼 자연스럽게 "
              f"합성해라. 기존 가구·구조·조명은 그대로 유지하고, 그림자와 원근을 "
              f"사진의 광원 방향에 맞춰라. 식물은 건강하고 보기 좋은 상태로.")
    return make_image(key, prompt, [space_bytes])
