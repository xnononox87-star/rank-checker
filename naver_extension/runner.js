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
  const captcha = !blocked && /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test(head);
  const leafs = [...document.querySelectorAll("a, button, span, em, div")].filter(el =>
    el.childElementCount === 0 && /^\s*(신고하기|정보\s*수정\s*요청)\s*$/.test(el.textContent || ""));
  const boxes = [];
  for (const mk of leafs) {
    let box = mk;
    while (box.parentElement && box.parentElement !== document.body &&
           !leafs.some(o => o !== mk && box.parentElement.contains(o))) box = box.parentElement;
    if (!boxes.includes(box)) boxes.push(box);
  }
  boxes.sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  const SKIP = /^(구매정보|적립|쇼핑몰별 최저가|전체보기.*|광고.*|등록일.*|찜.*|리뷰.*|.*pay.*|포인트.*|배송비.*|무료|최저|원|[\d,.]+원?|[\d.]+%.*|\(.*\)|★.*|구성 별 정보.*|판매처.*|신고하기|정보\s*수정\s*요청|.*>.*)$/i;
  const srcOf = i => [i.currentSrc, i.src, i.dataset && i.dataset.src, i.getAttribute("data-src")].find(u => u && /^https?:/.test(u)) || "";
  const items = boxes.map(box => {
    const lines = (box.innerText || "").split("\n").map(l => l.trim()).filter(Boolean);
    const links = [...box.querySelectorAll("a")].map(a => (a.innerText || "").trim()).filter(t => t.length >= 8 && !/신고|수정요청|구매정보|전체보기/.test(t));
    const title = links[0] || lines.find(l => l.length >= 10) || "";
    const mi = lines.findIndex(l => /^(신고하기|정보\s*수정\s*요청)$/.test(l) || /신고하기$/.test(l));
    const after = mi >= 0 ? lines.slice(mi + 1) : [];
    const catalog = after.includes("쇼핑몰별 최저가");
    const names = after.map(l => l.replace(/\s*[\d,]+원?$/, "").trim()).filter(l => l && !SKIP.test(l) && l.length <= 30);
    const im = [...box.querySelectorAll("img")].find(i => srcOf(i) && !/icon|logo|badge|npay/i.test(srcOf(i)));
    return { title, mall: catalog ? "" : (names[0] || ""), mall_list: catalog ? names.join("\n") : "",
             text: lines.join("\n").slice(0, 1500), img: im ? srcOf(im) : "" };
  }).filter(it => it.title);
  return { text: text.slice(0, 60000), blocked, captcha, url: location.href, items };
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
    items.push({ product_id: m[1], ids, name, price: priceM ? priceM[1] : "", img });
  }
  return { blocked, url: location.href, items };
}

// ---------------------------------------------------------------- 실행
const SITES = {
  naver: { label: "네이버", url: kw => "https://search.shopping.naver.com/search/all?query=" + encodeURIComponent(kw), collect: collectNaver },
  coupang: { label: "쿠팡", url: kw => "https://www.coupang.com/np/search?component=&q=" + encodeURIComponent(kw) + "&channel=user", collect: collectCoupang },
};

// 탭 하나 열기: 시크릿 허용이면 사이트마다 시크릿 창을 하나씩 열고(그 창의 첫 탭을 계속 씀), 안 되면 일반 창 뒤쪽 탭
async function openSearchTab(url, wantIncog) {
  if (wantIncog) {
    try {
      const w = await chrome.windows.create({ incognito: true, focused: false, width: 1300, height: 900, url });
      const tabId = w.tabs && w.tabs[0] ? w.tabs[0].id : (await chrome.tabs.query({ windowId: w.id }))[0].id;
      await sleep(800);
      await chrome.tabs.get(tabId);   // 웨일이 창을 바로 닫거나 못 찾으면 여기서 실패 -> 일반 창으로
      return { tabId, winId: w.id, incog: true };
    } catch (e) { log("시크릿 창을 열지 못해 일반 창 뒤쪽 탭으로 검색해요. (" + e.message + ")", "err"); }
  }
  const t = await chrome.tabs.create({ url, active: false });
  return { tabId: t.id, winId: null, incog: false };
}

async function runSite(site, run, kws, wantIncog) {
  const S = SITES[site];
  let tab = null;
  try {
    for (let i = 0; i < kws.length; i++) {
      const kw = kws[i], url = S.url(kw);
      log(`[${S.label}] (${i + 1}/${kws.length}) '${kw}' 확인 중...`);
      try {
        if (!tab) tab = await openSearchTab(url, wantIncog);
        else await chrome.tabs.update(tab.tabId, { url });
      } catch (e) {
        // 탭이 사라졌으면 한 번 새로 연다
        try { tab = await openSearchTab(url, wantIncog); } catch (e2) { log(`[${S.label}] 탭을 열지 못했어요: ${e2.message}`, "err"); break; }
      }
      await waitLoaded(tab.tabId); await sleep(2500 + Math.random() * 2000);
      let data = { blocked: false, url, items: [] };
      try { data = (await chrome.scripting.executeScript({ target: { tabId: tab.tabId }, func: S.collect }))[0].result; }
      catch (e) { log(`[${S.label}] '${kw}' 화면을 읽지 못했어요: ${e.message}`, "err"); }
      if (data.captcha) {
        log(`[${S.label}] ⚠️ 보안 확인이 떴어요. 앞으로 띄운 창에서 직접 풀어 주세요 (3분 기다려요)`, "err");
        try { await chrome.tabs.update(tab.tabId, { active: true }); const t = await chrome.tabs.get(tab.tabId); await chrome.windows.update(t.windowId, { focused: true }); } catch (e) {}
        for (let w = 0; w < 60; w++) {
          await sleep(3000);
          try {
            const still = (await chrome.scripting.executeScript({ target: { tabId: tab.tabId },
              func: () => /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test((document.body.innerText || "").slice(0, 3000)) }))[0].result;
            if (!still) break;
          } catch (e) {}
        }
        await sleep(2000);
        try { data = (await chrome.scripting.executeScript({ target: { tabId: tab.tabId }, func: S.collect }))[0].result; } catch (e) {}
      }
      try {
        await fetch(API + "/result", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ run_id: run, site, keyword: kw, incognito: tab.incog, ...data }) });
      } catch (e) { log("순위 확인 프로그램과 연결이 끊겼어요. run.bat 이 켜져 있는지 확인해 주세요.", "err"); break; }
      if (data.blocked) { log(`[${S.label}] 접속이 제한됐어요. ${S.label} 확인을 멈출게요. 몇 시간 뒤에 다시 해 주세요.`, "err"); break; }
      log(`[${S.label}] '${kw}' 완료 (${(data.items || []).length}개 상품)`, "ok");
      if (i < kws.length - 1) await sleep(15000 + Math.random() * 15000);
    }
  } catch (e) { log(`[${S.label}] 오류로 멈췄어요: ${e.message}`, "err"); }
  if (tab) {
    try { if (tab.winId !== null) await chrome.windows.remove(tab.winId); else await chrome.tabs.remove(tab.tabId); } catch (e) {}
  }
}

async function start(run, kws, sites, auto) {
  btn.disabled = true; logBox.innerHTML = "";
  let wantIncog = false;
  try { wantIncog = await chrome.extension.isAllowedIncognitoAccess(); } catch (e) {}
  log(wantIncog ? "웨일 시크릿 창에서 검색할게요. (끝나면 저절로 닫혀요)" : "⚠️ 시크릿 창 사용이 허용되지 않아 일반 창으로 검색해요.", wantIncog ? "" : "err");
  log(`키워드 ${kws.length}개 × ${sites.map(s => SITES[s].label).join("·")} (키워드 사이에 15~30초씩 쉬어요)`);
  await Promise.all(sites.map(s => runSite(s, run, kws, wantIncog)));
  try { await fetch(API + "/done", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: run }) }); } catch (e) {}
  log("끝났어요! 순위 확인 프로그램 화면에 자동으로 반영돼요.", "ok");
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
