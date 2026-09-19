/* Arkose PoW micro-runtime.
 * Runs the REAL per-session Arkose "sequence" worker JS in a Node vm sandbox
 * (with Web-Worker shims). Hashing is optional:
 *
 *   gpu_mode     — run transform until toBinary/btoa(encoded), then exit.
 *                  Go brute-forces sha512(piece+decimal nonce).
 *   hook_counts  — skip the hash loop (patched regenerator) so sequence
 *                  still emits the real finalTransform.
 *   default      — full in-vm hashcash (fallback).
 *
 * Usage:
 *   node pow_runner.js <sequence_js_path>   < input.json
 *   stdin JSON: {"seed":[...], "splits":[{"target_hash":...}], "starting_nonce":N, "timeout":30000,
 *                "gpu_mode":true | "hook_counts":[...], "hook_targets":[...]}
 *   timeout is the Arkose worker itimeout (ms). JS-hash fallback only; native brute does not use it.
 *   The poll deadline is timeout+5s so a missed hook fails fast.
 *   stdout JSON: gpu_mode → {"encoded","hook_patched","pieces"}
 *                else     → {"transform","result","hash_rate","execution_time"}
 */
const vm = require("vm");
const fs = require("fs");

// Per-session sequence variants. First match wins for that site; several may apply.
const HOOKS = [
  {
    name: "regenerator-case3",
    from: "hashData=sha512;case 3:",
    to: "hashData=sha512;if(globalThis.__powHookCount){attemptCount=globalThis.__powHookCount(split.target);_context4.next=13;break;}case 3:",
  },
];
const SENTINEL = "__POW_GPU_ENCODED__";

// Invite hash loop header is stable; the while *condition* is re-obfuscated
// every fetch (solo5 !==, solo8 !==+timer, solo12 wrapper(hash, obj[dec]),
// later: reversed args, decoder-callee, opaque helper). Always skip the while
// when hooked. Finding obj/rhs is best-effort; installHook also has a
// sequential fallback so we do not need to parse the compare.
const HASH_LOOP_HEAD =
  /(?:let|const|var)\s+(\w+)\s*=\s*startingNonce\s*,\s*(\w+)\s*=\s*['"]{2}\s*,\s*(\w+)\s*=\s*sha512\s*;\s*while\s*\(/;

function decRHS(m) {
  return m[1] + "[" + m[2] + "(" + m[3] + ")]";
}

function findWhileTarget(hash, cond) {
  const h = hash.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const DEC = "(\\w+)\\[(\\w+)\\((0x[0-9a-f]+|\\d+)\\)\\]";
  let m = new RegExp(h + "\\s*(?:!==|!=)\\s*" + DEC, "i").exec(cond);
  if (m) return { obj: m[1], rhs: decRHS(m) };
  m = new RegExp(DEC + "\\s*(?:!==|!=)\\s*" + h + "\\b", "i").exec(cond);
  if (m) return { obj: m[1], rhs: decRHS(m) };
  m = new RegExp(h + "\\s*(?:!==|!=)\\s*(\\w+)\\.target\\b").exec(cond);
  if (m) return { obj: m[1], rhs: m[1] + ".target" };
  m = new RegExp("(\\w+)\\.target\\s*(?:!==|!=)\\s*" + h + "\\b").exec(cond);
  if (m) return { obj: m[1], rhs: m[1] + ".target" };
  m = new RegExp(h + "\\s*(?:!==|!=)\\s*((\\w+)\\[['\"]target['\"]\\])").exec(cond);
  if (m) return { obj: m[2], rhs: m[1] };
  m = new RegExp(h + "\\s*,\\s*" + DEC, "i").exec(cond);
  if (m) return { obj: m[1], rhs: decRHS(m) };
  m = new RegExp(DEC + "\\s*,\\s*" + h + "\\b", "i").exec(cond);
  if (m) return { obj: m[1], rhs: decRHS(m) };
  m = new RegExp(h + "\\s*,\\s*(\\w+)\\.target\\b").exec(cond);
  if (m) return { obj: m[1], rhs: m[1] + ".target" };
  m = new RegExp("(\\w+)\\.target\\s*,\\s*" + h + "\\b").exec(cond);
  if (m) return { obj: m[1], rhs: m[1] + ".target" };
  const valRe = new RegExp(DEC + "(?!\\s*\\()", "gi");
  while ((m = valRe.exec(cond))) {
    if (m[1] !== hash) return { obj: m[1], rhs: decRHS(m) };
  }
  return null;
}

function patchAsyncWhile(code) {
  const m = HASH_LOOP_HEAD.exec(code);
  if (!m) return { code, hit: false };
  const nonce = m[1];
  const hash = m[2];
  if (code.indexOf("if(globalThis.__powHookCount){" + nonce + "=") !== -1) {
    return { code, hit: true };
  }
  const cond = code.slice(m.index + m[0].length, m.index + m[0].length + 280);
  const tgt = findWhileTarget(hash, cond);
  let body = nonce + "=globalThis.__powHookCount();";
  if (tgt) {
    body =
      nonce +
      "=globalThis.__powHookCount(" +
      tgt.obj +
      ".target);" +
      hash +
      "=" +
      tgt.rhs +
      ";";
  }
  const insert =
    m[0].replace(/while\s*\($/, "") +
    "if(globalThis.__powHookCount){" +
    body +
    "}while(!globalThis.__powHookCount&&";
  return { code: code.replace(m[0], insert), hit: true };
}

function patchSequence(code) {
  const sites = [];
  for (const h of HOOKS) {
    if (code.indexOf(h.from) !== -1) {
      code = code.replace(h.from, h.to);
      sites.push(h.name);
    }
  }
  const aw = patchAsyncWhile(code);
  if (aw.hit) {
    code = aw.code;
    sites.push("async-while-sha512");
  }
  return { code, sites };
}

function createSplits(encoded, n) {
  const size = Math.ceil(encoded.length / n);
  const out = [];
  for (let i = 0; i < n; i++) out.push(encoded.substr(i * size, size));
  return out;
}

function startData(input) {
  const itimeout = Number(input.timeout) > 0 ? Number(input.timeout) : 30000;
  const sd = {
    seed: input.seed,
    startingNonce: input.starting_nonce || 0,
    itimeout: itimeout,
  };
  if (input.splits) {
    sd.targetHashData = input.splits.map((s) => ({ targetHashData: s.target_hash }));
  }
  if (input.count !== undefined && input.count !== null) {
    sd.count = input.count;
    sd.difficulty = input.count;
  }
  return { sd, itimeout };
}

function makeSandbox() {
  const sandbox = {};
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.window = undefined;
  sandbox.onmessage = null;
  sandbox._done = null;
  sandbox._errored = null;
  sandbox.postMessage = function (msg) {
    if (!msg || !msg.type) return;
    if (msg.type === "loaded") sandbox._loaded = true;
    else if (msg.type === "done") sandbox._done = msg.data;
    else if (msg.type === "error") sandbox._errored = msg.data;
  };
  const _btoa = typeof btoa !== "undefined" ? btoa : (s) => Buffer.from(s, "binary").toString("base64");
  sandbox.btoa = function (s) {
    const out = _btoa(s);
    if (process.env.POW_DEBUG) console.error("[btoa] in_len=" + s.length + " out_head=" + out.slice(0, 80));
    return out;
  };
  sandbox.atob = typeof atob !== "undefined" ? atob : (s) => Buffer.from(s, "base64").toString("binary");
  sandbox.console = console;
  sandbox.performance = typeof performance !== "undefined" ? performance : { now: () => Date.now() };
  sandbox.setTimeout = setTimeout;
  sandbox.clearTimeout = clearTimeout;
  sandbox.setInterval = setInterval;
  sandbox.clearInterval = clearInterval;
  sandbox.Date = Date;
  sandbox.Math = Math;
  sandbox.JSON = JSON;
  sandbox.TextEncoder = TextEncoder;
  sandbox.TextDecoder = TextDecoder;
  try {
    const _c = require("crypto");
    sandbox.crypto = _c.webcrypto || _c;
  } catch (e) {
    sandbox.crypto = typeof crypto !== "undefined" ? crypto : undefined;
  }
  sandbox.importScripts = function () {};
  sandbox.location = { protocol: "https:", host: "arks-client.adobe.com", href: "https://arks-client.adobe.com/" };
  sandbox.addEventListener = function (type, fn) {
    if (type === "message") sandbox.onmessage = fn;
  };
  sandbox.removeEventListener = function () {};
  return sandbox;
}

function loadSequence(seqPath) {
  const raw = fs.readFileSync(seqPath, "utf8");
  const { code, sites } = patchSequence(raw);
  const sandbox = makeSandbox();
  const context = vm.createContext(sandbox);
  try {
    vm.runInContext(code, context, { filename: "sequence.js", timeout: 30000 });
  } catch (e) {
    console.error("sequence load error: " + ((e && e.stack) || e));
    process.exit(3);
  }
  if (typeof sandbox.onmessage !== "function") {
    console.error("onmessage not set after load (loaded=" + !!sandbox._loaded + ")");
    process.exit(4);
  }
  return { sandbox, hookPatched: sites.length > 0, hookSites: sites };
}

function installHook(sandbox, input) {
  if (!input.hook_counts || !input.hook_targets) return;
  const counts = input.hook_counts;
  const targets = input.hook_targets;
  const map = {};
  for (let i = 0; i < targets.length; i++) map[String(targets[i])] = counts[i];
  let seqIdx = 0;
  sandbox.__powHookCount = function (targetHash) {
    if (targetHash != null && targetHash !== "") {
      const k = String(targetHash);
      if (Object.prototype.hasOwnProperty.call(map, k)) return map[k];
    }
    if (seqIdx < counts.length) return counts[seqIdx++];
    return counts[counts.length - 1];
  };
}

async function solveGpu(seqPath, input) {
  const { sandbox, hookPatched, hookSites } = loadSequence(seqPath);
  let encoded = null;
  const origBtoa = sandbox.btoa;
  sandbox.btoa = function (s) {
    const out = origBtoa(s);
    if (!encoded && out && out.length > 16) {
      try {
        const buf = Buffer.from(out, "base64");
        const js = buf.toString("utf16le");
        const parsed = JSON.parse(js);
        if (Array.isArray(parsed)) {
          encoded = out;
          throw new Error(SENTINEL);
        }
      } catch (e) {
        if (e && e.message === SENTINEL) throw e;
      }
    }
    return out;
  };
  const { sd } = startData(input);
  const startMsg = { data: { type: "start", data: sd } };
  let run;
  try {
    run = Promise.resolve(sandbox.onmessage(startMsg));
  } catch (e) {
    if (!(e && e.message === SENTINEL)) throw e;
    run = Promise.resolve();
  }
  run = run.catch((e) => {
    if (!(e && e.message === SENTINEL)) throw e;
  });
  const deadline = Date.now() + 20000;
  while (!encoded && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 10));
  }
  await Promise.race([run, new Promise((r) => setTimeout(r, 50))]);
  if (!encoded) {
    console.error("gpu mode: encoded not captured");
    process.exit(8);
  }
  const n = Array.isArray(input.splits) ? input.splits.length : 0;
  const out = { encoded: encoded, hook_patched: hookPatched, hook_site: hookSites.join(",") };
  if (n > 0) out.pieces = createSplits(encoded, n);
  return out;
}

function emitDone(d) {
  const out = {
    transform: d.finalTransform,
    result: (d.targetHashData || []).map((t) => ({ target_hash: t.targetHash, attempt_count: t.iterations })),
    hash_rate: d.hashRate,
    execution_time: d.time,
  };
  if (!d.targetHashData && d.nonce !== undefined && d.nonce !== null) {
    out.result = { result: d.nonce, iteration_count: d.iterations };
  }
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
}

async function solveFull(seqPath, input) {
  const { sandbox } = loadSequence(seqPath);
  installHook(sandbox, input);
  const { sd, itimeout } = startData(input);
  const startMsg = { data: { type: "start", data: sd } };
  await Promise.resolve(sandbox.onmessage(startMsg));
  const deadline = Date.now() + itimeout + 5000;
  while (!sandbox._done) {
    if (sandbox._errored) {
      console.error("worker error: " + JSON.stringify(sandbox._errored));
      process.exit(6);
    }
    if (Date.now() > deadline) {
      console.error("timeout waiting for done");
      process.exit(7);
    }
    await new Promise((r) => setTimeout(r, 20));
  }
  emitDone(sandbox._done);
}

async function main() {
  const seqPath = process.argv[2];
  if (!seqPath) {
    console.error("usage: node pow_runner.js <sequence.js>");
    process.exit(2);
  }
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  if (input.gpu_mode) {
    const out = await solveGpu(seqPath, input);
    process.stdout.write(JSON.stringify(out));
    process.exit(0);
  }
  await solveFull(seqPath, input);
}

if (require.main === module) {
  main().catch((e) => {
    console.error("onmessage error: " + ((e && e.stack) || e));
    process.exit(5);
  });
}

module.exports = { patchAsyncWhile, patchSequence, findWhileTarget };
