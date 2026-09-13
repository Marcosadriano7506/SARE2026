(() => {
  const form = document.querySelector("[data-sare-student-form]");
  if (!form) return;

  let isSubmitting = false;

  const status = document.getElementById("submit-status");

  const showStatus = (text) => {
    if (!status) return;
    status.hidden = false;
    status.textContent = text;
  };

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
        control.dataset.originalValue = control.value;
        control.value = "Enviando...";
      } else {
        control.dataset.originalText = control.textContent;
        control.textContent = "Enviando...";
      }
    });

    showStatus("Salvando respostas e enviando a foto. Não feche esta página.");
  };

  const unlockSubmit = () => {
    isSubmitting = false;
    delete form.dataset.submitting;
    form.removeAttribute("aria-busy");

    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((control) => {
      control.disabled = false;
      control.removeAttribute("aria-disabled");
      if (control.tagName === "INPUT" && control.dataset.originalValue) {
        control.value = control.dataset.originalValue;
      } else if (control.dataset.originalText) {
        control.textContent = control.dataset.originalText;
      }
    });
  };

  const queueOffline = async (originalEvent) => {
    originalEvent.preventDefault();
    originalEvent.stopImmediatePropagation();

    if (window.SAREOfflineDraft && window.SAREOfflineDraft.queueSubmission) {
      const result = await window.SAREOfflineDraft.queueSubmission();
      if (result && result.queued) {
        showStatus(
          "Sem internet. O registro foi preservado neste aparelho e será enviado automaticamente quando a conexão voltar."
        );
      } else {
        showStatus(
          "Sem internet. As respostas foram salvas neste aparelho, mas ainda é necessário selecionar a foto da discursiva."
        );
      }
    } else {
      showStatus(
        "Sem internet. Não feche esta página até a conexão voltar."
      );
    }
  };

  form.addEventListener(
    "submit",
    async (event) => {
      if (isSubmitting) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return false;
      }

      if (!navigator.onLine) {
        await queueOffline(event);
        return false;
      }

      event.preventDefault();
      event.stopImmediatePropagation();

      if (window.SAREOfflineDraft && window.SAREOfflineDraft.captureCurrent) {
        await window.SAREOfflineDraft.captureCurrent().catch(() => {});
      }

      lockSubmit();

      try {
        const response = await fetch(form.action || window.location.href, {
          method: "POST",
          body: new FormData(form),
          credentials: "same-origin",
          redirect: "follow",
        });

        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }

        if (response.url.includes("/auth/login")) {
          throw new Error("Sessão expirada");
        }

        const currentPath = window.location.pathname;
        const responseUrl = new URL(response.url);

        if (responseUrl.pathname !== currentPath || responseUrl.search.includes("saved=")) {
          window.location.assign(response.url);
          return false;
        }

        // O servidor devolveu a própria tela (normalmente validação).
        const html = await response.text();
        document.open();
        document.write(html);
        document.close();
        return false;
      } catch (_) {
        unlockSubmit();

        if (window.SAREOfflineDraft && window.SAREOfflineDraft.queueSubmission) {
          const queued = await window.SAREOfflineDraft.queueSubmission().catch(() => null);
          if (queued && queued.queued) {
            showStatus(
              "A conexão falhou durante o envio. Seus dados ficaram salvos neste aparelho e serão reenviados quando a internet voltar."
            );
          } else {
            showStatus(
              "A conexão falhou. As respostas estão preservadas, mas confira a foto da discursiva antes de reenviar."
            );
          }
        } else {
          showStatus("Não foi possível enviar. Seus dados permanecem nesta página.");
        }
        return false;
      }
    },
    true
  );

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