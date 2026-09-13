#!/usr/bin/env python3
"""Teste de carga sem dependências externas para a homologação do SARE.

Cenários:
- coordinator: login + leitura do painel da coordenação.
- applicator: login + abertura da turma por código + leitura da lista.

Use somente usuários sintéticos em homologação.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


CSRF_RE = re.compile(
    rb'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']'
    rb'|value=["\']([^"\']+)["\'][^>]*name=["\']csrf_token["\']',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VirtualUser:
    username: str
    password: str
    class_code: str | None = None


@dataclass
class Sample:
    ok: bool
    elapsed: float
    label: str
    error: str | None = None


class Client:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def request(self, method: str, path: str, data: dict | None = None):
        url = self.base_url + path
        body = None
        headers = {"User-Agent": "SARE-Load-Test/1.0"}
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            # Reproduz os cabeçalhos enviados pelo navegador em formulários
            # same-origin. Flask-WTF/CSRF rejeita POST sem Referer em HTTPS.
            headers["Origin"] = self.base_url
            headers["Referer"] = self.base_url + path
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        started = time.perf_counter()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
                elapsed = time.perf_counter() - started
                return response.geturl(), response.status, payload, elapsed
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            snippet = payload[:400].decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{method} {path} retornou HTTP {exc.code}: {snippet}"
            ) from exc

    def csrf(self, path: str):
        _url, status, payload, elapsed = self.request("GET", path)
        if status != 200:
            raise RuntimeError(f"GET {path} retornou HTTP {status}")
        match = CSRF_RE.search(payload)
        if not match:
            raise RuntimeError(f"CSRF não encontrado em {path}")
        token = next(group for group in match.groups() if group)
        return token.decode("utf-8"), elapsed

    def login(self, username: str, password: str):
        token, first_elapsed = self.csrf("/auth/login")
        url, status, payload, second_elapsed = self.request(
            "POST",
            "/auth/login",
            {
                "csrf_token": token,
                "username": username,
                "password": password,
                "submit": "Entrar",
            },
        )
        if status != 200 or "/auth/login" in urllib.parse.urlparse(url).path:
            raise RuntimeError(f"Login falhou para {username}")
        return first_elapsed + second_elapsed, payload

    def open_class(self, class_code: str):
        token, first_elapsed = self.csrf("/aplicador/")
        url, status, payload, second_elapsed = self.request(
            "POST",
            "/aplicador/",
            {
                "csrf_token": token,
                "code": class_code,
                "submit": "Abrir turma",
            },
        )
        path = urllib.parse.urlparse(url).path
        if status != 200 or "/aplicador/turma/" not in path:
            raise RuntimeError(
                f"Abertura da turma {class_code} falhou; destino={path}"
            )
        return first_elapsed + second_elapsed, payload

    def get(self, path: str):
        return self.request("GET", path)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]


def run_coordinator(base_url, timeout, user, reads):
    samples: list[Sample] = []
    client = Client(base_url, timeout)
    try:
        elapsed, _payload = client.login(user.username, user.password)
        samples.append(Sample(True, elapsed, "login"))
        for _ in range(reads):
            _url, status, _payload, elapsed = client.get("/coordenacao/")
            samples.append(
                Sample(status == 200, elapsed, "coordinator_dashboard",
                       None if status == 200 else f"HTTP {status}")
            )
    except Exception as exc:
        samples.append(Sample(False, 0.0, "coordinator", str(exc)))
    return samples


def run_applicator(base_url, timeout, user, reads):
    samples: list[Sample] = []
    client = Client(base_url, timeout)
    try:
        try:
            elapsed, _payload = client.login(user.username, user.password)
        except Exception as exc:
            raise RuntimeError(f"Falha no login de {user.username}: {exc}") from exc
        samples.append(Sample(True, elapsed, "login"))

        if not user.class_code:
            raise RuntimeError("Usuário aplicador sem class_code.")

        try:
            elapsed, payload = client.open_class(user.class_code)
        except Exception as exc:
            raise RuntimeError(
                f"Falha ao abrir turma {user.class_code} para {user.username}: {exc}"
            ) from exc
        samples.append(Sample(True, elapsed, "open_class"))
        if b"Finalizar" not in payload and b"Estudante" not in payload:
            raise RuntimeError("Lista da turma não foi reconhecida.")
        # A URL da turma resulta do redirect do POST. Para leituras adicionais,
        # repetir o fluxo de entrada não é seguro porque tenta reclamar a turma.
        # Medimos GETs no dashboard autenticado, que exercitam sessão + banco.
        for _ in range(reads):
            _url, status, _payload, elapsed = client.get("/aplicador/")
            samples.append(
                Sample(status == 200, elapsed, "applicator_dashboard",
                       None if status == 200 else f"HTTP {status}")
            )
    except Exception as exc:
        samples.append(Sample(False, 0.0, "applicator", str(exc)))
    return samples


def derived_load_password(index: int) -> str:
    return f"SARE-LOAD-{index:03d}-ONLY"


def synthetic_users(prefix: str, password: str | None, count: int, scenario: str):
    users = []
    for index in range(1, count + 1):
        username = f"{prefix}{index:03d}"
        class_code = f"LOAD{index:04d}" if scenario == "applicator" else None
        user_password = password or derived_load_password(index)
        users.append(VirtualUser(username, user_password, class_code))
    return users


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--scenario", choices=["applicator", "coordinator"], default="applicator"
    )
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--reads", type=int, default=2)
    parser.add_argument("--prefix", default="load")
    parser.add_argument(
        "--password",
        help="Senha compartilhada. Se omitida, usa senha sintética derivada por usuário.",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-error-rate", type=float, default=0.02)
    parser.add_argument("--max-p95", type=float, default=3.0)
    args = parser.parse_args()

    if args.users < 1 or args.concurrency < 1:
        parser.error("users e concurrency devem ser maiores que zero")

    users = synthetic_users(
        args.prefix, args.password, args.users, args.scenario
    )
    worker = run_applicator if args.scenario == "applicator" else run_coordinator

    started = time.perf_counter()
    all_samples: list[Sample] = []
    lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(args.concurrency, args.users)
    ) as executor:
        futures = [
            executor.submit(
                worker,
                args.base_url,
                args.timeout,
                user,
                args.reads,
            )
            for user in users
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            with lock:
                all_samples.extend(result)

    duration = time.perf_counter() - started
    successes = [sample for sample in all_samples if sample.ok]
    failures = [sample for sample in all_samples if not sample.ok]
    latencies = [sample.elapsed for sample in successes if sample.elapsed > 0]
    total = len(all_samples)
    error_rate = len(failures) / total if total else 1.0

    print("\nSARE LOAD TEST")
    print(f"Cenário:       {args.scenario}")
    print(f"Usuários:      {args.users}")
    print(f"Concorrência:  {min(args.concurrency, args.users)}")
    print(f"Duração:       {duration:.2f}s")
    print(f"Amostras:      {total}")
    print(f"Falhas:        {len(failures)} ({error_rate * 100:.2f}%)")
    if latencies:
        print(f"Média:         {statistics.mean(latencies):.3f}s")
        print(f"P50:           {percentile(latencies, 0.50):.3f}s")
        print(f"P95:           {percentile(latencies, 0.95):.3f}s")
        print(f"P99:           {percentile(latencies, 0.99):.3f}s")
        print(f"Throughput:    {len(successes) / duration:.2f} req/s")

    if failures:
        print("\nPrimeiras falhas:")
        for sample in failures[:10]:
            print(f"- {sample.label}: {sample.error}")

    p95 = percentile(latencies, 0.95)
    passed = (
        total > 0
        and error_rate <= args.max_error_rate
        and p95 <= args.max_p95
    )
    print("\nRESULTADO:", "APROVADO" if passed else "REPROVADO")
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
