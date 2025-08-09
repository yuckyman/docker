import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone

import requests

try:
    import wearipedia
except Exception as e:  # pragma: no cover
    wearipedia = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("cronometer-sync")


def env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise SystemExit(f"Missing required env var: {name}")
    return val or ""


def compute_range(days: int) -> tuple[str, str]:
    tz = os.environ.get("TZ", "UTC")
    # For simplicity, use UTC; logs show TZ separately
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start.date().isoformat(), end.date().isoformat()


def fetch_cronometer(start: str, end: str) -> dict:
    source = env("CRONOMETER_SOURCE", "WEARIPEDIA").upper()
    if source != "WEARIPEDIA":
        raise SystemExit("Only WEARIPEDIA source supported in this image (CSV not implemented)")
    if wearipedia is None:
        raise SystemExit("wearipedia import failed - can't fetch data")

    username = env("CRONOMETER_EMAIL", required=True)
    password = env("CRONOMETER_PASSWORD", required=True)

    device = wearipedia.get_device("cronometer/cronometer")
    device.authenticate({"username": username, "password": password})
    params = {"start_date": start, "end_date": end}

    logger.info("Fetching Cronometer data %s -> %s", start, end)
    daily_summary = device.get_data("dailySummary", params=params)
    servings = device.get_data("servings", params=params)
    exercises = device.get_data("exercises", params=params)
    biometrics = device.get_data("biometrics", params=params)

    return {
        "dailySummary": daily_summary,
        "servings": servings,
        "exercises": exercises,
        "biometrics": biometrics,
    }


def post_to_wger(payload: dict) -> None:
    api_base = env("WGER_API_URL", "http://web:8000").rstrip("/")
    token = env("WGER_API_TOKEN", required=False)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"

    # This part is intentionally conservative: we just stash the fetched JSON into
    # a custom endpoint if available; otherwise we no-op with a log.
    # You can replace the following path with real wger endpoints or a Django mgmt command.
    url = f"{api_base}/api/v2/external/cronometer-ingest/"  # hypothetical endpoint
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if resp.status_code == 404:
            logger.warning("Ingest endpoint not found (%s). Dumping to log only.", url)
            logger.info("Fetched sample (truncated): %s", json.dumps(payload)[:2000])
            return
        resp.raise_for_status()
        logger.info("Posted Cronometer sync: %s", resp.status_code)
    except requests.RequestException as e:
        logger.error("Failed posting to wger: %s", e)
        # Do not crash the container on transient failure


def post_weight_entries(payload: dict) -> None:
    """Post weight biometrics to wger's weight diary via REST.

    - Converts pounds to kilograms if needed
    - Skips if API token not provided
    - Idempotent by date: checks for an existing entry on the date before posting
    """
    token = env("WGER_API_TOKEN", required=False)
    if not token:
        logger.info("No WGER_API_TOKEN set; skipping weightentry post")
        return

    api_base = env("WGER_API_URL", "http://web:8000").rstrip("/")
    headers = {"Content-Type": "application/json", "Authorization": f"Token {token}"}
    weights = []

    for item in payload.get("biometrics", []) or []:
        if str(item.get("Metric", "")).lower() != "weight":
            continue
        day = item.get("Day")
        unit = (item.get("Unit") or "").lower()
        amount = item.get("Amount")
        if not day or amount is None:
            continue
        try:
            value = float(amount)
        except (TypeError, ValueError):
            continue
        # Convert to kilograms if the unit is lbs; otherwise assume it's already kg
        if unit in ("lb", "lbs", "pound", "pounds"):
            value = value * 0.45359237
        weights.append({"date": day, "weight": round(value, 2)})

    if not weights:
        logger.info("No weight biometrics found to post")
        return

    list_url = f"{api_base}/api/v2/weightentry/"
    for entry in weights:
        date = entry["date"]
        try:
            # check existing entries for that date to avoid duplicates
            check = requests.get(f"{list_url}?date={date}", headers=headers, timeout=15)
            if check.ok:
                data = check.json()
                if isinstance(data, dict) and (data.get("count") or 0) > 0:
                    logger.info("Weightentry exists for %s, skipping", date)
                    continue
            resp = requests.post(list_url, headers=headers, data=json.dumps(entry), timeout=15)
            if not resp.ok:
                logger.warning("Failed to post weightentry %s: %s %s", date, resp.status_code, resp.text[:200])
            else:
                logger.info("Posted weightentry for %s", date)
        except requests.RequestException as e:
            logger.warning("Network error posting weightentry for %s: %s", date, e)

def main() -> int:
    try:
        days = int(env("CRONOMETER_RANGE_DAYS", "3"))
    except ValueError:
        days = 3
    start, end = compute_range(days)

    try:
        payload = fetch_cronometer(start, end)
    except SystemExit:
        raise
    except Exception as e:  # pragma: no cover
        logger.exception("Fetch failed: %s", e)
        return 1

    try:
        post_to_wger(payload)
        post_weight_entries(payload)
    except Exception as e:  # pragma: no cover
        logger.exception("Post failed: %s", e)
        return 2

    logger.info("Sync done: %s -> %s", start, end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
