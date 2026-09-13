(() => {
  const form = document.querySelector("[data-sare-student-form]");
  if (!form) return;

  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"], input[type="submit"]');
    const status = document.getElementById("submit-status");

    if (button) {
      button.disabled = true;
      if (button.tagName === "INPUT") {
        button.value = "Enviando...";
      } else {
        button.textContent = "Enviando...";
      }
    }

    if (status) {
      status.hidden = false;
      status.textContent = "Salvando respostas e enviando a foto. Não feche esta página.";
    }
  });
})();
