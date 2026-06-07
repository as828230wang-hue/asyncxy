# coding: utf-8
"""
asyncxy v2 — 透明反向代理（FastAPI + curl_cffi AsyncSession）。

用法：
  请求: {METHOD} /proxy/{目标URL}
  示例: POST /proxy/https://mail.ziggo.nl/ajax/login?action=login

特性：
  - /proxy/ 后面即目标地址，method/headers/body 原样透传
  - Cookie 透传：前端通过 X-Proxy-Cookie header 传入
  - Cookie 回传：通过 X-Cookie-Jar header 返回给前端
  - 代理 IP：通过 X-Proxy-Upstream header 指定（http/https/socks5）
  - CORS 全开放
  - curl_cffi AsyncSession 提供 Chrome TLS 指纹模拟
"""
import os
import json
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from curl_cffi.requests import AsyncSession

# 最大请求体 10MB
MAX_BODY_SIZE = 10 * 1024 * 1024

app = FastAPI(title="asyncxy", version="2.0.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Set-Cookie", "X-Cookie-Jar"],
)

# 代理内部 header，不转发给目标
STRIP_REQ_HEADERS = frozenset({
    "host", "x-proxy-cookie", "x-proxy-upstream", "x-proxy-timeout",
    "origin", "referer", "connection", "accept-encoding",
    "content-length", "transfer-encoding",
})


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "2.0"}


@app.api_route(
    "/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy(request: Request, path: str):
    """透明代理入口：/proxy/{目标完整URL}"""

    # ── 1. 解析目标 URL ──
    target_url = unquote(path)
    query = request.url.query
    if query:
        target_url += "?" + (query if isinstance(query, str) else query.decode())
    if not target_url.startswith(("http://", "https://")):
        return Response("Target URL must start with http:// or https://", status_code=400)

    method = request.method

    # ── 2. 构造转发 headers ──
    fwd_headers: dict[str, str] = {}
    for k, v in request.headers.items():
        if k.lower() not in STRIP_REQ_HEADERS:
            fwd_headers[k] = v

    # Cookie 透传：X-Proxy-Cookie → 解析为字典传入 curl_cffi cookies 参数
    proxy_cookie = request.headers.get("x-proxy-cookie")
    cookie_dict: dict[str, str] = {}
    if proxy_cookie:
        for pair in proxy_cookie.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                cookie_dict[k.strip()] = v.strip()

    # ── 3. 代理 IP ──
    upstream = request.headers.get("x-proxy-upstream") or None

    # ── 4. 超时 ──
    try:
        timeout = int(request.headers.get("x-proxy-timeout", "30"))
    except (ValueError, TypeError):
        timeout = 30
    timeout = max(5, min(timeout, 120))  # 限制 5~120 秒

    # ── 5. 读取请求体 ──
    body = await request.body()
    if len(body) > MAX_BODY_SIZE:
        return Response("Request body too large", status_code=413)
    if not body:
        body = None

    # ── 6. 转发请求 ──
    try:
        async with AsyncSession(impersonate="chrome", proxy=upstream, timeout=timeout) as session:
            resp = await session.request(
                method=method,
                url=target_url,
                headers=fwd_headers if fwd_headers else None,
                cookies=cookie_dict if cookie_dict else None,
                data=body,
            )

            # ── 7. 构造响应 ──
            resp_headers: dict[str, str] = {}

            # 回传 cookie 字典（前端直接可用）
            if session.cookies:
                resp_headers["X-Cookie-Jar"] = "; ".join(
                    f"{k}={v}" for k, v in session.cookies.items()
                )

            # 回传原始 Set-Cookie（供调试或高级用途）
            set_cookies = (
                resp.headers.get_list("set-cookie")
                if hasattr(resp.headers, "get_list")
                else []
            )
            if set_cookies:
                resp_headers["X-Set-Cookie"] = json.dumps(set_cookies)

            content_type = resp.headers.get("content-type", "application/octet-stream")

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp_headers,
                media_type=content_type,
            )

    except Exception as e:
        return Response(
            content=f"{type(e).__name__}: {e}",
            status_code=502,
            media_type="text/plain",
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
