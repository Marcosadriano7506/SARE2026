(() => {
  const updateConnectivity = () => {
    document.documentElement.dataset.online = navigator.onLine ? "true" : "false";
    const badge = document.getElementById("global-connectivity");
    if (!badge) return;
    badge.textContent = navigator.onLine ? "Online" : "Sem conexão";
    badge.dataset.state = navigator.onLine ? "online" : "offline";
  };

  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
  updateConnectivity();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // A aplicação continua funcional mesmo sem instalação PWA.
      });
    });
  }
})();
