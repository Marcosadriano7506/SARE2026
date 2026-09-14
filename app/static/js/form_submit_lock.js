(() => {
  const forms = document.querySelectorAll("[data-submit-lock]");
  if (!forms.length) return;

  forms.forEach((form) => {
    let locked = false;

    form.addEventListener("submit", (event) => {
      if (locked) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }

      locked = true;
      form.dataset.submitting = "true";
      form.setAttribute("aria-busy", "true");

      const controls = form.querySelectorAll('button[type="submit"], input[type="submit"]');
      controls.forEach((control) => {
        control.disabled = true;
        control.setAttribute("aria-disabled", "true");

        const loadingText =
          control.dataset.loadingText ||
          form.dataset.loadingText ||
          "Processando...";

        if (control.tagName === "INPUT") {
          control.dataset.originalValue = control.value;
          control.value = loadingText;
        } else {
          control.dataset.originalText = control.textContent;
          control.innerHTML = '<span class="button-spinner" aria-hidden="true"></span><span>' + loadingText + '</span>';
        }
      });

      const statusId = form.dataset.statusTarget;
      if (statusId) {
        const status = document.getElementById(statusId);
        if (status) {
          status.hidden = false;
          status.textContent = form.dataset.statusText || "Aguarde enquanto processamos sua solicitação.";
        }
      }
    }, true);

    form.addEventListener("click", (event) => {
      const submit = event.target.closest('button[type="submit"], input[type="submit"]');
      if (submit && locked) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);

    form.addEventListener("keydown", (event) => {
      if (locked && event.key === "Enter") {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  });
})();