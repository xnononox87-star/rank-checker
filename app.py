# -*- coding: utf-8 -*-
import datetime as dt

import pandas as pd
import streamlit as st

import engine as E
import updater as U

st.set_page_config(page_title="HGG 순위 확인", page_icon="🔎", layout="wide")
st.markdown(
    """
<style>
.block-container {padding-top: 1.6rem;}
.badge {display:inline-block;padding:2px 9px;border-radius:10px;font-size:0.85rem;font-weight:600;}
.b-top {background:#d1f2dc;color:#0c6b31;}
.b-p1 {background:#fff1c2;color:#8a5a00;}
.b-none {background:#fde0e0;color:#a11;}
.b-err {background:#e8e8e8;color:#555;}
</style>
""",
    unsafe_allow_html=True,
)

cfg = E.load_config()
STATUS_BADGE = {"상단": ("b-top", "상단"), "1페이지": ("b-p1", "1페이지 하단"),
                "없음": ("b-none", "1페이지 없음"), "확인불가": ("b-err", "확인 불가")}


def badge(status):
    cls, label = STATUS_BADGE.get(status, ("b-err", status))
    return f'<span class="badge {cls}">{label}</span>'


def ranks_text(ranks, items=None):
    if not ranks:
        return "-"
    parts = []
    for r in ranks:
        tag = ""
        if items:
            it = next((x for x in items if x["rank"] == r), None)
            if it and it.get("ad"):
                tag = "(광고)"
        parts.append(f"{r}위{tag}")
    return ", ".join(parts)


def change_text(now, before):
    if before is None:
        return "첫 기록"
    if not now and not before:
        return "변화 없음"
    if not before:
        return "🆕 새로 진입"
    if not now:
        return "⬇ 1페이지 밖으로"
    d = min(before) - min(now)
    if d > 0:
        return f"⬆ {d}계단 상승"
    if d < 0:
        return f"⬇ {-d}계단 하락"
    return "변화 없음"


st.title("🔎 HGG 키워드 순위 확인")
with st.sidebar:
    st.caption(f"프로그램 버전 v{U.local_version()}")
    if st.button("🔄 업데이트 확인"):
        with st.spinner("최신 버전 확인 중..."):
            ok, msg = U.update()
        (st.success if ok else st.info)(msg)
        if ok:
            st.caption("화면이 자동으로 새로고침돼요. 안 되면 F5를 눌러 주세요.")
tab1, tab2, tab3, tab4 = st.tabs(["순위 확인", "네이버 광고", "자료 넣기", "설정"])

# ================================================================ 1. 순위 확인
with tab1:
    c1, c2 = st.columns([3, 2])
    with c1:
        kws = st.multiselect("확인할 키워드", cfg["keywords"], default=cfg["keywords"])
    with c2:
        use_naver = st.checkbox("네이버 쇼핑", value=True)
        use_coupang = st.checkbox("쿠팡", value=True)
        st.caption("확인하는 동안 크롬 창이 따로 열려요. 끝날 때까지 건드리지 마세요.")
    st.caption(f"'상단' = 1페이지 {cfg['top_n']}위 이내 · 순위는 1페이지 안에서 몇 번째인지예요. 같은 상품을 여러 개 등록했다면 모두 표시돼요.")

    if st.button("▶ 순위 확인 시작", type="primary", disabled=not kws):
        run_time = E.now_str()
        res = {"time": run_time, "naver": {}, "coupang": {}}
        if use_naver or use_coupang:
            status_box = st.empty()
            try:
                br = E.browser_search_many(kws, cfg, do_naver=use_naver, do_coupang=use_coupang,
                                           progress=lambda m: status_box.info(m))
                res["naver"], res["coupang"] = br["naver"], br["coupang"]
            except Exception as e:
                msg = f"크롬을 열지 못했어요: {e}"
                if use_naver:
                    res["naver"] = {kw: {"error": msg} for kw in kws}
                if use_coupang:
                    res["coupang"] = {kw: {"error": msg} for kw in kws}
            status_box.empty()
        for plat in ("naver", "coupang"):
            for kw, r in res[plat].items():
                if "items" in r:
                    s = E.summarize(r["items"], cfg)
                    r["summary"] = s
                    r["before"] = E.previous_ranks(plat, kw, before_time=run_time)
                    E.append_history({"time": run_time, "platform": plat, "keyword": kw, "ok": True,
                                      "our_ranks": s["our_ranks"], "status": s["status"]})
        st.session_state["last"] = res

    res = st.session_state.get("last")
    if not res:
        hist = E.load_history()
        if hist:
            st.info(f"마지막 확인: {hist[-1]['time']} — [순위 확인 시작]을 누르면 새로 확인해요.")
        else:
            st.info("[순위 확인 시작]을 누르면 크롬 창이 열려 네이버·쿠팡을 차례로 확인해요.")
    else:
        st.subheader(f"결과 · {res['time']}")
        rows_html = ["<table style='width:100%;border-collapse:collapse;font-size:0.95rem'>",
                     "<tr style='background:#f3f4f6'><th style='padding:8px;text-align:left'>키워드</th>"
                     "<th style='text-align:left'>네이버 쇼핑</th><th style='text-align:left'>쿠팡</th></tr>"]
        for kw in kws if kws else cfg["keywords"]:
            cells = []
            for plat in ("naver", "coupang"):
                r = res[plat].get(kw)
                if r is None:
                    cells.append("<span style='color:#999'>확인 안 함</span>")
                elif "error" in r:
                    cells.append(badge("확인불가") + f"<br><span style='color:#999;font-size:0.8rem'>{r['error'][:60]}</span>")
                else:
                    s = r["summary"]
                    cells.append(f"{badge(s['status'])} <b>{ranks_text(s['our_ranks'], r['items'])}</b>"
                                 f"<br><span style='color:#666;font-size:0.82rem'>{change_text(s['our_ranks'], r.get('before'))}</span>")
            rows_html.append(f"<tr style='border-top:1px solid #e5e7eb'><td style='padding:10px 8px'><b>{kw}</b></td>"
                             f"<td>{cells[0]}</td><td>{cells[1]}</td></tr>")
        rows_html.append("</table>")
        st.markdown("".join(rows_html), unsafe_allow_html=True)
        st.write("")
        st.markdown("**키워드별 자세히 보기** (우리 상품은 ⭐)")
        for kw in kws if kws else cfg["keywords"]:
            with st.expander(kw):
                cc = st.columns(2)
                for col, plat, label in ((cc[0], "naver", "네이버 쇼핑 1페이지"), (cc[1], "coupang", "쿠팡 1페이지")):
                    with col:
                        st.markdown(f"**{label}**")
                        r = res[plat].get(kw)
                        if not r:
                            st.caption("확인 안 함")
                            continue
                        if "error" in r:
                            st.warning(r["error"])
                            continue
                        df = pd.DataFrame(r["items"])
                        df["우리"] = df["ours"].map(lambda x: "⭐" if x else "")
                        df["광고"] = df["ad"].map(lambda x: "광고" if x else "")
                        show = ["rank", "우리", "광고", "title", "price"] + (["mall", "category"] if plat == "naver" else [])
                        df = df[[c for c in show if c in df.columns]].rename(columns={"rank": "순위", "title": "상품명", "price": "가격", "mall": "판매처", "category": "카테고리"})
                        only = st.toggle("우리 상품만", key=f"only_{plat}_{kw}")
                        if only:
                            df = df[df["우리"] == "⭐"]
                        st.dataframe(df, hide_index=True, width="stretch", height=min(38 * (len(df) + 1) + 3, 420))
                        if plat == "naver":
                            st.caption("네이버 순위는 광고 자리를 포함한 화면 순서예요.")
                        else:
                            st.caption("쿠팡 순위는 광고 자리를 포함한 화면 순서예요.")

    with st.expander("📅 지난 기록"):
        hist = E.load_history()
        if hist:
            h = pd.DataFrame(hist)
            h["우리 위치"] = h["our_ranks"].map(lambda x: ", ".join(f"{r}위" for r in x) if x else "-")
            h["플랫폼"] = h["platform"].map({"naver": "네이버", "coupang": "쿠팡"})
            st.dataframe(h[["time", "플랫폼", "keyword", "우리 위치", "status"]].iloc[::-1]
                         .rename(columns={"time": "시간", "keyword": "키워드", "status": "상태"}),
                         hide_index=True, width="stretch")
        else:
            st.caption("아직 기록이 없어요.")

# ================================================================ 2. 네이버 광고
with tab2:
    st.markdown("네이버 **쇼핑검색 광고** 상품별 성과와 입찰가를 검색광고 API로 바로 불러와요.")
    today = dt.date.today()
    c1, c2, c3 = st.columns([2, 2, 1])
    since = c1.date_input("시작일", today - dt.timedelta(days=7))
    until = c2.date_input("종료일", today - dt.timedelta(days=1))
    c3.write("")
    if c3.button("불러오기", type="primary"):
        try:
            with st.spinner("광고 데이터 불러오는 중..."):
                st.session_state["ads"] = E.shopping_ads_report(cfg, since.isoformat(), until.isoformat())
                st.session_state["ads_range"] = f"{since} ~ {until}"
        except Exception as e:
            st.error(str(e))
    rows = st.session_state.get("ads")
    if rows:
        df = pd.DataFrame(rows).drop(columns=["ad_id"])
        imp, clk, cost = df["노출수"].sum(), df["클릭수"].sum(), df["광고비"].sum()
        m = st.columns(4)
        m[0].metric("노출", f"{imp:,}")
        m[1].metric("클릭", f"{clk:,}")
        m[2].metric("클릭률", f"{clk / imp * 100:.2f}%" if imp else "-")
        m[3].metric("광고비", f"{cost:,}원")
        st.caption(f"기간: {st.session_state['ads_range']} · 클릭률이 평균보다 낮은 상품은 노란색으로 표시돼요.")
        avg = clk / imp * 100 if imp else 0
        df = df.sort_values("노출수", ascending=False)
        st.dataframe(
            df.style.apply(lambda r: ["background-color:#fff4c2" if (r["노출수"] >= 500 and r["클릭률(%)"] < avg) else "" for _ in r], axis=1),
            hide_index=True, width="stretch")

# ================================================================ 3. 자료 넣기
with tab3:
    st.markdown("광고 리포트 **엑셀/CSV**, 검색결과 **캡처 이미지**는 아래 상자에 끌어다 놓거나 클릭해서 넣어 주세요. "
                "검색결과 **텍스트**는 아래 칸에 붙여넣으면 돼요.")
    files = st.file_uploader("파일 끌어넣기", type=["xlsx", "xls", "csv", "png", "jpg", "jpeg"], accept_multiple_files=True)
    for f in files or []:
        st.markdown(f"#### 📄 {f.name}")
        data = f.getvalue()
        if f.name.lower().endswith((".png", ".jpg", ".jpeg")):
            kw = st.selectbox("어떤 키워드 검색 화면인가요?", ["(선택)"] + cfg["keywords"], key=f"kw_{f.name}")
            plat = st.radio("어느 사이트 화면인가요?", ["네이버 쇼핑", "쿠팡"], horizontal=True, key=f"pl_{f.name}")
            with st.spinner("캡처 글자 읽는 중..."):
                text, err = E.ocr_image(data)
            if err:
                st.warning(err)
                st.image(data, width=360)
                continue
            if plat == "네이버 쇼핑":
                items = E.parse_naver_text(text, cfg)
                s = E.summarize(items, cfg)
                st.markdown(f"{badge(s['status'])} 우리 상품 위치: **{ranks_text(s['our_ranks'], items)}** (상품 {len(items)}개 인식)", unsafe_allow_html=True)
                if items and kw != "(선택)" and st.button("이 결과를 기록에 저장", key=f"sv_{f.name}"):
                    E.append_history({"time": E.now_str(), "platform": "naver", "keyword": kw, "ok": True,
                                      "our_ranks": s["our_ranks"], "status": s["status"], "source": "캡처"})
                    st.success("저장했어요.")
            else:
                hits = E.find_in_text(text, cfg)
                st.markdown(f"우리 상품 키워드가 나온 줄: **{len(hits)}개**")
                for h in hits:
                    st.caption(h)
            st.caption("캡처 글자 읽기는 베타예요. 화면 전체 캡처는 글자가 작아 정확도가 떨어질 수 있어요.")
            continue
        try:
            platform, df, summary = E.parse_report(data, f.name)
            st.markdown(f"**{'네이버' if platform == 'naver' else '쿠팡' if platform == 'coupang' else ''} 광고 리포트** · {summary}")
            st.dataframe(df, hide_index=True, width="stretch")
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.markdown("#### 📋 검색결과 텍스트 붙여넣기")
    st.caption("네이버 쇼핑 검색결과 화면에서 Ctrl+A → Ctrl+C 한 다음 아래 칸에 Ctrl+V 하세요.")
    pc1, pc2 = st.columns(2)
    pkw = pc1.selectbox("키워드", ["(선택)"] + cfg["keywords"], key="paste_kw")
    pplat = pc2.radio("사이트", ["네이버 쇼핑", "쿠팡"], horizontal=True, key="paste_plat")
    text = st.text_area("여기에 붙여넣기", height=180)
    if st.button("분석하기") and text.strip():
        if pplat == "네이버 쇼핑":
            items = E.parse_naver_text(text, cfg)
            s = E.summarize(items, cfg)
            st.markdown(f"{badge(s['status'])} 우리 상품 위치: **{ranks_text(s['our_ranks'], items)}** (상품 {len(items)}개 인식)", unsafe_allow_html=True)
            if items:
                st.dataframe(pd.DataFrame(items).rename(columns={"rank": "순위", "title": "상품명", "ad": "광고", "ours": "우리"}),
                             hide_index=True, width="stretch")
            if items and pkw != "(선택)":
                E.append_history({"time": E.now_str(), "platform": "naver", "keyword": pkw, "ok": True,
                                  "our_ranks": s["our_ranks"], "status": s["status"], "source": "붙여넣기"})
                st.success("지난 기록에 저장했어요.")
        else:
            hits = E.find_in_text(text, cfg)
            st.markdown(f"우리 상품 키워드가 나온 줄: **{len(hits)}개**")
            for h in hits:
                st.caption(h)
            st.caption("쿠팡 붙여넣기는 정확한 순번 계산이 어려워서, 우리 상품이 있는지만 보여줘요.")

# ================================================================ 4. 설정
with tab4:
    with st.form("settings"):
        st.markdown("#### 키워드")
        kw_text = st.text_area("한 줄에 하나씩", "\n".join(cfg["keywords"]), height=150)
        top_n = st.number_input("몇 위까지를 '상단'으로 볼까요?", 1, 40, int(cfg["top_n"]))

        st.markdown("#### 네이버 검색광고 API (광고 성과용)")
        st.caption("searchad.naver.com 광고시스템 → 도구 → API 사용 관리")
        akey = st.text_input("액세스 라이선스", cfg["searchad_api_key"])
        asec = st.text_input("비밀키", cfg["searchad_secret"], type="password")
        acid = st.text_input("CUSTOMER_ID", cfg["searchad_customer_id"])

        st.markdown("#### 우리 상품 찾는 기준")
        malls = st.text_input("네이버 스토어 이름 (쉼표로 구분)", ", ".join(cfg["our_naver_mall_names"]))
        tkw = st.text_input("상품명에 들어간 우리 브랜드 (쉼표로 구분)", ", ".join(cfg["our_title_keywords"]))
        cpids = st.text_area("쿠팡 우리 상품 — 상품 링크를 그대로 붙여넣거나 번호만 넣어도 돼요 (한 줄에 하나)", "\n".join(cfg["our_coupang_product_ids"]), height=120)

        if st.form_submit_button("저장", type="primary"):
            split_lines = lambda s: [x.strip() for x in s.splitlines() if x.strip()]
            split_comma = lambda s: [x.strip() for x in s.split(",") if x.strip()]
            cfg.update({"keywords": split_lines(kw_text), "top_n": int(top_n),
                        "searchad_api_key": akey.strip(), "searchad_secret": asec.strip(), "searchad_customer_id": acid.strip(),
                        "our_naver_mall_names": split_comma(malls), "our_title_keywords": split_comma(tkw), "our_coupang_product_ids": E.extract_coupang_ids(cpids)})
            E.save_config(cfg)
            st.success("저장했어요. 키는 이 컴퓨터의 config.json 파일에만 저장돼요.")
            st.rerun()
