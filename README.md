# asyncxy

通用透明反向代理。前端 fetch 调用目标 URL 时只需在前面加代理前缀，method/headers/body 原样透传。

## 特性

- 透明代理：`/proxy/{目标URL}` 即可转发任意请求
- Chrome TLS 指纹模拟（curl_cffi impersonate）
- Cookie 双向透传（`X-Proxy-Cookie` 传入，`X-Cookie-Jar` 返回）
- 代理 IP 出站（`X-Proxy-Upstream` 指定 HTTP/HTTPS/SOCKS5 代理）
- 可配置超时（`X-Proxy-Timeout`，默认 30 秒，范围 5-120）
- CORS 全开放
- 无状态，无业务逻辑，通用于任何前端项目
- FastAPI + uvicorn 高并发

## 部署到 Render

1. 导入此仓库到 Render
2. 选择 **Web Service** → 连接此 GitHub 仓库
3. 配置：
   - Name: `asyncxy`
   - Branch: `main`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Instance Type: Free
4. 部署完成后地址：`https://asyncxy.onrender.com`

## API

### 健康检查

```
GET /health → {"status": "ok", "version": "2.0"}
```

### 代理请求

```
{任意方法} /proxy/{目标完整URL}
```

#### 自定义 Headers（代理控制）

| Header | 说明 | 示例 |
|--------|------|------|
| `X-Proxy-Cookie` | 要携带给目标的 Cookie | `JSESSIONID=xxx; shard=yyy` |
| `X-Proxy-Upstream` | 上游代理地址 | `http://user:pass@ip:port` |
| `X-Proxy-Timeout` | 超时秒数（5-120） | `30` |

#### 响应 Headers

| Header | 说明 |
|--------|------|
| `X-Cookie-Jar` | 目标返回的所有 cookie（`k=v; k2=v2` 格式） |
| `X-Set-Cookie` | 原始 Set-Cookie 数组（JSON） |

## 使用示例

### 基础请求

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy/https://example.com/api/data');
const data = await resp.json();
```

### 带 Cookie 的多步请求

```javascript
// 1. 登录
const r1 = await fetch('/proxy/https://target.com/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user: 'xxx', pass: 'xxx' }),
});
const cookies = r1.headers.get('x-cookie-jar');

// 2. 带 cookie 请求
const r2 = await fetch('/proxy/https://target.com/api/data', {
  headers: { 'X-Proxy-Cookie': cookies },
});
```

### 通过代理 IP 出站

```javascript
fetch('/proxy/https://target.com/api', {
  headers: {
    'X-Proxy-Upstream': 'http://user:pass@proxy-ip:port',
  },
});
```

## 本地开发

```bash
pip install -r requirements.txt
python app.py
# 监听 http://localhost:8080
```

## 技术栈

- **FastAPI** — ASGI Web 框架
- **uvicorn** — ASGI 服务器
- **curl_cffi** — HTTP 客户端（Chrome TLS 指纹模拟）
