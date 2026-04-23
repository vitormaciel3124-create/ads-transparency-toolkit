const NATIVE_HOST = "com.cv.ads_downloader";
let currentStatus = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "DOWNLOAD_PAGE") {
    currentStatus = { status: "downloading", progress: "Conectando..." };

    const port = chrome.runtime.connectNative(NATIVE_HOST);

    port.onMessage.addListener((msg) => {
      if (msg.type === "progress") {
        currentStatus = { status: "downloading", progress: msg.text };
      } else if (msg.type === "done") {
        currentStatus = {
          status: "done",
          filename: msg.filename,
          path: msg.path,
        };
        port.disconnect();
      } else if (msg.type === "error") {
        currentStatus = { status: "error", error: msg.text };
        port.disconnect();
      }
    });

    port.onDisconnect.addListener(() => {
      if (currentStatus?.status === "downloading") {
        const err = chrome.runtime.lastError?.message || "Disconnected";
        currentStatus = { status: "error", error: err };
      }
    });

    port.postMessage({ action: "download_page", url: message.url });
    sendResponse({ started: true });
    return true;
  }

  if (message.type === "GET_STATUS") {
    sendResponse(currentStatus || { status: "idle" });
    return true;
  }
});
