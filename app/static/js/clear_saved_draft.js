(() => {
  const marker = document.querySelector("[data-clear-student-draft]");
  if (!marker) return;

  const applicationId = marker.dataset.applicationId;
  const studentId = marker.dataset.studentId;
  if (!applicationId || !studentId) return;

  try {
    localStorage.removeItem(
      "sare:draft:" + applicationId + ":" + studentId
    );
  } catch (_) {
    // O salvamento no servidor já ocorreu; limpar o rascunho é secundário.
  }
})();
