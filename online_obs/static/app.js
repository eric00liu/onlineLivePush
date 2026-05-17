const els = {
  apiStatus: document.querySelector("#apiStatus"),
  sessionStatus: document.querySelector("#sessionStatus"),
  sessionForm: document.querySelector("#sessionForm"),
  sessionId: document.querySelector("#sessionId"),
  apiToken: document.querySelector("#apiToken"),
  rtmpUrl: document.querySelector("#rtmpUrl"),
  bitrate: document.querySelector("#bitrate"),
  canvasWidth: document.querySelector("#canvasWidth"),
  canvasHeight: document.querySelector("#canvasHeight"),
  fps: document.querySelector("#fps"),
  refreshButton: document.querySelector("#refreshButton"),
  loadSessionButton: document.querySelector("#loadSessionButton"),
  sourceForm: document.querySelector("#sourceForm"),
  sourceId: document.querySelector("#sourceId"),
  sourceType: document.querySelector("#sourceType"),
  sourceValueWrap: document.querySelector("#sourceValueWrap"),
  sourceValueLabel: document.querySelector("#sourceValueLabel"),
  sourceValue: document.querySelector("#sourceValue"),
  fileUploadWrap: document.querySelector("#fileUploadWrap"),
  sourceFile: document.querySelector("#sourceFile"),
  fileLoopWrap: document.querySelector("#fileLoopWrap"),
  sourceLoop: document.querySelector("#sourceLoop"),
  volumeWrap: document.querySelector("#volumeWrap"),
  sourceVolume: document.querySelector("#sourceVolume"),
  fontWrap: document.querySelector("#fontWrap"),
  sourceFont: document.querySelector("#sourceFont"),
  clearSourceButton: document.querySelector("#clearSourceButton"),
  sourceCount: document.querySelector("#sourceCount"),
  sourcesBody: document.querySelector("#sourcesBody"),
  uploadCount: document.querySelector("#uploadCount"),
  refreshUploadsButton: document.querySelector("#refreshUploadsButton"),
  uploadList: document.querySelector("#uploadList"),
  canvasEditor: document.querySelector("#canvasEditor"),
  canvasMeta: document.querySelector("#canvasMeta"),
  selectedLayerMeta: document.querySelector("#selectedLayerMeta"),
  canvasStage: document.querySelector("#canvasStage"),
  layersBody: document.querySelector("#layersBody"),
  saveSceneButton: document.querySelector("#saveSceneButton"),
  backend: document.querySelector("#backend"),
  startButton: document.querySelector("#startButton"),
  restartButton: document.querySelector("#restartButton"),
  stopButton: document.querySelector("#stopButton"),
  pipelineButton: document.querySelector("#pipelineButton"),
  previewVideo: document.querySelector("#previewVideo"),
  previewState: document.querySelector("#previewState"),
  hlsLink: document.querySelector("#hlsLink"),
  hlsUrlText: document.querySelector("#hlsUrlText"),
  deleteSessionButton: document.querySelector("#deleteSessionButton"),
  sessionList: document.querySelector("#sessionList"),
  logsButton: document.querySelector("#logsButton"),
  outputBox: document.querySelector("#outputBox"),
  toast: document.querySelector("#toast"),
};

const state = {
  session: null,
  sessions: [],
  uploads: [],
  hls: null,
  previewTimer: null,
  statusPollTimer: null,
  previewUrl: "",
  exitLogSessionId: "",
  selectedLayerId: "",
  canvasDrag: null,
  config: {
    hlsHost: "127.0.0.1",
    hlsPort: 8888,
  },
};

const STATUS_POLL_INTERVAL_MS = 2500;

document.addEventListener("DOMContentLoaded", () => {
  els.apiToken.value = sessionStorage.getItem("onlineObsApiToken") || "";
  bindEvents();
  updateSourceFields();
  refreshAll();
  startStatusPolling();
});

function bindEvents() {
  els.sessionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runAction("会话已保存", async () => {
      const session = await persistSession();
      await loadSession(session.id);
    });
  });

  els.refreshButton.addEventListener("click", () => refreshAll());
  els.loadSessionButton.addEventListener("click", () => loadSessionFromInput());
  els.apiToken.addEventListener("input", () => {
    sessionStorage.setItem("onlineObsApiToken", els.apiToken.value.trim());
  });

  els.sourceType.addEventListener("change", updateSourceFields);
  els.sourceFile.addEventListener("change", syncFileSelection);
  els.refreshUploadsButton.addEventListener("click", () => runAction("素材已刷新", loadUploads));
  els.clearSourceButton.addEventListener("click", resetSourceForm);
  els.sourceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runAction("输入源已保存", saveSource);
  });

  els.sourcesBody.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const sourceId = button.dataset.sourceId;
    if (button.dataset.action === "edit-source") {
      fillSourceForm(sourceId);
    }
    if (button.dataset.action === "delete-source") {
      await runAction("输入源已删除", () => deleteSource(sourceId));
    }
  });

  els.uploadList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const storedName = button.dataset.storedName;
    if (button.dataset.action === "use-upload") {
      useUpload(storedName);
    }
    if (button.dataset.action === "delete-upload") {
      await runAction("素材已删除", () => deleteUpload(storedName));
    }
  });

  els.saveSceneButton.addEventListener("click", () => runAction("图层已保存", saveScene));
  els.layersBody.addEventListener("input", handleLayerTableChange);
  els.layersBody.addEventListener("change", handleLayerTableChange);
  els.layersBody.addEventListener("click", handleLayerTableClick);
  els.canvasStage.addEventListener("pointerdown", handleCanvasPointerDown);
  els.canvasWidth.addEventListener("input", renderCanvasFromTable);
  els.canvasHeight.addEventListener("input", renderCanvasFromTable);
  window.addEventListener("pointermove", handleCanvasPointerMove);
  window.addEventListener("pointerup", endCanvasDrag);
  window.addEventListener("pointercancel", endCanvasDrag);
  els.startButton.addEventListener("click", () => runAction("推流已启动", () => startSession("start")));
  els.restartButton.addEventListener("click", () => runAction("推流已重启", () => startSession("restart")));
  els.stopButton.addEventListener("click", () => runAction("推流已停止", stopSession));
  els.pipelineButton.addEventListener("click", () => runAction("命令已生成", renderPipeline));
  els.logsButton.addEventListener("click", () => runAction("日志已读取", readLogs));
  els.deleteSessionButton.addEventListener("click", () => runAction("会话已删除", deleteCurrentSession));

  els.sessionList.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-session-id]");
    if (!button) return;
    await runAction("会话已加载", () => loadSession(button.dataset.sessionId));
  });
}

async function refreshAll() {
  await runAction("已刷新", async () => {
    await checkHealth();
    await loadConfig();
    await loadUploads();
    await loadSessions();
    const currentId = normalizeId(els.sessionId.value);
    if (currentId) {
      try {
        await loadSession(currentId, { quiet: true });
      } catch {
        if (state.sessions.length) {
          await loadSession(state.sessions[0].id, { quiet: true });
        } else {
          renderEmptySession();
        }
      }
    }
  }, { quietSuccess: true });
}

async function checkHealth() {
  await api("/health");
  els.apiStatus.textContent = "API 在线";
  els.apiStatus.classList.add("ok");
  els.apiStatus.classList.remove("bad");
}

async function loadSessions() {
  const data = await api("/sessions");
  state.sessions = data.sessions || [];
  renderSessionList();
}

async function loadUploads() {
  const data = await api("/uploads");
  state.uploads = data.uploads || [];
  renderUploads();
}

async function loadConfig() {
  state.config = { ...state.config, ...(await api("/config")) };
  if (state.config.authRequired && !els.apiToken.value.trim()) {
    els.apiStatus.textContent = "API 需要 Token";
    els.apiStatus.classList.remove("ok");
  }
}

async function loadSessionFromInput() {
  const sessionId = requireSessionId();
  await runAction("会话已加载", () => loadSession(sessionId));
}

async function loadSession(sessionId, options = {}) {
  const session = await api(`/sessions/${encodeURIComponent(sessionId)}`);
  const previousStatus = state.session?.id === session.id ? state.session.status : "";
  state.session = session;
  if (session.status !== "exited") {
    state.exitLogSessionId = "";
  }
  fillSessionForm(session);
  renderSession(session);
  if (!options.quiet) {
    writeOutput(session);
  }
  await surfaceStatusTransition(previousStatus, session);
  return session;
}

async function persistSession() {
  const payload = sessionPayload();
  const sessionId = payload.id;
  const exists = state.sessions.some((session) => session.id === sessionId);
  const method = exists ? "PUT" : "POST";
  const path = exists ? `/sessions/${encodeURIComponent(sessionId)}` : "/sessions";
  const body = exists ? { canvas: payload.canvas, output: payload.output } : payload;
  const session = await api(path, { method, body });
  state.session = session;
  await loadSessions();
  return session;
}

function sessionPayload() {
  const id = requireSessionId();
  const url = els.rtmpUrl.value.trim();
  if (!url) {
    throw new Error("请填写输出 RTMP 地址");
  }
  return {
    id,
    canvas: {
      width: readInt(els.canvasWidth, "宽度"),
      height: readInt(els.canvasHeight, "高度"),
      fps: readInt(els.fps, "FPS"),
    },
    output: {
      type: "rtmp",
      url,
      bitrateKbps: readInt(els.bitrate, "码率"),
    },
  };
}

async function saveSource() {
  const session = await persistSession();
  const source = await sourcePayload();
  const existing = session.sources.some((item) => item.id === source.id);
  const path = existing
    ? `/sessions/${encodeURIComponent(session.id)}/sources/${encodeURIComponent(source.id)}`
    : `/sessions/${encodeURIComponent(session.id)}/sources`;
  await api(path, { method: existing ? "PUT" : "POST", body: source });
  await loadSession(session.id, { quiet: true });
  await saveScene({ quiet: true });
  resetSourceForm();
  await loadSession(session.id);
}

async function sourcePayload() {
  const id = normalizeId(els.sourceId.value);
  if (!id) {
    throw new Error("请填写源 ID");
  }
  const type = els.sourceType.value;
  const value = els.sourceValue.value.trim();
  const source = { id, type };
  if (["file", "audio"].includes(type) && els.sourceFile.files.length) {
    const uploaded = await uploadSourceFile(els.sourceFile.files[0]);
    els.sourceValue.value = uploaded.path;
    source.uri = uploaded.path;
    if (type === "file") {
      source.loop = els.sourceLoop.checked;
    }
    if (type === "audio") {
      source.volume = readVolume();
    }
    return source;
  }
  if (["rtmp", "rtsp", "file", "image", "audio"].includes(type)) {
    if (!value) throw new Error("请填写输入源地址");
    source.uri = value;
  }
  if (type === "file") {
    source.loop = els.sourceLoop.checked;
  }
  if (type === "audio") {
    source.volume = readVolume();
  }
  if (type === "text") {
    if (!value) throw new Error("请填写文字内容");
    source.text = value;
    source.font = els.sourceFont.value.trim() || "Sans 42";
  }
  if (type === "testsrc") {
    source.pattern = value || "smpte";
  }
  return source;
}

async function uploadSourceFile(file) {
  const form = new FormData();
  form.append("file", file);
  setPreviewStatus("正在上传文件");
  const uploaded = await api("/uploads", { method: "POST", body: form });
  await loadUploads();
  writeOutput(uploaded);
  return uploaded;
}

function useUpload(storedName) {
  const asset = state.uploads.find((item) => item.storedName === storedName);
  if (!asset) return;
  els.sourceType.value = isAudioAsset(asset) ? "audio" : "file";
  updateSourceFields();
  const currentId = normalizeId(els.sourceId.value);
  if (!currentId || currentId === "camera") {
    els.sourceId.value = slugFromFilename(asset.name || asset.storedName);
  }
  els.sourceValue.value = asset.path;
  els.sourceFile.value = "";
  showToast("素材已填入输入源");
}

async function deleteUpload(storedName) {
  const asset = state.uploads.find((item) => item.storedName === storedName);
  await api(`/uploads/${encodeURIComponent(storedName)}`, { method: "DELETE" });
  if (asset && els.sourceValue.value.trim() === asset.path) {
    els.sourceValue.value = "";
    els.sourceFile.value = "";
  }
  await loadUploads();
}

async function deleteSource(sourceId) {
  const sessionId = requireLoadedSessionId();
  const layers = collectLayers().filter((layer) => layer.sourceId !== sourceId);
  await api(`/sessions/${encodeURIComponent(sessionId)}/scene`, {
    method: "PUT",
    body: { canvas: currentCanvas(), layers },
  });
  await api(`/sessions/${encodeURIComponent(sessionId)}/sources/${encodeURIComponent(sourceId)}`, {
    method: "DELETE",
  });
  await loadSession(sessionId);
}

async function saveScene(options = {}) {
  const sessionId = requireLoadedSessionId();
  const layers = collectLayers();
  const session = await api(`/sessions/${encodeURIComponent(sessionId)}/scene`, {
    method: "PUT",
    body: { canvas: currentCanvas(), layers },
  });
  state.session = session;
  renderSession(session);
  if (!options.quiet) {
    writeOutput(session.scene);
  }
  return session;
}

async function startSession(action) {
  const session = await persistSession();
  await loadSession(session.id, { quiet: true });
  await saveScene({ quiet: true });
  const payload = { backend: els.backend.value };
  const result = await api(`/sessions/${encodeURIComponent(session.id)}/${action}`, {
    method: "POST",
    body: payload,
  });
  const previousStatus = state.session?.status || "";
  state.session = result.session;
  state.exitLogSessionId = "";
  await loadSessions();
  renderSession(result.session);
  await surfaceStatusTransition(previousStatus, result.session);
  writeOutput(result.session.pipeline);
  schedulePreview(result.session, { delayMs: 900, force: true });
}

async function stopSession() {
  const sessionId = requireLoadedSessionId();
  const session = await api(`/sessions/${encodeURIComponent(sessionId)}/stop`, { method: "POST" });
  const previousStatus = state.session?.status || "";
  state.session = session;
  state.exitLogSessionId = "";
  await loadSessions();
  renderSession(session);
  await surfaceStatusTransition(previousStatus, session);
  writeOutput(session);
  stopPreview("已停止");
}

async function renderPipeline() {
  const session = await persistSession();
  await loadSession(session.id, { quiet: true });
  await saveScene({ quiet: true });
  const pipeline = await api(`/sessions/${encodeURIComponent(session.id)}/pipeline`);
  if (state.session) {
    state.session.pipeline = pipeline;
  }
  writeOutput(pipeline);
}

async function readLogs() {
  const sessionId = requireLoadedSessionId();
  const logs = await api(`/sessions/${encodeURIComponent(sessionId)}/logs`);
  writeOutput(logs.stderr || "日志为空");
}

async function deleteCurrentSession() {
  const sessionId = requireLoadedSessionId();
  const result = await api(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  state.session = null;
  await loadSessions();
  renderEmptySession();
  writeOutput(result);
}

function renderSession(session) {
  state.session = session;
  fillSessionForm(session);
  renderSessionStatus(session);
  renderSources(session);
  renderLayers(session);
  renderSessionList();
  updateHlsLink(session);
  syncPreview(session);
}

function renderEmptySession() {
  state.session = null;
  els.sessionStatus.textContent = "未选择会话";
  els.sessionStatus.classList.remove("ok", "bad");
  els.sourcesBody.innerHTML = `<tr><td colspan="4" class="empty">暂无输入源</td></tr>`;
  els.layersBody.innerHTML = `<tr><td colspan="8" class="empty">暂无图层</td></tr>`;
  state.selectedLayerId = "";
  renderCanvas([], { width: 1280, height: 720 });
  els.sourceCount.textContent = "0";
  updateHlsLink(null);
  stopPreview("等待推流");
  renderSessionList();
}

function renderSessionStatus(session) {
  els.sessionStatus.textContent = `${session.id} · ${statusText(session.status)}`;
  els.sessionStatus.classList.toggle("ok", session.status === "running");
  els.sessionStatus.classList.toggle("bad", ["exited", "stopped"].includes(session.status));
}

function startStatusPolling() {
  clearInterval(state.statusPollTimer);
  state.statusPollTimer = setInterval(() => {
    pollSelectedSession();
  }, STATUS_POLL_INTERVAL_MS);
}

async function pollSelectedSession() {
  const sessionId = state.session?.id || normalizeId(els.sessionId.value);
  if (!sessionId) return;
  try {
    const session = await api(`/sessions/${encodeURIComponent(sessionId)}`);
    const previousStatus = state.session?.id === session.id ? state.session.status : "";
    applyPolledSession(session);
    await surfaceStatusTransition(previousStatus, session);
  } catch (error) {
    if (error.message.includes("was not found")) {
      if (state.session?.id === sessionId) {
        renderEmptySession();
      }
      return;
    }
    els.apiStatus.textContent = "API 异常";
    els.apiStatus.classList.add("bad");
    els.apiStatus.classList.remove("ok");
  }
}

function applyPolledSession(session) {
  if (!state.session || state.session.id !== session.id) {
    state.session = session;
  } else {
    state.session = {
      ...state.session,
      status: session.status,
      pipeline: session.pipeline,
    };
  }
  const listed = state.sessions.find((item) => item.id === session.id);
  if (listed) {
    listed.status = session.status;
    listed.pipeline = session.pipeline;
  }
  renderSessionStatus(state.session);
  renderSessionList();
  updateHlsLink(state.session);
  syncPreview(state.session);
}

async function surfaceStatusTransition(previousStatus, session) {
  if (session.status !== "exited") return;
  if (state.exitLogSessionId === session.id) return;
  state.exitLogSessionId = session.id;
  stopPreview("推流已退出", "error");
  const logs = await api(`/sessions/${encodeURIComponent(session.id)}/logs`);
  const stderr = logs.stderr || "进程已退出，日志为空";
  writeOutput(stderr);
  if (previousStatus && previousStatus !== "exited") {
    showToast("推流进程已退出，日志已更新", true);
  }
}

function fillSessionForm(session) {
  els.sessionId.value = session.id;
  els.canvasWidth.value = session.canvas.width;
  els.canvasHeight.value = session.canvas.height;
  els.fps.value = session.canvas.fps;
  if (session.output.type === "rtmp") {
    els.rtmpUrl.value = session.output.url;
    els.bitrate.value = session.output.bitrateKbps;
  }
}

function renderSources(session) {
  els.sourceCount.textContent = String(session.sources.length);
  if (!session.sources.length) {
    els.sourcesBody.innerHTML = `<tr><td colspan="4" class="empty">暂无输入源</td></tr>`;
    return;
  }
  els.sourcesBody.innerHTML = session.sources.map((source) => `
    <tr>
      <td>${escapeHtml(source.id)}</td>
      <td>${escapeHtml(sourceTypeText(source.type))}</td>
      <td>${escapeHtml(sourceSummary(source))}</td>
      <td>
        <div class="inline-actions">
          <button class="secondary" type="button" data-action="edit-source" data-source-id="${escapeHtml(source.id)}">编辑</button>
          <button class="danger" type="button" data-action="delete-source" data-source-id="${escapeHtml(source.id)}">删除</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderUploads() {
  els.uploadCount.textContent = `${state.uploads.length} 个文件`;
  if (!state.uploads.length) {
    els.uploadList.innerHTML = `<div class="empty">暂无上传文件</div>`;
    return;
  }
  els.uploadList.innerHTML = state.uploads.map((asset) => `
    <div class="asset-row">
      <div class="asset-main">
        <strong>${escapeHtml(asset.name || asset.storedName)}</strong>
        <span>${escapeHtml(asset.contentType || "未知类型")} · ${escapeHtml(formatBytes(asset.size))}</span>
        <code>${escapeHtml(asset.path)}</code>
      </div>
      <div class="inline-actions">
        <button class="secondary" type="button" data-action="use-upload" data-stored-name="${escapeHtml(asset.storedName)}">使用</button>
        <button class="danger" type="button" data-action="delete-upload" data-stored-name="${escapeHtml(asset.storedName)}">删除</button>
      </div>
    </div>
  `).join("");
}

function renderLayers(session) {
  const canvas = session.scene?.canvas || session.canvas;
  const existing = new Map((session.scene?.layers || []).map((layer) => [layer.sourceId, layer]));
  const visualSources = session.sources.filter((source) => source.type !== "audio");
  const layers = visualSources.map((source, index) => {
    return existing.get(source.id) || defaultLayer(source, index, canvas);
  });

  if (!layers.length) {
    els.layersBody.innerHTML = `<tr><td colspan="8" class="empty">暂无图层</td></tr>`;
    state.selectedLayerId = "";
    renderCanvas([], canvas);
    return;
  }

  if (!layers.some((layer) => layer.id === state.selectedLayerId)) {
    state.selectedLayerId = layers[0].id;
  }

  els.layersBody.innerHTML = layers.map((layer) => `
    <tr class="${layer.id === state.selectedLayerId ? "selected" : ""}" data-layer-id="${escapeHtml(layer.id)}" data-source-id="${escapeHtml(layer.sourceId)}">
      <td><input aria-label="${escapeHtml(layer.sourceId)} 显示" data-field="visible" type="checkbox" ${layer.visible ? "checked" : ""}></td>
      <td>${escapeHtml(layer.sourceId)}</td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} X" data-field="x" type="number" value="${escapeHtml(String(layer.x))}"></td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} Y" data-field="y" type="number" value="${escapeHtml(String(layer.y))}"></td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} 宽" data-field="width" type="number" min="1" value="${escapeHtml(String(layer.width))}"></td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} 高" data-field="height" type="number" min="1" value="${escapeHtml(String(layer.height))}"></td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} 透明度" data-field="alpha" type="number" min="0" max="1" step="0.05" value="${escapeHtml(String(layer.alpha))}"></td>
      <td><input aria-label="${escapeHtml(layer.sourceId)} 层级" data-field="zIndex" type="number" value="${escapeHtml(String(layer.zIndex))}"></td>
    </tr>
  `).join("");
  renderCanvas(layers, canvas);
}

function defaultLayer(source, index, canvas) {
  if (index === 0) {
    return {
      id: `${source.id}-layer`,
      sourceId: source.id,
      x: 0,
      y: 0,
      width: canvas.width,
      height: canvas.height,
      alpha: 1,
      zIndex: index,
      visible: true,
    };
  }
  const widthRatio = source.type === "text" ? 0.42 : 0.5;
  const heightRatio = source.type === "text" ? 0.18 : 0.38;
  const width = Math.max(120, Math.round(canvas.width * widthRatio));
  const height = Math.max(72, Math.round(canvas.height * heightRatio));
  const offset = Math.min(index, 5);
  return {
    id: `${source.id}-layer`,
    sourceId: source.id,
    x: Math.min(canvas.width - width, Math.round(canvas.width * 0.05 * offset)),
    y: Math.min(canvas.height - height, Math.round(canvas.height * 0.06 * offset)),
    width,
    height,
    alpha: 1,
    zIndex: index,
    visible: true,
  };
}

function renderCanvas(layers, canvas) {
  const safeCanvas = {
    width: Math.max(16, Number(canvas.width) || 1280),
    height: Math.max(16, Number(canvas.height) || 720),
  };
  els.canvasMeta.textContent = `${safeCanvas.width} x ${safeCanvas.height}`;
  els.canvasStage.style.aspectRatio = `${safeCanvas.width} / ${safeCanvas.height}`;
  if (!layers.length) {
    els.canvasStage.innerHTML = `<div class="canvas-empty">暂无图层</div>`;
    els.selectedLayerMeta.textContent = "未选择图层";
    return;
  }

  const ordered = [...layers].sort((a, b) => a.zIndex - b.zIndex);
  els.canvasStage.innerHTML = ordered.map((layer) => {
    const rect = layerPercentRect(layer, safeCanvas);
    const source = state.session?.sources.find((item) => item.id === layer.sourceId);
    const classes = [
      "canvas-layer",
      layer.visible ? "" : "hidden",
      layer.id === state.selectedLayerId ? "selected" : "",
    ].filter(Boolean).join(" ");
    return `
      <div class="${classes}" data-layer-id="${escapeHtml(layer.id)}" style="left:${rect.left}%;top:${rect.top}%;width:${rect.width}%;height:${rect.height}%;z-index:${100 + Number(layer.zIndex || 0)};opacity:${layer.visible ? Math.max(0.18, Number(layer.alpha || 1)) : 0.2};--layer-color:${sourceAccent(source)}">
        <span class="canvas-layer-label">${escapeHtml(layer.sourceId)}</span>
        <span class="canvas-layer-size">${escapeHtml(`${layer.width} x ${layer.height}`)}</span>
        <span class="canvas-resize-handle" data-resize="true" aria-hidden="true"></span>
      </div>
    `;
  }).join("");
  updateSelectedLayerMeta(layers);
}

function layerPercentRect(layer, canvas) {
  return {
    left: (Number(layer.x || 0) / canvas.width) * 100,
    top: (Number(layer.y || 0) / canvas.height) * 100,
    width: (Math.max(1, Number(layer.width || canvas.width)) / canvas.width) * 100,
    height: (Math.max(1, Number(layer.height || canvas.height)) / canvas.height) * 100,
  };
}

function sourceAccent(source) {
  const palette = {
    testsrc: "#3f7fc6",
    file: "#1f7a5d",
    image: "#9063b5",
    text: "#ad6b2b",
    rtmp: "#b24d61",
    rtsp: "#4f6f8f",
  };
  return palette[source?.type] || "#6b7280";
}

function updateSelectedLayerMeta(layers = collectLayers()) {
  const layer = layers.find((item) => item.id === state.selectedLayerId);
  if (!layer) {
    els.selectedLayerMeta.textContent = "未选择图层";
    return;
  }
  els.selectedLayerMeta.textContent = `${layer.sourceId} · ${layer.x}, ${layer.y} · ${layer.width} x ${layer.height}`;
}

function renderCanvasFromTable() {
  if (!els.layersBody.querySelector("tr[data-source-id]")) {
    renderCanvas([], safeCurrentCanvas());
    return;
  }
  renderCanvas(collectLayers(), safeCurrentCanvas());
}

function handleLayerTableClick(event) {
  const row = event.target.closest("tr[data-layer-id]");
  if (!row) return;
  selectLayer(row.dataset.layerId);
}

function handleLayerTableChange(event) {
  const row = event.target.closest("tr[data-layer-id]");
  if (row) {
    selectLayer(row.dataset.layerId, { render: false });
  }
  renderCanvasFromTable();
}

function handleCanvasPointerDown(event) {
  const layerEl = event.target.closest(".canvas-layer");
  if (!layerEl) return;
  const layer = collectLayers().find((item) => item.id === layerEl.dataset.layerId);
  if (!layer) return;
  const canvas = safeCurrentCanvas();
  const stageRect = els.canvasStage.getBoundingClientRect();
  state.canvasDrag = {
    layerId: layer.id,
    mode: event.target.closest("[data-resize]") ? "resize" : "move",
    startClientX: event.clientX,
    startClientY: event.clientY,
    startLayer: layer,
    canvas,
    stageRect,
  };
  selectLayer(layer.id);
  event.preventDefault();
}

function handleCanvasPointerMove(event) {
  if (!state.canvasDrag) return;
  const drag = state.canvasDrag;
  const dx = ((event.clientX - drag.startClientX) / drag.stageRect.width) * drag.canvas.width;
  const dy = ((event.clientY - drag.startClientY) / drag.stageRect.height) * drag.canvas.height;
  const next = { ...drag.startLayer };
  if (drag.mode === "resize") {
    next.width = Math.round(drag.startLayer.width + dx);
    next.height = Math.round(drag.startLayer.height + dy);
  } else {
    next.x = Math.round(drag.startLayer.x + dx);
    next.y = Math.round(drag.startLayer.y + dy);
  }
  updateLayerInputs(drag.layerId, clampLayer(next, drag.canvas));
  renderCanvasFromTable();
  event.preventDefault();
}

function endCanvasDrag() {
  state.canvasDrag = null;
}

function selectLayer(layerId, options = {}) {
  state.selectedLayerId = layerId || "";
  els.layersBody.querySelectorAll("tr[data-layer-id]").forEach((row) => {
    row.classList.toggle("selected", row.dataset.layerId === state.selectedLayerId);
  });
  if (options.render !== false) {
    renderCanvasFromTable();
  } else {
    updateSelectedLayerMeta();
  }
}

function updateLayerInputs(layerId, patch) {
  const row = els.layersBody.querySelector(`tr[data-layer-id="${cssEscape(layerId)}"]`);
  if (!row) return;
  for (const [field, value] of Object.entries(patch)) {
    const input = row.querySelector(`[data-field="${field}"]`);
    if (!input || field === "visible") continue;
    input.value = String(value);
  }
}

function clampLayer(layer, canvas) {
  const width = Math.min(canvas.width, Math.max(1, Math.round(Number(layer.width) || 1)));
  const height = Math.min(canvas.height, Math.max(1, Math.round(Number(layer.height) || 1)));
  return {
    x: Math.min(canvas.width - width, Math.max(0, Math.round(Number(layer.x) || 0))),
    y: Math.min(canvas.height - height, Math.max(0, Math.round(Number(layer.y) || 0))),
    width,
    height,
  };
}

function renderSessionList() {
  if (!state.sessions.length) {
    els.sessionList.innerHTML = `<div class="empty">暂无会话</div>`;
    return;
  }
  const activeId = state.session?.id || normalizeId(els.sessionId.value);
  els.sessionList.innerHTML = state.sessions.map((session) => `
    <button class="session-row ${session.id === activeId ? "active" : ""}" type="button" data-session-id="${escapeHtml(session.id)}">
      <span>
        <strong>${escapeHtml(session.id)}</strong>
        <span>${escapeHtml(session.output.type === "rtmp" ? session.output.url : session.output.type)}</span>
      </span>
      <span>${escapeHtml(statusText(session.status))}</span>
    </button>
  `).join("");
}

function collectLayers() {
  const canvas = safeCurrentCanvas();
  return [...els.layersBody.querySelectorAll("tr[data-source-id]")].map((row) => {
    const get = (field) => row.querySelector(`[data-field="${field}"]`);
    return {
      id: row.dataset.layerId,
      sourceId: row.dataset.sourceId,
      x: numberValue(get("x"), 0),
      y: numberValue(get("y"), 0),
      width: Math.max(1, numberValue(get("width"), canvas.width)),
      height: Math.max(1, numberValue(get("height"), canvas.height)),
      alpha: Math.min(1, Math.max(0, Number(get("alpha").value || 1))),
      zIndex: numberValue(get("zIndex"), 0),
      visible: get("visible").checked,
    };
  });
}

function currentCanvas() {
  return {
    width: readInt(els.canvasWidth, "宽度"),
    height: readInt(els.canvasHeight, "高度"),
    fps: readInt(els.fps, "FPS"),
  };
}

function safeCurrentCanvas() {
  return {
    width: Math.max(16, Number(els.canvasWidth.value) || 1280),
    height: Math.max(16, Number(els.canvasHeight.value) || 720),
    fps: Math.max(1, Number(els.fps.value) || 30),
  };
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return CSS.escape(value);
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function fillSourceForm(sourceId) {
  const source = state.session?.sources.find((item) => item.id === sourceId);
  if (!source) return;
  els.sourceId.value = source.id;
  els.sourceType.value = source.type;
  updateSourceFields();
  if (source.type === "text") {
    els.sourceValue.value = source.text || "";
    els.sourceFont.value = source.font || "Sans 42";
  } else if (source.type === "testsrc") {
    els.sourceValue.value = source.pattern || "smpte";
  } else {
    els.sourceValue.value = source.uri || "";
  }
  els.sourceLoop.checked = Boolean(source.loop);
  els.sourceVolume.value = String(source.volume ?? 1);
  els.sourceFile.value = "";
}

function resetSourceForm() {
  els.sourceId.value = "camera";
  els.sourceType.value = "testsrc";
  els.sourceValue.value = "smpte";
  els.sourceFont.value = "Sans 42";
  els.sourceFile.value = "";
  els.sourceLoop.checked = false;
  els.sourceVolume.value = "1";
  updateSourceFields();
}

function updateSourceFields() {
  const type = els.sourceType.value;
  els.fileUploadWrap.style.display = ["file", "audio"].includes(type) ? "grid" : "none";
  els.fileLoopWrap.style.display = type === "file" ? "flex" : "none";
  els.volumeWrap.style.display = type === "audio" ? "grid" : "none";
  els.fontWrap.style.display = type === "text" ? "grid" : "none";
  if (type === "text") {
    els.sourceValueLabel.textContent = "文字";
    els.sourceValue.placeholder = "直播标题";
  } else if (type === "testsrc") {
    els.sourceValueLabel.textContent = "测试图案";
    els.sourceValue.placeholder = "smpte";
  } else if (type === "file") {
    els.sourceValueLabel.textContent = "服务器路径";
    els.sourceValue.placeholder = "选择文件上传，或填写 /Users/.../demo.mp4";
  } else if (type === "audio") {
    els.sourceValueLabel.textContent = "音频地址";
    els.sourceValue.placeholder = "选择音频上传，或填写 /Users/.../music.wav";
  } else {
    els.sourceValueLabel.textContent = "输入地址";
    els.sourceValue.placeholder = type === "rtsp" ? "rtsp://..." : "rtmp://...";
  }
}

function syncFileSelection() {
  const file = els.sourceFile.files[0];
  if (!file) return;
  if (file.type.startsWith("audio/")) {
    els.sourceType.value = "audio";
    updateSourceFields();
  }
  if (normalizeId(els.sourceId.value) === "camera") {
    els.sourceId.value = slugFromFilename(file.name);
  }
  els.sourceValue.value = file.name;
}

function updateHlsLink(session) {
  const url = session?.output?.type === "rtmp" ? deriveHlsUrl(session.output.url) : "";
  if (!url) {
    els.hlsLink.href = "#";
    els.hlsLink.classList.add("disabled");
    els.hlsUrlText.textContent = "未生成 m3u8";
    return;
  }
  els.hlsLink.href = url;
  els.hlsUrlText.textContent = url;
  els.hlsLink.classList.remove("disabled");
}

function syncPreview(session) {
  if (session?.status === "running") {
    schedulePreview(session, { delayMs: 200 });
    return;
  }
  if (session?.status === "exited") {
    stopPreview("推流已退出", "error");
    return;
  }
  if (session?.status === "stopped") {
    stopPreview("已停止");
    return;
  }
  setPreviewStatus("等待推流");
}

function schedulePreview(session, options = {}) {
  const url = session?.output?.type === "rtmp" ? deriveHlsUrl(session.output.url) : "";
  clearTimeout(state.previewTimer);
  if (!url) {
    stopPreview("未生成 m3u8");
    return;
  }
  state.previewTimer = setTimeout(() => {
    loadPreview(url, { force: options.force });
  }, options.delayMs ?? 0);
}

function loadPreview(url, options = {}) {
  if (!options.force && state.previewUrl === url && !els.previewVideo.paused) {
    setPreviewStatus("正在播放", "live");
    return;
  }

  teardownHls();
  state.previewUrl = url;
  els.previewVideo.muted = true;
  els.previewVideo.autoplay = true;
  els.previewVideo.playsInline = true;
  setPreviewStatus("连接 m3u8");

  if (window.Hls?.isSupported()) {
    const hls = new Hls({
      backBufferLength: 30,
      enableWorker: true,
      liveDurationInfinity: true,
      lowLatencyMode: true,
    });
    state.hls = hls;
    hls.on(Hls.Events.MEDIA_ATTACHED, () => {
      hls.loadSource(url);
    });
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      playPreview();
    });
    hls.on(Hls.Events.ERROR, (event, data) => {
      if (!data?.fatal) return;
      setPreviewStatus("m3u8 等待中", "error");
      teardownHls();
      state.previewTimer = setTimeout(() => {
        if (state.session?.status === "running") {
          loadPreview(url, { force: true });
        }
      }, 1600);
    });
    hls.attachMedia(els.previewVideo);
    return;
  }

  if (els.previewVideo.canPlayType("application/vnd.apple.mpegurl")) {
    els.previewVideo.src = url;
    els.previewVideo.addEventListener("loadedmetadata", playPreview, { once: true });
    els.previewVideo.load();
    return;
  }

  stopPreview("HLS 播放器不可用", "error");
}

function playPreview() {
  const result = els.previewVideo.play();
  if (result?.catch) {
    result
      .then(() => setPreviewStatus("正在播放", "live"))
      .catch(() => setPreviewStatus("已加载，点击播放"));
    return;
  }
  setPreviewStatus("正在播放", "live");
}

function stopPreview(message = "等待推流", tone = "") {
  clearTimeout(state.previewTimer);
  teardownHls();
  state.previewUrl = "";
  els.previewVideo.pause();
  els.previewVideo.removeAttribute("src");
  els.previewVideo.load();
  setPreviewStatus(message, tone);
}

function teardownHls() {
  if (state.hls) {
    state.hls.destroy();
    state.hls = null;
  }
}

function setPreviewStatus(message, tone = "") {
  els.previewState.textContent = message;
  els.previewState.classList.toggle("live", tone === "live");
  els.previewState.classList.toggle("error", tone === "error");
}

function deriveHlsUrl(rtmpUrl) {
  try {
    const url = new URL(rtmpUrl);
    const path = url.pathname.replace(/^\/+/, "");
    if (!path) return "";
    const hlsHost = state.config.hlsHost || (
      url.hostname === "localhost" || url.hostname === "127.0.0.1" ? "127.0.0.1" : url.hostname
    );
    const hlsPort = Number(state.config.hlsPort || 8888);
    const host = hlsHost.includes(":") ? hlsHost : `${hlsHost}:${hlsPort}`;
    return `http://${host}/${path}/index.m3u8`;
  } catch {
    return "";
  }
}

async function api(path, options = {}) {
  const init = {
    method: options.method || "GET",
    headers: {},
  };
  if (options.body !== undefined) {
    if (options.body instanceof FormData) {
      init.body = options.body;
    } else {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
  }
  const token = els.apiToken?.value.trim() || sessionStorage.getItem("onlineObsApiToken") || "";
  if (token) {
    init.headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(path, init);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = payload.error?.message || `请求失败: ${response.status}`;
    const details = payload.error?.details ? `\n${JSON.stringify(payload.error.details, null, 2)}` : "";
    throw new Error(`${message}${details}`);
  }
  return payload;
}

async function runAction(successMessage, action, options = {}) {
  setBusy(true);
  try {
    const result = await action();
    if (!options.quietSuccess) showToast(successMessage);
    return result;
  } catch (error) {
    els.apiStatus.textContent = "API 异常";
    els.apiStatus.classList.add("bad");
    showToast(error.message, true);
    writeOutput(error.message);
    throw error;
  } finally {
    setBusy(false);
  }
}

function setBusy(isBusy) {
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = isBusy;
  });
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    els.toast.classList.remove("show");
  }, 2600);
}

function writeOutput(value) {
  els.outputBox.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function sourceSummary(source) {
  if (source.type === "text") return source.text;
  if (source.type === "testsrc") return source.pattern;
  if (source.type === "file") return `${source.uri}${source.loop ? " · loop" : ""}`;
  if (source.type === "audio") return `${source.uri} · 音量 ${Number(source.volume ?? 1).toFixed(2)}`;
  return source.uri;
}

function sourceTypeText(type) {
  return {
    testsrc: "测试画面",
    rtmp: "RTMP",
    rtsp: "RTSP",
    file: "文件",
    audio: "音频",
    image: "图片",
    text: "文字",
  }[type] || type;
}

function formatBytes(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "0 B";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

function statusText(status) {
  return {
    idle: "待机",
    running: "运行中",
    stopped: "已停止",
    exited: "已退出",
  }[status] || status;
}

function requireSessionId() {
  const id = normalizeId(els.sessionId.value);
  if (!id) {
    throw new Error("请填写会话 ID");
  }
  return id;
}

function requireLoadedSessionId() {
  if (state.session?.id) return state.session.id;
  return requireSessionId();
}

function normalizeId(value) {
  return value.trim();
}

function readInt(input, label) {
  const value = Number(input.value);
  if (!Number.isInteger(value) || value < Number(input.min || 0)) {
    throw new Error(`${label} 数值无效`);
  }
  return value;
}

function numberValue(input, fallback) {
  const value = Number(input.value);
  return Number.isFinite(value) ? value : fallback;
}

function readVolume() {
  const value = Number(els.sourceVolume.value);
  if (!Number.isFinite(value) || value < 0 || value > 2) {
    throw new Error("音量必须在 0 到 2 之间");
  }
  return value;
}

function slugFromFilename(filename) {
  const withoutExt = filename.replace(/\.[^.]+$/, "");
  const slug = withoutExt
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return slug || "clip";
}

function isAudioAsset(asset) {
  return String(asset.contentType || "").startsWith("audio/");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
