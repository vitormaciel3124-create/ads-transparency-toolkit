(function () {
  "use strict";

  let panelOpen = false;

  function isCreativePage() {
    return window.location.pathname.includes("/creative/");
  }

  function createUI() {
    if (document.getElementById("atd-fab")) return;

    const fab = document.createElement("button");
    fab.id = "atd-fab";
    fab.innerHTML = "⬇ Download";
    fab.onclick = togglePanel;
    document.body.appendChild(fab);

    const panel = document.createElement("div");
    panel.id = "atd-panel";
    document.body.appendChild(panel);
  }

  function togglePanel() {
    const fab = document.getElementById("atd-fab");
    if (fab.classList.contains("downloading")) return;

    const panel = document.getElementById("atd-panel");
    panelOpen = !panelOpen;
    panel.classList.toggle("open", panelOpen);
    if (panelOpen) renderPanel();
  }

  function renderPanel() {
    const panel = document.getElementById("atd-panel");
    const pageUrl = window.location.href;

    panel.innerHTML = `
      <h3>Baixar vídeo desta página</h3>
      <p style="color:#5f6368;font-size:13px;margin:0 0 16px 0">
        O vídeo será salvo em<br>
        <code style="font-size:11px;background:#f1f3f4;padding:2px 6px;border-radius:4px">
          TRANSPARENCY DOWNLOAD/
        </code>
      </p>
      <button class="atd-dl-all" id="atd-go">Baixar vídeo</button>
      <div id="atd-log" style="margin-top:12px;font-size:12px;color:#5f6368"></div>
    `;

    document.getElementById("atd-go").onclick = () => startDownload(pageUrl);
  }

  function startDownload(pageUrl) {
    const btn = document.getElementById("atd-go");
    const log = document.getElementById("atd-log");

    btn.disabled = true;
    btn.textContent = "Processando...";
    updateFab("downloading");
    log.textContent = "Extraindo video ID da página...";

    chrome.runtime.sendMessage(
      { type: "DOWNLOAD_PAGE", url: pageUrl },
      (response) => {
        if (chrome.runtime.lastError) {
          log.textContent = "Erro: " + chrome.runtime.lastError.message;
          btn.disabled = false;
          btn.textContent = "Tentar novamente";
          updateFab("error");
          return;
        }
        if (response?.started) {
          pollStatus();
        }
      }
    );
  }

  function pollStatus() {
    const log = document.getElementById("atd-log");
    const btn = document.getElementById("atd-go");

    const interval = setInterval(() => {
      chrome.runtime.sendMessage({ type: "GET_STATUS" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          clearInterval(interval);
          return;
        }

        if (response.status === "downloading") {
          if (log) log.textContent = response.progress || "Baixando...";
        } else if (response.status === "done") {
          clearInterval(interval);
          if (log) log.innerHTML = `✓ Salvo: <strong>${response.filename}</strong>`;
          if (btn) {
            btn.textContent = "✓ Baixado!";
            btn.style.background = "#1e8e3e";
          }
          updateFab("done");
        } else if (response.status === "error") {
          clearInterval(interval);
          if (log) log.textContent = "✗ Erro: " + (response.error || "desconhecido");
          if (btn) {
            btn.disabled = false;
            btn.textContent = "Tentar novamente";
          }
          updateFab("error");
        }
      });
    }, 1000);
  }

  function updateFab(state) {
    const fab = document.getElementById("atd-fab");
    if (!fab) return;
    fab.className = "";
    if (state === "downloading") {
      fab.innerHTML = '<span class="spinner"></span> Baixando...';
      fab.classList.add("downloading");
    } else if (state === "done") {
      fab.innerHTML = "✓ Baixado!";
      fab.classList.add("done");
      setTimeout(() => {
        fab.innerHTML = "⬇ Download";
        fab.className = "";
      }, 5000);
    } else if (state === "error") {
      fab.innerHTML = "✗ Erro";
      fab.classList.add("error");
      setTimeout(() => {
        fab.innerHTML = "⬇ Download";
        fab.className = "";
      }, 5000);
    }
  }

  const observer = new MutationObserver(() => {
    if (isCreativePage()) createUI();
  });
  observer.observe(document.body, { childList: true, subtree: true });

  setTimeout(() => {
    if (isCreativePage()) createUI();
  }, 2000);
})();
