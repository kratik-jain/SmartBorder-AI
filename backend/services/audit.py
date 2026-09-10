import hashlib, json
from datetime import datetime

def event_hash(case_id, actor, event_type, details, previous_hash=''):
    payload=f'{case_id}|{actor}|{event_type}|{json.dumps(details,sort_keys=True)}|{previous_hash}|{datetime.utcnow().isoformat()}'
    return hashlib.sha256(payload.encode()).hexdigest()
