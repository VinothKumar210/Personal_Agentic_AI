chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "clip") {
    const { tabId, backendUrl, apiKey } = request;

    // Execute script to get page HTML and selected text
    chrome.scripting.executeScript(
      {
        target: { tabId: tabId },
        func: () => {
          return {
            title: document.title,
            url: window.location.href,
            html_content: document.documentElement.outerHTML,
            selected_text: window.getSelection().toString()
          };
        }
      },
      (results) => {
        if (chrome.runtime.lastError || !results || !results[0]) {
          sendResponse({ success: false, error: "Failed to access page content." });
          return;
        }

        const data = results[0].result;

        // Post to backend
        fetch(`${backendUrl.replace(/\/$/, "")}/api/ingest/clip`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`
          },
          body: JSON.stringify(data)
        })
          .then(res => {
            if (!res.ok) {
              return res.text().then(text => {
                throw new Error(text || res.statusText);
              });
            }
            return res.json();
          })
          .then(data => {
            sendResponse({ success: true, data });
          })
          .catch(err => {
            sendResponse({ success: false, error: err.message });
          });
      }
    );
    
    return true; // Keep message channel open for async response
  }
});
