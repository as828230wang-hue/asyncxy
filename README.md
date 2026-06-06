# asyncxy

通用透明反向代理服务。前端调用任何 API 时，只需在 URL 前加代理前缀即可绕过 CORS、管理 Cookie、切换出站 IP。

## 核心能力

- **透明转发**：method、headers、body 原样转发到目标，响应原样返回
- **Chrome TLS 指纹**：基于 curl_cffi，模拟 Chrome 浏览器的 TLS 握手特征
- **Cookie 管理**：目标返回的 cookie 通过响应 header 回传给前端，前端在后续请求中通过请求 header 传回
- **代理 IP 出站**：支持 HTTP、HTTPS、SOCKS5 上游代理
- **无状态**：代理不存储任何数据，每次请求独立
- **CORS 全开放**：任何域的前端都可以直接调用

---

## 快速开始

### 本地运行

```bash
pip install -r requirements.txt
python app.py
# 监听 http://localhost:8080
```

### 部署到 Render

1. GitHub 连接此仓库
2. 创建 Web Service，配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
3. 部署后地址：`https://asyncxy.onrender.com`

---

## API 文档

### 健康检查

```
GET /health
```

响应：
```json
{"status": "ok", "version": "2.0"}
```

---

### 代理请求

```
{任意HTTP方法} /proxy/{目标完整URL}
```

#### 基本规则

| 项目 | 说明 |
|------|------|
| 路径格式 | `/proxy/https://目标域名/路径?参数` |
| 支持方法 | GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS |
| 请求体 | 原样转发，最大 10MB |
| 超时 | 默认 30 秒，范围 5-120 秒 |

---

## 自定义 Headers（代理控制参数）

前端通过以下自定义 header 控制代理行为，这些 header **不会**被转发给目标服务器：

### X-Proxy-Cookie

**用途**：携带 cookie 给目标服务器。

前端无法自动管理跨域 cookie，通过此 header 手动传递。值的格式和标准 `Cookie` header 一致。

```
X-Proxy-Cookie: JSESSIONID=abc123; session_token=xyz789
```

**获取方式**：从之前请求的响应 header `X-Cookie-Jar` 中获取。

---

### X-Proxy-Upstream

**用途**：指定上游代理 IP，请求通过该代理出站。

**格式**：`协议://用户名:密码@主机:端口`

支持的协议：

| 协议 | 格式 | 说明 |
|------|------|------|
| HTTP | `http://user:pass@host:port` | HTTP CONNECT 代理 |
| HTTPS | `https://user:pass@host:port` | 加密的 HTTP 代理 |
| SOCKS5 | `socks5://user:pass@host:port` | SOCKS5 代理 |

**示例**：

```
X-Proxy-Upstream: http://xy5c72939-region-US:6jcx65dw@us.novproxy.io:1000
X-Proxy-Upstream: socks5://user:pass@192.168.1.1:1080
X-Proxy-Upstream: http://proxyuser:proxypass@residential.proxy.com:8080
```

**不带认证的代理**：

```
X-Proxy-Upstream: http://192.168.1.1:8080
X-Proxy-Upstream: socks5://127.0.0.1:1080
```

**不传此 header 时**：代理服务器直接出站（使用代理服务器自身的 IP）。

---

### X-Proxy-Timeout

**用途**：设置请求超时时间（秒）。

```
X-Proxy-Timeout: 60
```

| 约束 | 值 |
|------|------|
| 默认 | 30 秒 |
| 最小 | 5 秒 |
| 最大 | 120 秒 |

---

## 响应 Headers

代理在响应中添加以下 header，前端可以读取：

### X-Cookie-Jar

目标服务器返回的所有 cookie，格式为 `key=value; key2=value2`。

前端在后续请求中将此值传入 `X-Proxy-Cookie` 即可保持会话。

```
X-Cookie-Jar: JSESSIONID=abc123; session_id=xyz; shard=server1
```

### X-Set-Cookie

目标服务器返回的原始 `Set-Cookie` header 数组（JSON 格式），包含 Path、Expires 等属性。

```
X-Set-Cookie: ["JSESSIONID=abc; Path=/; HttpOnly", "shard=s1; Path=/; Secure"]
```

---

## 使用示例

### 1. 简单 GET 请求

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy/https://api.example.com/data');
const data = await resp.json();
```

### 2. 带认证的 POST 请求

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy/https://api.example.com/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ username: 'user', password: 'pass' }),
});
const cookies = resp.headers.get('x-cookie-jar');
const data = await resp.json();
```

### 3. 后续请求携带 Cookie

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy/https://api.example.com/protected', {
  headers: {
    'X-Proxy-Cookie': cookies,  // 从步骤 2 获取
  },
});
```

### 4. 使用代理 IP 出站

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy/https://target.com/api', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Proxy-Upstream': 'http://user:pass@us.proxy.io:8080',
    'X-Proxy-Cookie': cookies,
  },
  body: JSON.stringify({ key: 'value' }),
});
```

### 5. 完整会话示例（登录 → 操作 → 发送）

```javascript
const PROXY = 'https://asyncxy.onrender.com/proxy/';

// 步骤 1：登录
const loginResp = await fetch(PROXY + 'https://mail.example.com/api/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'user=me@example.com&pass=secret',
});
const cookies = loginResp.headers.get('x-cookie-jar');
const session = (await loginResp.json()).session;

// 步骤 2：使用 session 和 cookie 操作
const dataResp = await fetch(PROXY + `https://mail.example.com/api/data?session=${session}`, {
  headers: { 'X-Proxy-Cookie': cookies },
});
const result = await dataResp.json();
```

---

## 错误响应

| 状态码 | 含义 |
|--------|------|
| 400 | 目标 URL 格式错误（不以 http:// 或 https:// 开头） |
| 413 | 请求体超过 10MB |
| 502 | 代理请求失败（网络错误、超时、代理连接失败等） |

502 响应体为纯文本错误信息：
```
Timeout: Connection timed out after 30001 milliseconds
ProxyError: Failed to perform, curl: (56) CONNECT tunnel failed, response 403
```

---

## 技术栈

- **FastAPI** — ASGI Web 框架
- **uvicorn** — 高性能 ASGI 服务器
- **curl_cffi** — HTTP 客户端，提供 Chrome/Firefox TLS 指纹模拟
