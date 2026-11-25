const API = "http://127.0.0.1:8765";
const logBox = document.getElementById("log");
const btn = document.getElementById("go");
const log = (m, cls) => { const d = document.createElement("div"); if (cls) d.className = cls; d.textContent = m; logBox.appendChild(d); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

function waitLoaded(tabId) {
  return new Promise(resolve => {
    const done = (id, info) => { if (id === tabId && info.status === "complete") { chrome.tabs.onUpdated.removeListener(done); resolve(); } };
    chrome.tabs.onUpdated.addListener(done);
    setTimeout(() => { chrome.tabs.onUpdated.removeListener(done); resolve(); }, 30000);
  });
}

// 검색 화면 안에서 실행: 천천히 내려가며 상품을 다 불러온 뒤 글자와 상품 사진 주소를 모은다
async function collect() {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 14; i++) { window.scrollBy(0, 900 + Math.random() * 500); await sleep(500 + Math.random() * 500); }
  window.scrollTo(0, 0);
  const text = document.body.innerText || "";
  const blocked = /접속이 일시적으로 제한|비정상적인 접근|보안 확인|자동입력 방지/.test(text.slice(0, 3000));
  const images = [];
  for (const img of document.querySelectorAll("img")) {
    const src = img.currentSrc || img.src || "";
    if (!src.startsWith("http") || (img.naturalWidth && img.naturalWidth < 60)) continue;
    // 상품 칸(‘찜하기’가 들어 있는 가장 가까운 상자)까지 올라가서 그 칸의 글자를 같이 보낸다
    let box = img, t = "", fallback = "";
    for (let k = 0; k < 12 && box; k++) {
      box = box.parentElement; if (!box) break;
      t = box.innerText || "";
      if (!fallback && t.length > 20) fallback = t;
      if (t.includes("찜하기") || t.includes("찜")) break;
      if (t.length > 1500) { t = fallback; break; }
    }
    images.push({ src, text: (t || fallback).slice(0, 400), alt: img.alt || "" });
  }
  // 상품 칸 단위로 읽기 (가격비교 화면): 칸 안에 오른쪽 판매처 칸까지 같이 들어 있어 순위가 밀리지 않는다
  const sels = ['[class*="product_item__"], [class*="adProduct_item__"], [class*="superSavingProduct_item__"]',
                '[class*="basicList_item"]', 'li[class*="product_list_item"], div[class*="product_list_item"]'];
  let best = [];
  for (const sel of sels) {
    let els = [...document.querySelectorAll(sel)];
    els = els.filter(e => !els.some(o => o !== e && o.contains(e)));
    if (els.length > best.length) best = els;
  }
  const items = best.map(e => {
    const q = s => e.querySelector(s);
    const t = q('[class*="product_title__"], [class*="adProduct_title__"], [class*="superSavingProduct_title__"], [class*="title"] a');
    const m = q('[class*="product_mall_title__"], [class*="adProduct_mall_title__"], [class*="product_mall__"], [class*="adProduct_mall__"], [class*="mall_title"]');
    const list = q('[class*="product_mall_list__"], [class*="mall_list"]');
    const mimg = m ? m.querySelector('img[alt]') : null;
    const img = q('img[src^="http"]');
    const txt = (e.innerText || '').trim();
    return { title: t ? t.innerText.trim() : '', mall: (m && m.innerText.trim()) || (mimg ? mimg.alt : ''),
             mall_list: list ? list.innerText.trim() : '', text: txt.slice(0, 1500),
             ad: /adProduct/.test(e.className) || /(^|\n)\s*광고/.test(txt),
             img: img ? (img.currentSrc || img.src) : '' };
  }).filter(it => it.title || it.text);
  return { text, blocked, url: location.href, images: images.slice(0, 200), items };
}

async function start(run, kws, auto) {
  btn.disabled = true; logBox.innerHTML = "";
  log(`키워드 ${kws.length}개를 확인할게요. (키워드 사이에 15~30초씩 쉬어요)`);
  for (let i = 0; i < kws.length; i++) {
    const kw = kws[i];
    log(`(${i + 1}/${kws.length}) '${kw}' 확인 중...`);
    const url = "https://search.shopping.naver.com/search/all?query=" + encodeURIComponent(kw);
    const tab = await chrome.tabs.create({ url, active: false });
    await waitLoaded(tab.id); await sleep(2500 + Math.random() * 2000);
    let data = { text: "", blocked: false, url, images: [] };
    try { data = (await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: collect }))[0].result; }
    catch (e) { log(`  '${kw}' 화면을 읽지 못했어요: ${e}`, "err"); }
    try { await chrome.tabs.remove(tab.id); } catch (e) {}
    try {
      await fetch(API + "/result", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: run, keyword: kw, ...data }) });
    } catch (e) { log("순위 확인 프로그램과 연결이 끊겼어요. run.bat 이 켜져 있는지 확인해 주세요.", "err"); break; }
    if (data.blocked) { log("네이버가 접속을 제한했어요. 확인을 멈출게요. 몇 시간 뒤에 다시 해 주세요.", "err"); break; }
    log(`  '${kw}' 완료`, "ok");
    if (i < kws.length - 1) await sleep(15000 + Math.random() * 15000);
  }
  try { await fetch(API + "/done", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: run }) }); } catch (e) {}
  log("끝났어요! 순위 확인 프로그램 화면에 자동으로 반영돼요.", "ok");
  btn.disabled = false;
  if (auto) { await sleep(3000); const t = await chrome.tabs.getCurrent(); if (t) chrome.tabs.remove(t.id); }
}

btn.onclick = async () => {
  let job;
  try { job = await (await fetch(API + "/keywords")).json(); }
  catch (e) { log("순위 확인 프로그램에 연결하지 못했어요. run.bat 을 먼저 켜 주세요.", "err"); return; }
  start(job.run_id, job.keywords || [], false);
};

// 순위 프로그램이 시킨 자동 실행
const q = new URLSearchParams(location.search);
if (q.get("auto") === "1") {
  document.title = "HGG 네이버 순위 확인 (자동)";
  start(q.get("run"), JSON.parse(q.get("kws") || "[]"), true);
}
