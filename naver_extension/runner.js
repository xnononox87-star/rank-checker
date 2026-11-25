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
    let box = img, t = "";
    for (let k = 0; k < 7 && box; k++) { box = box.parentElement; t = (box && box.innerText) || ""; if (t.length > 20) break; }
    images.push({ src, text: t.slice(0, 300), alt: img.alt || "" });
  }
  return { text, blocked, url: location.href, images: images.slice(0, 200) };
}

btn.onclick = async () => {
  btn.disabled = true; logBox.innerHTML = "";
  let job;
  try { job = await (await fetch(API + "/keywords")).json(); }
  catch (e) { log("순위 확인 프로그램에 연결하지 못했어요. run.bat 을 먼저 켜 주세요.", "err"); btn.disabled = false; return; }
  const run = job.run_id, kws = job.keywords || [];
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
    await fetch(API + "/result", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: run, keyword: kw, ...data }) });
    if (data.blocked) { log("네이버가 접속을 제한했어요. 확인을 멈출게요. 몇 시간 뒤에 다시 해 주세요.", "err"); break; }
    log(`  '${kw}' 완료`, "ok");
    if (i < kws.length - 1) await sleep(15000 + Math.random() * 15000);
  }
  await fetch(API + "/done", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: run }) });
  log("끝났어요! 순위 확인 프로그램 화면에서 [네이버 결과 불러오기]를 눌러 주세요.", "ok");
  btn.disabled = false;
};
