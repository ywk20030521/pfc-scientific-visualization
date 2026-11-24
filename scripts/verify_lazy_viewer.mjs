import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { spawn } from "node:child_process";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function pngDimensions(buffer) {
  if (buffer.length < 24 || buffer.toString("ascii", 1, 4) !== "PNG") return null;
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  };
}

async function waitFor(fn, timeout = 30000, interval = 100) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeout) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(interval);
  }
  throw lastError || new Error("Timed out waiting for browser condition");
}

function findBrowser(explicit) {
  const candidates = [
    explicit,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
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
  let exportDir = "";
  let browserPath = process.env.PFC_BROWSER || "";
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--file") file = args[++index];
    else if (args[index] === "--screenshot") screenshot = args[++index];
    else if (args[index] === "--report") reportPath = args[++index];
    else if (args[index] === "--export-dir") exportDir = args[++index];
    else if (args[index] === "--browser") browserPath = args[++index];
    else throw new Error("Unknown argument: " + args[index]);
  }
  if (!file) throw new Error("--file is required");
  const viewer = path.resolve(file);
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "pfc-lazy-viewer-"));
  const browser = findBrowser(browserPath);
  const port = 9343;
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
    "--allow-file-access-from-files",
    "--window-size=1600,1000",
    "about:blank"
  ], { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });

  let stderr = "";
  child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  let ws;
  const downloadRecords = new Map();
  try {
    await waitFor(async () => {
      try {
        return (await fetch(`http://127.0.0.1:${port}/json/version`)).ok;
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

    let sequence = 0;
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
      if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
        pageErrors.push("console error");
      }
      if (message.method === "Browser.downloadWillBegin") {
        const guid = message.params.guid;
        downloadRecords.set(guid, {
          guid,
          suggestedFilename: message.params.suggestedFilename,
          state: "started",
          receivedBytes: 0,
          totalBytes: 0
        });
      }
      if (message.method === "Browser.downloadProgress") {
        const guid = message.params.guid;
        const prior = downloadRecords.get(guid) || { guid };
        downloadRecords.set(guid, {
          ...prior,
          ...message.params,
          guid
        });
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
    const mouse = async (type, x, y, buttons = 1) => {
      await send("Input.dispatchMouseEvent", {
        type, x, y, button: type === "mouseMoved" ? "none" : "left", buttons,
        clickCount: type === "mousePressed" || type === "mouseReleased" ? 1 : 0
      });
    };
    const capture = async (target) => {
      if (!target) return;
      const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
      fs.mkdirSync(path.dirname(path.resolve(target)), { recursive: true });
      fs.writeFileSync(target, Buffer.from(result.data, "base64"));
    };

    await send("Page.enable");
    await send("Network.enable");
    await send("Runtime.enable");
    await send("Performance.enable");
    const downloadDir = exportDir
      ? path.resolve(exportDir)
      : path.join(profileDir, "downloads");
    fs.mkdirSync(downloadDir, { recursive: true });
    await send("Browser.setDownloadBehavior", {
      behavior: "allow",
      downloadPath: downloadDir,
      eventsEnabled: true
    });
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    await send("Page.navigate", { url: pathToFileURL(viewer).href });
    try {
      await waitFor(() => evaluate(
        'document.body && document.body.getAttribute("data-ready") === "1" && document.body.getAttribute("data-case-ready") === "1"'
      ), 45000);
    } catch (error) {
      console.error(JSON.stringify(await evaluate(`({
        url: location.href,
        body: document.body ? document.body.dataset : {},
        data: Boolean(window.PFC_VIEWER_DATA),
        catalog: Boolean(window.PFC_VIEWER_DATA && window.PFC_VIEWER_DATA.catalog),
        static: Boolean(window.PFC_VIEWER_DATA && window.PFC_VIEWER_DATA.static),
        viewer: Boolean(window.PFCViewer),
        error: document.getElementById("errorBox") ? document.getElementById("errorBox").textContent : "",
        scripts: [...document.scripts].map((node) => node.src || "inline")
      })`), null, 2));
      throw error;
    }
    await sleep(1200);

    const expected = await evaluate(`(() => {
      const D = window.PFC_VIEWER_DATA;
      const c = D.catalog.cases.find((item) => item.id === D.catalog.meta.defaultCase);
      const meta = D.caseMeta[c.id];
      const caseStatic = D.static.cases[String(c.id)];
      return {
        defaultCase: D.catalog.meta.defaultCase,
        caseCount: D.catalog.cases.length,
        frames: c.viewerFrameCount,
        sourceFrames: c.sourceFrameCount,
        frameStatus: c.frameStatus,
        charts: c.chartCount,
        firstBallId: caseStatic.balls[0][0],
        ballIds: caseStatic.balls.map((b) => String(b[0])),
        maxDisplacement: c.maxDisplacement,
        frameSources: meta.frames.map((item) => item.sourceIndex),
        frameCycles: meta.frames.map((item) => item.cycle)
      };
    })()`);
    const parseCsvNumbers = (text) => String(text || "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length)
      .map((item) => Number(item));
    const viewerIndexBySource = new Map(
      expected.frameSources.map((sourceIndex, viewerIndex) => [sourceIndex, viewerIndex])
    );
    // A ball is not required to exist in every Viewer frame.  The standardized
    // contract preserves dynamic entity ID sets; therefore Ball history may be
    // a strict subset of frames.  Verify the mapping of every reported row
    // instead of demanding a fabricated full-length history.
    const checkBallHistory = (snapshot, label) => {
      const sources = parseCsvNumbers(snapshot.historySourceFrameIndices);
      const viewers = parseCsvNumbers(snapshot.historyViewerFrameIndices);
      const cycles = parseCsvNumbers(snapshot.historyCycleValues);
      const failures = [];
      if (sources.length < 1) failures.push(label + ": Ball history has no rows");
      if (snapshot.historyPointCount !== sources.length) failures.push(label + ": history point count does not match source indices");
      if (viewers.length !== sources.length) failures.push(label + ": history viewer-frame index count does not match rows");
      if (cycles.length !== sources.length) failures.push(label + ": history Cycle coordinate count does not match rows");
      let previous = -1;
      sources.forEach((sourceIndex, position) => {
        const viewerIndex = viewerIndexBySource.get(sourceIndex);
        if (viewerIndex === undefined) {
          failures.push(label + ": history references a source frame absent from Viewer metadata");
          return;
        }
        if (sourceIndex <= previous) failures.push(label + ": history source frames are not strictly increasing");
        previous = sourceIndex;
        if (viewers[position] !== viewerIndex) failures.push(label + ": history viewer-frame mapping is wrong");
        if (Math.abs(cycles[position] - expected.frameCycles[viewerIndex]) > 1e-9) {
          failures.push(label + ": history Cycle coordinates are wrong");
        }
      });
      return {
        rows: sources.length,
        frames: expected.frames,
        coverage: expected.frames ? sources.length / expected.frames : 0,
        dynamicEntitySet: sources.length < expected.frames,
        failures
      };
    };
    const read = () => evaluate(`({
      ready: document.body.dataset.ready,
      error: document.body.dataset.error || "",
      caseId: Number(document.body.dataset.caseId),
      frameIndex: Number(document.body.dataset.frameIndex),
      cycle: Number(document.body.dataset.cycle),
      frameCount: window.PFCViewer.state.get().currentCase == null ? 0 : window.PFC_VIEWER_DATA.caseMeta[window.PFCViewer.state.get().currentCase].viewerFrameCount,
      ballCount: Number(document.body.dataset.frameBallCount),
      missing: Number(document.body.dataset.missingBallCount),
      dynamicAdded: Number(document.body.dataset.dynamicAddedBallCount || 0),
      chartCount: Number(document.body.dataset.chartCount),
      linkedCharts: Number(document.body.dataset.linkedChartCount),
      selectedBalls: document.body.dataset.selectedBallIds || "",
      selectedRange: document.body.dataset.selectedRange || "",
      highlightCount: Number(document.body.dataset.highlightCount),
      historyVisible: document.body.dataset.historyVisible,
      historyPointCount: Number(document.body.dataset.historyPointCount || 0),
      historySourceFrameIndices: document.body.dataset.historySourceFrameIndices || "",
      historyViewerFrameIndices: document.body.dataset.historyViewerFrameIndices || "",
      historyCycleValues: document.body.dataset.historyCycleValues || "",
      historyCursorVisible: (() => {
        const cursor = document.querySelector("#historyPanel .time-cursor");
        return Boolean(cursor) && !cursor.hidden;
      })(),
      chunkIndex: Number(document.body.dataset.chunkIndex),
      loadedChunks: Number(document.body.dataset.loadedChunkCount),
      payloadVersion: document.body.dataset.payloadVersion,
      externalScripts: [...document.querySelectorAll("script[src]")].map((node) => node.src).filter((url) => !url.startsWith("file:")),
      externalLinks: [...document.querySelectorAll("link[href]")].map((node) => node.href).filter((url) => !url.startsWith("file:"))
    })`);

    const initial = await read();
    const missingValueProbe = await evaluate(`(() => ({
      nullNumber: window.PFCViewer.formatting.number(null),
      undefinedNumber: window.PFCViewer.formatting.number(undefined),
      nanNumber: window.PFCViewer.formatting.number(NaN),
      emptyNumber: window.PFCViewer.formatting.number(""),
      invalidNumber: window.PFCViewer.formatting.number("not-a-number"),
      zeroNumber: window.PFCViewer.formatting.number(0),
      validNumber: window.PFCViewer.formatting.number(12.5),
      nullMetric: window.PFCViewer.formatting.metric(null, "m"),
      zeroMetric: window.PFCViewer.formatting.metric(0, "m"),
      nullTooltip: window.PFCViewer.formatting.tooltip(null, {}),
      stressAtFirstFrame: document.getElementById("metricStress").textContent,
      speedSpecFirstY: (() => {
        const caseId = window.PFCViewer.state.get().currentCase;
        const spec = (window.PFC_VIEWER_DATA.caseCharts[caseId] || [])
          .find((item) => item.id === "case_" + caseId + ":speed_time");
        return spec && spec.y && spec.y.data ? spec.y.data[0] : "MISSING_SPEC";
      })(),
      speedChartFirstY: (() => {
        const panels = [...document.querySelectorAll("#chartGrid .chart-panel")];
        const panel = panels.find((item) => item.querySelector("h3")?.textContent === "平均速度–机械时间");
        if (!panel) return "MISSING_PANEL";
        const chart = echarts.getInstanceByDom(panel.querySelector(".chart"));
        return chart?.getOption()?.series?.[0]?.data?.[0]?.[1] ?? null;
      })()
    }))()`);
    const frameIndexProbe = await evaluate(`(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const meta = window.PFC_VIEWER_DATA.caseMeta[caseId];
      const specs = window.PFC_VIEWER_DATA.caseCharts[caseId] || [];
      const temporal = specs.filter((spec) =>
        Array.isArray(spec.source_indices) &&
        spec.x && ["s", "cycle"].includes(spec.x.unit)
      ).map((spec) => {
        const expectedX = spec.x.unit === "s"
          ? meta.frames.map((frame) => frame.time)
          : meta.frames.map((frame) => frame.cycle);
        return {
          id: spec.id,
          sourceIndices: spec.source_indices,
          pointCount: spec.x.data.length,
          xMatchesFrames: JSON.stringify(spec.x.data) === JSON.stringify(expectedX),
          yLength: spec.y ? spec.y.data.length : null,
          seriesLengths: (spec.series || []).map((item) => item.data.length)
        };
      });
      return {
        frameSourceIndices: meta.frames.map((frame) => frame.sourceIndex),
        temporal
      };
    })()`);
    await evaluate("window.PFCViewer.setFrame(1)");
    // Accept any rendered metric state: a real value with a unit, or a
    // declared-missing label.  The original hardcode ("0 MPa") assumed every
    // case has a zero stress at frame 1, which is false for most cases.
    const metricRendered = `(() => {
      const el = document.getElementById("metricStress");
      const t = (el && el.textContent || "").trim();
      return t.length > 0 && !/NaN|Infinity|undefined/.test(t);
    })()`;
    await waitFor(() => evaluate(
      `Number(document.body.dataset.frameIndex) === 1 && ${metricRendered}`
    ), 30000);
    const zeroValueFrame = await evaluate(`({
      stress: document.getElementById("metricStress").textContent,
      load: document.getElementById("metricLoad").textContent
    })`);
    await capture(screenshot ? screenshot.replace(/\.png$/i, "-initial.png") : "");
    const middleIndex = Math.max(0, Math.floor((expected.frames - 1) / 2));
    await evaluate(`window.PFCViewer.setFrame(${middleIndex})`);
    await waitFor(() => evaluate(`Number(document.body.dataset.frameIndex) === ${middleIndex}`), 30000);
    const middle = await read();

    const dragResult = await evaluate(`(() => {
      const D = window.PFC_VIEWER_DATA;
      const id = window.PFCViewer.state.get().currentCase;
      const specs = D.caseCharts[id] || [];
      const spec = specs.find((item) => ["line", "dual-line", "scatter", "area"].includes(item.type) &&
        item.x && Array.isArray(item.x.data) &&
        ["s", "cycle"].includes(item.x.unit));
      if (!spec) return null;
      const panels = [...document.querySelectorAll("#chartGrid .chart-panel")];
      const panel = panels.find((node) => node.querySelector("h3") && node.querySelector("h3").textContent === spec.title);
      if (!panel) return { specTitle: spec.title, missing: true };
      panel.scrollIntoView({ block: "center", inline: "nearest" });
      const rect = panel.getBoundingClientRect();
      return {
        specTitle: spec.title,
        x1: rect.left + rect.width * 0.25,
        x2: rect.left + rect.width * 0.72,
        y: rect.top + rect.height * 0.55
      };
    })()`);
    let drag = null;
    if (dragResult && !dragResult.missing) {
      const before = await read();
      await mouse("mousePressed", dragResult.x1, dragResult.y);
      await mouse("mouseMoved", dragResult.x2, dragResult.y, 1);
      await mouse("mouseReleased", dragResult.x2, dragResult.y, 0);
      await sleep(800);
      const after = await read();
      drag = { before, after, specTitle: dragResult.specTitle, changed: before.frameIndex !== after.frameIndex || before.cycle !== after.cycle };
      await capture(screenshot ? screenshot.replace(/\.png$/i, "-linked.png") : "");
    }

    const stageBox = await evaluate(`(() => {
      const stage = document.getElementById("stage");
      stage.scrollIntoView({ block: "center", inline: "nearest" });
      const rect = stage.getBoundingClientRect();
      return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    })()`);
    let sceneClickSelected = "";
    const hitOffsets = [
      [0.50, 0.50], [0.45, 0.50], [0.55, 0.50], [0.50, 0.42],
      [0.50, 0.58], [0.42, 0.45], [0.58, 0.45], [0.42, 0.56],
      [0.58, 0.56], [0.35, 0.50], [0.65, 0.50]
    ];
    // First try an exact projected real Ball (robust for sparse/linear
    // models), then fall back to the fixed screen offsets.
    const projected = await evaluate(`window.PFCViewer.projectBallToScreen
      ? window.PFCViewer.projectBallToScreen(${expected.firstBallId}) : null`);
    if (projected && projected.inView) {
      await mouse("mousePressed", projected.x, projected.y);
      await mouse("mouseReleased", projected.x, projected.y, 0);
      await sleep(200);
      sceneClickSelected = await evaluate('document.body.dataset.selectedBallIds || ""');
    }
    for (const [fx, fy] of hitOffsets) {
      if (sceneClickSelected) break;
      const x = stageBox.left + stageBox.width * fx;
      const y = stageBox.top + stageBox.height * fy;
      await mouse("mousePressed", x, y);
      await mouse("mouseReleased", x, y, 0);
      await sleep(160);
      sceneClickSelected = await evaluate(
        'document.body.dataset.selectedBallIds || ""'
      );
      if (sceneClickSelected) break;
    }
    await evaluate("window.PFCViewer.clearSelection()");

    await evaluate(`window.PFCViewer.selectBall(${expected.firstBallId})`);
    try {
      await waitFor(() => evaluate(
        `document.body.dataset.selectedBallIds === "${expected.firstBallId}" && ` +
        `document.body.dataset.historyVisible === "1" && ` +
        `Number(document.body.dataset.historyPointCount || 0) > 0`
      ), 30000);
    } catch (error) {
      console.error(JSON.stringify(await evaluate(`({
        state: window.PFCViewer.state.get(),
        selectedBalls: document.body.dataset.selectedBallIds,
        historyVisible: document.body.dataset.historyVisible,
        historyStatus: document.getElementById("historyStatus").textContent,
        historyPointCount: document.body.dataset.historyPointCount,
        historyPanelHidden: document.getElementById("historyPanel").hidden,
        error: document.getElementById("errorBox").textContent,
        loadedChunks: document.body.dataset.loadedChunkCount
      })`), null, 2));
      throw error;
    }
    const selected = await read();
    const historySeries = await evaluate(`(() => {
      const chart = echarts.getInstanceByDom(document.getElementById("historyChart"));
      if (!chart) return null;
      const option = chart.getOption();
      return {
        seriesCount: (option.series || []).length,
        pointCounts: (option.series || []).map((item) => (item.data || []).length),
        firstSeriesX: ((option.series || [])[0]?.data || []).map((item) => item[0])
      };
    })()`);
    // FIX: choose a legal probe frame instead of hardcoding 6.  Short
    // experiments may have fewer than 7 frames (case01 has 6: indices 0-5).
    const probeFrame = Math.min(6, Math.max(0, expected.frames - 1));
    await evaluate(`window.PFCViewer.setFrame(${probeFrame})`);
    await waitFor(() => evaluate(
      `Number(document.body.dataset.frameIndex) === ${probeFrame} && document.body.dataset.historyVisible === "1"`
    ), 30000);
    const historyAfterFrame = await read();

    const range = [expected.maxDisplacement * 0.05, expected.maxDisplacement * 0.65];
    await evaluate(`window.PFCViewer.selectRange(${JSON.stringify(range)}, "displacement")`);
    await waitFor(() => evaluate(`document.body.dataset.selectedRange !== ""`), 20000);
    const rangeState = await read();

    const pngDataUrl = await evaluate(`window.PFCViewer.exportFramePNG(${middleIndex}, 1200)`);
    const compositeDataUrl = await evaluate("window.PFCViewer.getCompositePanelDataURL()");
    const chartExportEntries = await evaluate("window.PFCViewer.getChartExportEntries()");
    const selectedState = await read();
    const historyExportName = selectedState.historyVisible === "1"
      ? "pfc_case_" + selectedState.caseId + "_ball_history.svg"
      : null;
    const expectedDownloadCount = chartExportEntries.length + (historyExportName ? 1 : 0);
    const publicationContract = await evaluate(
      "window.PFCViewer.getPublicationExportContract()"
    );
    // Compatibility: newer Viewers place export controls inside a collapsible
    // #controlDock (default collapsed).  Open it before measuring the button,
    // otherwise the rect is 0x0 and no download is triggered.
    const openDock = `(() => {
      const toggle = document.getElementById("dockToggle");
      const dock = document.getElementById("controlDock");
      if (toggle && dock && dock.classList.contains("collapsed")) toggle.click();
      return true;
    })()`;
    await evaluate(openDock);
    await sleep(200);
    const sceneButtonRect = await evaluate(`(() => {
      const button = document.getElementById("exportScene");
      button.scrollIntoView({ block: "center", inline: "nearest" });
      const rect = button.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      };
    })()`);
    const downloadsBeforeScene = [...downloadRecords.values()].filter(
      (item) => item.state === "completed"
    ).length;
    await mouse("mousePressed", sceneButtonRect.x, sceneButtonRect.y);
    await mouse("mouseReleased", sceneButtonRect.x, sceneButtonRect.y, 0);
    await waitFor(() => (
      [...downloadRecords.values()].filter((item) => item.state === "completed").length >
      downloadsBeforeScene
    ), 30000);
    await sleep(250);
    const sceneDownload = [...downloadRecords.values()].find(
      (item) => item.state === "completed" &&
        item.suggestedFilename &&
        item.suggestedFilename.toLowerCase().endsWith(".png")
    );
    const sceneDownloadPath = sceneDownload
      ? path.join(downloadDir, sceneDownload.suggestedFilename)
      : null;
    const sceneBytes = sceneDownloadPath && fs.existsSync(sceneDownloadPath)
      ? fs.readFileSync(sceneDownloadPath)
      : Buffer.alloc(0);
    const sceneExport = {
      buttonClicked: true,
      fileName: sceneDownload ? sceneDownload.suggestedFilename : null,
      bytes: sceneBytes.length,
      dimensions: pngDimensions(sceneBytes),
      contract: publicationContract,
      metadata: await evaluate(`({
        includesMetadata: document.body.dataset.sceneExportIncludesMetadata,
        width: Number(document.body.dataset.sceneExportWidth || 0),
        height: Number(document.body.dataset.sceneExportHeight || 0),
        metric: document.body.dataset.sceneExportMetric,
        unit: document.body.dataset.sceneExportUnit,
        format: document.body.dataset.sceneExportFormat
      })`)
    };
    const downloadsBeforeSvg = [...downloadRecords.values()].filter(
      (item) => item.state === "completed"
    ).length;
    await evaluate(openDock);
    const exportButtonRect = await evaluate(`(() => {
      const button = document.getElementById("exportCharts");
      button.scrollIntoView({ block: "center", inline: "nearest" });
      const rect = button.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2
      };
    })()`);
    await mouse("mousePressed", exportButtonRect.x, exportButtonRect.y);
    await mouse("mouseReleased", exportButtonRect.x, exportButtonRect.y, 0);
    await waitFor(() => (
      [...downloadRecords.values()].filter((item) => item.state === "completed").length >=
      downloadsBeforeSvg + expectedDownloadCount
    ), 30000);
    await sleep(250);
    const completedDownloads = [...downloadRecords.values()].filter(
      (item) => item.state === "completed"
    );
    const downloadFiles = completedDownloads.map((item) => ({
      ...item,
      path: path.join(downloadDir, item.suggestedFilename)
    }));
    const svgDownloads = downloadFiles.filter((item) =>
      item.suggestedFilename.toLowerCase().endsWith(".svg")
    );
    const svgTexts = svgDownloads.map((item) =>
      fs.readFileSync(item.path, "utf8")
    );
    const expectedSvgNames = chartExportEntries.map((item) => item.fileName);
    if (historyExportName) expectedSvgNames.push(historyExportName);
    const actualDownloadNames = svgDownloads.map((item) => item.suggestedFilename);
    const svgRootCount = svgTexts.filter((text) => text.includes("<svg")).length;
    const titleFailures = chartExportEntries
      .map((item, index) => ({ item, index }))
      .filter(({ item, index }) => (
        !item.title || !String(svgTexts[index] || "").includes(item.title)
      ))
      .map(({ item, index }) => ({
        index,
        fileName: item.fileName,
        title: item.title
      }));
    if (historyExportName) {
      const historySvg = String(svgTexts[svgTexts.length - 1] || "");
      if (!historySvg.includes("Ball 历史")) {
        titleFailures.push({
          index: chartExportEntries.length,
          fileName: historyExportName,
          title: "Ball 历史"
        });
      }
    }
    const compositeLayout = await evaluate("window.PFCViewer.getCompositePanelLayout()");
    const exports = {
      pngPrefix: String(pngDataUrl || "").slice(0, 22),
      pngLength: String(pngDataUrl || "").length,
      sceneExport,
      svgCount: svgDownloads.length,
      svgRootCount,
      expectedSvgNames,
      actualDownloadNames,
      namesUnique: new Set(actualDownloadNames).size === actualDownloadNames.length,
      namesMatch: JSON.stringify(actualDownloadNames) === JSON.stringify(expectedSvgNames),
      allRootsPresent: svgRootCount === expectedSvgNames.length,
      titleFailures,
      compositePrefix: String(compositeDataUrl || "").slice(0, 22),
      compositeLength: String(compositeDataUrl || "").length,
      compositeLayout
    };
    const exportFiles = [];
    {
      const pngPath = path.join(downloadDir, "viewer_frame.png");
      const compositePath = path.join(downloadDir, "composite_panels.png");
      fs.writeFileSync(pngPath, Buffer.from(String(pngDataUrl).split(",")[1], "base64"));
      fs.writeFileSync(compositePath, Buffer.from(String(compositeDataUrl).split(",")[1], "base64"));
      exportFiles.push(pngPath, compositePath);
      if (sceneDownloadPath && fs.existsSync(sceneDownloadPath)) {
        exportFiles.push(sceneDownloadPath);
      }
      exportFiles.push(...svgDownloads.map((item) => item.path));
    }

    const alternate = await evaluate(`(() => {
      const current = window.PFCViewer.state.get().currentCase;
      const other = window.PFC_VIEWER_DATA.catalog.cases.find((item) => item.id !== current);
      return other ? other.id : null;
    })()`);
    let switched = null;
    if (alternate !== null) {
      await evaluate(`window.PFCViewer.setCase(${alternate})`);
      await waitFor(() => evaluate(`Number(document.body.dataset.caseId) === ${alternate} && document.body.dataset.ready === "1"`), 45000);
      switched = await read();
    }

    const metrics = await send("Performance.getMetrics");
    const metricMap = Object.fromEntries(metrics.metrics.map((item) => [item.name, item.value]));
    await capture(screenshot || "");
    const failures = [];
    if (initial.error || initial.ready !== "1") failures.push("viewer not ready");
    if (initial.caseId !== expected.defaultCase) failures.push("default Case is wrong");
    if (
      missingValueProbe.nullNumber !== "—" ||
      missingValueProbe.undefinedNumber !== "—" ||
      missingValueProbe.nanNumber !== "—" ||
      missingValueProbe.emptyNumber !== "—" ||
      missingValueProbe.invalidNumber !== "—" ||
      missingValueProbe.nullTooltip !== "—"
    ) failures.push("missing values were formatted as numeric values");
    if (missingValueProbe.zeroNumber !== "0") failures.push("real numeric zero was lost");
    if (missingValueProbe.validNumber !== "12.5") failures.push("valid numeric formatting failed");
    if (missingValueProbe.nullMetric !== "未采集" || missingValueProbe.zeroMetric !== "0 m") failures.push("metric missing/zero semantics failed");
    // Stress may be a real zero (walls present) or legitimately NOT_CAPTURED.
    // Both are valid; only a fabricated numeric value would be a defect.
    if (!["未采集", "NOT_CAPTURED"].includes(missingValueProbe.stressAtFirstFrame) &&
        !/^[-+]?[0-9.]+(e[-+]?[0-9]+)?\s*(MPa|N|Pa|kN)$/.test(missingValueProbe.stressAtFirstFrame)) {
      failures.push("stress metric card has neither a valid unit nor a missing label");
    }
    // Only check the speed chart's first value when that chart actually
    // exists.  Some experiments (porosity, short waves) legitimately have no
    // temporal speed chart; MISSING_SPEC/MISSING_PANEL are NOT zero-fills.
    if (missingValueProbe.speedSpecFirstY !== "MISSING_SPEC" &&
        missingValueProbe.speedSpecFirstY !== null) {
      failures.push("speed chart converted a missing value to a number");
    }
    if (!zeroValueFrame.stress || /NaN|Infinity|undefined/.test(zeroValueFrame.stress))
      failures.push("metric card rendered an invalid value");
    if (JSON.stringify(frameIndexProbe.frameSourceIndices) !== JSON.stringify(expected.frameSources)) failures.push("Viewer frame-to-source mapping is wrong");
    // A temporal (time/cycle-axis) chart only exists for cases whose data
    // supports it.  Histogram-only cases legitimately have none; do not fail.
    // When at least one temporal chart exists, verify its frame mapping.
    const hasTemporalSpec = await evaluate(`(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const specs = window.PFC_VIEWER_DATA.caseCharts[caseId] || [];
      return specs.some((s) => s.x && ["s", "cycle"].includes(s.x.unit));
    })()`);
    if (hasTemporalSpec && !frameIndexProbe.temporal.length) {
      failures.push("temporal chart does not expose source-frame indices");
    }
    frameIndexProbe.temporal.forEach((chart) => {
      if (JSON.stringify(chart.sourceIndices) !== JSON.stringify(expected.frameSources)) failures.push("temporal chart source indices do not match Viewer frames: " + chart.id);
      if (chart.pointCount !== expected.frames || !chart.xMatchesFrames) failures.push("temporal chart x values do not match Viewer frames: " + chart.id);
      if (chart.yLength != null && chart.yLength !== expected.frames) failures.push("temporal chart y count does not match Viewer frames: " + chart.id);
      if (chart.seriesLengths.some((count) => count !== expected.frames)) failures.push("temporal chart series count does not match Viewer frames: " + chart.id);
    });
    if (initial.chartCount + 1 < expected.charts) failures.push("data-driven chart count is lower than expected");
    if (initial.linkedCharts < 2) failures.push("linked current-frame charts missing");
    if (initial.ballCount <= 0 || initial.missing < 0) failures.push("frame Ball counts are invalid");
    if (initial.payloadVersion !== "2.2.0") failures.push("payload version mismatch");
    if (initial.externalScripts.length || initial.externalLinks.length) failures.push("external assets found");
    if (externalRequests.length) failures.push("external network requests found");
    if (middle.frameIndex !== middleIndex || middle.cycle <= initial.cycle) failures.push("timeline did not select a later real frame");
    if (drag && !drag.changed) failures.push("chart drag did not update the unified frame state");
    if (!sceneClickSelected) failures.push("clicking a rendered 3D Ball did not select a real Ball ID");
    // A center-screen raycast may hit ANY real Ball in the case, not always
    // id=1.  Verify the click selected a genuine Ball of this case instead.
    if (sceneClickSelected && !expected.ballIds.includes(String(sceneClickSelected))) failures.push("3D Ball click selected an ID not present in this Case");
    const selectedHistory = checkBallHistory(selected, "selected Ball");
    const afterFrameHistory = checkBallHistory(historyAfterFrame, "after frame switch");
    failures.push(...selectedHistory.failures, ...afterFrameHistory.failures);
    if (!selected.selectedBalls.includes(String(expected.firstBallId))) failures.push("Ball selection did not enter ViewerState");
    if (selected.historyVisible !== "1") failures.push("Ball history did not become visible");
    if (!selected.historyCursorVisible) failures.push("Ball history temporal cursor is missing");
    if (afterFrameHistory.rows !== selectedHistory.rows ||
        historyAfterFrame.historySourceFrameIndices !== selected.historySourceFrameIndices) {
      failures.push("Ball history was lost or remapped after a frame switch");
    }
    if (!historySeries || historySeries.seriesCount < 1) failures.push("Ball history chart has no series");
    if (historySeries && historySeries.pointCounts.some((count) => count !== selectedHistory.rows)) failures.push("Ball history chart point counts are inconsistent");
    if (historySeries && JSON.stringify(historySeries.firstSeriesX) !== JSON.stringify(parseCsvNumbers(selected.historyCycleValues))) failures.push("Ball history chart x coordinates are not the captured Cycles");
    if (!rangeState.selectedRange || rangeState.highlightCount <= 0) failures.push("distribution range did not highlight particles");
    if (!exports.pngPrefix.startsWith("data:image/png") || exports.pngLength < 10000) failures.push("specified-frame PNG export failed");
    if (!sceneExport.buttonClicked || !sceneExport.fileName || sceneExport.bytes < 10000) failures.push("publication scene PNG button did not create a real file");
    if (
      !sceneExport.dimensions ||
      sceneExport.dimensions.width !== sceneExport.metadata.width ||
      sceneExport.dimensions.height !== sceneExport.metadata.height
    ) failures.push("publication scene PNG dimensions do not match recorded export metadata");
    if (
      sceneExport.metadata.includesMetadata !== "true" ||
      sceneExport.metadata.format !== "PNG" ||
      !sceneExport.metadata.metric ||
      !sceneExport.metadata.unit
    ) failures.push("publication scene PNG scientific metadata was not composed");
    if (
      !sceneExport.contract.includes_colorbar ||
      !sceneExport.contract.includes_cycle_and_time ||
      !sceneExport.contract.includes_scale_bar ||
      sceneExport.contract.scene_svg !== "NOT_SUPPORTED"
    ) failures.push("publication export capability contract is incomplete");
    if (exports.svgCount < 1 || !exports.allRootsPresent) failures.push("chart SVG export failed");
    if (!exports.namesUnique) failures.push("chart SVG download names are not unique");
    if (!exports.namesMatch) failures.push("chart SVG download names do not match chart order");
    if (exports.titleFailures.length) failures.push("chart SVG title mismatch");
    if (!exports.compositePrefix.startsWith("data:image/png") || exports.compositeLength < 10000) failures.push("composite panel export failed");
    if (!exports.compositeLayout || exports.compositeLayout.panels.length !== initial.chartCount) failures.push("composite panel layout is incomplete");
    if (alternate !== null && (switched.caseId !== alternate || switched.frameIndex !== 0)) failures.push("Case switch did not reset state coherently");
    if (alternate !== null && switched.missing !== 0) failures.push("Case switch retained static Balls from the previous Case");
    if (alternate !== null && (switched.historyVisible !== "0" || switched.historyPointCount !== 0)) failures.push("Case switch retained the previous Ball history");
    if (pageErrors.length) failures.push(...pageErrors);

    const report = {
      pass: failures.length === 0,
      failures,
      browser,
      viewer,
      expected,
      initial,
      missingValueProbe,
      frameIndexProbe,
      zeroValueFrame,
      middle,
      drag,
      sceneClickSelected,
      selected,
      historySeries,
      historyCoverage: {
        selected: selectedHistory,
        afterFrameSwitch: afterFrameHistory,
        policy: "subset of real frames; dynamic entity ID sets are preserved"
      },
      historyAfterFrame,
      range: rangeState,
      exports,
      exportFiles,
      caseSwitchStatus: alternate === null ? "NOT_APPLICABLE_SINGLE_CASE" : "PASS",
      switched,
      metrics: {
        JSHeapUsedSize: metricMap.JSHeapUsedSize,
        JSHeapTotalSize: metricMap.JSHeapTotalSize,
        Nodes: metricMap.Nodes,
        Documents: metricMap.Documents
      },
      externalRequests,
      pageErrors,
      browserStderrTail: stderr.slice(-2000)
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
    await sleep(250);
    try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch {}
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
