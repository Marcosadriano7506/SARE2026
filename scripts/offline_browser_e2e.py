#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "https://sare-homologacao.onrender.com"
USER_INDEX = 96
USERNAME = f"load{USER_INDEX:03d}"
CLASS_CODE = f"LOAD{USER_INDEX:04d}"
PASSWORD = hashlib.sha256(b"SARE_LOAD_PUBLIC_TEST_2026").hexdigest()[:24]

PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        image_path = Path(tmp) / "offline-discursiva.png"
        image_path.write_bytes(PNG)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()

            print("[1/7] Login")
            page.goto(f"{BASE_URL}/auth/login", wait_until="networkidle", timeout=60000)
            page.locator('input[name="username"]').fill(USERNAME)
            page.locator('input[name="password"]').fill(PASSWORD)
            page.locator('input[type="submit"], button[type="submit"]').first.click()
            page.wait_for_url("**/aplicador/**", timeout=60000)

            print("[2/7] Abrindo turma sintética")
            page.locator('input[name="code"]').fill(CLASS_CODE)
            page.locator('input[type="submit"], button[type="submit"]').first.click()
            page.wait_for_url("**/aplicador/turma/**", timeout=60000)

            print("[3/7] Abrindo estudante")
            student_link = page.locator('a[href*="/aluno/"]').first
            student_link.wait_for(state="visible", timeout=30000)
            student_link.click()
            page.wait_for_selector("[data-sare-student-form]", timeout=30000)

            print("[4/7] Preenchendo presença e foto antes da queda")
            page.locator('input[name="presence"][value="PRESENT"]').check()
            page.locator('input[name="discursive"]').set_input_files(str(image_path))
            page.wait_for_timeout(600)

            local_state = page.evaluate("""async () => {
              const form = document.querySelector('[data-sare-student-form]');
              const appId = form.dataset.applicationId;
              const studentId = form.dataset.studentId;
              const key = 'sare:draft:' + appId + ':' + studentId;
              return {
                draft: localStorage.getItem(key),
                offlineApi: !!window.SAREOfflineDraft
              };
            }""")
            assert local_state["offlineApi"], "API offline não carregou."
            assert local_state["draft"], "Rascunho local não foi criado."

            print("[5/7] Derrubando internet e salvando")
            context.set_offline(True)
            page.wait_for_timeout(300)

            page.locator('input[type="submit"], button[type="submit"]').last.click()
            page.wait_for_timeout(1200)

            status = page.locator("#submit-status").inner_text()
            draft_status = page.locator("#draft-status").inner_text()
            print("submit-status:", status)
            print("draft-status:", draft_status)
            assert "Sem internet" in status or "Sem conexão" in status
            assert "preserv" in status.lower() or "salv" in status.lower()

            queued = page.evaluate("""async () => {
              const form = document.querySelector('[data-sare-student-form]');
              const key = form.dataset.applicationId + ':' + form.dataset.studentId;
              return await new Promise((resolve, reject) => {
                const req = indexedDB.open('sare-offline-v1', 1);
                req.onerror = () => reject(req.error);
                req.onsuccess = () => {
                  const db = req.result;
                  const tx = db.transaction('student_submissions', 'readonly');
                  const get = tx.objectStore('student_submissions').get(key);
                  get.onerror = () => reject(get.error);
                  get.onsuccess = () => {
                    const value = get.result;
                    resolve({
                      exists: !!value,
                      queued: !!(value && value.queued),
                      hasImage: !!(value && value.image),
                      presence: value && value.fields ? value.fields.presence : null
                    });
                  };
                };
              });
            }""")
            print("fila local:", queued)
            assert queued["exists"] and queued["queued"], "Envio offline não ficou na fila."
            assert queued["hasImage"], "Foto não ficou preservada no IndexedDB."
            assert queued["presence"] == "PRESENT"

            print("[6/7] Restaurando internet e aguardando sincronização")
            context.set_offline(False)
            page.wait_for_timeout(500)

            page.wait_for_url(
                lambda url: "/aplicador/turma/" in url and "/aluno/" not in url,
                timeout=90000,
            )

            assert "saved=" in page.url, f"Sincronização não confirmou salvamento: {page.url}"
            print("destino após sincronizar:", page.url)

            print("[7/7] Confirmando que a fila local foi limpa")
            cleared = page.evaluate("""async () => {
              const marker = document.querySelector('[data-clear-student-draft]');
              if (!marker) return {marker:false};
              const key = marker.dataset.applicationId + ':' + marker.dataset.studentId;
              return await new Promise((resolve, reject) => {
                const req = indexedDB.open('sare-offline-v1', 1);
                req.onerror = () => reject(req.error);
                req.onsuccess = () => {
                  const db = req.result;
                  const tx = db.transaction('student_submissions', 'readonly');
                  const get = tx.objectStore('student_submissions').get(key);
                  get.onsuccess = () => resolve({marker:true, queued: !!get.result});
                  get.onerror = () => reject(get.error);
                };
              });
            }""")
            print("estado final:", cleared)
            assert cleared.get("marker") is True
            assert cleared.get("queued") is False, "Fila local não foi limpa após salvar no servidor."

            browser.close()

    print("\nRESULTADO: OFFLINE E2E APROVADO")
    print("Respostas + foto preservadas sem internet e sincronizadas automaticamente.")


if __name__ == "__main__":
    main()
