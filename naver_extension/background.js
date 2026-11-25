const API = "http://127.0.0.1:8765";

// 아이콘을 누르면 순위 확인 창을 연다 (직접 실행)
chrome.action.onClicked.addListener(() => {
  chrome.tabs.create({ url: chrome.runtime.getURL("runner.html") });
});

// 순위 프로그램에서 [순위 확인 시작]을 누르면 자동으로 네이버 확인을 시작한다 (15초마다 확인)
function ensureAlarm() { chrome.alarms.create("poll", { periodInMinutes: 0.25 }); }
chrome.runtime.onInstalled.addListener(ensureAlarm);
chrome.runtime.onStartup.addListener(ensureAlarm);
ensureAlarm();

chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name !== "poll") return;
  // 프로그램이 업데이트돼서 폴더의 확장 파일이 새것이면 스스로 새로고침 (↻ 안 눌러도 됨)
  try {
    const v = (await (await fetch(API + "/ext_version")).json()).version;
    const running = await chrome.tabs.query({ url: chrome.runtime.getURL("runner.html") + "*" });
    if (v && v !== chrome.runtime.getManifest().version && running.length === 0) {
      const { tried } = await chrome.storage.local.get("tried");
      if (tried !== v) { await chrome.storage.local.set({ tried: v }); chrome.runtime.reload(); return; }
    }
  } catch (e) {}
  try {
    const j = await (await fetch(API + "/pending")).json();
    if (j && j.run_id) {
      const url = chrome.runtime.getURL("runner.html") + "?auto=1&run=" + j.run_id +
        "&kws=" + encodeURIComponent(JSON.stringify(j.keywords || [])) +
        "&sites=" + encodeURIComponent(JSON.stringify(j.sites || ["naver"]));
      chrome.tabs.create({ url, active: false });
    }
  } catch (e) { /* 순위 프로그램이 꺼져 있으면 아무것도 안 함 */ }
});
