#!/usr/bin/env node
/*
 * 用 CloakBrowser Pro 有头浏览器,给「被企业邀请的新号」跑首登+设密码(过 Arkose)。
 * 每个号:全新浏览器(临时 profile,用完删)+ 从 porxy 随机取一个代理 +
 *   geoip(时区/语言随代理、WebRTC 出口 IP 随代理)+ humanize + Pro license。
 * OTP 通过 spawn 后端的 otp_helper.py 取。每步截图到 shots/<email>/。
 *
 * 环境变量:
 *   ACCOUNTS_FILE  账号文件(默认 ../../1000-第一批.txt)
 *   PROXY_FILE     代理文件(默认 ../../porxy)
 *   MAX_ACCOUNTS   跑前 N 个(默认 50)
 *   CONCURRENCY    并发浏览器数(默认 5)
 *   START_INDEX    从第几个开始(默认 0)
 *   COMPLETE_PASSWORD  设置的密码(默认 CHANGE_ME_PASSWORD)
 *   HEADLESS       true 则无头(默认 false=有头)
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { launchPersistentContext } from "cloakbrowser";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const toolDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(toolDir, "..", "..");

const ACCOUNTS_FILE = process.env.ACCOUNTS_FILE || path.join(repoRoot, "1000-第一批.txt");
const PROXY_FILE = process.env.PROXY_FILE || path.join(repoRoot, "porxy");
const MAX_ACCOUNTS = parseInt(process.env.MAX_ACCOUNTS || "50", 10);
const CONCURRENCY = parseInt(process.env.CONCURRENCY || "5", 10);
const START_INDEX = parseInt(process.env.START_INDEX || "0", 10);
const COMPLETE_PASSWORD = process.env.COMPLETE_PASSWORD || "CHANGE_ME_PASSWORD";
const HEADLESS = process.env.HEADLESS === "true";
const OTP_HELPER = path.join(toolDir, "otp_helper.py");
// 可选:2captcha solver 扩展路径(设了就加载,用于解设密码页的 Arkose FunCaptcha)。不设=原行为。
const EXT_2CAPTCHA = process.env.EXT_2CAPTCHA ? path.resolve(process.env.EXT_2CAPTCHA) : "";
const PY = process.env.PYTHON || "python3";
const SHOTS_ROOT = path.join(toolDir, "shots");

function log(...a) { console.log(new Date().toISOString().slice(11, 19), ...a); }

function parseAccount(line) {
  const parts = line.split("----").map((s) => s.trim());
  const email = parts.find((p) => p.includes("@")) || parts[0] || "";
  // 格式:邮箱----密码----ClientID(uuid)----RefreshToken(M....)
  const rest = parts.filter((p) => p !== email);
  let clientId = "", refreshToken = "", mailUrl = "";
  for (const p of rest) {
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(p)) clientId = p;
    else if (p.startsWith("M.")) refreshToken = p;
    else if (/^https?:\/\//i.test(p) || p.startsWith("moemail://")) mailUrl = p;
  }
  return { email, clientId, refreshToken, mailUrl, raw: line };
}

function loadAccounts() {
  const lines = fs.readFileSync(ACCOUNTS_FILE, "utf8").split(/\r?\n/).filter((l) => l.trim());
  return lines.slice(START_INDEX, START_INDEX + MAX_ACCOUNTS).map(parseAccount).filter((a) => a.email);
}

function loadProxies() {
  return fs.readFileSync(PROXY_FILE, "utf8").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
}

function proxyToUrl(line) {
  const parts = line.split(":");
  if (parts.length === 4) {
    const [host, port, user, pass] = parts;
    return `http://${encodeURIComponent(user)}:${encodeURIComponent(pass)}@${host}:${port}`;
  }
  if (line.includes("://")) return line;
  return `http://${line}`;
}

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

const FIRST = ["Daniel", "Michael", "James", "David", "Emily", "Sarah", "Olivia", "Emma", "Ryan", "Kevin", "Laura", "Sophia", "Andrew", "Grace", "Ethan", "Chloe"];
const LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Moore", "Clark", "Lewis", "Walker", "Young", "King"];
function randName() { return { first: pick(FIRST), last: pick(LAST) }; }

// spawn 后端 otp_helper.py 取验证码
function fetchOtp(acc, timeoutSec = 180) {
  return new Promise((resolve) => {
    const p = spawn(PY, [OTP_HELPER, acc.email, acc.refreshToken, acc.clientId, acc.mailUrl || ""], {
      env: { ...process.env, OTP_TIMEOUT: String(timeoutSec) },
    });
    let out = "", err = "";
    p.stdout.on("data", (d) => (out += d));
    p.stderr.on("data", (d) => { err += d; process.stderr.write(`[otp:${acc.email}] ${d}`); });
    p.on("close", (code) => {
      const m = (out.trim().match(/\b(\d{4,8})\b/) || [])[1];
      resolve(code === 0 && m ? m : null);
    });
  });
}

async function shot(page, dir, name) {
  try { await page.screenshot({ path: path.join(dir, name + ".png"), fullPage: false }); } catch {}
}
async function pageInfo(page) {
  let url = "", txt = "";
  try { url = page.url(); } catch {}
  try { txt = (await page.evaluate(() => document.body.innerText.slice(0, 400))) || ""; } catch {}
  return { url, txt: txt.replace(/\s+/g, " ").slice(0, 300) };
}

// 等任意一个选择器"可见";返回最先可见的那个,超时/全失败返回 null
function waitAny(page, selectors, timeout = 15000) {
  return new Promise((resolve) => {
    let done = false, pending = selectors.length;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const t = setTimeout(() => finish(null), timeout);
    selectors.forEach((sel) => {
      page.waitForSelector(sel, { state: "visible", timeout }).then(() => { clearTimeout(t); finish(sel); }).catch(() => { if (--pending === 0) { clearTimeout(t); finish(null); } });
    });
  });
}
async function fillFirst(page, selectors, value, timeout = 15000) {
  const sel = await waitAny(page, selectors, timeout);
  if (!sel) return null;
  const el = await page.$(sel);
  if (!el) return null;
  try { await el.fill(value); } catch { try { await el.click(); await el.type(value, { delay: 25 }); } catch {} }
  return sel;
}
// 直接设 DOM value + 触发 React/Spectrum 事件(绕过 humanize 逐字符模拟,瞬间填入、不截断)
async function setValue(page, selectors, value, timeout = 6000) {
  const sel = await waitAny(page, selectors, timeout);
  if (!sel) return null;
  const el = await page.$(sel);
  if (!el) return null;
  try {
    await el.evaluate((node, val) => {
      const proto = node.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
      setter.call(node, val);
      node.dispatchEvent(new Event("input", { bubbles: true }));
      node.dispatchEvent(new Event("change", { bubbles: true }));
    }, value);
    return sel;
  } catch { return null; }
}
// 按可读标签(aria-label / <label>)定位并填(Spectrum 表单字段有标签)
async function fillLabel(page, labelRe, value) {
  try {
    const loc = page.getByLabel(labelRe);
    if (await loc.count()) { await loc.first().fill(value); return true; }
  } catch {}
  return false;
}
async function clickFirst(page, selectors, timeout = 10000) {
  const sel = await waitAny(page, selectors, timeout);
  if (!sel) return null;
  const el = await page.$(sel);
  if (!el) return null;
  try { await el.click(); } catch { try { await el.click({ force: true }); } catch {} }
  return sel;
}

async function processAccount(acc) {
  const dir = path.join(SHOTS_ROOT, acc.email.replace(/[^a-zA-Z0-9._-]/g, "_"));
  fs.mkdirSync(dir, { recursive: true });
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "cloak-adb-"));
  const proxy = proxyToUrl(pick(PROXIES));
  log(`▶ ${acc.email}  proxy=${proxy.replace(/\/\/.*@/, "//***@")}`);
  let context;
  try {
    context = await launchPersistentContext({
      userDataDir: profileDir,
      headless: HEADLESS,
      humanize: true,
      humanPreset: "careful",
      geoip: true,                 // 时区/语言随代理 + WebRTC 出口 IP 随代理
      locale: "en-US",
      proxy,
      viewport: null,
      licenseKey: process.env.CLOAKBROWSER_LICENSE_KEY,
      ...(EXT_2CAPTCHA ? { extensionPaths: [EXT_2CAPTCHA] } : {}),
    });
    const page = context.pages()[0] || (await context.newPage());
    page.setDefaultTimeout(20_000);

    // 1) 打开 Adobe 登录,等邮箱输入框可见(会跳到 auth.services.adobe.com)
    await page.goto("https://account.adobe.com/", { waitUntil: "domcontentloaded", timeout: 60_000 }).catch(() => {});
    const emailSel0 = await waitAny(page, ['input[name="username"]', 'input[type="email"]', '#EmailPage-EmailField', 'input#username'], 40_000);
    await shot(page, dir, "01-signin");
    const info1 = await pageInfo(page);
    log(`  01 signin url=${info1.url} emailField=${emailSel0} txt="${info1.txt}"`);
    if (!emailSel0) { log(`  ✗ 没等到邮箱输入框`); return { email: acc.email, ok: false, reason: "no_email_field", url: info1.url }; }

    // 2) 填邮箱 + 继续(setValue 直接填,绕过 humanize 逐字符,快)
    await setValue(page, [emailSel0], acc.email, 5000);
    await shot(page, dir, "02-email");
    const cont2 = await clickFirst(page, ['[data-id="EmailPage-ContinueButton"]', 'button[type="submit"]', 'button[data-id*="Continue"]', 'button:has-text("Continue")'], 10000);
    log(`  02 email filled, continue=${cont2}`);
    await page.waitForTimeout(5000);
    await shot(page, dir, "03-after-continue");
    const info3 = await pageInfo(page);
    log(`  03 after-continue url=${info3.url} txt="${info3.txt}"`);

    // 3) 已在"输入验证码"页(6 个框)。等码框可见 → 取码 → 逐位输入(自动跳格,填满自动提交)
    await waitAny(page, ['input[maxlength="1"]', 'input[data-id^="CodeInput"]', 'input[autocomplete="one-time-code"]', 'input[type="tel"]'], 15000);
    await shot(page, dir, "04-otp-page");
    log(`  取验证码中…`);
    const code = await fetchOtp(acc, Number(process.env.OTP_TIMEOUT) || 300);
    if (!code) { log(`  ✗ 没取到验证码`); await shot(page, dir, "04b-no-otp"); return { email: acc.email, ok: false, reason: "no_otp" }; }
    log(`  验证码=${code}`);
    const firstBox = await page.$('input[data-id^="CodeInput"], input[maxlength="1"], input[autocomplete="one-time-code"], input[type="tel"]');
    if (firstBox) { try { await firstBox.click(); } catch {} }
    await page.keyboard.type(code, { delay: 70 });
    await shot(page, dir, "05-otp-filled");
    await page.waitForTimeout(6000);
    // 兜底:若没自动提交,点 Continue(只点 Continue,避开 Back/Resend)
    await clickFirst(page, ['button[data-id*="Continue"]', 'button:has-text("Continue")'], 3000);
    await page.waitForTimeout(4000);
    await shot(page, dir, "06-after-otp");
    const info6 = await pageInfo(page);
    log(`  06 after-otp url=${info6.url} txt="${info6.txt}"`);

    // 5) 补全表单:姓名/密码/生日 → Complete Account(Arkose 由 CloakBrowser 静默通过)
    const hasForm = await waitAny(page, ['input[name="firstName"]', 'input[type="password"]', 'button:has-text("Complete Account")'], 15000);
    await shot(page, dir, "07-complete-form");
    if (!hasForm) {
      // 没有补全表单:可能已直接登录成功(老号已补全)
      const info7 = await pageInfo(page);
      const already = /account\.adobe\.com/.test(info7.url);
      log(`  07 无补全表单 url=${info7.url} already=${already}`);
      return { email: acc.email, ok: already, reason: already ? "already_complete" : "no_form", url: info7.url };
    }
    const nm = randName();
    const month = 1 + Math.floor(Math.random() * 12);
    const year = 1985 + Math.floor(Math.random() * 15);
    await setValue(page, ['input[name="firstName"]', '#Signup-FirstNameField', 'input[aria-label="First name"]'], nm.first, 6000);
    await setValue(page, ['input[name="lastName"]', '#Signup-LastNameField', 'input[aria-label="Last name"]'], nm.last, 4000);
    await setValue(page, ['input[type="password"]', 'input[name="password"]', '#Signup-PasswordField'], COMPLETE_PASSWORD, 4000);
    // 生日:Month 是原生 select(选月名的那个),Year 是文本框
    try {
      const selects = await page.$$("select");
      for (const s of selects) {
        const opts = await s.$$eval("option", (os) => os.map((o) => (o.textContent || "").trim()));
        if (opts.some((o) => /January|February|Month/i.test(o))) { await s.selectOption({ index: month }).catch(() => {}); break; }
      }
    } catch {}
    // Year:名字/占位失败就按标签定位(Spectrum 有可读标签)
    // Year:先直接 setValue(瞬间),不稳再逐字符(delay 小求快),再兜底 label
    let yset = (await setValue(page, ['input[name="year"]', 'input[aria-label="Year"]', 'input[placeholder*="Year"]', 'input[placeholder*="year"]'], String(year), 2500)) ? "setvalue" : null;
    if (!yset) {
      const ysel = await waitAny(page, ['input[name="year"]', 'input[aria-label="Year"]', 'input[placeholder*="Year"]', 'input[placeholder*="year"]'], 1500);
      if (ysel) { const yel = await page.$(ysel); if (yel) { try { await yel.click(); await yel.press("Control+A").catch(() => {}); await yel.type(String(year), { delay: 15 }); yset = "type"; } catch {} } }
    }
    if (!yset) yset = (await fillLabel(page, /year/i, String(year))) ? "label" : null;
    await shot(page, dir, "07b-form-filled");
    log(`  07b 表单:${nm.first} ${nm.last} / ${month}月 ${year}(year_set=${yset}) / 密码已填,点 Complete`);

    // 6) 提交(Arkose 由 CloakBrowser 静默通过)。注意:signin URL 的 redirect_uri 里含
    //    account.adobe.com 子串,必须按 hostname 判,不能用 includes。
    const hostOf = (u) => { try { return new URL(u).hostname; } catch { return ""; } };
    await clickFirst(page, ['button:has-text("Complete Account")', '[data-id*="Complete"]', 'button[type="submit"]'], 8000);
    // 若弹出 Arkose FunCaptcha:装了 2captcha 扩展时 autoSolveArkoselabs 会自动解,给足时间(解题 ~60-120s)。
    await page.waitForURL((u) => hostOf(u) === "account.adobe.com", { timeout: EXT_2CAPTCHA ? 220_000 : 70_000 }).catch(() => {});
    await page.waitForTimeout(3000);
    await shot(page, dir, "08-after-submit");
    const host = hostOf(page.url());
    const stillForm = await page.$('button:has-text("Complete Account")');
    const done = host === "account.adobe.com" && !stillForm;
    log(`  08 host=${host} done=${done} stillForm=${!!stillForm}`);
    return { email: acc.email, ok: done, reason: done ? "completed" : "submit_no_confirm", url: page.url() };
  } catch (e) {
    log(`  ✗ 异常 ${acc.email}: ${e.message}`);
    try { const p = context && (context.pages()[0]); if (p) await shot(p, dir, "99-error"); } catch {}
    return { email: acc.email, ok: false, reason: "error", error: e.message };
  } finally {
    try { if (context) await context.close(); } catch {}
    try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch {}
  }
}

// 并发池(错峰启动:各 worker 首个任务按槽位延迟,避免同一刻抢微软令牌/读邮件)
async function runPool(items, size, worker, staggerMs = 0) {
  const results = [];
  let idx = 0;
  const runners = Array.from({ length: Math.min(size, items.length) }, async (_v, slot) => {
    if (staggerMs) await new Promise((r) => setTimeout(r, slot * staggerMs));
    while (idx < items.length) {
      const my = idx++;
      const r = await worker(items[my], my);
      results[my] = r;
      // 每个号处理完立刻落盘:成功→completed.txt(下次自动跳过),失败→failed.txt。随时停都不丢。
      try {
        if (r && r.ok === true) fs.appendFileSync(path.join(toolDir, "completed.txt"), r.email + "\n");
        else if (r && r.ok === false) fs.appendFileSync(path.join(toolDir, "failed.txt"), `${r.email}\t${r.reason || ""}\n`);
      } catch {}
    }
  });
  await Promise.all(runners);
  return results;
}

// 跳过名单:completed.txt 里已通过的 + 环境变量 SKIP_EMAILS(逗号/空格分隔)
const DONE = new Set();
try { fs.readFileSync(path.join(toolDir, "completed.txt"), "utf8").split(/\r?\n/).forEach((e) => { e = e.trim(); if (e) DONE.add(e.toLowerCase()); }); } catch {}
(process.env.SKIP_EMAILS || "").split(/[,\s]+/).forEach((e) => { e = e.trim(); if (e) DONE.add(e.toLowerCase()); });

const ALL = loadAccounts();
const ACCOUNTS = ALL.filter((a) => !DONE.has(a.email.toLowerCase()));
const PROXIES = loadProxies();
fs.mkdirSync(SHOTS_ROOT, { recursive: true });
log(`范围 ${ALL.length} 个,跳过(已完成)${ALL.length - ACCOUNTS.length} 个,待跑 ${ACCOUNTS.length} 个,代理 ${PROXIES.length},并发 ${CONCURRENCY},headless=${HEADLESS}`);
if (!ACCOUNTS.length || !PROXIES.length) { log("待跑账号或代理为空,退出"); process.exit(1); }

const STAGGER_MS = parseInt(process.env.STAGGER_MS || "10000", 10);
const results = await runPool(ACCOUNTS, CONCURRENCY, processAccount, STAGGER_MS);
const okList = results.filter((r) => r && r.ok === true).map((r) => r.email);
const failList = results.filter((r) => r && r.ok === false).map((r) => `${r.email}\t${r.reason || ""}`);
log(`=== 完成:通过 ${okList.length} / 失败 ${failList.length} / 共 ${results.length} ===`);
fs.writeFileSync(path.join(SHOTS_ROOT, "results.json"), JSON.stringify(results, null, 2));
// completed.txt / failed.txt 已在每个号处理完时即时追加,这里只汇总
log(`本轮:通过 ${okList.length} -> completed.txt;失败 ${failList.length} -> failed.txt`);
