# benchmark_http_clients

Small script that times repeated HTTP GETs with **requests**, **httpx**, **niquests**, and **aiohttp**, comparing **one-off clients** vs **connection reuse** (session / shared client).

Results print sorted by wall time; **Gain** is percent time saved versus the slowest run in that batch.

## Run

```bash
uv sync
uv run main.py
```

Edit `REQUESTS_COUNT` and `URL` in `main.py` to change the workload.

## Sample output

One run on a typical broadband connection (values vary by machine, network, and time). Default target: Cloudflare trace endpoint.

```
200 GET requests to https://www.cloudflare.com/cdn-cgi/trace

Client                                        Time (s)      Gain
----------------------------------------------------------------
niquests (Session / keep-alive / HTTP/1.1)       1.762     89.3%
aiohttp (one ClientSession / keep-alive)         1.781     89.2%
httpx (Client / keep-alive / HTTP/2)             1.979     88.0%
httpx (Client / keep-alive / HTTP/1.1)           2.004     87.8%
niquests (Session / HTTP/2 only)                 2.015     87.7%
niquests (Session / HTTP/3 only)                 2.035     87.6%
requests (Session / keep-alive)                  2.319     85.9%
aiohttp (new ClientSession each request)         6.821     58.5%
httpx (no Client / HTTP/1.1)                     7.133     56.6%
httpx (no Client / HTTP/2)                       7.236     56.0%
requests (no Session)                            8.299     49.5%
niquests (get / one-shot default)                8.722     47.0%
niquests (no Session / HTTP/1.1)                16.445      0.0%
```
