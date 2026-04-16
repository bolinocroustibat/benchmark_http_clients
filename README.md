# Benchmark Python HTTP Clients

Small script that times repeated HTTP GETs with **requests**, **httpx**, **niquests**, and **aiohttp**, comparing **one-off clients** vs **connection reuse** (session / shared client), plus optional **HTTP/2** / **HTTP/3** stacks where supported.

The script prints **two tables**:

1. **Sequential** — one request after another (same total count).
2. **Parallel async** — the same total number of GETs, split into batches of **`PARALLEL_CONCURRENCY`** concurrent in-flight requests using **`httpx.AsyncClient`**, **`niquests.AsyncSession`** (with **`session.gather()`** when multiplexing), and **`aiohttp.ClientSession`**. This better stresses **HTTP/2** / **HTTP/3** multiplexing than a purely serial loop.

**Gain** in each table is the percent time saved versus the **slowest row in that table only** (the two blocks are not merged).

## Run

```bash
uv sync
uv run main.py
```

Edit in `main.py`:

- **`REQUESTS_COUNT`** and **`URL`** — workload and target (default: Cloudflare trace URL, good for H2/H3).
- **`PARALLEL_CONCURRENCY`** — max concurrent requests per async batch (batches are sized so the parallel phase still totals **`REQUESTS_COUNT`** requests).

## Sample output

Illustrative numbers from a single machine; your order and timings will differ.

### Sequential block

```
200 sequential GET requests to https://www.cloudflare.com/cdn-cgi/trace
(Gain = percent time saved vs slowest in this block)

Client                                        Time (s)      Gain
----------------------------------------------------------------
niquests (Session / HTTP/2 only)                 1.676     85.6%
niquests (Session / keep-alive / HTTP/1.1)       1.734     85.1%
niquests (Session / HTTP/3 only)                 1.751     84.9%
httpx (Client / keep-alive / HTTP/2)             1.847     84.1%
aiohttp (one ClientSession / keep-alive)         1.884     83.8%
httpx (Client / keep-alive / HTTP/1.1)           1.907     83.6%
requests (Session / keep-alive)                  1.935     83.4%
aiohttp (new ClientSession each request)         6.117     47.4%
httpx (no Client / HTTP/1.1)                     7.034     39.5%
httpx (no Client / HTTP/2)                       7.043     39.4%
requests (no Session)                            8.484     27.0%
niquests (get / one-shot default)                8.506     26.8%
niquests (no Session / HTTP/1.1)                11.621      0.0%
```

### Parallel async block

```
200 GET requests to https://www.cloudflare.com/cdn-cgi/trace (40 concurrent per batch; async)
(Gain = percent time saved vs slowest in this block)

Client                                              Time (s)      Gain
----------------------------------------------------------------------
aiohttp (ClientSession / parallel / HTTP/1.1)          0.129     78.7%
niquests (AsyncSession / parallel / HTTP/2 only)       0.190     68.5%
httpx (AsyncClient / parallel / HTTP/2)                0.302     49.9%
niquests (AsyncSession / parallel / HTTP/1.1)          0.324     46.3%
niquests (AsyncSession / parallel / HTTP/3 only)       0.380     36.9%
httpx (AsyncClient / parallel / HTTP/1.1)              0.603      0.0%
```

**aiohttp** is still HTTP/1.1-only. Under high concurrency, its connector typically uses **multiple TCP connections** to the same host (each connection carries one request at a time in HTTP/1.1). That can make wall time look very good next to a **single** multiplexed HTTP/2 or HTTP/3 connection — it is **not** a strict apples-to-apples protocol comparison.
