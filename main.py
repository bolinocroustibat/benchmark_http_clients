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
# Concurrent in-flight requests per batch (same total count as sequential, see _parallel_batch_sizes).
PARALLEL_CONCURRENCY = 40
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


def _parallel_batch_sizes() -> list[int]:
    """Batch sizes that sum to REQUESTS_COUNT (each batch runs concurrently)."""
    total = REQUESTS_COUNT
    cap = PARALLEL_CONCURRENCY
    if cap < 1:
        raise ValueError("PARALLEL_CONCURRENCY must be >= 1")
    batches: list[int] = []
    while total > 0:
        chunk = min(cap, total)
        batches.append(chunk)
        total -= chunk
    return batches


def _print_result_table(results: list[RunResult], intro: str) -> None:
    slowest = max(t for _, t in results)
    results = sorted(results, key=lambda item: item[1])
    print(intro)
    label_w = max(len(name) for name, _ in results)
    print(f"{'Client':<{label_w}}  {'Time (s)':>10}  {'Gain':>8}")
    print("-" * (label_w + 10 + 8 + 4))
    for name, sec in results:
        gain = _pct_gain_vs_slowest(sec, slowest)
        print(f"{name:<{label_w}}  {sec:>10.3f}  {gain:>7.1f}%")
    print()


async def _parallel_httpx(http2: bool, label: str) -> RunResult:
    _testing(label)
    batches = _parallel_batch_sizes()
    start = time.perf_counter()
    async with httpx.AsyncClient(http1=True, http2=http2) as client:

        async def one_get() -> None:
            response = await client.get(URL)
            await response.aread()

        for size in batches:
            await asyncio.gather(*(one_get() for _ in range(size)))
    return (label, time.perf_counter() - start)


async def _parallel_niquests_http1() -> RunResult:
    label = "niquests (AsyncSession / parallel / HTTP/1.1)"
    _testing(label)
    batches = _parallel_batch_sizes()
    start = time.perf_counter()
    async with niquests.AsyncSession(
        disable_http2=True, disable_http3=True, multiplexed=False
    ) as session:

        async def one() -> str:
            response = await session.get(URL)
            return response.text

        for size in batches:
            await asyncio.gather(*(one() for _ in range(size)))
    return (label, time.perf_counter() - start)


async def _parallel_niquests_http2() -> RunResult:
    label = "niquests (AsyncSession / parallel / HTTP/2 only)"
    _testing(label)
    batches = _parallel_batch_sizes()
    start = time.perf_counter()
    async with niquests.AsyncSession(
        disable_http1=True, disable_http3=True, multiplexed=True
    ) as session:
        for size in batches:
            pending: list[object] = []
            for _ in range(size):
                pending.append(await session.get(URL))
            await session.gather(*pending)
    return (label, time.perf_counter() - start)


async def _parallel_niquests_http3() -> RunResult | None:
    label = "niquests (AsyncSession / parallel / HTTP/3 only)"
    _testing(label)
    try:
        host = _url_hostname()
        batches = _parallel_batch_sizes()
        start = time.perf_counter()
        async with niquests.AsyncSession(
            disable_http1=True, disable_http2=True, multiplexed=True
        ) as session:
            session.quic_cache_layer.add_domain(host)
            for size in batches:
                pending: list[object] = []
                for _ in range(size):
                    pending.append(await session.get(URL))
                await session.gather(*pending)
        return (label, time.perf_counter() - start)
    except Exception as exc:
        print(f"Skipped: {label} ({exc})", file=sys.stderr)
        return None


async def _parallel_aiohttp() -> RunResult:
    label = "aiohttp (ClientSession / parallel / HTTP/1.1)"
    _testing(label)
    batches = _parallel_batch_sizes()
    start = time.perf_counter()
    async with aiohttp.ClientSession() as session:

        async def one() -> str:
            async with session.get(URL) as response:
                return await response.text()

        for size in batches:
            await asyncio.gather(*(one() for _ in range(size)))
    return (label, time.perf_counter() - start)


async def _async_parallel_benchmarks() -> list[RunResult]:
    out: list[RunResult] = []
    out.append(
        await _parallel_httpx(False, "httpx (AsyncClient / parallel / HTTP/1.1)")
    )
    out.append(await _parallel_httpx(True, "httpx (AsyncClient / parallel / HTTP/2)"))
    out.append(await _parallel_niquests_http1())
    out.append(await _parallel_niquests_http2())
    h3 = await _parallel_niquests_http3()
    if h3 is not None:
        out.append(h3)
    out.append(await _parallel_aiohttp())
    return out


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

    parallel = asyncio.run(_async_parallel_benchmarks())

    seq_intro = (
        f"\n{REQUESTS_COUNT} sequential GET requests to {URL}\n"
        f"(Gain = percent time saved vs slowest in this block)\n"
    )
    _print_result_table(results, seq_intro)

    par_intro = (
        f"{REQUESTS_COUNT} GET requests to {URL} "
        f"({PARALLEL_CONCURRENCY} concurrent per batch; async)\n"
        f"(Gain = percent time saved vs slowest in this block)\n"
    )
    _print_result_table(parallel, par_intro)


if __name__ == "__main__":
    main()
