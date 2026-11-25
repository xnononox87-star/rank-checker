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
  const head = text.slice(0, 3000);
  const blocked = /접속이 일시적으로 제한|비정상적인 접근/.test(head);
  const captcha = !blocked && /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test(head);
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
  // 상품 칸 단위로 읽기 (가격비교 화면)
  // 상품마다 꼭 한 번 나오는 '신고하기'(일반 상품) / '정보 수정요청'(가격비교 묶음)을 기준으로,
  // 그 글자 하나만 품고 있는 가장 큰 상자 = 상품 한 칸 (왼쪽 상품정보 + 오른쪽 판매처가 같이 들어 있음)
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
  const items = boxes.map(box => {
    const lines = (box.innerText || "").split("\n").map(l => l.trim()).filter(Boolean);
    const links = [...box.querySelectorAll("a")].map(a => (a.innerText || "").trim()).filter(t => t.length >= 8 && !/신고|수정요청|구매정보|전체보기/.test(t));
    const title = links[0] || lines.find(l => l.length >= 10) || "";
    const mi = lines.findIndex(l => /^(신고하기|정보\s*수정\s*요청)$/.test(l) || /신고하기$/.test(l));
    const after = mi >= 0 ? lines.slice(mi + 1) : [];
    const catalog = after.includes("쇼핑몰별 최저가");
    const names = after.map(l => l.replace(/\s*[\d,]+원?$/, "").trim()).filter(l => l && !SKIP.test(l) && l.length <= 30);
    const srcOf = i => [i.currentSrc, i.src, i.dataset && i.dataset.src, i.getAttribute("data-src")].find(u => u && /^https?:/.test(u)) || "";
    const im = [...box.querySelectorAll("img")].find(i => srcOf(i) && !/icon|logo|badge|npay/i.test(srcOf(i)));
    return { title, mall: catalog ? "" : (names[0] || ""), mall_list: catalog ? names.join("\n") : "",
             text: lines.join("\n").slice(0, 1500), ad: /(^|\n)광고/.test(lines.join("\n")),
             img: im ? srcOf(im) : "" };
  }).filter(it => it.title);
  return { text, blocked, captcha, url: location.href, images: images.slice(0, 200), items };
}

async function start(run, kws, auto) {
  btn.disabled = true; logBox.innerHTML = "";
  // 시크릿 창 기준으로 검색 (로그인·검색기록 영향 없이). 시크릿 허용이 꺼져 있으면 일반 창으로.
  let winId = null, incog = false;
  try {
    if (await chrome.extension.isAllowedIncognitoAccess()) {
      const w = await chrome.windows.create({ incognito: true, focused: false, url: "about:blank", width: 1300, height: 900 });
      winId = w.id; incog = true;
      log("시크릿 창에서 검색할게요.");
    } else {
      log("⚠️ 시크릿 창 사용이 허용되지 않아 일반 창으로 검색해요. (설정 방법은 프로그램 안내 참고)", "err");
    }
  } catch (e) {}
  log(`키워드 ${kws.length}개를 확인할게요. (키워드 사이에 15~30초씩 쉬어요)`);
  for (let i = 0; i < kws.length; i++) {
    const kw = kws[i];
    log(`(${i + 1}/${kws.length}) '${kw}' 확인 중...`);
    const url = "https://search.shopping.naver.com/search/all?query=" + encodeURIComponent(kw);
    const tab = winId ? await chrome.tabs.create({ windowId: winId, url, active: true }) : await chrome.tabs.create({ url, active: false });
    await waitLoaded(tab.id); await sleep(2500 + Math.random() * 2000);
    let data = { text: "", blocked: false, url, images: [] };
    try { data = (await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: collect }))[0].result; }
    catch (e) { log(`  '${kw}' 화면을 읽지 못했어요: ${e}`, "err"); }
    if (data.captcha) {
      // 보안 확인(영수증 문제 등)이 뜨면 그 탭을 앞으로 띄우고 CH님이 풀 때까지 최대 3분 기다린다
      log(`  ⚠️ 네이버 보안 확인이 떴어요. 앞으로 띄운 탭에서 직접 풀어 주세요 (3분 기다려요)`, "err");
      try { await chrome.tabs.update(tab.id, { active: true }); const t = await chrome.tabs.get(tab.id); await chrome.windows.update(t.windowId, { focused: true }); } catch (e) {}
      for (let w = 0; w < 60; w++) {
        await sleep(3000);
        try {
          const still = (await chrome.scripting.executeScript({ target: { tabId: tab.id },
            func: () => /보안 확인|자동입력 방지|영수증|정답을 입력|실제 사용자/.test((document.body.innerText || "").slice(0, 3000)) }))[0].result;
          if (!still) break;
        } catch (e) {}
      }
      await sleep(2000);
      try { data = (await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: collect }))[0].result; } catch (e) {}
      if (data.captcha) log(`  '${kw}' 보안 확인을 못 넘어서 건너뛰었어요.`, "err"); else log(`  보안 확인 통과! 계속할게요.`, "ok");
    }
    try { await chrome.tabs.remove(tab.id); } catch (e) {}
    try {
      await fetch(API + "/result", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: run, keyword: kw, incognito: incog, ...data }) });
    } catch (e) { log("순위 확인 프로그램과 연결이 끊겼어요. run.bat 이 켜져 있는지 확인해 주세요.", "err"); break; }
    if (data.blocked) { log("네이버가 접속을 제한했어요. 확인을 멈출게요. 몇 시간 뒤에 다시 해 주세요.", "err"); break; }
    log(`  '${kw}' 완료`, "ok");
    if (i < kws.length - 1) await sleep(15000 + Math.random() * 15000);
  }
  if (winId) { try { await chrome.windows.remove(winId); } catch (e) {} }
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
