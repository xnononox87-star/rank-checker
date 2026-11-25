# -*- coding: utf-8 -*-
"""순위 확인 프로그램 - 데이터 수집/분석 엔진
- 네이버 쇼핑·쿠팡: 로그인하지 않은 별도 크롬 창을 열어 검색 결과만 읽음 (클릭 안 함)
  (네이버 쇼핑 검색 API는 2026-07-31 종료되어 사용하지 않음)
- 네이버 광고: 네이버 검색광고 API 사용
- 자료 넣기: 광고 리포트 엑셀/CSV, 붙여넣은 검색결과 텍스트, 캡처 이미지(OCR, 윈도우 전용)
"""
import base64
import datetime as dt
import hashlib
import hmac
import html
import io
import json
import os
import random
import re
import time
from urllib.parse import quote

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
CONFIG_PATH = os.path.join(BASE, "config.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_CONFIG = {
    "keywords": ["차수판", "창문차수막", "창문가림막", "플러드백", "방범창", "차양막"],
    "top_n": 10,  # 1페이지 중 몇 위까지를 '상단'으로 볼지
    "naver_page_size": 40,
    "coupang_page_size": 36,
    "naver_client_id": "",
    "naver_client_secret": "",
    "searchad_api_key": "",
    "searchad_secret": "",
    "searchad_customer_id": "",
    "our_naver_mall_names": [],
    "our_naver_product_ids": [],
    "our_title_keywords": [],
    "our_coupang_product_ids": [],
}


# ---------------------------------------------------------------- 설정/기록
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    if not cfg.get("brands_v2"):  # 1회: 브랜드 목록을 HGG/HGG테크/HGGTECH/가드랩/GUARDLAB 으로 통합
        merged = list(dict.fromkeys(DEFAULT_BRANDS + list(cfg.get("our_title_keywords") or []) + list(cfg.get("our_naver_mall_names") or [])))
        cfg.update({"our_title_keywords": merged, "our_naver_mall_names": [], "brands_v2": True})
        if os.path.exists(CONFIG_PATH):
            save_config(cfg)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def append_history(entry):
    hist = load_history()
    hist.append(entry)
    hist = hist[-500:]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)


def previous_ranks(platform, keyword, before_time=None):
    """지난번 기록에서 우리 상품 순위 목록"""
    for h in reversed(load_history()):
        if h.get("platform") == platform and h.get("keyword") == keyword and h.get("ok"):
            if before_time and h.get("time") >= before_time:
                continue
            return h.get("our_ranks", [])
    return None


# ---------------------------------------------------------------- 공통
def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _norm(s):
    return re.sub(r"\s+", "", (s or "")).lower()


DEFAULT_BRANDS = ["HGG", "HGG테크", "HGGTECH", "가드랩", "GUARDLAB"]


def our_brands(cfg):
    b = list(cfg.get("our_title_keywords") or []) + list(cfg.get("our_naver_mall_names") or [])
    return [x for x in dict.fromkeys(b) if x] or DEFAULT_BRANDS


def _title_is_ours(title, cfg):
    """스토어 이름이든 상품명이든 우리 브랜드가 들어 있으면 우리 상품 (대소문자·띄어쓰기 무시)"""
    t = _norm(title)
    return any(_norm(k) in t for k in our_brands(cfg))


def extract_coupang_ids(text):
    """쿠팡 링크/번호 여러 줄 -> 상품번호 목록 (coupang.com/vp/products/123?itemId=.. 형태 지원)"""
    ids = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        found = re.findall(r"(?:/products/|itemId=|vendorItemId=)(\d+)", line) or re.findall(r"\d{5,}", line)
        for f in found:
            if f not in ids:
                ids.append(f)
    return ids


def summarize(items, cfg):
    """순위 목록 -> 우리 상품 위치 요약"""
    ours = [it for it in items if it.get("ours")]
    ranks = [it["rank"] for it in ours]
    top_n = int(cfg.get("top_n", 10))
    if not items:
        status = "확인불가"
    elif any(r <= top_n for r in ranks):
        status = "상단"
    elif ranks:
        status = "1페이지"
    else:
        status = "없음"
    return {"our_ranks": ranks, "status": status, "count": len(items)}


# ---------------------------------------------------------------- 네이버 쇼핑
def naver_shop_search(keyword, cfg):
    cid, sec = cfg.get("naver_client_id"), cfg.get("naver_client_secret")
    if not cid or not sec:
        raise RuntimeError("설정 탭에서 네이버 검색 API Client ID / Secret 을 먼저 입력해 주세요.")
    r = requests.get(
        "https://openapi.naver.com/v1/search/shop.json",
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec},
        params={"query": keyword, "display": int(cfg.get("naver_page_size", 40)), "start": 1, "sort": "sim"},
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"네이버 API 오류 {r.status_code}: {r.text[:200]}")
    mall_names = {_norm(m) for m in cfg.get("our_naver_mall_names", []) if m}
    pids = {str(p).strip() for p in cfg.get("our_naver_product_ids", []) if str(p).strip()}
    out = []
    for i, it in enumerate(r.json().get("items", []), 1):
        title = _clean(it.get("title"))
        mall = _clean(it.get("mallName"))
        pid = str(it.get("productId", ""))
        ours = _norm(mall) in mall_names or pid in pids or _title_is_ours(title, cfg)
        cat = " > ".join(c for c in [it.get("category1"), it.get("category2"), it.get("category3"), it.get("category4")] if c)
        try:
            price = int(it.get("lprice") or 0)
        except ValueError:
            price = 0
        out.append({"rank": i, "title": title, "mall": mall, "price": price, "category": cat,
                    "link": it.get("link", ""), "product_id": pid, "ad": False, "ours": ours})
    return out


# ---------------------------------------------------------------- 쿠팡
_COUPANG_JS = r"""
() => {
  const root = document.querySelector('#product-list, #productList, ul.search-product-list, [class*="search-product-list"]') || document;
  const anchors = [...root.querySelectorAll('a[href*="/vp/products/"]')];
  const seen = new Set();
  const out = [];
  for (const a of anchors) {
    const m = a.href.match(/\/vp\/products\/(\d+)/);
    if (!m) continue;
    const box = a.closest('li') || a;
    if (seen.has(box)) continue;
    seen.add(box);
    const text = (box.innerText || '').trim();
    if (!text) continue;
    const nameEl = box.querySelector('.name, [class*="productName"], [class*="ProductUnit_productName"], [class*="title"]');
    let name = nameEl ? nameEl.innerText.trim() : '';
    if (!name) name = (text.split('\n').find(t => t.trim().length > 8) || '').trim();
    const priceM = text.match(/([\d,]+)\s*원/);
    const isAd = !!box.querySelector('[class*="ad-badge"], [class*="AdMark"], [class*="adMark"], [class*="AdBadge"]')
                 || /(^|\n)\s*AD\s*(\n|$)/.test(text);
    const ids = [m[1]];
    for (const k of ['itemId', 'vendorItemId']) { const mm = a.href.match(new RegExp(k + '=(\\d+)')); if (mm) ids.push(mm[1]); }
    out.push({product_id: m[1], ids: ids, name: name, price: priceM ? priceM[1] : '', is_ad: isAd});
  }
  return out;
}
"""


def _wait_if_captcha(page, progress, label):
    """보안문자(캡차)가 뜨면 CH님이 직접 풀 때까지 최대 90초 기다린다."""
    words = ["보안 확인", "자동입력 방지", "captcha", "CAPTCHA", "보안문자", "로봇이 아닙니다"]
    try:
        body = page.inner_text("body")[:3000]
    except Exception:
        return
    if any(w in body for w in words):
        if progress:
            progress(f"{label}: 보안문자가 떴어요. 열린 크롬 창에서 직접 풀어 주세요 (90초 기다려요)")
        for _ in range(45):
            page.wait_for_timeout(2000)
            try:
                body = page.inner_text("body")[:3000]
            except Exception:
                continue
            if not any(w in body for w in words):
                page.wait_for_timeout(2000)
                return


def _scroll(page, times=8):
    for _ in range(times):
        page.mouse.wheel(0, random.randint(1100, 1600))
        page.wait_for_timeout(random.randint(400, 800))


def _naver_one(page, kw, cfg, progress):
    size = int(cfg.get("naver_page_size", 40))
    url = f"https://search.shopping.naver.com/search/all?query={quote(kw)}&pagingIndex=1&pagingSize={size}&sort=rel"
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(random.randint(3000, 5000))
    _wait_if_captcha(page, progress, f"네이버 '{kw}'")
    _scroll(page, 10)
    text = page.inner_text("body")
    items = parse_naver_text(text, cfg)[:size]
    if not items:
        return {"error": "네이버 쇼핑 결과를 읽지 못했어요(보안문자·화면 구조 변경 가능). 붙여넣기로 확인해 주세요."}
    return {"items": items}


def _coupang_one(page, kw, cfg, progress):
    size = int(cfg.get("coupang_page_size", 36))
    pids = {str(p).strip() for p in cfg.get("our_coupang_product_ids", []) if str(p).strip()}
    url = f"https://www.coupang.com/np/search?q={quote(kw)}&page=1&listSize={size}"
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(random.randint(3000, 5000))
    _wait_if_captcha(page, progress, f"쿠팡 '{kw}'")
    _scroll(page, 8)
    raw = page.evaluate(_COUPANG_JS)
    if not raw:
        body = (page.inner_text("body") or "")[:2000]
        blocked = any(w in body for w in ["Access Denied", "접근이 차단", "비정상적인"]) or "denied" in page.title().lower()
        return {"error": "쿠팡이 자동 검색을 차단했어요. 붙여넣기로 확인해 주세요." if blocked
                else "검색 결과를 읽지 못했어요(화면 구조 변경 가능). 붙여넣기로 확인해 주세요."}
    items, organic = [], 0
    for i, it in enumerate(raw[:size], 1):
        if not it["is_ad"]:
            organic += 1
        ours = bool(pids & set(it.get("ids") or [it["product_id"]])) or _title_is_ours(it["name"], cfg)
        items.append({"rank": i, "organic_rank": None if it["is_ad"] else organic,
                      "title": it["name"], "price": it["price"], "ad": it["is_ad"],
                      "product_id": it["product_id"],
                      "link": f"https://www.coupang.com/vp/products/{it['product_id']}", "ours": ours})
    return {"items": items}


def browser_search_many(keywords, cfg, do_naver=True, do_coupang=True, progress=None):
    """로그인하지 않은 전용 크롬 창으로 네이버 쇼핑·쿠팡 검색 결과 1페이지를 읽는다. 클릭은 하지 않는다."""
    from playwright.sync_api import sync_playwright

    profile = os.path.join(DATA_DIR, "browser_profile")
    results = {"naver": {}, "coupang": {}}
    jobs = [("naver", kw) for kw in keywords if do_naver] + [("coupang", kw) for kw in keywords if do_coupang]
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, channel="chrome", headless=False, locale="ko-KR",
            viewport={"width": 1300, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        last_site = None
        for n, (site, kw) in enumerate(jobs):
            label = "네이버" if site == "naver" else "쿠팡"
            if progress:
                progress(f"{label} '{kw}' 확인 중... ({n + 1}/{len(jobs)}, 키워드 사이에 몇 초씩 쉬어요)")
            try:
                if site != last_site:
                    home = "https://shopping.naver.com/" if site == "naver" else "https://www.coupang.com/"
                    try:
                        page.goto(home, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(random.randint(2500, 4000))
                    except Exception:
                        pass
                    last_site = site
                fn = _naver_one if site == "naver" else _coupang_one
                results[site][kw] = fn(page, kw, cfg, progress)
            except Exception as e:  # noqa
                results[site][kw] = {"error": f"오류: {e}"}
            if n < len(jobs) - 1:
                time.sleep(random.uniform(6, 12))
        ctx.close()
    return results


# ---------------------------------------------------------------- 네이버 검색광고 API
class SearchAd:
    BASE_URL = "https://api.searchad.naver.com"

    def __init__(self, cfg):
        self.key = cfg.get("searchad_api_key")
        self.secret = cfg.get("searchad_secret")
        self.cid = str(cfg.get("searchad_customer_id") or "")
        if not (self.key and self.secret and self.cid):
            raise RuntimeError("설정 탭에서 검색광고 API 라이선스 / 비밀키 / CUSTOMER_ID 를 먼저 입력해 주세요.")

    def _headers(self, method, uri):
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(hmac.new(self.secret.encode(), f"{ts}.{method}.{uri}".encode(), hashlib.sha256).digest()).decode()
        return {"X-Timestamp": ts, "X-API-KEY": self.key, "X-Customer": self.cid, "X-Signature": sig,
                "Content-Type": "application/json; charset=UTF-8"}

    def get(self, uri, params=None):
        r = requests.get(self.BASE_URL + uri, headers=self._headers("GET", uri), params=params, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"검색광고 API 오류 {r.status_code} ({uri}): {r.text[:200]}")
        return r.json()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def shopping_ads_report(cfg, since, until):
    api = SearchAd(cfg)
    rows = []
    for c in api.get("/ncc/campaigns"):
        if c.get("campaignTp") != "SHOPPING":
            continue
        for g in api.get("/ncc/adgroups", {"nccCampaignId": c["nccCampaignId"]}):
            for a in api.get("/ncc/ads", {"nccAdgroupId": g["nccAdgroupId"]}):
                ref = a.get("referenceData") or {}
                attr = a.get("adAttr") or {}
                name = ref.get("productName") or ref.get("productTitle") or (a.get("ad") or {}).get("productName") or a.get("nccAdId")
                use_group = attr.get("useGroupBidAmt", True)
                bid = g.get("bidAmt") if use_group or attr.get("bidAmt") is None else attr.get("bidAmt")
                on = not (a.get("userLock") or g.get("userLock") or c.get("userLock"))
                rows.append({"ad_id": a.get("nccAdId"), "캠페인": c.get("name"), "광고그룹": g.get("name"),
                             "상품": name, "상태": "ON" if on else "OFF",
                             "입찰가": int(bid or 0), "그룹입찰가사용": "예" if use_group else "아니오"})
    ids = [r["ad_id"] for r in rows if r["ad_id"]]
    stats = {}
    fields = ["impCnt", "clkCnt", "ctr", "cpc", "avgRnk", "salesAmt"]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = api.get("/stats", {"ids": ",".join(chunk), "fields": json.dumps(fields),
                                  "timeRange": json.dumps({"since": since, "until": until})})
        for d in (data.get("data") or []):
            stats[d.get("id")] = d
    for r in rows:
        s = stats.get(r["ad_id"], {})
        r["노출수"] = int(_num(s.get("impCnt")))
        r["클릭수"] = int(_num(s.get("clkCnt")))
        r["클릭률(%)"] = round(_num(s.get("ctr")), 2)
        r["평균CPC"] = int(_num(s.get("cpc")))
        r["평균노출순위"] = round(_num(s.get("avgRnk")), 1)
        r["광고비"] = int(_num(s.get("salesAmt")))
    return rows


# ---------------------------------------------------------------- 리포트 파일
def _to_number(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace(",", "").replace("원", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_report(data, filename):
    """네이버/쿠팡 광고 리포트(엑셀/CSV) -> (플랫폼, 표, 요약문)"""
    import pandas as pd

    name = filename.lower()
    if name.endswith(".csv"):
        raw = None
        for enc in ("utf-8-sig", "cp949"):
            try:
                raw = pd.read_csv(io.BytesIO(data), header=None, encoding=enc, dtype=str)
                break
            except Exception:
                continue
        sheets = [raw] if raw is not None else []
    else:
        xl = pd.read_excel(io.BytesIO(data), header=None, sheet_name=None, dtype=object)
        sheets = list(xl.values())
    for raw in sheets:
        hdr = None
        for i in range(min(len(raw), 30)):
            vals = [str(v) for v in raw.iloc[i].tolist()]
            if any("노출" in v for v in vals) and any("클릭" in v for v in vals):
                hdr = i
                break
        if hdr is None:
            continue
        cols = [str(c).strip() if str(c) != "nan" else f"col{j}" for j, c in enumerate(raw.iloc[hdr].tolist())]
        df = raw.iloc[hdr + 1:].copy()
        df.columns = cols
        df = df.dropna(how="all")
        joined = " ".join(cols)
        platform = "naver" if ("소재" in joined or "평균노출순위" in joined) else ("coupang" if any(k in joined for k in ["ROAS", "전환", "광고집행", "광고비"]) else "unknown")
        if platform == "naver" and "소재 ID" in df.columns:
            df = df[df["소재 ID"].astype(str).str.startswith("nad-")]
            df["상품"] = df["소재"].astype(str).str.split(",").str[0]
        name_col = next((c for c in df.columns if c == "상품"), None) or \
            next((c for c in df.columns if "상품명" in c), None) or \
            next((c for c in df.columns if "캠페인" in c), None) or \
            next((c for c in df.columns if "소재" in c and "ID" not in c), None)
        imp_col = next((c for c in df.columns if "노출수" in c or c == "노출"), None)
        clk_col = next((c for c in df.columns if "클릭수" in c or c == "클릭"), None)
        cost_col = next((c for c in df.columns if c in ("광고비", "총비용", "집행 광고비", "광고비(원)") or ("광고비" in c and "%" not in c)), None)
        sales_col = next((c for c in df.columns if "전환매출" in c or ("매출" in c and "1일" in c)), None) or next((c for c in df.columns if "매출" in c), None)
        out = pd.DataFrame()
        out["상품/캠페인"] = df[name_col].astype(str) if name_col else ""
        out["노출수"] = df[imp_col].map(_to_number) if imp_col else None
        out["클릭수"] = df[clk_col].map(_to_number) if clk_col else None
        if cost_col:
            out["광고비"] = df[cost_col].map(_to_number)
        if sales_col:
            out["전환매출"] = df[sales_col].map(_to_number)
        for extra in ["입찰가", "평균노출순위", "PC통검평균노출순위", "모바일통검평균노출순위"]:
            if extra in df.columns:
                out[extra] = df[extra].map(_to_number)
        if name_col:
            num_cols = [c for c in out.columns if c not in ("상품/캠페인", "입찰가") and "순위" not in c]
            agg = {c: "sum" for c in num_cols}
            for c in out.columns:
                if c == "입찰가" or "순위" in c:
                    agg[c] = "mean"
            out = out.groupby("상품/캠페인", as_index=False).agg(agg)
        out["클릭률(%)"] = (out["클릭수"] / out["노출수"].where(out["노출수"] > 0) * 100).round(2)
        if "광고비" in out.columns:
            out["CPC"] = (out["광고비"] / out["클릭수"].where(out["클릭수"] > 0)).round(0)
            if "전환매출" in out.columns:
                out["ROAS(%)"] = (out["전환매출"] / out["광고비"].where(out["광고비"] > 0) * 100).round(0)
        out = out.sort_values("노출수", ascending=False).reset_index(drop=True)
        tot_imp, tot_clk = out["노출수"].sum(), out["클릭수"].sum()
        summary = f"상품 {len(out)}개 · 노출 {int(tot_imp):,} · 클릭 {int(tot_clk):,} · 클릭률 {tot_clk / tot_imp * 100:.2f}%" if tot_imp else "합계를 계산할 수 없어요."
        if "광고비" in out.columns and out["광고비"].sum():
            summary += f" · 광고비 {int(out['광고비'].sum()):,}원"
        return platform, out, summary
    raise ValueError("이 파일에서 '노출수/클릭수' 머리글을 찾지 못했어요. 광고 리포트 파일이 맞는지 확인해 주세요.")


# ---------------------------------------------------------------- 붙여넣은 텍스트 / 캡처
_NAVER_END = re.compile(r"(신고하기|정보\s*수정\s*요청)")


def parse_naver_text(text, cfg):
    """네이버 쇼핑 검색결과 화면을 Ctrl+A, Ctrl+C 로 복사한 텍스트(또는 캡처 OCR 결과)를 상품 단위로 나눈다."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    start = 0
    for i, l in enumerate(lines):  # 정렬 메뉴 이후부터 시작
        if "등록일순" in l or "네이버 랭킹순" in l:
            start = i + 1
    blocks, cur = [], []
    for l in lines[start:]:
        cur.append(l)
        if _NAVER_END.search(l):
            blocks.append(cur)
            cur = []
    items = []
    for i, b in enumerate(blocks, 1):
        joined = "\n".join(b)
        title = next((l for l in b if len(l) > 12 and "원" not in l[-2:] and not l.startswith("등록일")), b[0])
        ad = any(re.match(r"^광고", l) for l in b)
        ours = _title_is_ours(joined, cfg)
        items.append({"rank": i, "title": title[:80], "ad": ad, "ours": ours})
    return items


def find_in_text(text, cfg):
    """구조를 알 수 없는 텍스트(쿠팡 등)에서 우리 상품 키워드가 나오는 줄 찾기"""
    keys = [k for k in cfg.get("our_title_keywords", []) + cfg.get("our_naver_mall_names", []) if k]
    keys += [str(p) for p in cfg.get("our_coupang_product_ids", []) if str(p).strip()]
    hits = []
    for l in (text or "").splitlines():
        if any(_norm(k) in _norm(l) for k in keys):
            hits.append(l.strip()[:100])
    return hits


def ocr_image(data):
    """캡처 이미지 글자 읽기 (윈도우 기본 OCR 사용, 베타). 반환: (텍스트, 오류메시지)"""
    try:
        import asyncio
        from PIL import Image
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    except Exception:
        return "", "이 컴퓨터에서는 캡처 글자 읽기(OCR)를 쓸 수 없어요. 검색결과 화면을 Ctrl+A → Ctrl+C 로 복사해서 붙여넣어 주세요."

    async def _one(png_bytes):
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(png_bytes)
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bmp = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("윈도우에 한국어 OCR 언어가 없어요.")
        res = await engine.recognize_async(bmp)
        return "\n".join(l.text for l in res.lines)

    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        scale = 2 if img.width < 1400 else 1
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale))
        texts, tile = [], 1800
        for y in range(0, img.height, tile - 100):
            part = img.crop((0, y, img.width, min(img.height, y + tile)))
            if part.width > 4000:
                part = part.resize((4000, int(part.height * 4000 / part.width)))
            buf = io.BytesIO()
            part.save(buf, format="PNG")
            texts.append(asyncio.run(_one(buf.getvalue())))
        return "\n".join(texts), ""
    except Exception as e:
        return "", f"캡처 글자 읽기에 실패했어요({e}). 텍스트 복사·붙여넣기를 이용해 주세요."


def now_str():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")
