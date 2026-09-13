#!/usr/bin/env python3
"""Teste de rajada realista: usuários já autenticados e dashboard carregado.

Mede somente o clique em "Abrir turma": POST /aplicador/ + redirect até a turma.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import threading
import time
import urllib.parse

from load_test import Client, CSRF_RE, derived_load_password


def pct(values, p):
    values = sorted(values)
    if not values:
        return 0.0
    i = min(len(values) - 1, max(0, round((len(values) - 1) * p)))
    return values[i]


def prepare(base_url, timeout, index):
    username = f"load{index:03d}"
    password = derived_load_password(index)
    code = f"LOAD{index:04d}"
    client = Client(base_url, timeout)
    _elapsed, payload = client.login(username, password)
    match = CSRF_RE.search(payload)
    if not match:
        raise RuntimeError(f"CSRF do dashboard não encontrado para {username}")
    token = next(group for group in match.groups() if group).decode("utf-8")
    return client, username, code, token


def run_one(prepared, barrier):
    client, username, code, token = prepared
    barrier.wait()
    started = time.perf_counter()
    url, status, payload, _elapsed = client.request(
        "POST",
        "/aplicador/",
        {
            "csrf_token": token,
            "code": code,
            "submit": "Abrir turma",
        },
    )
    elapsed = time.perf_counter() - started
    path = urllib.parse.urlparse(url).path
    ok = status == 200 and "/aplicador/turma/" in path
    return username, ok, elapsed, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--users", type=int, required=True)
    ap.add_argument("--timeout", type=float, default=30)
    args = ap.parse_args()

    print(f"Preparando {args.users} sessões autenticadas...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.users) as ex:
        prepared = list(ex.map(
            lambda i: prepare(args.base_url, args.timeout, i),
            range(1, args.users + 1),
        ))

    barrier = threading.Barrier(args.users)
    print(f"Disparando {args.users} aberturas de turma simultâneas...")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.users) as ex:
        futures = [ex.submit(run_one, p, barrier) for p in prepared]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    duration = time.perf_counter() - started

    failures = [r for r in results if not r[1]]
    lat = [r[2] for r in results if r[1]]

    print("\nSARE REALISTIC OPEN-CLASS BURST")
    print(f"Usuários simultâneos: {args.users}")
    print(f"Falhas:               {len(failures)} ({(len(failures)/args.users)*100:.2f}%)")
    print(f"Duração da rajada:    {duration:.3f}s")
    if lat:
        print(f"Média:                 {statistics.mean(lat):.3f}s")
        print(f"P50:                   {pct(lat, .50):.3f}s")
        print(f"P95:                   {pct(lat, .95):.3f}s")
        print(f"P99:                   {pct(lat, .99):.3f}s")
        print(f"Máximo:                {max(lat):.3f}s")
    for username, ok, elapsed, path in sorted(results):
        print(f"{username}: {'OK' if ok else 'FALHA'} {elapsed:.3f}s -> {path}")

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
