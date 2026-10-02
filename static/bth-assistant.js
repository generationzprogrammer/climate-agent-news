/* BTH live assistant. Conversation stays in memory; no API key or subscriber data. */
(() => {
  "use strict";
  const chat = {messages: [], busy: false, root: null, language: "zh", config: null, token: "", widget: null, pending: ""};
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const label = (zh, en) => chat.language === "en" ? en : zh;
  const errorLabels = {
    service_not_configured: "管理员尚未启用模型服务。", verification_failed: "安全验证已过期，请重新验证后提交。",
    daily_limit: "今日使用额度已满，请明天再试。", slow_down: "提问过于频繁，请稍等10秒。",
    model_key_invalid: "模型密钥配置无效，请联系管理员。", model_quota_or_permission: "模型免费额度已用完或未开通权限。",
    model_rate_limit: "模型服务繁忙，请稍后重试。", model_timeout: "模型响应超时，请缩短请求后重试。",
    invalid_model_response: "模型输出不完整，本次未生成文件；请重试或缩短报告。",
  };
  let configPromise, turnstilePromise;
  async function configuration() {
    configPromise ||= fetch("./data/bth_assistant_config.json", {cache: "no-cache"}).then(r => {if (!r.ok) throw new Error("config_unavailable"); return r.json();});
    return configPromise;
  }
  function turnstileScript() {
    if (window.turnstile) return Promise.resolve();
    turnstilePromise ||= new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.onload = resolve; script.onerror = () => reject(new Error("verification_unavailable"));
      document.head.append(script);
    });
    return turnstilePromise;
  }
  function status(value) {const node = chat.root?.querySelector(".bth-chat-status"); if (node) node.textContent = value;}
  function answerHtml(message) {
    return message.result ? window.GruenBthReport.citationText(message.content, message.result.sources, {html: true, language: chat.language}) : esc(message.content);
  }
  function sourceHtml(source, index) {
    const title = `[${index + 1}] ${source.title} · ${source.source}${source.locator ? ` · ${source.locator}` : ""}`;
    const url = window.GruenBthReport.sourceUrl(source.url);
    return url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)}</a>` : `<span>${esc(title)}</span>`;
  }
  function messages() {
    const root = chat.root?.querySelector(".bth-chat-messages"); if (!root) return;
    root.innerHTML = chat.messages.map((m, index) => `<article class="bth-chat-message ${m.role}"><b>${esc(m.role === "user" ? label("您", "You") : label("研究助手", "Research assistant"))}</b><div class="bth-chat-answer">${answerHtml(m)}</div>${m.result ? `<div class="bth-chat-sources">${m.result.sources.map(sourceHtml).join("")}</div><div class="bth-chat-charts">${m.result.charts.map(c => window.GruenBthReport.chartSvg(c, m.result.sources)).join("")}</div><div class="bth-chat-downloads"><button type="button" data-export="docx" data-answer="${index}">${label("下载Word", "Download Word")}</button><button type="button" data-export="pdf" data-answer="${index}">${label("下载PDF", "Download PDF")}</button>${m.result.charts.map((c, i) => `<button type="button" data-export="png" data-answer="${index}" data-chart="${i}">${label("下载图", "Download chart")} ${i + 1}</button>`).join("")}</div>` : ""}</article>`).join("") + (chat.busy ? `<article class="bth-chat-message assistant streaming"><b>${label("研究助手", "Research assistant")}</b><div class="bth-chat-answer">${esc(window.GruenBthReport.citationText(chat.pending, [], {streaming: true}) || label("正在检索与分析…", "Retrieving evidence…"))}</div></article>` : "");
    root.querySelectorAll("[data-export]").forEach(button => button.addEventListener("click", async () => {
      const result = chat.messages[Number(button.dataset.answer)].result;
      button.disabled = true;
      try {await window.GruenBthReport.download(result, button.dataset.export, Number(button.dataset.chart || 0));}
      catch (e) {status(label("文件生成失败，请重试。", "Export failed. Please retry."));}
      finally {button.disabled = false;}
    }));
    root.scrollTop = root.scrollHeight;
  }
  function partialAnswer(raw) {
    const match = /"answer"\s*:\s*"/.exec(raw); if (!match) return "";
    const start = match.index + match[0].length; let escape = false, end = start;
    for (; end < raw.length; end++) {const c = raw[end]; if (!escape && c === '"') break; if (!escape && c === "\\") escape = true; else escape = false;}
    let value = raw.slice(start, end);
    if (escape) value = value.slice(0, -1);
    value = value.replace(/\\u[0-9a-fA-F]{0,3}$/, "");
    try {return JSON.parse('"' + value + '"');} catch {return chat.pending;}
  }
  async function submit(event) {
    event.preventDefault(); if (chat.busy) return;
    const input = chat.root.querySelector("textarea"), question = input.value.trim(); if (!question) return;
    if (!chat.config?.endpoint || !chat.config?.sitekey) {status(label("实时服务待管理员启用。", "Live service awaits administrator setup.")); return;}
    if (!chat.token) {status(label("请先完成安全验证；若无法加载，请检查网络。", "Complete the security check first.")); return;}
    const history = chat.messages.filter(m => m.role !== "error").slice(-6).map(m => ({role: m.role, content: m.content.slice(0, 1000)}));
    chat.messages.push({role: "user", content: question}); input.value = ""; chat.busy = true; chat.pending = "";
    const token = chat.token; chat.token = "";
    chat.controller = new AbortController(); const timer = setTimeout(() => chat.controller.abort(), 105000);
    chat.root.querySelector(".bth-chat-send").disabled = true;
    chat.root.querySelector(".bth-chat-stop").hidden = false;
    let raw = "", gotResult = false, reader;
    messages(); status(label("正在连接模型…", "Connecting to the model…"));
    try {
      const response = await fetch(chat.config.endpoint.replace(/\/$/, "") + "/chat", {method: "POST", signal: chat.controller.signal, headers: {"Content-Type": "application/json"}, body: JSON.stringify({question, history, token})});
      if (!response.ok) {const error = await response.json().catch(() => ({})); throw new Error(error.error || "service_unavailable");}
      reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const {done, value} = await reader.read(); if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const frames = buffer.split(/\r?\n\r?\n/); buffer = frames.pop();
        for (const frame of frames) {
          const name = /^event: (.+)$/m.exec(frame)?.[1], data = /^data: (.+)$/m.exec(frame)?.[1]; if (!data) continue;
          const payload = JSON.parse(data);
          if (name === "status") status(label(`已检索 ${payload.evidence_count} 条证据，正在分析…`, `${payload.evidence_count} evidence records retrieved…`));
          if (name === "delta") {raw += payload.text; chat.pending = partialAnswer(raw); messages();}
          if (name === "error") throw new Error(payload.error);
          if (name === "result") {chat.messages.push({role: "assistant", content: payload.answer, result: payload}); gotResult = true; status(label("回答完成", "Completed"));}
        }
      }
      if (!gotResult) throw new Error("invalid_model_response");
    } catch (e) {status(e.name === "AbortError" ? label("已停止；未完成的结果不会保存。", "Stopped. Incomplete results are not saved.") : label(errorLabels[e.message] || "连接失败，请检查网络或稍后重试。", `Request failed: ${e.message}`));}
    finally {
      clearTimeout(timer); await reader?.cancel().catch(() => {}); chat.busy = false; chat.pending = "";
      chat.root?.querySelector(".bth-chat-send")?.removeAttribute("disabled");
      const stop = chat.root?.querySelector(".bth-chat-stop"); if (stop) stop.hidden = true;
      if (window.turnstile && chat.widget !== null) window.turnstile.reset(chat.widget);
      messages();
    }
  }
  async function mount(root, language) {
    if (window.turnstile && chat.widget !== null) {window.turnstile.remove(chat.widget); chat.widget = null; chat.token = "";}
    chat.root = root; chat.language = language || "zh"; if (!root) return;
    root.innerHTML = `<section class="bth-live-assistant"><div class="bth-chat-heading"><h3>${label("京津冀研究问答", "BTH research assistant")}</h3><button type="button" class="secondary bth-chat-clear">${label("清空对话", "Clear conversation")}</button></div><div class="bth-chat-messages" role="log" aria-label="${label("对话记录", "Conversation")}" aria-live="off"></div><form class="bth-chat-form"><label for="bthChatQuestion">${label("问题", "Question")}</label><textarea id="bthChatQuestion" rows="3" maxlength="2000" required placeholder="${label("例如：比较三地2025年的光伏装机规模，生成图表和简短报告。", "Compare 2025 solar capacity across Beijing, Tianjin and Hebei; generate a chart and a short report.")}"></textarea><div class="bth-turnstile"></div><div class="bth-chat-controls"><button class="bth-chat-send" type="submit" ${chat.busy ? "disabled" : ""}>${label("发送", "Send")}</button><button class="secondary bth-chat-stop" type="button" ${chat.busy ? "" : "hidden"}>${label("停止", "Stop")}</button><span class="bth-chat-status" role="status"></span></div><details class="bth-chat-privacy"><summary>${label("数据与隐私", "Data and privacy")}</summary><p>${label("问题、最近三轮对话和检索到的公开资料会发送至阿里云百炼。本站不保存对话；请勿输入个人隐私或未公开资料。回答中的分析判断不等于官方结论，政策条款请核对原文。", "Your question, the latest three turns and public evidence are sent to Alibaba Cloud Model Studio. This site does not retain chats. Do not enter personal or confidential information. Check original policies before relying on specific provisions.")}</p></details></form></section>`;
    root.querySelector("form").addEventListener("submit", submit);
    root.querySelector(".bth-chat-stop").addEventListener("click", () => chat.controller?.abort());
    root.querySelector(".bth-chat-clear").addEventListener("click", () => {if (!chat.busy) {chat.messages = []; messages(); status("");}});
    messages();
    try {
      chat.config = await configuration(); if (!root.isConnected || root !== chat.root) return;
      if (!chat.config.endpoint || !chat.config.sitekey) {status(label("实时服务待管理员启用。", "Live service awaits administrator setup.")); return;}
      await turnstileScript(); if (!root.isConnected || root !== chat.root) return;
      chat.widget = window.turnstile.render(root.querySelector(".bth-turnstile"), {sitekey: chat.config.sitekey, action: "bth_chat", callback: token => {chat.token = token;}, "expired-callback": () => {chat.token = "";}, "error-callback": () => {chat.token = ""; status(label("安全验证暂不可用，请检查网络。", "Security verification is unavailable."));}});
    } catch {status(label("实时服务配置或安全验证加载失败。", "Could not load service configuration or verification."));}
  }
  window.GruenBthAssistant = {mount};
})();
