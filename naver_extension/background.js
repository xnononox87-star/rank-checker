// 아이콘을 누르면 순위 확인 창(runner.html)을 연다
chrome.action.onClicked.addListener(() => {
  chrome.tabs.create({ url: chrome.runtime.getURL("runner.html") });
});
