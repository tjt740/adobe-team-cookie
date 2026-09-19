#!/usr/bin/env node

import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { launchPersistentContext } from "cloakbrowser";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const toolDir = path.resolve(scriptDir, "..");
const captureDir = path.resolve(
  process.env.CLOAK_CAPTURE_DIR || path.join(toolDir, "captures"),
);
const profileDir = path.resolve(
  process.env.CLOAK_PROFILE_DIR || path.join(toolDir, ".profiles", "adobe-capture"),
);
const targetUrl = process.env.CLOAK_TARGET_URL || "https://account.adobe.com/";
const debugPort = Number.parseInt(process.env.CLOAK_DEBUG_PORT || "0", 10);
const stamp = new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-");
const harPath = path.join(captureDir, `adobe-cloak-${stamp}.har`);
const summaryPath = path.join(captureDir, `adobe-cloak-${stamp}.jsonl`);
const proxy = normalizeProxy(process.env.CLOAK_PROXY || "127.0.0.1:17897");

fs.mkdirSync(captureDir, { recursive: true });
fs.mkdirSync(profileDir, { recursive: true });
await assertProxyReachable(proxy);

console.log(`[capture] profile: ${profileDir}`);
console.log(`[capture] HAR:     ${harPath}`);
console.log(`[capture] summary: ${summaryPath}`);
console.log(`[capture] proxy:   ${proxy ? "configured" : "direct"}`);
console.log(`[capture] debug:   ${debugPort > 0 ? `127.0.0.1:${debugPort}` : "disabled"}`);

const browserArgs = [
  "--lang=en-US",
  "--disable-webrtc",
  "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
];
if (debugPort > 0) {
  browserArgs.push(
    `--remote-debugging-port=${debugPort}`,
    "--remote-debugging-address=127.0.0.1",
  );
}

const context = await launchPersistentContext({
  userDataDir: profileDir,
  headless: false,
  humanize: true,
  humanPreset: "careful",
  locale: "en-US",
  viewport: null,
  ...(proxy ? { proxy } : {}),
  contextOptions: {
    recordHar: {
      path: harPath,
      mode: "full",
      content: "embed",
    },
    extraHTTPHeaders: {
      "Accept-Language": "en-US,en;q=0.9",
    },
  },
  args: browserArgs,
});

context.on("response", async (response) => {
  const url = response.url();
  if (!isRelevantAdobeRequest(url)) return;

  const request = response.request();
  const record = {
    time: new Date().toISOString(),
    status: response.status(),
    method: request.method(),
    url,
    resourceType: request.resourceType(),
  };
  fs.appendFileSync(summaryPath, `${JSON.stringify(record)}\n`);
  console.log(`[capture] ${record.status} ${record.method} ${url}`);
});

const page = context.pages()[0] || (await context.newPage());
try {
  await page.goto(targetUrl, { waitUntil: "commit", timeout: 60_000 });
} catch (error) {
  console.warn(`[capture] initial navigation did not settle: ${error.message}`);
}
await page.bringToFront();

console.log("[capture] browser ready; close the browser window to finish the HAR.");

let closePromise;
const close = async () => {
  if (closePromise) return closePromise;
  closePromise = (async () => {
    try {
      await context.close();
    } catch {
      // The window may already be closed.
    }
  })();
  return closePromise;
};

process.once("SIGINT", () => void close());
process.once("SIGTERM", () => void close());
await new Promise((resolve) => context.once("close", resolve));
console.log(`[capture] HAR saved: ${harPath}`);

function normalizeProxy(value) {
  const input = value.trim();
  if (!input) return "";
  if (input.includes("://")) return input;

  const parts = input.split(":");
  if (parts.length === 4) {
    const [host, port, username, password] = parts;
    return `http://${encodeURIComponent(username)}:${encodeURIComponent(password)}@${host}:${port}`;
  }
  return `http://${input}`;
}

async function assertProxyReachable(proxyUrl) {
  const url = new URL(proxyUrl);
  const port = Number.parseInt(url.port || (url.protocol === "https:" ? "443" : "80"), 10);

  await new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: url.hostname, port });
    const timer = setTimeout(() => {
      socket.destroy();
      reject(new Error(`proxy unavailable: ${url.hostname}:${port}`));
    }, 3_000);
    socket.once("connect", () => {
      clearTimeout(timer);
      socket.destroy();
      resolve();
    });
    socket.once("error", (error) => {
      clearTimeout(timer);
      reject(new Error(`proxy unavailable: ${url.hostname}:${port} (${error.message})`));
    });
  });
}

function isRelevantAdobeRequest(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "adobe.com" || host.endsWith(".adobe.com") ||
      host === "adobelogin.com" || host.endsWith(".adobelogin.com") ||
      host === "adobe.io" || host.endsWith(".adobe.io");
  } catch {
    return false;
  }
}
