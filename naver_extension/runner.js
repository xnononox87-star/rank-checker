const API = "http://127.0.0.1:8765";
const logBox = document.getElementById("log");
const btn = document.getElementById("go");
const log = (m, cls) => { const d = document.createElement("div"); if (cls) d.className = cls; d.textContent = m; logBox.appendChild(d); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function waitLoaded(tabId) {
  return new Promise(resolve => {
    let done = false;
    const fin = () => { if (!done) { done = true; chrome.tabs.onUpdated.removeListener(on); resolve(); } };
    const on = (id, info) => { if (id === tabId && info.status === "complete") fin(); };
    chrome.tabs.onUpdated.addListener(on);
    setTimeout(fin, 30000);
  });
}

// ---------------------------------------------------------------- 검색 화면 안에서 실행되는 함수들
// 네이버 가격비교: 상품마다 한 번 나오는 '신고하기' / '정보 수정요청' 을 기준으로 상품 한 줄씩 읽는다
async function collectNaver() {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 25; i++) {
    window.scrollBy(0, 900 + Math.random() * 500); await sleep(450 + Math.random() * 450);
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 50) break;
  }
  window.scrollTo(0, 0);
  const text = document.body.innerText || "";
  const head = text.slice(0, 3000);
  const blocked = /접속이 일시적으로 제한|비정상적인 접근/.test(head);
  const login = /nid\.naver\.com/.test(location.host) || (!!document.querySelector('input[type="password"]') && /로그인/.test(head));
  const captcha = !blocked && !login && /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test(head);
  // '신고하기' 글자를 가진 가장 안쪽 요소 (앞에 종 모양 아이콘이 붙어 있어도 찾도록)
  const MK = /^\s*(신고하기|정보\s*수정\s*요청)\s*$/;
  const leafs = [...document.querySelectorAll("a, button, span, em, div, p")].filter(el =>
    MK.test(el.textContent || "") && ![...el.children].some(c => MK.test(c.textContent || "")));
  const boxes = [];
  for (const mk of leafs) {
    let box = mk;
    while (box.parentElement && box.parentElement !== document.body &&
           !leafs.some(o => o !== mk && box.parentElement.contains(o))) box = box.parentElement;
    if (!boxes.includes(box)) boxes.push(box);
  }
  boxes.sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  const SKIP = /^(톡톡|톡톡문의|문의|공유|찜하기|장바구니|구매하기|상세보기|N\+.*|네이버페이|오늘출발|도착보장|무료배송|구매정보|적립|쇼핑몰별 최저가|전체보기.*|광고.*|등록일.*|찜.*|리뷰.*|.*pay.*|포인트.*|배송비.*|무료|최저|원|[\d,.]+원?|[\d.]+%.*|\(.*\)|★.*|구성 별 정보.*|판매처.*|신고하기|정보\s*수정\s*요청|.*>.*)$/i;
  const srcOf = i => [i.currentSrc, i.src, i.dataset && i.dataset.src, i.getAttribute("data-src")].find(u => u && /^https?:/.test(u)) || "";
  const items = boxes.map((box, idx) => {
    box.setAttribute("data-hgg-idx", String(idx));
    const alts = [...box.querySelectorAll("img[alt]")].map(i => i.alt).filter(Boolean).join("\n");
    const lines = (box.innerText || "").split("\n").map(l => l.trim()).filter(Boolean);
    const links = [...box.querySelectorAll("a")].map(a => (a.innerText || "").trim()).filter(t => t.length >= 8 && !/신고|수정요청|구매정보|전체보기/.test(t));
    const title = links[0] || lines.find(l => l.length >= 10) || "";
    const mi = lines.findIndex(l => /^(신고하기|정보\s*수정\s*요청)$/.test(l) || /신고하기$/.test(l));
    const after = mi >= 0 ? lines.slice(mi + 1) : [];
    const catalog = after.includes("쇼핑몰별 최저가");
    const names = after.map(l => l.replace(/\s*[\d,]+원?$/, "").trim()).filter(l => l && !SKIP.test(l) && l.length <= 30);
    const im = [...box.querySelectorAll("img")].find(i => srcOf(i) && !/icon|logo|badge|npay/i.test(srcOf(i)));
    // 판매처가 글자 없이 로고 이미지로만 나오면 그 이미지 이름(alt)을 판매처로
    const logoAlt = [...box.querySelectorAll("img[alt]")].map(i => (i.alt || "").trim())
      .find(a => a && a !== title && a.length <= 30 && !/톡톡|npay|네이버페이|배지|badge|아이콘/i.test(a)) || "";
    return { title, mall: catalog ? "" : (names[0] || logoAlt), mall_list: catalog ? names.join("\n") : "",
             text: lines.join("\n").slice(0, 1500), alts, idx, img: im ? srcOf(im) : "" };
  }).filter(it => it.title);
  const images = [...document.querySelectorAll("img")].map(i => ({ src: srcOf(i), alt: i.alt || "",
    text: ((i.closest("li, [class*=item]") || i.parentElement || {}).innerText || "").slice(0, 300) })).filter(x => x.src).slice(0, 300);
  return { text: text.slice(0, 60000), blocked, captcha, login, url: location.href, items, images };
}

// 쿠팡: 상품 칸이 가장 많이 모여 있는 목록 = 검색 결과 본문 (배너·추천 줄은 뺀다), 왼쪽 위부터 순서대로
async function collectCoupang() {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 25; i++) {
    window.scrollBy(0, 900 + Math.random() * 500); await sleep(450 + Math.random() * 450);
    if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 50) break;
  }
  window.scrollTo(0, 0);
  const text = document.body.innerText || "";
  const blocked = /Access Denied|접근이 차단|비정상적인/.test(text.slice(0, 2000)) || /denied/i.test(document.title);
  const cards = new Map();
  for (const a of document.querySelectorAll('a[href*="/vp/products/"]')) {
    const card = a.closest("li") || a.parentElement;
    if (!card || cards.has(card)) continue;
    // 화면에 실제로 보이는 상품 칸만 (숨겨진 빈 칸·자리표시 칸은 순위에서 뺀다)
    const r = card.getBoundingClientRect();
    const cs = getComputedStyle(card);
    if (r.width < 50 || r.height < 50 || cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) continue;
    if (!/[\d,]+\s*원/.test(card.innerText || "")) continue;   // 가격이 없는 칸은 상품이 아님
    cards.set(card, a);
  }
  const groups = new Map();
  for (const c of cards.keys()) { const p = c.parentElement; if (!groups.has(p)) groups.set(p, []); groups.get(p).push(c); }
  let mainParent = null, max = 0;
  for (const [p, g] of groups) if (g.length > max) { max = g.length; mainParent = p; }
  let lists = mainParent ? [mainParent] : [];
  const gp = mainParent && mainParent.parentElement;
  if (gp) {
    const sibs = [...gp.children].filter(el => el !== mainParent && el.tagName === mainParent.tagName &&
      el.className === mainParent.className && groups.has(el) && groups.get(el).length >= 2);
    if (sibs.length) lists = [...gp.children].filter(el => el === mainParent || sibs.includes(el));
  }
  const srcOf = i => [i.currentSrc, i.src, i.dataset && i.dataset.src, i.getAttribute("data-src")].find(u => u && /^(https?:)?\/\//.test(u)) || "";
  const items = [];
  for (const l of lists) for (const box of l.children) {
    if (!cards.has(box)) continue;
    const a = cards.get(box);
    const m = a.href.match(/\/vp\/products\/(\d+)/) || [null, ""];
    const ids = [m[1]];
    for (const k of ["itemId", "vendorItemId"]) { const mm = a.href.match(new RegExp(k + "=(\\d+)")); if (mm) ids.push(mm[1]); }
    const t = (box.innerText || "").trim();
    const nameEl = box.querySelector('.name, [class*="productName"], [class*="ProductUnit_productName"], [class*="title"]');
    const name = (nameEl ? nameEl.innerText.trim() : "") || (t.split("\n").find(x => x.trim().length > 8) || "").trim();
    const priceM = t.match(/([\d,]+)\s*원/);
    const im = [...box.querySelectorAll("img")].find(i => srcOf(i));
    let img = im ? srcOf(im) : "";
    if (img.startsWith("//")) img = "https:" + img;
    box.setAttribute("data-hgg-idx", String(items.length));
    items.push({ idx: items.length, product_id: m[1], ids, name, price: priceM ? priceM[1] : "", img,
                 alts: [...box.querySelectorAll("img[alt]")].map(i => i.alt).filter(Boolean).join("\n") });
  }
  return { blocked, url: location.href, items };
}

// ---------------------------------------------------------------- 우리 상품 칸 캡처 (썸네일)
let OURS = { brands: [], ids: [] };
const norm = x => (x || "").replace(/\s+/g, "").toLowerCase();
function isOurs(it) {
  const t = norm([it.title, it.name, it.mall, it.mall_list, it.text, it.alts].join(" "));
  return OURS.brands.some(b => b && t.includes(norm(b))) || (it.ids || []).some(id => OURS.ids.includes(id));
}
let capLock = Promise.resolve();
function withLock(fn) { const p = capLock.then(fn, fn); capLock = p.catch(() => {}); return p; }

async function captureItem(tabId, idx) {
  return withLock(async () => {
    try {
      const tab = await chrome.tabs.get(tabId);
      await chrome.windows.update(tab.windowId, { focused: true });   // 가려진 창은 화면이 안 그려져서 잠깐 앞으로
      const r = (await chrome.scripting.executeScript({ target: { tabId }, args: [idx], func: (i) => {
        const el = document.querySelector(`[data-hgg-idx="${i}"]`);
        if (!el) return null;
        el.scrollIntoView({ block: "center" });
        const b = el.getBoundingClientRect();
        return { x: b.left, y: b.top, w: b.width, h: b.height, dpr: window.devicePixelRatio || 1 };
      } }))[0].result;
      if (!r) return "";
      await sleep(900);
      const shot = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "jpeg", quality: 80 });
      const bmp = await createImageBitmap(await (await fetch(shot)).blob());
      const side = Math.min(r.w, r.h);              // 칸의 왼쪽 위 정사각형 = 상품 사진 자리
      const c = document.createElement("canvas"); c.width = 180; c.height = 180;
      c.getContext("2d").drawImage(bmp, r.x * r.dpr, Math.max(0, r.y) * r.dpr, side * r.dpr, side * r.dpr, 0, 0, 180, 180);
      return c.toDataURL("image/jpeg", 0.8);
    } catch (e) { return ""; }
  });
}

async function addShots(tabId, data) {
  for (const it of (data.items || [])) {
    if (isOurs(it)) { it.ours_js = true; it.shot = await captureItem(tabId, it.idx); }
  }
  try { await chrome.scripting.executeScript({ target: { tabId }, func: () => window.scrollTo(0, 0) }); } catch (e) {}
}

// ---------------------------------------------------------------- 실행
const SITES = {
  naver: { label: "네이버", url: kw => "https://search.shopping.naver.com/search/all?query=" + encodeURIComponent(kw), collect: collectNaver },
  coupang: { label: "쿠팡", url: kw => "https://www.coupang.com/np/search?component=&q=" + encodeURIComponent(kw) + "&channel=user", collect: collectCoupang },
};

// 키워드마다 새 탭으로 검색하고, 검색한 탭은 닫지 않고 남겨 둔다 (나중에 결과와 비교할 수 있게)
// 사이트마다 창 하나: 쿠팡은 시크릿 창, 네이버는 시크릿 창(로그인을 요구하면 일반 창)
async function newSearchTab(url, w) {
  if (w.id !== null) {
    try {
      const t = await chrome.tabs.create({ windowId: w.id, url, active: true });
      return t.id;
    } catch (e) { /* 웨일이 그 창에 탭 추가를 막으면 새 창으로 */ }
  }
  try {
    const win = await chrome.windows.create({ incognito: w.incog, focused: false, width: 1300, height: 900, url });
    w.id = win.id;
    const tabId = win.tabs && win.tabs[0] ? win.tabs[0].id : (await chrome.tabs.query({ windowId: win.id }))[0].id;
    await sleep(800);
    await chrome.tabs.get(tabId);
    return tabId;
  } catch (e) {
    if (w.incog) {
      log("시크릿 창을 열지 못해 일반 창으로 검색해요. (" + e.message + ")", "err");
      w.incog = false; w.id = null;
      return newSearchTab(url, w);
    }
    throw e;
  }
}

async function runSite(site, run, kws, wantIncog) {
  const S = SITES[site];
  const w = { id: null, incog: wantIncog };
  try {
    for (let i = 0; i < kws.length; i++) {
      const kw = kws[i], url = S.url(kw);
      log(`[${S.label}] (${i + 1}/${kws.length}) '${kw}' 새 탭에서 검색 중...`);
      let tabId;
      try { tabId = await newSearchTab(url, w); }
      catch (e) { log(`[${S.label}] 탭을 열지 못했어요: ${e.message}`, "err"); break; }
      await waitLoaded(tabId); await sleep(2500 + Math.random() * 2000);
      let data = { blocked: false, url, items: [] };
      let readErr = "";
      try { data = (await chrome.scripting.executeScript({ target: { tabId }, func: S.collect }))[0].result; }
      catch (e) { readErr = e.message || String(e); }
      if (readErr) {
        let cur = "";
        try { cur = (await chrome.tabs.get(tabId)).url || ""; } catch (e) {}
        if (/nid\.naver\.com|login/i.test(cur)) data.login = true;
        else log(`[${S.label}] '${kw}' 화면을 읽지 못했어요: ${readErr} (${cur})`, "err");
      }
      if (data.login && w.incog) {
        // 시크릿 창에서 네이버가 로그인을 요구 -> 로그인된 일반 창으로 바꿔서 같은 키워드부터 다시
        log(`[${S.label}] 시크릿 창에서 로그인을 요구해서, 일반 창으로 바꿔 검색할게요.`, "err");
        const old = w.id;
        w.incog = false; w.id = null;
        try { if (old !== null) await chrome.windows.remove(old); } catch (e) {}
        tabId = await newSearchTab(url, w);
        await waitLoaded(tabId); await sleep(2500 + Math.random() * 2000);
        try { data = (await chrome.scripting.executeScript({ target: { tabId }, func: S.collect }))[0].result; }
        catch (e) { log(`[${S.label}] '${kw}' 화면을 읽지 못했어요: ${e.message}`, "err"); }
      }
      if (data.captcha) {
        log(`[${S.label}] ⚠️ 보안 확인이 떴어요. 앞으로 띄운 창에서 직접 풀어 주세요 (3분 기다려요)`, "err");
        try { await chrome.tabs.update(tabId, { active: true }); const t = await chrome.tabs.get(tabId); await chrome.windows.update(t.windowId, { focused: true }); } catch (e) {}
        for (let k = 0; k < 60; k++) {
          await sleep(3000);
          try {
            const still = (await chrome.scripting.executeScript({ target: { tabId },
              func: () => /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test((document.body.innerText || "").slice(0, 3000)) }))[0].result;
            if (!still) break;
          } catch (e) {}
        }
        await sleep(2000);
        try { data = (await chrome.scripting.executeScript({ target: { tabId }, func: S.collect }))[0].result; } catch (e) {}
      }
      if (!data.blocked && !data.login) await addShots(tabId, data);
      try {
        await fetch(API + "/result", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ run_id: run, site, keyword: kw, incognito: w.incog, ...data }) });
      } catch (e) { log("순위 확인 프로그램과 연결이 끊겼어요. run.bat 이 켜져 있는지 확인해 주세요.", "err"); break; }
      if (data.blocked) { log(`[${S.label}] 접속이 제한됐어요. ${S.label} 확인을 멈출게요. 몇 시간 뒤에 다시 해 주세요.`, "err"); break; }
      log(`[${S.label}] '${kw}' 완료 (${(data.items || []).length}개 상품) — 탭은 남겨 둘게요`, "ok");
      if (i < kws.length - 1) await sleep(site === "naver" ? 60000 + Math.random() * 60000 : 15000 + Math.random() * 15000);
    }
  } catch (e) { log(`[${S.label}] 오류로 멈췄어요: ${e.message}`, "err"); }
}

async function start(run, kws, sites, auto) {
  btn.disabled = true; logBox.innerHTML = "";
  try { OURS = await (await fetch(API + "/ours")).json(); } catch (e) {}
  let wantIncog = false;
  try { wantIncog = await chrome.extension.isAllowedIncognitoAccess(); } catch (e) {}
  log(wantIncog ? "웨일 시크릿 창에서 키워드마다 새 탭으로 검색할게요. (끝나도 탭은 남겨 둬요)" : "⚠️ 시크릿 창 사용이 허용되지 않아 일반 창으로 검색해요.", wantIncog ? "" : "err");
  log(`키워드 ${kws.length}개 × ${sites.map(s => SITES[s].label).join("·")} (쿠팡은 키워드 사이 15~30초, 네이버는 차단을 피하려고 1~2분씩 쉬어요)`);
  await Promise.all(sites.map(s => runSite(s, run, kws, wantIncog)));
  try { await fetch(API + "/done", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: run }) }); } catch (e) {}
  log("끝났어요! 순위 확인 프로그램 화면에 자동으로 반영돼요. 검색한 창·탭은 비교해 보시라고 남겨 뒀어요.", "ok");
  btn.disabled = false;
  if (auto) { await sleep(3000); try { const t = await chrome.tabs.getCurrent(); if (t) chrome.tabs.remove(t.id); } catch (e) {} }
}

btn.onclick = async () => {
  let job;
  try { job = await (await fetch(API + "/keywords")).json(); }
  catch (e) { log("순위 확인 프로그램에 연결하지 못했어요. run.bat 을 먼저 켜 주세요.", "err"); return; }
  start(job.run_id, job.keywords || [], ["naver", "coupang"], false);
};

// 순위 프로그램이 시킨 자동 실행
const q = new URLSearchParams(location.search);
if (q.get("auto") === "1") {
  document.title = "HGG 순위 확인 (자동)";
  start(q.get("run"), JSON.parse(q.get("kws") || "[]"), JSON.parse(q.get("sites") || '["naver"]'), true);
}
