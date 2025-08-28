import json, os
from datetime import datetime, timezone
from dateutil import tz
from constants import ARTIFACTS_DIR, TIMEZONE

os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def save_json(filename, payload):
    path = os.path.join(ARTIFACTS_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    return path

def now_local_and_utc():
    local_zone = tz.gettz(TIMEZONE)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(local_zone)
    return now_local.isoformat(timespec='seconds'), now_utc.isoformat(timespec='seconds')
