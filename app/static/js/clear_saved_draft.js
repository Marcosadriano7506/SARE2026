(() => {
  const marker = document.querySelector("[data-clear-student-draft]");
  if (!marker) return;

  const applicationId = marker.dataset.applicationId;
  const studentId = marker.dataset.studentId;
  if (!applicationId || !studentId) return;

  const localKey = "sare:draft:" + applicationId + ":" + studentId;
  const queueKey = applicationId + ":" + studentId;

  try {
    localStorage.removeItem(localKey);
  } catch (_) {
    // O salvamento no servidor já ocorreu; limpar o rascunho é secundário.
  }

  if (!("indexedDB" in window)) return;

  try {
    const request = indexedDB.open("sare-offline-v1", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("student_submissions")) {
        db.createObjectStore("student_submissions", { keyPath: "key" });
      }
    };
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction("student_submissions", "readwrite");
      tx.objectStore("student_submissions").delete(queueKey);
      tx.oncomplete = () => db.close();
      tx.onerror = () => db.close();
    };
  } catch (_) {
    // A limpeza do IndexedDB também é secundária.
  }
})();