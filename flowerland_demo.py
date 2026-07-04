# ══════════════ 얼굴 & MBTI (3단계) ══════════════
elif page == "face":
    header()
    if st.button("← 홈으로", key=f"home_{page}", use_container_width=False): go("home")
    step = ss.face_step

    if step == 1:
        st.markdown("<div class='step'>1단계: 셀카 등록</div>", unsafe_allow_html=True)
        st.markdown("<div class='big'>분석할 셀카를 찍어주세요</div>", unsafe_allow_html=True)
        st.caption("(A single, best photo is recommended)")
        t1, t2 = st.tabs(["📷 직접 촬영하기", "🖼️ 갤러리에서 선택"])
        with t1: cam = st.camera_input("촬영", label_visibility="collapsed")  # ◀ "노트북 카메라"에서 "촬영"으로 한글화
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
        st.image(face_mesh_overlay(ss.face_img), use_container_width=True) # ◀ 화면 폭에 꽉 차게 확대
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
