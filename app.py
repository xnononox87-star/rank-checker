# -*- coding: utf-8 -*-
import datetime as dt
import os
import time

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


@st.cache_resource
def _receiver():
    return E.start_receiver()


_receiver()
STATUS_BADGE = {"상단": ("b-top", "상단"), "1페이지": ("b-p1", "1페이지 하단"),
                "없음": ("b-none", "1페이지 없음"), "확인불가": ("b-err", "확인 불가")}


def badge(status):
    cls, label = STATUS_BADGE.get(status, ("b-err", status))
    return f'<span class="badge {cls}">{label}</span>'


def thumb_uri(path):
    """캡처 파일 -> 작은 썸네일(base64). 한 번 만들면 .thumb.jpg 로 저장해 재사용."""
    import base64
    if not path or not os.path.exists(path):
        return ""
    tp = path + ".thumb.jpg"
    try:
        if not os.path.exists(tp):
            from PIL import Image
            im = Image.open(path).convert("RGB")
            w = 180
            im = im.resize((w, max(1, int(im.height * w / im.width))))
            im.save(tp, "JPEG", quality=80)
        with open(tp, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def rank_cards(ranks, items):
    """'3위 직구유통' + 썸네일 카드 여러 개"""
    out = []
    for r in ranks:
        it = next((x for x in items if x["rank"] == r), {}) or {}
        uri = thumb_uri(it.get("shot")) or it.get("thumb_url", "")
        img = (f"<img src='{uri}' style='width:86px;height:86px;object-fit:cover;object-position:top;"
               f"border-radius:6px;border:1px solid #ddd;display:block;margin:0 auto 3px'>") if uri else \
              "<div style='width:86px;height:86px;border-radius:6px;background:#f1f1f1;margin:0 auto 3px;" \
              "display:flex;align-items:center;justify-content:center;color:#aaa;font-size:0.7rem'>사진 없음</div>"
        ad = ""
        out.append(f"<div title='{(it.get('title') or '').replace(chr(39), '')}' style='display:inline-block;width:96px;margin:4px 4px 2px 0;"
                   f"vertical-align:top;text-align:center;font-size:0.78rem;line-height:1.25'>{img}"
                   f"<b>{r}위</b>{ad}<br><span style='color:#555'>{it.get('mall', '')}</span></div>")
    return "".join(out)


def ranks_text(ranks, items=None):
    if not ranks:
        return "-"
    parts = []
    for r in ranks:
        tag = ""
        if items:
            it = next((x for x in items if x["rank"] == r), None)
            if it and it.get("ad"):
                tag = ""
            if it and it.get("mall"):
                tag += f" {it['mall']}"
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
        use_coupang = st.checkbox("쿠팡 (자동)", value=True)
        use_whale = st.checkbox("네이버 가격비교 (웨일 확장)", value=True,
                                help="웨일에 설치한 'HGG 네이버 순위 확인'이 웨일 뒤쪽 탭에서 천천히 검색해요. 웨일이 켜져 있어야 해요.")
        use_naver = False  # 네이버 자동 크롬은 접속 제한 때문에 사용 안 함
        st.caption("쿠팡은 크롬 창이 따로 열리고, 네이버는 웨일 뒤쪽 탭에서 확인해요. 둘 다 끝날 때까지 그 창·탭은 닫지 마세요.")
    st.caption(f"'상단' = 1페이지 {cfg['top_n']}위 이내 · 순위는 1페이지 안에서 몇 번째인지예요. 같은 상품을 여러 개 등록했다면 모두 표시돼요.")

    if st.button("▶ 순위 확인 시작", type="primary", disabled=not kws):
        run_time = E.now_str()
        prev = st.session_state.get("last") or {}
        res = {"time": run_time, "naver": {} if use_naver else dict(prev.get("naver") or {}), "coupang": {}}
        naver_run = E.request_naver(kws) if use_whale else None
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
        if naver_run:  # 웨일 확장이 끝날 때까지 기다렸다가 가져오기 (최대 10분)
            wait_box = st.empty()
            t0 = time.time()
            while True:
                state, n = E.pending_state(naver_run)
                if state == "done":
                    break
                if state == "waiting" and time.time() - t0 > 60:
                    wait_box.warning("웨일 확장이 응답하지 않아요. 웨일이 켜져 있는지, whale://extensions 에서 'HGG 네이버 순위 확인'의 [새로고침]을 눌렀는지 확인해 주세요.")
                    break
                if time.time() - t0 > 600:
                    wait_box.warning("네이버 확인이 오래 걸려서 기다리기를 멈췄어요. 끝나면 [네이버 결과 불러오기]를 눌러 주세요.")
                    break
                wait_box.info(f"네이버 가격비교 확인 중... 웨일 뒤쪽 탭에서 진행 ({n}/{len(kws)})")
                time.sleep(3)
            wait_box.empty()
            st.session_state["last"] = res
            st.session_state.pop("inbox_loaded", None)
        for plat in ("naver", "coupang"):
            if plat == "naver" and not use_naver:
                continue
            for kw, r in res[plat].items():
                if "items" in r:
                    s = E.summarize(r["items"], cfg)
                    r["summary"] = s
                    r["before"] = E.previous_ranks(plat, kw, before_time=run_time)
                    E.append_history({"time": run_time, "platform": plat, "keyword": kw, "ok": True,
                                      "our_ranks": s["our_ranks"], "status": s["status"]})
        st.session_state["last"] = res

    st.markdown("##### 🟢 네이버 가격비교 (웨일 확장 프로그램)")
    st.caption("웨일 오른쪽 위 확장 아이콘 **HGG 네이버 순위 확인** → [네이버 순위 확인 시작] → 끝나면 아래 버튼. 몇 분 간격으로 계속 돌리지는 마세요.")
    run = E.latest_inbox()
    if run:
        n_done = len(run.get("results") or {})
        st.caption(f"마지막 네이버 확인: {run['run_id'][:4]}-{run['run_id'][4:6]}-{run['run_id'][6:8]} "
                   f"{run['run_id'][9:11]}:{run['run_id'][11:13]} · 키워드 {n_done}개 · {'완료' if run.get('done') else '진행 중'}")
    if run and run.get("results") and not any((r or {}).get("incognito") for r in run["results"].values()):
        st.warning("네이버를 **시크릿 창이 아닌 일반 창**으로 검색했어요 (로그인·검색기록이 순위에 섞일 수 있어요). "
                   "웨일 주소창 `whale://extensions` → **HGG 네이버 순위 확인**의 **H 아이콘** 클릭 → "
                   "**'시크릿 모드에서 허용'**(또는 '시크릿 창에서 사용') 켜기 → 다음 확인부터 시크릿 창으로 검색해요.")
    auto = run and run.get("done") and st.session_state.get("inbox_loaded") != run["run_id"]
    if (st.button("네이버 결과 불러오기") or auto) and run:
        parsed = E.parse_inbox(run, cfg)
        last = st.session_state.get("last") or {"time": E.now_str(), "naver": {}, "coupang": {}}
        rt = f"{run['run_id'][:4]}-{run['run_id'][4:6]}-{run['run_id'][6:8]} {run['run_id'][9:11]}:{run['run_id'][11:13]}"
        already = {h.get("run_id") for h in E.load_history() if h.get("run_id")}
        for kw, r in parsed.items():
            if "items" in r:
                sm = E.summarize(r["items"], cfg)
                r["summary"] = sm
                r["before"] = E.previous_ranks("naver", kw, before_time=rt)
                if run["run_id"] not in already:
                    E.append_history({"time": rt, "platform": "naver", "keyword": kw, "ok": True, "run_id": run["run_id"],
                                      "our_ranks": sm["our_ranks"], "status": sm["status"], "source": "웨일 확장"})
            last["naver"][kw] = r
        st.session_state["last"] = last
        st.session_state["inbox_loaded"] = run["run_id"]
    for kw, r in ((st.session_state.get("last") or {}).get("naver") or {}).items():
        if r.get("raw") and os.path.exists(r["raw"]):
            with open(r["raw"], "rb") as f:
                st.download_button(f"'{kw}' 원문 받기 (Claude에게 보내기)", f.read(), file_name=os.path.basename(r["raw"]), key=f"raw_{kw}")

    with st.expander("📋 네이버 직접 붙여넣기 (확장 프로그램이 안 될 때)", expanded=False):
        st.markdown("1) 키워드 버튼을 눌러 평소 브라우저에서 네이버 쇼핑을 열고 → 2) 화면에서 **Ctrl+A → Ctrl+C** → "
                    "3) 그 키워드 칸에 **Ctrl+V** → 4) 맨 아래 **[네이버 결과 반영]**")
        pasted = {}
        for kw in (kws or cfg["keywords"]):
            a, b = st.columns([1, 3])
            a.link_button(f"'{kw}' 열기", f"https://search.shopping.naver.com/search/all?query={E.quote(kw)}")
            pasted[kw] = b.text_area(f"{kw} 붙여넣기", key=f"np_{kw}", height=68, label_visibility="collapsed",
                                     placeholder=f"'{kw}' 검색 화면 전체를 여기에 붙여넣기")
        if st.button("네이버 결과 반영", type="primary"):
            run_time = E.now_str()
            last = st.session_state.get("last") or {"time": run_time, "naver": {}, "coupang": {}}
            done = 0
            for kw, text in pasted.items():
                if not text.strip():
                    continue
                items = E.parse_naver_text(text, cfg)
                if not items:
                    last["naver"][kw] = {"error": "붙여넣은 내용에서 상품을 찾지 못했어요. 검색 화면 전체(Ctrl+A)를 복사했는지 확인해 주세요."}
                    continue
                sm = E.summarize(items, cfg)
                last["naver"][kw] = {"items": items, "summary": sm, "before": E.previous_ranks("naver", kw, before_time=run_time)}
                E.append_history({"time": run_time, "platform": "naver", "keyword": kw, "ok": True,
                                  "our_ranks": sm["our_ranks"], "status": sm["status"], "source": "붙여넣기"})
                done += 1
            st.session_state["last"] = last
            st.success(f"{done}개 키워드를 반영했어요. 아래 결과 표에서 확인하세요.")

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
                    cells.append(f"{badge(s['status'])} <span style='color:#666;font-size:0.82rem'>{change_text(s['our_ranks'], r.get('before'))}</span>"
                                 f"<br>{rank_cards(s['our_ranks'], r['items']) if s['our_ranks'] else '-'}")
            rows_html.append(f"<tr style='border-top:1px solid #e5e7eb'><td style='padding:10px 8px;vertical-align:top;white-space:nowrap'><b>{kw}</b></td>"
                             f"<td style='padding:8px;vertical-align:top'>{cells[0]}</td><td style='padding:8px;vertical-align:top'>{cells[1]}</td></tr>")
        rows_html.append("</table>")
        rows_html.append("<div style='color:#888;font-size:0.8rem;margin-top:6px'>쿠팡은 검색 화면에 판매자가 안 나와서, 그 노출상품을 등록한 우리 계정 이름으로 표시해요. 여러 계정이 같은 노출상품을 쓰면 실제로는 그중 아이템위너 한 곳이 노출돼요.</div>")
        st.markdown("".join(rows_html), unsafe_allow_html=True)
        st.write("")
        shots = []
        for kw in kws if kws else cfg["keywords"]:
            for plat, label in (("naver", "네이버"), ("coupang", "쿠팡")):
                r = res[plat].get(kw) or {}
                for it in r.get("items", []):
                    if it.get("ours") and it.get("shot") and os.path.exists(it["shot"]):
                        tag = ""
                        shots.append((it["shot"], f"{kw} · {label} {it['rank']}위 {tag}{it.get('mall', '')}"))
        if shots:
            with st.expander("📸 우리 상품 캡처 크게 보기"):
                for i in range(0, len(shots), 4):
                    cols = st.columns(4)
                    for col, (path, cap) in zip(cols, shots[i:i + 4]):
                        col.image(path, caption=cap, width="stretch")
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
                            d = r.get("debug") or {}
                            if d.get("shot") and os.path.exists(d["shot"]):
                                st.caption(f"그때 화면 · {d.get('url', '')}")
                                st.image(d["shot"], width="stretch")
                            continue
                        df = pd.DataFrame(r["items"])
                        df["우리"] = df["ours"].map(lambda x: "⭐" if x else "")
                        df["광고"] = df["ad"].map(lambda x: "광고" if x else "")
                        show = ["rank", "우리", "mall", "title", "price"]
                        df = df[[c for c in show if c in df.columns]].rename(columns={"rank": "순위", "title": "상품명", "price": "가격", "mall": "상점", "category": "카테고리"})
                        for it in r["items"]:
                            if it.get("ours") and it.get("shot") and os.path.exists(it["shot"]):
                                st.image(it["shot"], caption=f"{it['rank']}위 {it.get('mall', '')}", width="stretch")
                        only = st.toggle("우리 상품만", key=f"only_{plat}_{kw}")
                        if only:
                            df = df[df["우리"] == "⭐"]
                        st.dataframe(df, hide_index=True, width="stretch", height=min(38 * (len(df) + 1) + 3, 420))
                        if plat == "naver":
                            st.caption("네이버 순위는 시크릿 창에서 검색했을 때 화면 맨 위부터 센 순서예요.")
                        else:
                            st.caption("쿠팡 순위는 시크릿 창에서 검색했을 때 검색 결과 목록 맨 위 왼쪽부터 센 순서예요.")

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
                st.dataframe(pd.DataFrame(items).drop(columns=["ad"], errors="ignore").rename(columns={"rank": "순위", "title": "상품명", "ours": "우리", "mall": "상점", "price": "가격"}),
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
        tkw = st.text_input("우리 브랜드·스토어 이름 (쉼표로 구분) — 스토어 이름이나 상품명에 이 중 하나라도 들어가면 우리 상품 (대소문자·띄어쓰기 무시)",
                            ", ".join(E.our_brands(cfg)))
        cpids = st.text_area("쿠팡 우리 상품 — 노출상품ID 또는 옵션ID, 상품 링크 아무거나 (한 줄에 하나, 등록상품ID는 안 돼요)", "\n".join(cfg["our_coupang_product_ids"]), height=120)

        if st.form_submit_button("저장", type="primary"):
            split_lines = lambda s: [x.strip() for x in s.splitlines() if x.strip()]
            split_comma = lambda s: [x.strip() for x in s.split(",") if x.strip()]
            cfg.update({"keywords": split_lines(kw_text), "top_n": int(top_n),
                        "searchad_api_key": akey.strip(), "searchad_secret": asec.strip(), "searchad_customer_id": acid.strip(),
                        "our_naver_mall_names": [], "our_title_keywords": split_comma(tkw), "our_coupang_product_ids": E.extract_coupang_ids(cpids)})
            E.save_config(cfg)
            st.success("저장했어요. 키는 이 컴퓨터의 config.json 파일에만 저장돼요.")
            st.rerun()
