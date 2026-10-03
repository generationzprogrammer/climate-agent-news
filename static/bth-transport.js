/* Text-based transport for Safari, Android and embedded browsers. No chat storage. */
(() => {
  "use strict";
  function eventParser(onEvent) {
    let buffer = "", size = 0;
    const frame = value => {
      let name = "message"; const lines = [];
      for (const line of value.split(/\r?\n/)) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        if (line.startsWith("data:")) lines.push(line.slice(5).replace(/^ /, ""));
      }
      if (lines.length) onEvent(name, JSON.parse(lines.join("\n")));
    };
    return (chunk, final = false) => {
      size += chunk.length; if (size > 1000000) throw new Error("invalid_model_response");
      buffer += chunk;
      let separator;
      while ((separator = /\r?\n\r?\n/.exec(buffer))) {
        frame(buffer.slice(0, separator.index));
        buffer = buffer.slice(separator.index + separator[0].length);
      }
      if (final && buffer.trim()) {frame(buffer); buffer = "";}
    };
  }
  function request(url, {method = "GET", payload, signal, timeout = 120000, onEvent = () => {}, onConnected = () => {}} = {}) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest(); let settled = false, offset = 0, connected = false;
      const finish = (error, value) => {
        if (settled) return; settled = true;
        signal?.removeEventListener("abort", abort);
        xhr.onload = xhr.onerror = xhr.ontimeout = xhr.onabort = xhr.onprogress = xhr.onreadystatechange = null;
        // A validated result frame is sufficient; do not wait for a proxy to close.
        if (xhr.readyState !== 4) xhr.abort();
        error ? reject(error) : resolve(value);
      };
      const abort = () => finish(new DOMException("Aborted", "AbortError"));
      const parse = eventParser((name, value) => {
        if (name === "error") {finish(new Error(value.error || "service_unavailable")); return;}
        onEvent(name, value);
        if (name === "result") finish(null, value);
      });
      const consume = final => {
        if (settled || xhr.status < 200 || xhr.status >= 300) return;
        const contentType = xhr.getResponseHeader("Content-Type") || "";
        if (contentType.includes("application/json")) {
          if (final) finish(null, JSON.parse(xhr.responseText));
          return;
        }
        if (!contentType.includes("text/event-stream")) throw new Error("service_unavailable");
        const value = xhr.responseText.slice(offset); offset = xhr.responseText.length;
        parse(value, final);
        if (final && !settled) throw new Error("invalid_model_response");
      };
      if (signal?.aborted) {abort(); return;}
      signal?.addEventListener("abort", abort, {once: true});
      xhr.open(method, url, true); xhr.timeout = timeout;
      xhr.setRequestHeader("Accept", method === "GET" ? "application/json" : "text/event-stream");
      // JSON encoded as CORS-safelisted text avoids an extra mobile preflight.
      // Origin, Turnstile and limits are still checked by the backend.
      if (payload !== undefined) xhr.setRequestHeader("Content-Type", "text/plain;charset=UTF-8");
      xhr.onreadystatechange = () => {
        if (!settled && !connected && xhr.readyState >= 2 && xhr.status) {
          connected = true; onConnected();
        }
      };
      xhr.onprogress = () => {try {consume(false);} catch (error) {finish(error);}};
      xhr.onload = () => {
        try {
          if (xhr.status < 200 || xhr.status >= 300) {
            let code = "service_unavailable";
            try {code = JSON.parse(xhr.responseText).error || code;} catch {}
            finish(new Error(code));
          } else consume(true);
        } catch (error) {finish(error);}
      };
      xhr.onerror = () => finish(new Error("network_unreachable"));
      xhr.ontimeout = () => finish(new Error("connection_timeout"));
      xhr.onabort = abort;
      xhr.send(payload === undefined ? null : JSON.stringify(payload));
    });
  }
  async function health(endpoint, signal) {
    let result;
    try {result = await request(endpoint.replace(/\/$/, "") + "/health", {signal, timeout: 10000});}
    catch (error) {if (error.message === "connection_timeout") throw new Error("network_unreachable"); throw error;}
    if (!result.ok || !result.ready) throw new Error("service_not_configured");
  }
  window.GruenBthTransport = {request, health, eventParser};
})();
