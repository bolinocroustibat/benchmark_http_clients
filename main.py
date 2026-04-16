"""Compare sync/async HTTP clients with and without connection reuse."""

import asyncio
import sys
import time
from collections.abc import Callable
from urllib.parse import urlparse

import aiohttp
import httpx
import niquests
import requests

REQUESTS_COUNT = 200
# Cloudflare serves HTTP/1.1, HTTP/2 and HTTP/3
URL = "https://www.cloudflare.com/cdn-cgi/trace"

RunResult = tuple[str, float]


def _testing(label: str) -> None:
    print(f"Testing: {label}...", flush=True)


def _url_hostname() -> str:
    host = urlparse(URL).hostname
    if not host:
        raise ValueError("URL must include a hostname")
    return host


def _try_bench(description: str, fn: Callable[[], RunResult]) -> RunResult | None:
    _testing(description)
    try:
        return fn()
    except Exception as exc:
        print(f"Skipped: {description} ({exc})", file=sys.stderr)
        return None


def _bench_requests_no_session() -> RunResult:
    label = "requests (no Session)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        response = requests.get(URL)
        _ = response.text
    return (label, time.perf_counter() - start)


def _bench_requests_session() -> RunResult:
    label = "requests (Session / keep-alive)"
    _testing(label)
    start = time.perf_counter()
    with requests.Session() as session:
        for _ in range(REQUESTS_COUNT):
            response = session.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_httpx_no_client() -> RunResult:
    label = "httpx (no Client / HTTP/1.1)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        with httpx.Client(http1=True, http2=False) as client:
            response = client.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_httpx_client() -> RunResult:
    label = "httpx (Client / keep-alive / HTTP/1.1)"
    _testing(label)
    start = time.perf_counter()
    with httpx.Client(http1=True, http2=False) as client:
        for _ in range(REQUESTS_COUNT):
            response = client.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_httpx_no_client_http2() -> RunResult:
    label = "httpx (no Client / HTTP/2)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        with httpx.Client(http1=True, http2=True) as client:
            response = client.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_httpx_client_http2() -> RunResult:
    label = "httpx (Client / keep-alive / HTTP/2)"
    _testing(label)
    start = time.perf_counter()
    with httpx.Client(http1=True, http2=True) as client:
        for _ in range(REQUESTS_COUNT):
            response = client.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_niquests_get_default() -> RunResult:
    label = "niquests (get / one-shot default)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        response = niquests.get(URL)
        _ = response.text
    return (label, time.perf_counter() - start)


def _bench_niquests_no_session() -> RunResult:
    label = "niquests (no Session / HTTP/1.1)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        with niquests.Session(disable_http2=True, disable_http3=True) as session:
            response = session.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_niquests_session() -> RunResult:
    label = "niquests (Session / keep-alive / HTTP/1.1)"
    _testing(label)
    start = time.perf_counter()
    with niquests.Session(disable_http2=True, disable_http3=True) as session:
        for _ in range(REQUESTS_COUNT):
            response = session.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_niquests_session_http2_only() -> RunResult:
    label = "niquests (Session / HTTP/2 only)"
    start = time.perf_counter()
    with niquests.Session(disable_http1=True, disable_http3=True) as session:
        for _ in range(REQUESTS_COUNT):
            response = session.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


def _bench_niquests_session_http3_only() -> RunResult:
    label = "niquests (Session / HTTP/3 only)"
    host = _url_hostname()
    start = time.perf_counter()
    with niquests.Session(disable_http1=True, disable_http2=True) as session:
        session.quic_cache_layer.add_domain(host)
        for _ in range(REQUESTS_COUNT):
            response = session.get(URL)
            _ = response.text
    return (label, time.perf_counter() - start)


async def _aiohttp_benchmarks() -> list[RunResult]:
    results: list[RunResult] = []

    label = "aiohttp (new ClientSession each request)"
    _testing(label)
    start = time.perf_counter()
    for _ in range(REQUESTS_COUNT):
        async with aiohttp.ClientSession() as session:
            async with session.get(URL) as response:
                await response.text()
    results.append((label, time.perf_counter() - start))

    label = "aiohttp (one ClientSession / keep-alive)"
    _testing(label)
    start = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        for _ in range(REQUESTS_COUNT):
            async with session.get(URL) as response:
                await response.text()
    results.append((label, time.perf_counter() - start))

    return results


def _pct_gain_vs_slowest(seconds: float, slowest: float) -> float:
    if slowest <= 0:
        return 0.0
    return 100.0 * (slowest - seconds) / slowest


def main() -> None:
    results: list[RunResult] = [
        _bench_requests_no_session(),
        _bench_requests_session(),
        _bench_httpx_no_client(),
        _bench_httpx_client(),
        _bench_httpx_no_client_http2(),
        _bench_httpx_client_http2(),
        _bench_niquests_get_default(),
        _bench_niquests_no_session(),
        _bench_niquests_session(),
    ]
    for fn, label in (
        (_bench_niquests_session_http2_only, "niquests (Session / HTTP/2 only)"),
        (_bench_niquests_session_http3_only, "niquests (Session / HTTP/3 only)"),
    ):
        row = _try_bench(label, fn)
        if row:
            results.append(row)

    results.extend(asyncio.run(_aiohttp_benchmarks()))

    slowest = max(t for _, t in results)
    results.sort(key=lambda item: item[1])

    print(f"\n{REQUESTS_COUNT} GET requests to {URL}\n")
    label_w = max(len(name) for name, _ in results)
    print(f"{'Client':<{label_w}}  {'Time (s)':>10}  {'Gain':>8}")
    print("-" * (label_w + 10 + 8 + 4))
    for name, sec in results:
        gain = _pct_gain_vs_slowest(sec, slowest)
        print(f"{name:<{label_w}}  {sec:>10.3f}  {gain:>7.1f}%")


if __name__ == "__main__":
    main()
