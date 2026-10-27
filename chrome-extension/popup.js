document.addEventListener("DOMContentLoaded", () => {
  const backendUrlInput = document.getElementById("backendUrl");
  const apiKeyInput = document.getElementById("apiKey");
  const clipBtn = document.getElementById("clipBtn");
  const statusDiv = document.getElementById("status");

  // Load saved settings
  chrome.storage.sync.get(["backendUrl", "apiKey"], (items) => {
    if (items.backendUrl) backendUrlInput.value = items.backendUrl;
    if (items.apiKey) apiKeyInput.value = items.apiKey;
  });

  clipBtn.addEventListener("click", () => {
    const backendUrl = backendUrlInput.value.trim();
    const apiKey = apiKeyInput.value.trim();

    if (!backendUrl || !apiKey) {
      showStatus("Please provide both URL and API Key.", "error");
      return;
    }

    // Save settings
    chrome.storage.sync.set({ backendUrl, apiKey });

    clipBtn.disabled = true;
    showStatus("Clipping...", "");

    // Get active tab and trigger clip in background
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      chrome.runtime.sendMessage(
        { action: "clip", tabId: activeTab.id, backendUrl, apiKey },
        (response) => {
          clipBtn.disabled = false;
          if (response && response.success) {
            showStatus("Saved successfully!", "success");
          } else {
            showStatus("Error: " + (response ? response.error : "Unknown error"), "error");
          }
        }
      );
    });
  });

  function showStatus(message, className) {
    statusDiv.textContent = message;
    statusDiv.className = className;
  }
});
