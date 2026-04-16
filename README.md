# Benchmark Python HTTP Clients

Small script that times repeated HTTP GETs with **requests**, **httpx**, **niquests**, and **aiohttp**, comparing **one-off clients** vs **connection reuse** (session / shared client).

Results print sorted by wall time; **Gain** is percent time saved versus the slowest run in that batch.

## Run

```bash
uv sync
uv run main.py
```

Edit `REQUESTS_COUNT` and `URL` in `main.py` to change the workload.

## Sample output

One run with Python 3.14.4 on a typical broadband connection (values vary by machine, network, and time). Default target: Cloudflare trace endpoint.

```
200 GET requests to https://www.cloudflare.com/cdn-cgi/trace

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
