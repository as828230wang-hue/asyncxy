# asyncxy

通用反向代理服务。部署后前端可通过单一接口转发任意 HTTP 请求，解决跨域、Cookie 透传、代理 IP 出站等问题。

## 特性

- 支持所有 HTTP 方法（GET/POST/PUT/DELETE/PATCH）
- 动态目标 URL（前端指定）
- 代理 IP 出站（HTTP/HTTPS/SOCKS5）
- Cookie 透传（前端管理生命周期，代理负责携带）
- TLS 指纹模拟 Chrome（基于 curl_cffi）
- CORS 全开放，任意前端域可调用

## 部署到 Render

1. Fork 或导入此仓库到你的 GitHub
2. 打开 https://dashboard.render.com/
3. **New** → **Web Service** → 选择此仓库
4. 配置：
   - Name: `asyncxy`
   - Branch: `main`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
   - Instance Type: Free
5. 点击 **Create Web Service**

部署完成后地址类似：`https://asyncxy.onrender.com`

## API

### 健康检查

```
GET /health
→ {"status": "ok"}
```

### 代理请求

```
POST /proxy
Content-Type: application/json
```

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✅ | 目标 URL |
| method | string | ❌ | HTTP 方法，默认 GET |
| headers | object | ❌ | 请求头 |
| body | string | ❌ | 请求体 |
| proxy | string | ❌ | 代理地址，如 `http://user:pass@ip:port` 或 `socks5://ip:port` |
| cookies | object | ❌ | Cookie 字典，会被合并到请求 Cookie header |
| timeout | number | ❌ | 超时秒数，默认 30 |

**响应体：**

```json
{
  "ok": true,
  "status": 200,
  "headers": {"content-type": "application/json", ...},
  "set_cookies": ["JSESSIONID=xxx; Path=/; HttpOnly", ...],
  "cookies": {"JSESSIONID": "xxx", ...},
  "body": "响应体字符串"
}
```

## 使用示例

### 基础请求

```javascript
const resp = await fetch('https://asyncxy.onrender.com/proxy', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://httpbin.org/get',
    method: 'GET',
  })
});
const data = await resp.json();
console.log(data.body);
```

### 带 Cookie 的多步请求（如登录后操作）

```javascript
// 第一步：登录，获取 cookies
const login = await proxyFetch({
  url: 'https://example.com/api/login',
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'user=xxx&pass=xxx',
});
const { cookies } = login;

// 第二步：带 cookies 访问需要认证的接口
const result = await proxyFetch({
  url: 'https://example.com/api/data',
  method: 'GET',
  cookies,  // 把第一步返回的 cookies 传入
});
```

### 通过代理 IP 出站

```javascript
const resp = await proxyFetch({
  url: 'https://target.com/api',
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ key: 'value' }),
  proxy: 'socks5://user:pass@proxy-ip:1080',
});
```

## 本地开发

```bash
pip install -r requirements.txt
python app.py
# 默认监听 http://localhost:8080
```

## 注意事项

- Render 免费版实例 15 分钟无请求会休眠，首次唤醒约 30 秒
- 不要用于传输敏感凭据到不受信任的代理服务器
- `curl_cffi` 模拟 Chrome TLS 指纹，可绕过部分 bot 检测
