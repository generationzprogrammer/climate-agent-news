const json = (payload, status = 200, origin = "") => new Response(JSON.stringify(payload), {
  status,
  headers: {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type,authorization",
    "cache-control": "no-store",
    "vary": "origin",
  },
});

const normaliseEmail = value => String(value || "").trim().toLowerCase();
const validEmail = value => /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/.test(value);

async function keyFor(email) {
  const data = new TextEncoder().encode(email);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return `subscriber:${[...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, "0")).join("")}`;
}

function allowedOrigin(request, env) {
  const configured = String(env.CLIMATE_ALLOWED_ORIGIN || "https://generationzprogrammer.github.io").replace(/\/$/, "");
  const origin = String(request.headers.get("origin") || "").replace(/\/$/, "");
  return origin === configured ? configured : "";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = allowedOrigin(request, env);
    if (request.method === "OPTIONS") {
      return origin ? json({ ok: true }, 200, origin) : json({ error: "origin_not_allowed" }, 403, "null");
    }
    if (url.pathname === "/health") return json({ ok: true, service: "climate-news-subscriptions" }, 200, origin || "null");
    if (url.pathname === "/subscribers" && request.method === "GET") {
      const auth = request.headers.get("authorization") || "";
      if (!env.CLIMATE_SUBSCRIBER_ADMIN_TOKEN || auth !== `Bearer ${env.CLIMATE_SUBSCRIBER_ADMIN_TOKEN}`) return json({ error: "unauthorized" }, 401, "null");
      const emails = [];
      let cursor;
      do {
        const page = await env.CLIMATE_SUBSCRIBERS_KV.list({ prefix: "subscriber:", cursor });
        for (const key of page.keys) {
          const record = await env.CLIMATE_SUBSCRIBERS_KV.get(key.name, "json");
          if (record?.status === "active" && validEmail(record.email)) emails.push(record.email);
        }
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      return json({ subscribers: [...new Set(emails)].sort() }, 200, "null");
    }
    if (!origin) return json({ error: "origin_not_allowed" }, 403, "null");
    if (!["/subscribe", "/unsubscribe"].includes(url.pathname) || request.method !== "POST") {
      return json({ error: "not_found" }, 404, origin);
    }
    let body;
    try {
      body = await request.json();
    } catch (_) {
      return json({ error: "invalid_json" }, 400, origin);
    }
    const email = normaliseEmail(body.email);
    if (!validEmail(email)) return json({ error: "invalid_email" }, 400, origin);
    const key = await keyFor(email);
    if (url.pathname === "/unsubscribe") {
      await env.CLIMATE_SUBSCRIBERS_KV.delete(key);
      return json({ ok: true, status: "unsubscribed" }, 200, origin);
    }
    await env.CLIMATE_SUBSCRIBERS_KV.put(key, JSON.stringify({
      email,
      status: "active",
      subscribed_at: new Date().toISOString(),
      source: "climate-agent-news",
    }));
    return json({ ok: true, status: "subscribed" }, 201, origin);
  },
};
