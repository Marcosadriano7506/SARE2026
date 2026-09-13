(() => {
  const form = document.querySelector("[data-sare-student-form]");
  if (!form) return;

  const applicationId = form.dataset.applicationId;
  const studentId = form.dataset.studentId;
  const key = "sare:draft:" + applicationId + ":" + studentId;
  const status = document.getElementById("draft-status");

  const setStatus = (text, state) => {
    if (!status) return;
    status.textContent = text;
    status.dataset.state = state;
  };

  const serialize = () => {
    const presence = form.querySelector('input[name="presence"]:checked');
    const declaration = form.querySelector('[name="self_declaration"]');
    const answers = {};

    form.querySelectorAll('input[type="radio"][name^="q_"]:checked').forEach((input) => {
      answers[input.name] = input.value;
    });

    return {
      presence: presence ? presence.value : "",
      selfDeclaration: declaration ? declaration.value : "",
      answers: answers,
      savedAt: Date.now()
    };
  };

  const saveDraft = () => {
    try {
      localStorage.setItem(key, JSON.stringify(serialize()));
      setStatus(
        navigator.onLine ? "Rascunho salvo neste aparelho" : "Sem conexão · rascunho salvo",
        navigator.onLine ? "draft" : "offline"
      );
    } catch (_) {
      setStatus("Não foi possível salvar o rascunho local", "error");
    }
  };

  const restoreDraft = () => {
    let draft = null;
    try {
      draft = JSON.parse(localStorage.getItem(key) || "null");
    } catch (_) {
      draft = null;
    }

    if (!draft) {
      setStatus(
        navigator.onLine ? "Conectado" : "Sem conexão",
        navigator.onLine ? "online" : "offline"
      );
      return;
    }

    if (draft.presence) {
      const presenceInputs = form.querySelectorAll('input[name="presence"]');
      presenceInputs.forEach((input) => {
        if (input.value === draft.presence) input.checked = true;
      });
    }

    const declaration = form.querySelector('[name="self_declaration"]');
    if (declaration && draft.selfDeclaration !== undefined) {
      declaration.value = draft.selfDeclaration;
    }

    Object.keys(draft.answers || {}).forEach((name) => {
      const wantedValue = draft.answers[name];
      form.querySelectorAll('input[name="' + name + '"]').forEach((input) => {
        if (input.value === wantedValue) input.checked = true;
      });
    });

    form.dispatchEvent(new CustomEvent("sare:draft-restored"));
    setStatus("Rascunho local restaurado", "draft");
  };

  let saveTimer = null;
  const scheduleSave = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveDraft, 150);
  };

  form.addEventListener("change", scheduleSave);
  window.addEventListener("offline", () => {
    setStatus("Sem conexão · rascunho preservado", "offline");
  });
  window.addEventListener("online", () => {
    setStatus("Conexão restaurada · revise e salve", "draft");
  });

  restoreDraft();
})();
