(() => {
  const form = document.querySelector("[data-sare-student-form]");
  if (!form) return;

  const applicationId = form.dataset.applicationId;
  const studentId = form.dataset.studentId;
  const localKey = "sare:draft:" + applicationId + ":" + studentId;
  const queueKey = applicationId + ":" + studentId;
  const status = document.getElementById("draft-status");
  const hasServerDiscursive = form.dataset.hasDiscursive === "true";

  const DB_NAME = "sare-offline-v1";
  const DB_VERSION = 1;
  const STORE = "student_submissions";

  const setStatus = (text, state) => {
    if (!status) return;
    status.textContent = text;
    status.dataset.state = state;
  };

  const openDb = () =>
    new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) {
        reject(new Error("IndexedDB indisponível"));
        return;
      }
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: "key" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error("Falha ao abrir armazenamento local"));
    });

  const idbGet = async () => {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(queueKey);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
      tx.oncomplete = () => db.close();
    });
  };

  const idbPut = async (value) => {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(value);
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => {
        db.close();
        reject(tx.error);
      };
    });
  };

  const idbDelete = async () => {
    try {
      const db = await openDb();
      await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).delete(queueKey);
        tx.oncomplete = () => {
          db.close();
          resolve();
        };
        tx.onerror = () => {
          db.close();
          reject(tx.error);
        };
      });
    } catch (_) {
      // Limpeza local é secundária.
    }
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
      answers,
      savedAt: Date.now(),
    };
  };

  const selectedFile = () => {
    const input = form.querySelector('input[type="file"][name="discursive"]');
    return input && input.files && input.files[0] ? input.files[0] : null;
  };

  const saveLocalJson = (draft) => {
    try {
      localStorage.setItem(localKey, JSON.stringify(draft));
      return true;
    } catch (_) {
      return false;
    }
  };

  const captureCurrent = async ({ queued = false } = {}) => {
    const draft = serialize();
    const file = selectedFile();
    const previous = await idbGet().catch(() => null);

    const payload = {
      key: queueKey,
      applicationId,
      studentId,
      path: window.location.pathname,
      fields: draft,
      queued: Boolean(queued || (previous && previous.queued)),
      image: file || (previous && previous.image) || null,
      imageName: file ? file.name : (previous && previous.imageName) || null,
      imageType: file ? file.type : (previous && previous.imageType) || null,
      updatedAt: Date.now(),
    };

    saveLocalJson(draft);

    try {
      await idbPut(payload);
    } catch (_) {
      // localStorage ainda preserva presença e respostas mesmo sem IndexedDB.
    }

    return payload;
  };

  const saveDraft = async () => {
    const draft = serialize();
    const jsonSaved = saveLocalJson(draft);

    try {
      await captureCurrent();
      setStatus(
        navigator.onLine
          ? "Rascunho salvo neste aparelho"
          : "Sem conexão · respostas preservadas neste aparelho",
        navigator.onLine ? "draft" : "offline"
      );
    } catch (_) {
      setStatus(
        jsonSaved
          ? "Respostas salvas localmente · foto pode precisar ser selecionada novamente"
          : "Não foi possível salvar o rascunho local",
        jsonSaved ? "draft" : "error"
      );
    }
  };

  const restoreDraft = async () => {
    let draft = null;
    try {
      draft = JSON.parse(localStorage.getItem(localKey) || "null");
    } catch (_) {
      draft = null;
    }

    if (draft) {
      if (draft.presence) {
        form.querySelectorAll('input[name="presence"]').forEach((input) => {
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
    }

    const queued = await idbGet().catch(() => null);
    if (queued && queued.queued) {
      setStatus(
        navigator.onLine
          ? "Envio pendente preservado · tentando sincronizar"
          : "Sem conexão · envio pendente preservado",
        navigator.onLine ? "draft" : "offline"
      );
      return;
    }

    if (queued && queued.image) {
      setStatus(
        navigator.onLine
          ? "Rascunho restaurado · foto preservada neste aparelho"
          : "Sem conexão · respostas e foto preservadas",
        navigator.onLine ? "draft" : "offline"
      );
      return;
    }

    if (draft) {
      setStatus("Rascunho local restaurado", "draft");
    } else {
      setStatus(
        navigator.onLine ? "Conectado" : "Sem conexão",
        navigator.onLine ? "online" : "offline"
      );
    }
  };

  const queueSubmission = async () => {
    const payload = await captureCurrent({ queued: true });
    const present = payload.fields.presence === "PRESENT";

    if (present && !payload.image && !hasServerDiscursive) {
      setStatus(
        "Sem conexão · respostas salvas. Selecione a foto da discursiva antes de sair.",
        "offline"
      );
      return { queued: false, reason: "missing-image" };
    }

    payload.queued = true;
    await idbPut(payload);
    setStatus(
      "Sem conexão · envio salvo neste aparelho e será sincronizado quando a internet voltar",
      "offline"
    );
    return { queued: true };
  };

  const clearLocal = async () => {
    try {
      localStorage.removeItem(localKey);
    } catch (_) {}
    await idbDelete();
  };

  let syncing = false;
  const syncPending = async () => {
    if (syncing || !navigator.onLine) return false;

    const pending = await idbGet().catch(() => null);
    if (!pending || !pending.queued) return false;

    syncing = true;
    setStatus("Conexão restaurada · enviando dados preservados...", "draft");

    try {
      const fresh = await fetch(pending.path, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
      });

      if (!fresh.ok || fresh.url.includes("/auth/login")) {
        setStatus("Conexão restaurada · faça login novamente para sincronizar", "error");
        syncing = false;
        return false;
      }

      const html = await fresh.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const csrf = doc.querySelector('input[name="csrf_token"]');
      if (!csrf || !csrf.value) {
        throw new Error("Token CSRF não encontrado");
      }

      const body = new FormData();
      body.append("csrf_token", csrf.value);
      body.append("presence", pending.fields.presence || "");
      body.append("self_declaration", pending.fields.selfDeclaration || "");
      Object.entries(pending.fields.answers || {}).forEach(([name, value]) => {
        body.append(name, value);
      });
      if (pending.image) {
        body.append(
          "discursive",
          pending.image,
          pending.imageName || "discursiva-sare.jpg"
        );
      }
      body.append("submit", "Salvar estudante");

      const response = await fetch(pending.path, {
        method: "POST",
        body,
        credentials: "same-origin",
        redirect: "follow",
      });

      if (!response.ok || response.url.includes("/auth/login")) {
        throw new Error("Servidor não aceitou a sincronização");
      }

      if (response.url.includes("/aplicador/turma/") && response.url !== window.location.href) {
        await clearLocal();
        setStatus("Dados sincronizados com sucesso", "online");
        window.location.assign(response.url);
        return true;
      }

      const responseText = await response.text();
      if (responseText.includes("error") || responseText.includes("obrigat")) {
        setStatus("Conexão restaurada · revise os dados antes de reenviar", "error");
        syncing = false;
        return false;
      }

      await clearLocal();
      setStatus("Dados sincronizados com sucesso", "online");
      window.location.reload();
      return true;
    } catch (_) {
      setStatus(
        navigator.onLine
          ? "Não foi possível sincronizar agora · seus dados continuam salvos neste aparelho"
          : "Sem conexão · envio pendente preservado",
        navigator.onLine ? "error" : "offline"
      );
      syncing = false;
      return false;
    }
  };

  let saveTimer = null;
  const scheduleSave = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      saveDraft();
    }, 150);
  };

  form.addEventListener("change", scheduleSave);

  form.addEventListener("sare:offline-submit", async (event) => {
    if (event && event.detail && event.detail.originalEvent) {
      event.detail.originalEvent.preventDefault();
    }
    await queueSubmission();
  });

  window.addEventListener("offline", async () => {
    await captureCurrent().catch(() => {});
    setStatus("Sem conexão · rascunho preservado neste aparelho", "offline");
  });

  window.addEventListener("online", () => {
    setStatus("Conexão restaurada · verificando envios pendentes...", "draft");
    syncPending();
  });

  window.SAREOfflineDraft = {
    captureCurrent,
    queueSubmission,
    clearLocal,
    syncPending,
  };

  restoreDraft().then(() => {
    if (navigator.onLine) syncPending();
  });
})();