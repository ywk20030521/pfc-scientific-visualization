// DEPRECATED (2026-11-22): this script targets the retired single-file viewer
// schema (`window.PFC_DATA`).  Current viewers expose `window.PFC_VIEWER_DATA`
// with catalog/static/caseMeta structure.  Use verify_lazy_viewer.mjs for
// acceptance; it exercises the current payload contract and also exports
// real SVG/PNG publication assets.  Kept only for historical comparison.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { spawn } from "node:child_process";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(fn, timeout = 20000, interval = 100) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    const value = await fn();
    if (value) return value;
    await sleep(interval);
  }
  throw new Error("Timed out waiting for browser condition");
}

function findBrowser(explicit) {
  const candidates = [
    explicit,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  ].filter(Boolean);
  const found = candidates.find((item) => fs.existsSync(item));
  if (!found) throw new Error("No Chromium/Edge browser found");
  return found;
}

async function main() {
  const args = process.argv.slice(2);
  let file = "";
  let screenshot = "";
  let reportPath = "";
  let browserPath = process.env.PFC_BROWSER || "";
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--file") file = args[++i];
    else if (args[i] === "--screenshot") screenshot = args[++i];
    else if (args[i] === "--report") reportPath = args[++i];
    else if (args[i] === "--browser") browserPath = args[++i];
    else throw new Error("Unknown argument: " + args[i]);
  }
  if (!file) throw new Error("--file is required");
  const viewer = path.resolve(file);
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "pfc-live-viewer-"));
  const browser = findBrowser(browserPath);
  const port = 9341;
  const child = spawn(browser, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--remote-debugging-address=127.0.0.1",
    `--user-data-dir=${profileDir}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--no-sandbox",
    "--disable-gpu-sandbox",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--window-size=1600,1000",
    "about:blank"
  ], { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });

  let stderr = "";
  child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  let ws;
  try {
    await waitFor(async () => {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/json/version`);
        return response.ok;
      } catch {
        return false;
      }
    }, 15000);
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const page = targets.find((target) => target.type === "page");
    if (!page) throw new Error("No page target");
    ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", reject, { once: true });
    });

    let seq = 0;
    const pending = new Map();
    const pageErrors = [];
    const externalRequests = [];
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && pending.has(message.id)) {
        const entry = pending.get(message.id);
        pending.delete(message.id);
        if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
        else entry.resolve(message.result);
        return;
      }
      if (message.method === "Network.requestWillBeSent") {
        const url = String(message.params.request.url || "");
        if (!/^(file|data|blob|about):/i.test(url)) externalRequests.push(url);
      }
      if (message.method === "Runtime.exceptionThrown") {
        pageErrors.push("exception: " + message.params.exceptionDetails.text);
      }
      if (message.method === "Runtime.consoleAPICalled" &&
          message.params.type === "error") {
        pageErrors.push("console error");
      }
    });
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++seq;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async (expression) => {
      const result = await send("Runtime.evaluate", {
        expression, returnByValue: true, awaitPromise: true
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.text || "Evaluation failed");
      }
      return result.result.value;
    };
    const capture = async (target) => {
      if (!target) return;
      const result = await send("Page.captureScreenshot", {
        format: "png", fromSurface: true
      });
      fs.mkdirSync(path.dirname(path.resolve(target)), { recursive: true });
      fs.writeFileSync(target, Buffer.from(result.data, "base64"));
    };

    await send("Page.enable");
    await send("Network.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    await send("Page.navigate", { url: pathToFileURL(viewer).href });
    await waitFor(() => evaluate(
      'document.body && document.body.getAttribute("data-ready") === "1"'
    ), 30000);
    await sleep(800);

    // Expected values come from the embedded data, never from constants.
    const expected = await evaluate(`(() => {
      const D = window.PFC_DATA;
      return {
        defaultCase: D.meta.defaultCase,
        staticBalls: D.static.balls.length,
        cases: D.cases.map((c) => {
          const first = c.frames[0], last = c.frames[c.frames.length - 1];
          return {
            id: c.id,
            frames: c.frames.length,
            firstCycle: first.cycle, firstBalls: first.ballCount,
            lastCycle: last.cycle, lastBalls: last.ballCount,
            lastMissing: D.static.balls.length - last.ballCount,
            cracksAvailable: c.cracksAvailable,
            lastCracks: c.cracks.filter((r) => r[6] <= last.cycle).length
          };
        })
      };
    })()`);
    const defaultExpected = expected.cases.find((c) => c.id === expected.defaultCase) || expected.cases[0];
    const initial = await evaluate(`({
      ready: document.body.getAttribute("data-ready"),
      error: document.body.getAttribute("data-error"),
      caseId: Number(document.body.getAttribute("data-case-id")),
      frameIndex: Number(document.body.getAttribute("data-frame-index")),
      frameCount: Number(document.body.getAttribute("data-frame-count")),
      cycle: Number(document.body.getAttribute("data-cycle")),
      ballCount: Number(document.body.getAttribute("data-frame-ball-count")),
      missing: Number(document.body.getAttribute("data-missing-ball-count")),
      cracks: Number(document.body.getAttribute("data-cracks-visible")),
      crackChannel: document.body.getAttribute("data-crack-channel"),
      charts: document.querySelectorAll(".echart canvas").length,
      externalScripts: document.querySelectorAll("script[src]").length,
      externalLinks: document.querySelectorAll("link[href]").length,
      viewport: [innerWidth, innerHeight]
    })`);
    await capture(screenshot ? screenshot.replace(/\.png$/i, "-start.png") : "");

    const frames = defaultExpected.frames;
    const midIndex = frames >= 3 ? Math.floor((frames - 1) / 2) : Math.min(1, frames - 1);
    const setSlider = (value) => evaluate(`(() => {
      const slider = document.getElementById("timeline");
      slider.value = String(${value});
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    })()`);
    const frameIs = (n) => waitFor(() => evaluate(
      `document.body.getAttribute("data-frame-index") === "${n}"`
    ));
    const readFrame = () => evaluate(`({
      frameIndex: Number(document.body.getAttribute("data-frame-index")),
      cycle: Number(document.body.getAttribute("data-cycle")),
      ballCount: Number(document.body.getAttribute("data-frame-ball-count")),
      cracks: Number(document.body.getAttribute("data-cracks-visible"))
    })`);

    await setSlider(midIndex);
    await frameIs(midIndex);
    const middle = await readFrame();

    let next = middle, prev = middle, playback = middle;
    const canStep = midIndex + 1 <= frames - 1;
    if (canStep) {
      await evaluate('document.getElementById("next").click()');
      await frameIs(midIndex + 1);
      next = await readFrame();
      await evaluate('document.getElementById("prev").click()');
      await frameIs(midIndex);
      prev = await readFrame();
      await evaluate('document.getElementById("play").click()');
      try {
        await waitFor(() => evaluate(
          `Number(document.body.getAttribute("data-frame-index")) > ${midIndex}`
        ), 8000);
      } catch {}
      await evaluate('document.getElementById("play").textContent.includes("暂停") && document.getElementById("play").click()');
      playback = await readFrame();
    }

    // Visit every case: crack channel flag and the exact final real state.
    const perCase = [];
    for (const exp of expected.cases) {
      await evaluate(`(() => {
        const sel = document.getElementById("caseSelect");
        const idx = window.PFC_DATA.cases.findIndex((c) => c.id === ${exp.id});
        sel.value = String(idx);
        sel.dispatchEvent(new Event("change", { bubbles: true }));
      })()`);
      await waitFor(() => evaluate(
        `document.body.getAttribute("data-case-id") === "${exp.id}"`
      ));
      await setSlider(exp.frames - 1);
      await frameIs(exp.frames - 1);
      const state = await evaluate(`({
        caseId: Number(document.body.getAttribute("data-case-id")),
        frameCount: Number(document.body.getAttribute("data-frame-count")),
        cycle: Number(document.body.getAttribute("data-cycle")),
        ballCount: Number(document.body.getAttribute("data-frame-ball-count")),
        missing: Number(document.body.getAttribute("data-missing-ball-count")),
        cracks: Number(document.body.getAttribute("data-cracks-visible")),
        crackChannel: document.body.getAttribute("data-crack-channel"),
        crackText: document.getElementById("cracks").textContent
      })`);
      perCase.push({ expected: exp, state });
      if (exp.id === expected.defaultCase) {
        await capture(screenshot ? screenshot.replace(/\.png$/i, "-final.png") : "");
      }
    }

    await send("Emulation.setDeviceMetricsOverride", {
      width: 820, height: 1100, deviceScaleFactor: 1, mobile: false
    });
    await sleep(800);
    const narrow = await evaluate(`({
      overflowX: document.documentElement.scrollWidth - innerWidth,
      charts: document.querySelectorAll(".echart canvas").length,
      ready: document.body.getAttribute("data-ready")
    })`);
    await capture(screenshot ? screenshot.replace(/\.png$/i, "-narrow.png") : "");

    const failures = [];
    if (initial.ready !== "1" || initial.error) failures.push("viewer not ready");
    if (initial.caseId !== defaultExpected.id || initial.frameCount !== defaultExpected.frames) failures.push("default case frame set differs from embedded data");
    if (initial.cycle !== defaultExpected.firstCycle || initial.ballCount !== defaultExpected.firstBalls) failures.push("initial state differs from embedded data");
    if (initial.missing !== expected.staticBalls - defaultExpected.firstBalls) failures.push("initial missing-Ball count is wrong");
    if (initial.charts < 2) failures.push("expected two ECharts canvases");
    if (initial.externalScripts || initial.externalLinks) failures.push("external assets found");
    if (externalRequests.length) failures.push("external network requests found");
    if (frames >= 3 && !(middle.frameIndex === midIndex && middle.cycle > initial.cycle)) failures.push("middle timeline did not select a real later frame");
    if (canStep) {
      if (next.frameIndex !== midIndex + 1 || next.cycle <= middle.cycle) failures.push("next frame did not advance");
      if (prev.frameIndex !== midIndex || prev.cycle !== middle.cycle) failures.push("previous frame did not restore exact state");
      if (playback.frameIndex <= midIndex) failures.push("playback did not advance");
    }
    for (const { expected: exp, state } of perCase) {
      const tag = "Case " + exp.id;
      if (state.frameCount !== exp.frames) failures.push(tag + " frame count differs from data");
      if (state.cycle !== exp.lastCycle || state.ballCount !== exp.lastBalls) failures.push(tag + " final real state is wrong");
      if (state.missing !== exp.lastMissing) failures.push(tag + " final missing-Ball count is wrong");
      if (exp.cracksAvailable) {
        if (state.crackChannel !== "available" || state.cracks !== exp.lastCracks) failures.push(tag + " final crack count is wrong");
      } else if (state.crackChannel !== "missing" || state.crackText !== "未采集") {
        failures.push(tag + " missing crack channel is not explicit");
      }
    }
    if (narrow.overflowX > 1 || narrow.charts < 2) failures.push("narrow layout failed");
    if (pageErrors.length) failures.push(...pageErrors);

    const report = {
      pass: failures.length === 0,
      failures,
      browser,
      initial,
      middle,
      next,
      prev,
      playback,
      expected,
      perCase,
      narrow,
      externalRequests,
      pageErrors
    };
    const text = JSON.stringify(report, null, 2);
    console.log(text);
    if (reportPath) {
      fs.mkdirSync(path.dirname(path.resolve(reportPath)), { recursive: true });
      fs.writeFileSync(reportPath, text + "\n", "utf8");
    }
    return failures.length ? 1 : 0;
  } finally {
    if (ws) {
      try { ws.close(); } catch {}
    }
    child.kill();
    await sleep(200);
    try {
      fs.rmSync(profileDir, { recursive: true, force: true });
    } catch {}
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
