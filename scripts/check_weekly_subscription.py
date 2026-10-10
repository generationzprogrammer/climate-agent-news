"""Private service audit: output counts only, never addresses or credentials."""
import json
import os
import urllib.request
from climate_agent.providers import fetch_subscribers, resolve_subscriber_endpoint

form = os.getenv("CLIMATE_SUBSCRIBE_ENDPOINT", "").strip()
token = os.getenv("CLIMATE_SUBSCRIBER_ADMIN_TOKEN", "").strip()
if not form or not token:
    raise SystemExit("Required subscription configuration is missing; no credentials printed.")
endpoint = resolve_subscriber_endpoint(form, os.getenv("CLIMATE_WEEKLY_SUBSCRIBERS_ENDPOINT", ""))
public = "https://generationzprogrammer.github.io/climate-agent-news/data/subscription.json"
with urllib.request.urlopen(urllib.request.Request(public,headers={"User-Agent":"GruenSubscriptionAudit/1.0"}),timeout=20) as response:
    live = json.load(response)
if live.get("endpoint", "").rstrip("/") != form.rstrip("/"):
    raise SystemExit("The published form differs from the weekly subscription service. Rebuild Pages first.")
subscribers = fetch_subscribers(endpoint,token,timeout=20)
fixed = {x.strip().lower() for x in os.getenv("CLIMATE_WEEKLY_SUBSCRIBERS", "").split(",") if x.strip()}
print(json.dumps({"public_form_and_weekly_reader":"same_service", "subscriber_endpoint":"ok",
                  "active_subscribers":len(subscribers), "subscribers_outside_fixed_list":len(set(subscribers)-fixed),
                  "credentials_or_addresses_logged":False, "emails_sent_by_this_check":0}))
