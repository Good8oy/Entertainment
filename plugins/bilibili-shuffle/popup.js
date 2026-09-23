const toggleButton = document.querySelector("#toggle");
const toggleLabel = document.querySelector("#toggle-label");

function render(enabled) {
  toggleButton.setAttribute("aria-pressed", String(enabled));
  toggleLabel.textContent = enabled ? "乱序播放：已开启" : "乱序播放：已关闭";
}

chrome.storage.local.get({ enabled: false }, ({ enabled }) => render(enabled));

toggleButton.addEventListener("click", async () => {
  const { enabled = false } = await chrome.storage.local.get("enabled");
  const nextEnabled = !enabled;
  await chrome.storage.local.set({ enabled: nextEnabled });
  render(nextEnabled);

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    chrome.tabs.sendMessage(tab.id, { type: "bilibili-shuffle:state", enabled: nextEnabled }, () => {
      // The extension can be toggled from any tab; non-Bilibili tabs have no content script.
      void chrome.runtime.lastError;
    });
  }
});
