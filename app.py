# coding: utf-8
"""
通用反向代理服务。部署于 Render。
前端发 POST /proxy，服务端转发到目标 URL 并返回完整响应。

支持：
  - 所有 HTTP 方法（GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS）
  - 自定义请求 headers
  - 自定义请求 body（字符串或 JSON）
  - 代理 IP（HTTP/HTTPS/SOCKS5）
  - Cookie 透传（前端手动管理 cookie 生命周期）
  - 返回响应 headers（含 Set-Cookie 原文）

请求格式：
  POST /proxy
  Content-Type: application/json
  {
    "url": "https://target.com/api/xxx",
    "method": "POST",                    // 可选，默认 GET
    "headers": {"Content-Type": "..."},  // 可选
    "body": "...",                        // 可选，字符串
    "proxy": "http://user:pass@ip:port", // 可选
    "cookies": {"name": "value", ...},   // 可选，上次响应返回的 cookies
    "timeout": 30                        // 可选，默认 30 秒
  }

响应格式：
  {
    "ok": true,
    "status": 200,
    "headers": {"content-type": "...", ...},
    "set_cookies": ["JSESSIONID=xxx; Path=/; HttpOnly", ...],
    "cookies": {"JSESSIONID": "xxx", ...},
    "body": "响应体字符串"
  }
"""
import os
import json
from http.cookies import SimpleCookie
from typing import Optional

from aiohttp import web
from curl_cffi.requests import AsyncSession


async def handle_proxy(request: web.Request) -> web.Response:
    """通用代理入口"""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "error": "无效的 JSON"}, status=400)

    url: str = data.get("url", "").strip()
    if not url:
        return web.json_response({"ok": False, "error": "缺少 url 参数"}, status=400)

    method: str = data.get("method", "GET").upper()
    headers: dict = data.get("headers") or {}
    body: Optional[str] = data.get("body")
    proxy: Optional[str] = data.get("proxy")
    cookies: Optional[dict] = data.get("cookies")
    timeout: int = data.get("timeout", 30)

    # 如果前端传了 cookies，构造 Cookie header
    if cookies and isinstance(cookies, dict):
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        # 合并到 headers（如果已有 Cookie header 则追加）
        existing = headers.get("Cookie", "")
        headers["Cookie"] = (existing + "; " + cookie_str).strip("; ")

    try:
        async with AsyncSession(
            impersonate="chrome",
            proxy=proxy if proxy else None,
            timeout=timeout,
        ) as session:
            resp = await session.request(
                method=method,
                url=url,
                headers=headers if headers else None,
                data=body.encode("utf-8") if body else None,
            )

            # 解析响应 headers
            resp_headers = dict(resp.headers)

            # 提取 Set-Cookie（可能多个）
            set_cookie_list = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []

            # 解析 cookies 为简单字典
            parsed_cookies = dict(session.cookies)

            # 响应体
            try:
                resp_body = resp.text
            except Exception:
                resp_body = resp.content.decode("utf-8", errors="replace")

            return web.json_response({
                "ok": True,
                "status": resp.status_code,
                "headers": resp_headers,
                "set_cookies": set_cookie_list,
                "cookies": parsed_cookies,
                "body": resp_body,
            })

    except Exception as e:
        return web.json_response({
            "ok": False,
            "error": f"{type(e).__name__}: {str(e)}",
        }, status=502)


async def handle_health(request: web.Request) -> web.Response:
    """健康检查"""
    return web.json_response({"status": "ok"})


async def handle_cors_preflight(request: web.Request) -> web.Response:
    """处理 CORS 预检"""
    return web.Response(
        status=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400",
        },
    )


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """CORS 中间件，允许所有来源"""
    if request.method == "OPTIONS":
        return await handle_cors_preflight(request)
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post("/proxy", handle_proxy)
    app.router.add_get("/health", handle_health)
    app.router.add_options("/proxy", handle_cors_preflight)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"代理服务启动于端口 {port}")
    web.run_app(create_app(), host="0.0.0.0", port=port)
