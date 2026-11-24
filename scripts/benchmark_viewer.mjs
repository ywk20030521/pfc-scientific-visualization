import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { spawn } from "node:child_process";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(fn, timeout = 60000, interval = 100) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const value = await fn();
      if (value) return value;
    } catch {}
    await sleep(interval);
  }
  throw new Error("Timed out waiting for benchmark page");
}

function findBrowser(explicit) {
  return [
    explicit,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium"
  ].filter(Boolean).find((item) => fs.existsSync(item));
}

async function main() {
  const args = process.argv.slice(2);
  let file = "";
  let reportPath = "";
  let label = "viewer";
  let playSeconds = 8;
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--file") file = args[++index];
    else if (args[index] === "--report") reportPath = args[++index];
    else if (args[index] === "--label") label = args[++index];
    else if (args[index] === "--seconds") playSeconds = Number(args[++index]);
  }
  if (!file) throw new Error("--file is required");
  const browser = findBrowser(process.env.PFC_BROWSER);
  if (!browser) throw new Error("No Chromium/Edge browser found");
  const viewer = path.resolve(file);
  const stat = fs.statSync(viewer);
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "pfc-benchmark-"));
  const port = 9345;
  const child = spawn(browser, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    "--remote-debugging-address=127.0.0.1",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--no-sandbox",
    "--disable-gpu-sandbox",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--allow-file-access-from-files",
    "--window-size=1600,1000",
    "about:blank"
  ], { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });
  let ws;
  try {
    await waitFor(async () => {
      try { return (await fetch(`http://127.0.0.1:${port}/json/version`)).ok; } catch { return false; }
    }, 15000);
    const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    const page = targets.find((target) => target.type === "page");
    ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      ws.addEventListener("open", resolve, { once: true });
      ws.addEventListener("error", reject, { once: true });
    });
    let sequence = 0;
    const pending = new Map();
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && pending.has(message.id)) {
        const entry = pending.get(message.id);
        pending.delete(message.id);
        if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
        else entry.resolve(message.result);
      }
    });
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const id = ++sequence;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async (expression) => {
      const result = await send("Runtime.evaluate", {
        expression, returnByValue: true, awaitPromise: true
      });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Evaluation failed");
      return result.result.value;
    };
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Performance.enable");
    await send("HeapProfiler.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    const navigationStarted = Date.now();
    await send("Page.navigate", { url: pathToFileURL(viewer).href });
    await waitFor(() => evaluate('document.body && document.body.getAttribute("data-ready") === "1"'), 90000);
    const readyMs = Date.now() - navigationStarted;
    await sleep(800);
    const initial = await evaluate(`({
      loadMs: Number(document.body.dataset.loadMs || 0),
      frameIndex: Number(document.body.dataset.frameIndex || 0),
      frameBallCount: Number(document.body.dataset.frameBallCount || 0),
      fps: Number(document.body.dataset.fps || 0),
      drawCalls: Number(document.body.dataset.drawCalls || 0),
      geometries: Number(document.body.dataset.geometries || 0),
      loadedChunks: Number(document.body.dataset.loadedChunkCount || 0),
      memory: performance.memory ? performance.memory.usedJSHeapSize : null,
      error: document.body.dataset.error || ""
    })`);

    const playButtonId = await evaluate(
      'document.getElementById("playButton") ? "playButton" : "play"'
    );
    const speedId = await evaluate(
      'document.getElementById("playbackSpeed") ? "playbackSpeed" : "speed"'
    );
    await evaluate(`(() => {
      const speed = document.getElementById("${speedId}");
      if (speed) { speed.value = speed.options[speed.options.length - 1].value; speed.dispatchEvent(new Event("change", {bubbles:true})); }
      document.getElementById("${playButtonId}").click();
    })()`);
    const samples = [];
    const started = Date.now();
    let peak = initial.memory || 0;
    while (Date.now() - started < playSeconds * 1000) {
      await sleep(250);
      const sample = await evaluate(`({
        memory: performance.memory ? performance.memory.usedJSHeapSize : null,
        frameIndex: Number(document.body.dataset.frameIndex || 0),
        fps: Number(document.body.dataset.fps || 0),
        drawCalls: Number(document.body.dataset.drawCalls || 0),
        geometries: Number(document.body.dataset.geometries || 0),
        loadedChunks: Number(document.body.dataset.loadedChunkCount || 0)
      })`);
      samples.push(sample);
      if (sample.memory) peak = Math.max(peak, sample.memory);
    }
    await evaluate(`document.getElementById("${playButtonId}").click()`);
    await sleep(500);
    await send("HeapProfiler.collectGarbage");
    await sleep(500);
    const final = await evaluate(`({
      memory: performance.memory ? performance.memory.usedJSHeapSize : null,
      frameIndex: Number(document.body.dataset.frameIndex || 0),
      fps: Number(document.body.dataset.fps || 0),
      drawCalls: Number(document.body.dataset.drawCalls || 0),
      geometries: Number(document.body.dataset.geometries || 0),
      loadedChunks: Number(document.body.dataset.loadedChunkCount || 0)
    })`);
    const fpsSamples = samples.map((item) => item.fps).filter((value) => value > 0);
    const result = {
      label,
      viewer,
      fileBytes: stat.size,
      readyMs,
      initial,
      playbackSeconds: playSeconds,
      peakJsHeapBytes: peak,
      finalJsHeapBytes: final.memory,
      heapRetentionRatio: initial.memory && final.memory ? final.memory / initial.memory : null,
      medianFps: fpsSamples.length ? [...fpsSamples].sort((a, b) => a - b)[Math.floor(fpsSamples.length / 2)] : null,
      maxLoadedChunks: Math.max(initial.loadedChunks, ...samples.map((item) => item.loadedChunks), 0),
      maxDrawCalls: Math.max(initial.drawCalls, ...samples.map((item) => item.drawCalls), 0),
      maxGeometries: Math.max(initial.geometries, ...samples.map((item) => item.geometries), 0),
      final,
      samples,
      status: initial.error ? "FAIL" : "GENERATED"
    };
    const text = JSON.stringify(result, null, 2);
    console.log(text);
    if (reportPath) {
      fs.mkdirSync(path.dirname(path.resolve(reportPath)), { recursive: true });
      fs.writeFileSync(reportPath, text + "\n", "utf8");
    }
    return initial.error ? 1 : 0;
  } finally {
    if (ws) try { ws.close(); } catch {}
    child.kill();
    await sleep(250);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
