// ==UserScript==
// @name         Crash Feed Inspector — SignalR Bridge
// @namespace    crash-feed-inspector
// @version      1.0.0
// @description  Forward completed OnCrash multipliers from the currently open game page to the local Termux collector.
// @match        https://*/*
// @run-at       document-start
// @sandbox     raw
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
  const MAX_RETRIES = 3;
  const seen = new Set();

  function postToBridge(body, attempt = 0) {
    const retry = reason => {
      if (attempt >= MAX_RETRIES) {
        console.warn("[Crash Feed Inspector] Bridge delivery failed after retries:", reason);
        return;
      }
      const delay = 500 * (2 ** attempt);
      setTimeout(() => postToBridge(body, attempt + 1), delay);
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
      onload: response => {
        if (response.status >= 200 && response.status < 300) {
          try {
            const result = JSON.parse(response.responseText || "{}");
            if (result.status === "conflict") {
              console.warn("[Crash Feed Inspector] Conflicting value for an existing round.");
            }
          } catch (_) {
            console.warn("[Crash Feed Inspector] Bridge returned an unreadable response.");
          }
          return;
        }
        if (response.status === 429 || response.status >= 500) {
          retry("HTTP " + response.status);
        } else {
          console.warn("[Crash Feed Inspector] Bridge rejected an event (HTTP " + response.status + ").");
        }
      },
      onerror: () => retry("network error"),
      ontimeout: () => retry("request timeout")
    });
  }

  function forward(data) {
    if (!data || typeof data !== "object") return;
    const multiplier = Number(data.f);
    if (!Number.isFinite(multiplier) || multiplier < 1 || multiplier > 99999999.9999) return;
    if (Math.abs(multiplier * 10000 - Math.round(multiplier * 10000)) > 0.00001) return;

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
    postToBridge(body);
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
  window.WebSocket = WrappedWebSocket;
})();
