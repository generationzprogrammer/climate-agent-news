"""Private service audit: output counts only, never addresses or credentials."""
import json
import os
import urllib.request
import time
import uuid
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

# Reserved .invalid addresses cannot belong to real subscribers; no mail is sent.
# Verify that a new outsider can enter the EXACT protected list used by weekly delivery.
probe = "subscription-audit-" + uuid.uuid4().hex + "@example.invalid"
relay = "https://gruen-climate-subscriptions.pages.dev"
def submit(action, language="en"):
    request = urllib.request.Request(relay + "/" + action,
        data=json.dumps({"email":probe,"language":language}).encode(), method="POST",
        headers={"Origin":"https://generationzprogrammer.github.io","Content-Type":"text/plain;charset=UTF-8","User-Agent":"GruenSubscriptionAudit/1.0"})
    with urllib.request.urlopen(request,timeout=25) as response:
        return json.load(response)
try:
    result=submit("subscribe")
    if not (result.get("status")=="subscribed" and result.get("language")=="en"):
        raise RuntimeError("Subscription acknowledgement or language preference missing")
    confirmed=False
    for attempt in range(4):
        if attempt: time.sleep(20)
        rows=fetch_subscribers(endpoint,token,timeout=20,include_preferences=True)
        if any(row["email"]==probe and row["language"]=="en" for row in rows):
            confirmed=True
            break
    if not confirmed: raise RuntimeError("New subscriber was not found in the weekly delivery list")
    print(json.dumps({"new_external_subscriber_roundtrip":"passed","english_preference_persisted":True,"emails_sent":0}))
finally:
    result=submit("unsubscribe")
    if result.get("status")!="unsubscribed": raise RuntimeError("Synthetic subscriber cleanup was not confirmed")
    print(json.dumps({"synthetic_subscriber_cleanup":"confirmed"}))
