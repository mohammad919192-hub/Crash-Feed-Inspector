// ==UserScript==
// @name         Crash Feed Inspector — SignalR Bridge
// @namespace    crash-feed-inspector
// @version      1.0.0
// @description  Forward completed OnCrash multipliers from the currently open game page to the local Termux collector.
// @match        https://*/*
// @match        http://*/*
// @run-at       document-start
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

(() => {
  "use strict";

  // Set this to the same local-only token in Crash-Feed-Inspector/.env.
  const BRIDGE_URL = "http://127.0.0.1:8765/crash";
  const BRIDGE_TOKEN = "REPLACE_WITH_LOCAL_CRASH_BRIDGE_TOKEN";
  const TARGET_PATH = "/sockets/crash";
  const MAX_SEEN = 2000;
  const seen = new Set();

  function forward(data) {
    if (!data || typeof data !== "object") return;
    const multiplier = Number(data.f);
    if (!Number.isFinite(multiplier) || multiplier < 1 || multiplier > 1e9) return;

    const eventId = (globalThis.crypto?.randomUUID?.() ||
      (Date.now().toString(36) + Math.random().toString(36).slice(2)));
    if (seen.has(eventId)) return;
    seen.add(eventId);
    if (seen.size > MAX_SEEN) seen.clear();

    const body = {
      event: "OnCrash",
      eventId,
      observedAtMs: Date.now(),
      host: location.hostname,
      data: { f: multiplier, l: data.l ?? null }
    };

    GM_xmlhttpRequest({
      method: "POST",
      url: BRIDGE_URL,
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + BRIDGE_TOKEN
      },
      data: JSON.stringify(body),
      timeout: 5000,
      onerror: () => console.warn("[Crash Feed Inspector] Local bridge unavailable."),
      ontimeout: () => console.warn("[Crash Feed Inspector] Local bridge timed out.")
    });
  }

  function inspectFrame(raw) {
    const text = typeof raw === "string" ? raw : "";
    for (const part of text.split("\x1e")) {
      const frame = part.trim();
      if (!frame || frame === "{}") continue;
      let message;
      try { message = JSON.parse(frame); } catch { continue; }
      if (message?.type !== 1 || message?.target !== "OnCrash") continue;
      const data = Array.isArray(message.arguments) ? message.arguments[0] : null;
      forward(data);
    }
  }

  const NativeWebSocket = window.WebSocket;
  if (!NativeWebSocket) return;

  const WrappedWebSocket = new Proxy(NativeWebSocket, {
    construct(Target, args) {
      const socket = Reflect.construct(Target, args, Target);
      const url = String(args[0] || "");
      if (url.toLowerCase().includes(TARGET_PATH)) {
        socket.addEventListener("message", event => {
          if (typeof event.data === "string") inspectFrame(event.data);
        });
        console.info("[Crash Feed Inspector] Monitoring crash events on this page.");
      }
      return socket;
    }
  });
  WrappedWebSocket.prototype = NativeWebSocket.prototype;
  Object.setPrototypeOf(WrappedWebSocket, NativeWebSocket);
  window.WebSocket = WrappedWebSocket;
})();
