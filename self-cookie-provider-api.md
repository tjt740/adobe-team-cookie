# Adobe Cookie 重登录接口对接说明

我们的号池在账号 cookie 失效(Adobe 返回 401)时,会拿账号**邮箱**调你的接口,换一份新的 Adobe
登录 cookie。你只需要实现**一个 HTTP 接口**;什么时候调、调完怎么用,都在我们这边,你不用关心。

## 对接信息(由我们提供)

| 项 | 值 |
|---|---|
| 你的服务地址(base_url) | `__________`(你部署好告诉我们) |
| X-API-Key | `__________`(双方约定一个固定字符串) |

---

## 接口

```
POST {base_url}/api/v1/adobe/cookie/refresh
Content-Type: application/json
X-API-Key: <约定的固定值>
```

### 请求体

```json
{ "email": "user@example.com" }
```

- **每次只传一个邮箱**,没有批量。
- 邮箱按我们库里的原文传(不改大小写),你那边请按**不区分大小写**匹配。
- 请求体只有这一个字段,以后加字段会提前通知,请**忽略不认识的字段**而不是报错。

### 响应体

只要请求本身合法(鉴权通过、body 能解析),**一律回 HTTP 200**,登录成功还是失败看 body:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ok` | bool | 是 | `true` = 拿到了新 cookie;`false` = 这次没拿到 |
| `email` | string | 建议 | 回显请求里的邮箱,方便对账 |
| `cookie` | string | `ok=true` 时必填且非空 | 新的 Adobe cookie,格式见下 |
| `code` | string | `ok=false` 时必填 | 失败原因,机器可读,取值见下 |
| `message` | string | 否 | 失败原因的自由文本,只进我们的日志,随便写 |

成功:

```json
{
  "ok": true,
  "email": "user@example.com",
  "cookie": "ims_sid=xxx; aux_sid=yyy; ucat=zzz; ...",
  "code": "",
  "message": ""
}
```

失败:

```json
{
  "ok": false,
  "email": "user@example.com",
  "cookie": "",
  "code": "login_failed",
  "message": "password rejected by Adobe"
}
```

### `code` 取值

| code | 含义 | 我们怎么处理 |
|---|---|---|
| `login_failed` | 密码错、卡验证码、登录流程没走通,**这次**没拿到 | 账号回池,下次再 401 会再来问一次 |
| `account_disabled` | 号被 Adobe 封了 / 不存在 / 你那边确认救不回 | 同上(后续我们可能改成直接下线该账号,所以请**只在确定救不回时**用这个) |
| `rate_limited` | 你那边处理不过来,让我们晚点再来 | 同上 |
| `internal` | 你服务自身异常 | 同上 |

目前四个 code 我们处理方式一样,区分它们是为了日志能看出原因、以后能针对性处理。**请如实填**,不要全填 `internal`。

### `cookie` 格式

- 就是登录后浏览器请求 `adobe.com` 时带的 **Cookie 请求头的值原文**,形如 `k1=v1; k2=v2; k3=v3`,
  和我们导入页/推号接口里的 cookie 字符串是同一种东西。
- 要包含 IMS 登录态的那几个 cookie(`ims_sid` 等),我们拿它去换 access token;完整把当前会话的
  cookie 都给我们最保险。
- 前面带不带 `cookie:` 前缀都行,我们会剥掉。
- **不要**给 JSON 数组、不要 base64、不要 `Set-Cookie` 格式(带 `Path=` / `Expires=` 那种)。

---

## HTTP 状态码约定

| 状态码 | 什么时候回 |
|---|---|
| `200` | 请求合法,处理完了,**不管登录成功还是失败**都回 200,结果看 body |
| `400` | body 不是合法 JSON,或缺 `email` |
| `401` / `403` | `X-API-Key` 缺失或不对 |
| `5xx` | 你的服务挂了 |

**重点**:我们对**非 2xx** 一律当"传输层错误"处理(记日志、账号回池、不重试),**不会读 body**。所以
"登录失败"这种业务结果一定要用 `200 + ok=false + code`,不要用 4xx/5xx 表达,否则我们分不清是你挂了
还是号有问题。

---

## 我们这边的调用行为(你实现时要知道)

- **同一个邮箱不会并发调用**(我们有去重),**不同邮箱最多 10 个并发**。请按这个并发量准备。
- **同步等结果**,我们客户端超时 **5 分钟**。Adobe 登录慢没关系,在 5 分钟内把结果同步返回即可,
  **不要做成异步任务 + 轮询**。超过 5 分钟我们会断开并放弃这次结果,不会重发。
- 请做成**幂等**的:同一个邮箱隔一会儿再来一次是正常现象(账号又 401 了),每次都重新登录一遍即可。
- 没有固定调用节奏,触发条件是账号在出图时吃到 401,量取决于当时有多少号失效。

---

## 自测

把 `<base_url>` 和 `<key>` 换成你的:

```bash
# 1. 正常请求,期望 200 + ok=true + 非空 cookie
curl -sS -X POST '<base_url>/api/v1/adobe/cookie/refresh' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <key>' \
  -d '{"email":"user@example.com"}'

# 2. 一个你确定登不上的邮箱,期望 200 + ok=false + code 非空
curl -sS -X POST '<base_url>/api/v1/adobe/cookie/refresh' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <key>' \
  -d '{"email":"bad@example.com"}'

# 3. 错误的 key,期望 401 或 403
curl -sS -o /dev/null -w '%{http_code}\n' -X POST '<base_url>/api/v1/adobe/cookie/refresh' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: wrong' \
  -d '{"email":"user@example.com"}'

# 4. 缺 email,期望 400
curl -sS -o /dev/null -w '%{http_code}\n' -X POST '<base_url>/api/v1/adobe/cookie/refresh' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <key>' \
  -d '{}'
```

四条都符合预期就可以把 base_url 和 key 给我们接入了。
