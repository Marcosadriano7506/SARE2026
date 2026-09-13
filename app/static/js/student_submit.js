(() => {
  const form = document.querySelector("[data-sare-student-form]");
  if (!form) return;

  let isSubmitting = false;

  const lockSubmit = () => {
    isSubmitting = true;
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");

    const submitControls = form.querySelectorAll(
      'button[type="submit"], input[type="submit"]'
    );

    submitControls.forEach((control) => {
      control.disabled = true;
      control.setAttribute("aria-disabled", "true");

      if (control.tagName === "INPUT") {
        control.value = "Enviando...";
      } else {
        control.textContent = "Enviando...";
      }
    });

    const status = document.getElementById("submit-status");
    if (status) {
      status.hidden = false;
      status.textContent =
        "Salvando respostas e enviando a foto. Não feche esta página.";
    }
  };

  form.addEventListener(
    "submit",
    (event) => {
      if (isSubmitting) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return false;
      }

      lockSubmit();
      return true;
    },
    true
  );

  // Camada extra contra toques/cliques repetidos em celulares.
  form.addEventListener(
    "click",
    (event) => {
      const submitControl = event.target.closest(
        'button[type="submit"], input[type="submit"]'
      );

      if (submitControl && isSubmitting) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );

  // Também bloqueia novo envio pelo teclado (Enter) enquanto a primeira
  // requisição ainda está em andamento.
  form.addEventListener(
    "keydown",
    (event) => {
      if (isSubmitting && event.key === "Enter") {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );
})();
