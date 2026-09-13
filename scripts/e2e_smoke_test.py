#!/usr/bin/env python3
"""Smoke test ponta a ponta do fluxo do aplicador em dados sintéticos.

Usa uma conta loadXXX e uma turma LOADXXXX. Pode:
- autenticar;
- abrir/retomar a turma;
- enviar uma imagem discursiva sintética para o Drive;
- remover essa imagem ao marcar o aluno ausente;
- registrar os demais alunos como ausentes;
- finalizar a turma;
- validar a geração do comprovante PDF.

NUNCA use com usuários/turmas reais.
"""

from __future__ import annotations

import argparse
import base64
import re
import time
import urllib.parse
import urllib.request
import uuid

from load_test import Client, CSRF_RE, derived_load_password


STUDENT_LINK_RE = re.compile(rb'href=["\'](/aplicador/turma/\d+/aluno/\d+)["\']')
APPLICATION_RE = re.compile(rb'/aplicador/turma/(\d+)')

# PNG 1x1 válido. O serviço aceita PNG e não exige dimensões mínimas.
TEST_PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg=="
)


def csrf_from(payload: bytes) -> str:
    match = CSRF_RE.search(payload)
    if not match:
        raise RuntimeError("Token CSRF não encontrado.")
    return next(group for group in match.groups() if group).decode("utf-8")


def multipart_body(fields: dict[str, str], file_field: str, filename: str, content: bytes):
    boundary = "----SARESmoke" + uuid.uuid4().hex
    chunks: list[bytes] = []

    for key, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ])

    chunks.extend([
        f"--{boundary}\r\n".encode(),
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
        ).encode(),
        b"Content-Type: image/png\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return boundary, b"".join(chunks)


def multipart_post(client: Client, path: str, fields: dict[str, str]):
    boundary, body = multipart_body(
        fields,
        "discursive",
        "sare-smoke-discursiva.png",
        TEST_PNG,
    )
    url = client.base_url + path
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "SARE-E2E-Smoke/1.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Origin": client.base_url,
            "Referer": url,
        },
    )
    started = time.perf_counter()
    with client.opener.open(req, timeout=client.timeout) as response:
        return response.geturl(), response.status, response.read(), time.perf_counter() - started


def ensure(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--user-index", type=int, default=99)
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    idx = args.user_index
    username = f"load{idx:03d}"
    code = f"LOAD{idx:04d}"
    password = derived_load_password(idx)

    client = Client(args.base_url, args.timeout)

    print(f"[1/8] Login sintético: {username}")
    client.login(username, password)

    print(f"[2/8] Abrindo/retomando turma: {code}")
    _elapsed, classroom = client.open_class(code)
    app_match = APPLICATION_RE.search(classroom)
    ensure(app_match is not None, "Não foi possível identificar a aplicação.")
    application_id = int(app_match.group(1))

    student_paths = sorted(
        {match.decode("utf-8") for match in STUDENT_LINK_RE.findall(classroom)}
    )
    ensure(student_paths, "Nenhum estudante sintético encontrado na turma.")
    print(f"      aplicação={application_id} estudantes={len(student_paths)}")

    first = student_paths[0]
    print("[3/8] Testando envio de discursiva ao Google Drive")
    _url, status, student_page, _elapsed = client.get(first)
    ensure(status == 200, "Falha ao abrir primeiro estudante.")
    token = csrf_from(student_page)
    url, status, payload, _elapsed = multipart_post(
        client,
        first,
        {
            "csrf_token": token,
            "presence": "PRESENT",
            "self_declaration": "",
            "submit": "Salvar estudante",
        },
    )
    ensure(status == 200, f"POST com imagem retornou HTTP {status}.")
    ensure("/aplicador/turma/" in urllib.parse.urlparse(url).path, "Upload não retornou à turma.")

    print("[4/8] Confirmando persistência da discursiva")
    _url, status, student_page, _elapsed = client.get(first)
    ensure(status == 200, "Falha ao reabrir estudante após upload.")
    ensure(
        "Foto já confirmada".encode("utf-8") in student_page or b"Foto j&#225; confirmada" in student_page,
        "A interface não confirmou a discursiva persistida.",
    )

    print("[5/8] Removendo arquivo de teste e marcando primeiro estudante ausente")
    token = csrf_from(student_page)
    _url, status, _payload, _elapsed = client.request(
        "POST",
        first,
        {
            "csrf_token": token,
            "presence": "ABSENT",
            "self_declaration": "",
            "submit": "Salvar estudante",
        },
    )
    ensure(status == 200, "Falha ao remover discursiva sintética.")

    print("[6/8] Registrando demais estudantes sintéticos como ausentes")
    for pos, path in enumerate(student_paths[1:], start=2):
        token, _elapsed = client.csrf(path)
        _url, status, _payload, _elapsed = client.request(
            "POST",
            path,
            {
                "csrf_token": token,
                "presence": "ABSENT",
                "self_declaration": "",
                "submit": "Salvar estudante",
            },
        )
        ensure(status == 200, f"Falha ao salvar estudante sintético #{pos}.")

    print("[7/8] Finalizando turma sintética e verificando idempotência")
    class_path = f"/aplicador/turma/{application_id}"
    _url, status, class_page, _elapsed = client.get(class_path)
    ensure(status == 200, "Falha ao recarregar turma.")
    token = csrf_from(class_page)
    finalize_path = f"{class_path}/finalizar"

    url, status, final_page, _elapsed = client.request(
        "POST",
        finalize_path,
        {"csrf_token": token},
    )
    ensure(status == 200, "Finalização falhou.")
    ensure(
        b"Turma finalizada com sucesso" in final_page,
        "Tela de sucesso não foi reconhecida.",
    )

    # Reenvio intencional: a rota deve apenas retornar à mesma tela final.
    _url, status, second_final, _elapsed = client.request(
        "POST",
        finalize_path,
        {"csrf_token": token},
    )
    ensure(status == 200, "Reenvio idempotente da finalização falhou.")
    ensure(
        b"Turma finalizada com sucesso" in second_final,
        "Reenvio não retornou à tela final.",
    )

    print("[8/8] Validando comprovante PDF")
    receipt_path = f"{class_path}/comprovante"
    _url, status, pdf, _elapsed = client.get(receipt_path)
    ensure(status == 200, "Falha ao baixar comprovante.")
    ensure(pdf.startswith(b"%PDF"), "Comprovante retornado não é um PDF válido.")

    print("\nRESULTADO: APROVADO")
    print("Fluxo verificado: login → turma → estudante → Drive → limpeza → finalização → PDF")
    print("Apenas dados sintéticos loadXXX foram utilizados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
