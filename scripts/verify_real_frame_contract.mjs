import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);

function argValue(args, name) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : "";
}

function findBrowser(explicit) {
  const candidates = [
    explicit,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe"
  ].filter(Boolean);
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) throw new Error("No Chromium/Edge browser found");
  return found;
}

function loadPlaywright() {
  const bundledCandidates = [
    path.join(path.dirname(process.execPath), "node_modules", "playwright"),
    path.join(
      path.dirname(path.dirname(process.execPath)),
      "node_modules",
      "playwright"
    )
  ];
  const bundled = bundledCandidates.find((candidate) => fs.existsSync(candidate));
  const modulePath = process.env.PFC_PLAYWRIGHT_MODULE ||
    bundled ||
    "playwright";
  return require(modulePath);
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
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw lastError || new Error("Timed out waiting for browser condition");
}

async function main() {
  const args = process.argv.slice(2);
  const viewerPath = argValue(args, "--file");
  const screenshot = argValue(args, "--screenshot");
  const reportPath = argValue(args, "--report");
  const downloadDir = argValue(args, "--download-dir");
  const browserPath = findBrowser(argValue(args, "--browser") || process.env.PFC_BROWSER);
  if (!viewerPath) throw new Error("--file is required");
  if (!downloadDir) throw new Error("--download-dir is required");
  fs.mkdirSync(downloadDir, { recursive: true });

  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    executablePath: browserPath,
    headless: true,
    args: ["--allow-file-access-from-files", "--no-sandbox", "--disable-gpu-sandbox"]
  });
  const context = await browser.newContext({
    acceptDownloads: true,
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.stack || String(error)));
  page.on("console", (message) => {
    if (message.type() === "error") pageErrors.push("console: " + message.text());
  });

  try {
    await page.goto(pathToFileURL(path.resolve(viewerPath)).href);
    await page.waitForFunction(() => (
      document.body?.dataset.ready === "1" &&
      document.body?.dataset.caseReady === "1"
    ), null, { timeout: 60000 });
    const dataBoundary = await page.evaluate(
      () => window.PFC_VIEWER_DATA.catalog.meta.dataBoundary
    );

    const formatting = await page.evaluate(() => ({
      nullNumber: window.PFCViewer.formatting.number(null),
      undefinedNumber: window.PFCViewer.formatting.number(undefined),
      nanNumber: window.PFCViewer.formatting.number(NaN),
      invalidNumber: window.PFCViewer.formatting.number("invalid"),
      zeroNumber: window.PFCViewer.formatting.number(0),
      nullMetric: window.PFCViewer.formatting.metric(null, "m"),
      zeroMetric: window.PFCViewer.formatting.metric(0, "m"),
      nullTooltip: window.PFCViewer.formatting.tooltip(null, {})
    }));

    const frameContract = await page.evaluate(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const meta = window.PFC_VIEWER_DATA.caseMeta[caseId];
      const specs = window.PFC_VIEWER_DATA.caseCharts[caseId] || [];
      const temporal = specs.filter((spec) => (
        Array.isArray(spec.source_indices) &&
        spec.x &&
        ["s", "cycle"].includes(spec.x.unit)
      )).map((spec) => {
        const x = spec.x.data;
        const y = spec.y ? spec.y.data : null;
        const expectedX = spec.x.unit === "s"
          ? meta.frames.map((frame) => frame.time)
          : meta.frames.map((frame) => frame.cycle);
        const panel = [...document.querySelectorAll("#chartGrid .chart-panel")].find(
          (item) => item.querySelector("h3")?.textContent === spec.title
        );
        const chart = panel
          ? echarts.getInstanceByDom(panel.querySelector(".chart"))
          : null;
        const renderedY = chart?.getOption()?.series?.[0]?.data?.map(
          (item) => Array.isArray(item) ? item[1] : item
        ) || null;
        return {
          id: spec.id,
          sourceIndices: spec.source_indices,
          x,
          y,
          renderedY,
          expectedX,
          seriesLengths: (spec.series || []).map((item) => item.data.length)
        };
      });
      return {
        caseId,
        sourceFrameCount: meta.sourceFrameCount,
        viewerFrameCount: meta.viewerFrameCount,
        frameSources: meta.frames.map((frame) => frame.sourceIndex),
        frameCycles: meta.frames.map((frame) => frame.cycle),
        temporal
      };
    });
    const comparisonContract = await page.evaluate(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const specs = [
        ...(window.PFC_VIEWER_DATA.caseCharts[caseId] || []),
        ...(window.PFC_VIEWER_DATA.globalCharts || [])
      ];
      return specs.filter((spec) => spec.type === "case-compare").map((spec) => {
        const panel = [...document.querySelectorAll("#chartGrid .chart-panel")].find(
          (item) => item.querySelector("h3")?.textContent === spec.title
        );
        const status = panel?.querySelector("header span")?.textContent || "";
        const chart = panel
          ? echarts.getInstanceByDom(panel.querySelector(".chart"))
          : null;
        const rendered = chart?.getOption()?.series?.[0]?.data || [];
        const rowsWithMissingValue = spec.data
          .filter((row) => row[spec.metric_key] == null)
          .map((row) => Number(row.case_id));
        const renderedColors = [...new Set(rendered
          .filter((item) => item && item.value != null)
          .map((item) => item.itemStyle?.color)
          .filter(Boolean))];
        return {
          id: spec.id,
          total: Number(spec.total_case_count),
          available: Number(spec.available_case_count),
          missing: Number(spec.missing_case_count),
          missingCaseIds: (spec.missing_case_ids || []).map(Number),
          decisionMissing: Number(spec.decision?.missing_count),
          decisionAvailability: spec.decision?.availability || null,
          color: spec.color,
          colorPolicy: spec.color_policy,
          caseAvailabilityCount: (spec.case_availability || []).length,
          rowsWithMissingValue,
          renderedNullCount: rendered.filter((item) => item?.value == null).length,
          renderedColors,
          panelStatus: status,
          panelMissingIds: panel?.dataset.missingCaseIds || ""
        };
      });
    });
    const axisContract = await page.evaluate(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const specs = [
        ...(window.PFC_VIEWER_DATA.caseCharts[caseId] || []),
        ...(window.PFC_VIEWER_DATA.globalCharts || [])
      ];
      return specs.filter((spec) => spec.axis_contract).flatMap((spec) => {
        const panel = [...document.querySelectorAll("#chartGrid .chart-panel")].find(
          (item) => item.querySelector("h3")?.textContent === spec.title
        );
        const chart = panel
          ? echarts.getInstanceByDom(panel.querySelector(".chart"))
          : null;
        if (!chart) return [];
        const option = chart.getOption();
        const model = chart.getModel();
        const checks = [];
        const inspect = (axisName, contract, axisIndex) => {
          if (!contract) return;
          const configured = axisName === "y"
            ? (Array.isArray(option.yAxis) ? option.yAxis[axisIndex] : option.yAxis)
            : (Array.isArray(option.xAxis) ? option.xAxis[axisIndex] : option.xAxis);
          if (!configured || configured.type === "category") return;
          const axisModel = model.getComponent(axisName + "Axis", axisIndex);
          const ticks = axisModel?.axis?.scale?.getTicks?.() || [];
          const formatter = configured.axisLabel?.formatter;
          const labels = ticks.map((tick, index) => {
            const value = tick && typeof tick === "object" ? tick.value : tick;
            return typeof formatter === "function" ? formatter(value, index) : value;
          });
          checks.push({
            id: spec.id,
            axis: axisName,
            index: axisIndex,
            includeZero: contract.include_zero,
            rangePolicy: contract.range_policy,
            notation: contract.notation,
            scaleLabel: contract.axis_scale_label,
            configuredScale: configured.scale,
            name: configured.name,
            labels
          });
        };
        inspect("x", spec.axis_contract.x, 0);
        if (spec.axis_contract.series) {
          spec.axis_contract.series.forEach((contract, index) => (
            inspect("y", contract, index)
          ));
        } else {
          inspect("y", spec.axis_contract.y, 0);
        }
        return checks;
      });
    });
    const visualContract = await page.evaluate(() => {
      const optionsFor = (title) => {
        const panel = [...document.querySelectorAll("#chartGrid .chart-panel")].find(
          (item) => item.querySelector("h3")?.textContent === title
        );
        return panel
          ? echarts.getInstanceByDom(panel.querySelector(".chart"))?.getOption()
          : null;
      };
      const density = [...document.querySelectorAll("#chartGrid h3")]
        .map((node) => node.textContent)
        .find((title) => title && title.includes("颗粒数密度"));
      const densityOption = density ? optionsFor(density) : null;
      const correlationOption = optionsFor("通道相关性");
      const clipping = [...document.querySelectorAll("#chartGrid .chart-panel")]
        .flatMap((panel) => {
          const svg = panel.querySelector(".chart > svg");
          if (!svg) return [];
          const rootRect = svg.getBoundingClientRect();
          return [...svg.querySelectorAll("text")].filter((text) => {
            const box = text.getBoundingClientRect();
            return box.left < rootRect.left - 1 ||
              box.right > rootRect.right + 1 ||
              box.top < rootRect.top - 1 ||
              box.bottom > rootRect.bottom + 1;
          }).map((text) => {
            const box = text.getBoundingClientRect();
            return {
              title: panel.querySelector("h3")?.textContent || "",
              text: text.textContent || "",
              delta: {
                left: box.left - rootRect.left,
                right: box.right - rootRect.right,
                top: box.top - rootRect.top,
                bottom: box.bottom - rootRect.bottom
              },
              rootRect: {
                left: rootRect.left,
                right: rootRect.right,
                top: rootRect.top,
                bottom: rootRect.bottom
              },
              textRect: {
                left: box.left,
                right: box.right,
                top: box.top,
                bottom: box.bottom
              }
            };
          });
        });
      return {
        densityColorbar: densityOption?.visualMap?.[0]?.text || [],
        correlationColorbar: correlationOption?.visualMap?.[0]?.text || [],
        clipping
      };
    });
    const finalFrameIndex = frameContract.viewerFrameCount - 1;
    await page.evaluate((index) => window.PFCViewer.setFrame(index), finalFrameIndex);
    await page.waitForFunction(
      (index) => Number(document.body.dataset.frameIndex) === index &&
        [...document.querySelectorAll("#chartGrid .chart-panel")]
          .filter((panel) => panel.querySelector("h3")?.textContent.includes("当前帧"))
          .every((panel) => panel.dataset.histogramRangePolicy),
      finalFrameIndex,
      { timeout: 30000 }
    );
    const histogramContract = await page.evaluate(() => {
      const caseId = window.PFCViewer.state.get().currentCase;
      const spec = (window.PFC_VIEWER_DATA.caseCharts[caseId] || [])
        .find((item) => item.id === "case_" + caseId + ":displacement_hist");
      const panel = [...document.querySelectorAll("#chartGrid .chart-panel")]
        .find((item) => item.querySelector("h3")?.textContent === "当前帧累计位移分布");
      const chart = panel
        ? echarts.getInstanceByDom(panel.querySelector(".chart"))
        : null;
      const option = chart?.getOption();
      const rendered = (option?.series?.[0]?.data || []).map(
        (item) => item && typeof item === "object" ? item.value : item
      );
      return {
        spec: spec ? {
          rangePolicy: spec.range_policy,
          finiteCount: Number(spec.finite_count),
          missingCount: Number(spec.missing_count),
          underflowCount: Number(spec.underflow_count),
          overflowCount: Number(spec.overflow_count),
          countsSum: (spec.counts || []).reduce((sum, value) => sum + Number(value), 0),
          firstLabel: (spec.bin_labels || [])[0],
          lastLabel: (spec.bin_labels || []).at(-1),
          interiorMin: Number(spec.interior_min),
          interiorMax: Number(spec.interior_max)
        } : null,
        live: panel ? {
          rangePolicy: panel.dataset.histogramRangePolicy,
          finiteCount: Number(panel.dataset.histogramFiniteCount),
          underflowCount: Number(panel.dataset.histogramUnderflowCount),
          overflowCount: Number(panel.dataset.histogramOverflowCount),
          interiorMin: Number(panel.dataset.histogramInteriorMin),
          interiorMax: Number(panel.dataset.histogramInteriorMax),
          countsSum: rendered.reduce((sum, value) => sum + Number(value || 0), 0),
          labels: option?.xAxis?.[0]?.data || [],
          status: panel.querySelector("header span")?.textContent || ""
        } : null
      };
    });
    await page.evaluate(() => window.PFCViewer.setFrame(0));
    await page.waitForFunction(
      () => Number(document.body.dataset.frameIndex) === 0,
      null,
      { timeout: 30000 }
    );

    await page.locator("#stage").scrollIntoViewIfNeeded();
    const stage = await page.locator("#stage").boundingBox();
    if (!stage) throw new Error("Viewer stage has no bounding box");
    let selectedId = "";
    for (const [fx, fy] of [
      [0.5, 0.5], [0.45, 0.45], [0.55, 0.45], [0.45, 0.55],
      [0.55, 0.55], [0.35, 0.5], [0.65, 0.5], [0.5, 0.35],
      [0.5, 0.65], [0.25, 0.35], [0.75, 0.65]
    ]) {
      await page.mouse.click(stage.x + stage.width * fx, stage.y + stage.height * fy);
      await page.waitForTimeout(160);
      selectedId = await page.evaluate(
        () => document.body.dataset.selectedBallIds || ""
      );
      if (selectedId) break;
    }
    if (!selectedId) throw new Error("Physical Ball click selected no entity");
    await page.waitForFunction(() => (
      document.body.dataset.historyVisible === "1" &&
      Number(document.body.dataset.historyPointCount || 0) > 0
    ), null, { timeout: 30000 });

    const history = await page.evaluate(() => {
      const chart = echarts.getInstanceByDom(document.getElementById("historyChart"));
      const option = chart?.getOption();
      const parse = (name) => (document.body.dataset[name] || "")
        .split(",")
        .filter(Boolean)
        .map(Number);
      return {
        selectedBallIds: document.body.dataset.selectedBallIds || "",
        pointCount: Number(document.body.dataset.historyPointCount || 0),
        sourceFrames: parse("historySourceFrameIndices"),
        viewerFrames: parse("historyViewerFrameIndices"),
        cycles: parse("historyCycleValues"),
        seriesPointCounts: (option?.series || []).map(
          (series) => (series.data || []).length
        ),
        firstSeriesX: ((option?.series || [])[0]?.data || []).map(
          (item) => item[0]
        )
      };
    });

    const currentFrame = await page.evaluate(() => Number(document.body.dataset.frameIndex));
    const nextFrame = Math.min(
      frameContract.viewerFrameCount - 1,
      currentFrame + 1
    );
    await page.evaluate((index) => window.PFCViewer.setFrame(index), nextFrame);
    await page.waitForFunction(
      (index) => Number(document.body.dataset.frameIndex) === index,
      nextFrame,
      { timeout: 30000 }
    );
    const historyAfterFrame = await page.evaluate(() => ({
      pointCount: Number(document.body.dataset.historyPointCount || 0),
      sourceFrames: document.body.dataset.historySourceFrameIndices || "",
      historyVisible: document.body.dataset.historyVisible || ""
    }));
    const alternateCase = await page.evaluate((current) => (
      window.PFC_VIEWER_DATA.catalog.cases.find((item) => item.id !== current)?.id ?? null
    ), frameContract.caseId);
    let caseSwitch = null;
    if (alternateCase != null) {
      await page.evaluate((caseId) => window.PFCViewer.setCase(caseId), alternateCase);
      await page.waitForFunction(
        (caseId) => Number(document.body.dataset.caseId) === caseId &&
          document.body.dataset.ready === "1",
        alternateCase,
        { timeout: 60000 }
      );
      caseSwitch = await page.evaluate(() => ({
        caseId: Number(document.body.dataset.caseId),
        frameIndex: Number(document.body.dataset.frameIndex),
        historyVisible: document.body.dataset.historyVisible || "",
        historyPointCount: Number(document.body.dataset.historyPointCount || 0),
        selectedBallIds: document.body.dataset.selectedBallIds || ""
      }));
      await page.evaluate(
        (caseId) => window.PFCViewer.setCase(caseId),
        frameContract.caseId
      );
      await page.waitForFunction(
        (caseId) => Number(document.body.dataset.caseId) === caseId &&
          document.body.dataset.ready === "1",
        frameContract.caseId,
        { timeout: 60000 }
      );
    }

    await page.evaluate(() => window.PFCViewer.clearSelection());
    await page.waitForFunction(() => document.body.dataset.historyVisible === "0");
    const exportEntries = await page.evaluate(
      () => window.PFCViewer.getChartExportEntries()
    );
    const downloads = [];
    page.on("download", (download) => {
      downloads.push((async () => {
        const tempPath = await download.path();
        const name = download.suggestedFilename();
        const filePath = path.join(downloadDir, name);
        fs.copyFileSync(tempPath, filePath);
        return {
          name,
          path: filePath,
          text: name.toLowerCase().endsWith(".svg")
            ? fs.readFileSync(filePath, "utf8")
            : ""
        };
      })());
    });
    await page.locator("#exportCharts").click();
    await waitFor(() => downloads.length >= exportEntries.length, 30000);
    const downloaded = await Promise.all(downloads);
    const uniqueNames = new Set(downloaded.map((item) => item.name)).size;
    const titleFailures = exportEntries.filter((entry, index) => (
      !entry.title || !downloaded[index]?.text.includes(entry.title)
    ));
    const rootFailures = downloaded.filter((item) => !item.text.includes("<svg"));
    const identityFailures = downloaded.filter((item, index) => {
      const entry = exportEntries[index];
      return !entry ||
        !item.text.includes('data-pfc-chart-id="' + entry.id + '"') ||
        !item.text.includes('data-pfc-title="' + entry.title + '"');
    });

    if (screenshot) {
      fs.mkdirSync(path.dirname(path.resolve(screenshot)), { recursive: true });
      await page.screenshot({ path: screenshot, fullPage: false });
    }

    const failures = [];
    if (dataBoundary !== "REAL_PFC") failures.push("Viewer data boundary is not REAL_PFC");
    if (
      formatting.nullNumber !== "—" ||
      formatting.undefinedNumber !== "—" ||
      formatting.nanNumber !== "—" ||
      formatting.invalidNumber !== "—" ||
      formatting.nullTooltip !== "—"
    ) failures.push("missing values are not consistently labeled");
    if (formatting.zeroNumber !== "0" || formatting.nullMetric !== "未采集" || formatting.zeroMetric !== "0 m") failures.push("zero/missing value semantics are not distinct");
    if (!frameContract.temporal.length) failures.push("no temporal chart exposes source indices");
    frameContract.temporal.forEach((chart) => {
      if (JSON.stringify(chart.sourceIndices) !== JSON.stringify(frameContract.frameSources)) failures.push("source indices mismatch: " + chart.id);
      if (chart.x.length !== frameContract.viewerFrameCount || JSON.stringify(chart.x) !== JSON.stringify(chart.expectedX)) failures.push("x axis mismatch: " + chart.id);
      if (chart.y && chart.y.length !== frameContract.viewerFrameCount) failures.push("y count mismatch: " + chart.id);
      if (chart.seriesLengths.some((count) => count !== frameContract.viewerFrameCount)) failures.push("series count mismatch: " + chart.id);
      if (chart.y && chart.renderedY) {
        chart.y.forEach((value, index) => {
          if (value == null && chart.renderedY[index] != null) failures.push("missing chart value became numeric: " + chart.id);
        });
      }
    });
    comparisonContract.forEach((chart) => {
      if (chart.available + chart.missing !== chart.total) failures.push("comparison availability counts do not add up: " + chart.id);
      if (chart.decisionMissing !== chart.missing) failures.push("comparison decision missing_count is wrong: " + chart.id);
      if (chart.caseAvailabilityCount !== chart.total) failures.push("comparison case availability list is incomplete: " + chart.id);
      if (JSON.stringify(chart.missingCaseIds) !== JSON.stringify(chart.rowsWithMissingValue)) failures.push("comparison missing Case IDs do not match values: " + chart.id);
      if (chart.renderedNullCount !== chart.missing) failures.push("comparison missing values were not rendered as null bars: " + chart.id);
      if (chart.colorPolicy !== "SINGLE_COLOR_BY_METRIC_SEMANTICS") failures.push("comparison color policy is not declared: " + chart.id);
      if (chart.renderedColors.length !== 1 || chart.renderedColors[0].toLowerCase() !== String(chart.color).toLowerCase()) failures.push("comparison uses ambiguous cycling colors: " + chart.id);
      if (!chart.panelStatus.includes(String(chart.available)) || !chart.panelStatus.includes(String(chart.total)) || !chart.panelStatus.includes(String(chart.missing))) failures.push("comparison panel does not show availability counts: " + chart.id);
      if (chart.panelMissingIds !== chart.missingCaseIds.join(",")) failures.push("comparison panel missing Case identity is wrong: " + chart.id);
      if (!chart.decisionAvailability || Number(chart.decisionAvailability.missing_case_count) !== chart.missing) failures.push("comparison decision availability contract is missing: " + chart.id);
    });
    axisContract.forEach((axis) => {
      const expectsScale = axis.includeZero === false;
      if (Boolean(axis.configuredScale) !== expectsScale) failures.push("axis zero policy is not applied: " + axis.id + " " + axis.axis);
      if (axis.notation === "SCIENTIFIC_SHARED_EXPONENT") {
        if (!axis.scaleLabel || !String(axis.name).includes(axis.scaleLabel)) failures.push("shared scientific scale is missing from axis name: " + axis.id + " " + axis.axis);
        if (axis.labels.some((label) => String(label).includes("×") || /e[+-]?\d/i.test(String(label)))) failures.push("axis mixes scientific notation per tick: " + axis.id + " " + axis.axis);
      }
    });
    if (
      !visualContract.densityColorbar.some((text) => String(text).includes("颗粒数")) ||
      !visualContract.correlationColorbar.some((text) => String(text).includes("Pearson r"))
    ) failures.push("colorbar variable or statistical meaning is missing");
    if (visualContract.clipping.length) failures.push("ECharts text is clipped outside its SVG panel");
    if (!histogramContract.spec || !histogramContract.live) {
      failures.push("robust histogram contract is missing");
    } else {
      if (histogramContract.spec.rangePolicy !== "ROBUST_P05_P95_WITH_OVERFLOW" || histogramContract.live.rangePolicy !== histogramContract.spec.rangePolicy) failures.push("analysis/live histogram range policy differs");
      if (histogramContract.spec.countsSum !== histogramContract.spec.finiteCount || histogramContract.live.countsSum !== histogramContract.live.finiteCount) failures.push("robust histogram did not retain every finite observation");
      if (histogramContract.live.finiteCount !== histogramContract.spec.finiteCount) failures.push("analysis/live histogram finite counts differ");
      if (histogramContract.spec.firstLabel !== "< P05" || histogramContract.spec.lastLabel !== "> P95" || histogramContract.live.labels[0] !== "< P05" || histogramContract.live.labels.at(-1) !== "> P95") failures.push("robust histogram overflow bins are missing");
      if (histogramContract.live.countsSum < histogramContract.live.underflowCount + histogramContract.live.overflowCount) failures.push("robust histogram tail counts are inconsistent");
    }
    if (!selectedId) failures.push("physical Ball click did not select an entity");
    if (history.pointCount <= 0 || history.sourceFrames.length !== history.pointCount || history.viewerFrames.length !== history.pointCount || history.cycles.length !== history.pointCount) failures.push("history frame mapping is incomplete");
    history.sourceFrames.forEach((sourceIndex, index) => {
      const viewerIndex = history.viewerFrames[index];
      if (viewerIndex == null || frameContract.frameSources[viewerIndex] !== sourceIndex) failures.push("history source/viewer mapping is wrong");
      if (history.cycles[index] !== frameContract.frameCycles[viewerIndex]) failures.push("history Cycle coordinates are wrong");
    });
    if (history.seriesPointCounts.some((count) => count !== history.pointCount)) failures.push("history chart point count is inconsistent");
    if (JSON.stringify(history.firstSeriesX) !== JSON.stringify(history.cycles)) failures.push("history chart x coordinates are wrong");
    if (historyAfterFrame.pointCount !== history.pointCount || historyAfterFrame.sourceFrames !== history.sourceFrames.join(",")) failures.push("history changed incorrectly after frame switch");
    if (alternateCase != null && (
      caseSwitch.caseId !== alternateCase ||
      caseSwitch.frameIndex !== 0 ||
      caseSwitch.historyVisible !== "0" ||
      caseSwitch.historyPointCount !== 0 ||
      caseSwitch.selectedBallIds !== ""
    )) failures.push("Case switch did not clear the previous Ball history");
    if (downloads.length !== exportEntries.length || uniqueNames !== downloaded.length) failures.push("SVG downloads are missing or duplicated");
    if (rootFailures.length) failures.push("SVG root is missing");
    if (titleFailures.length) failures.push("SVG title does not match chart");
    if (identityFailures.length) failures.push("SVG chart identity metadata is missing or wrong");
    if (pageErrors.length) failures.push(...pageErrors);

    const report = {
      pass: failures.length === 0,
      failures,
      browser: browserPath,
      viewer: path.resolve(viewerPath),
      dataBoundary,
      formatting,
      frameContract,
      comparisonContract,
      axisContract,
      visualContract,
      histogramContract,
      selectedId,
      history,
      historyAfterFrame,
      caseSwitch,
      exports: {
        expectedCount: exportEntries.length,
        actualCount: downloaded.length,
        uniqueNames,
        names: downloaded.map((item) => item.name),
        titleFailures: titleFailures.map((item) => item.fileName),
        rootFailures: rootFailures.map((item) => item.name),
        identityFailures: identityFailures.map((item) => item.name)
      },
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
    await context.close();
    await browser.close();
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
