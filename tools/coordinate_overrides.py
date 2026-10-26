"""Apply the finalized local review before building spatial catalogue indexes."""
import hashlib
import json
import math
import re


def apply_coordinate_overrides(db, path):
    if path is None:
        return None
    raw = path.read_bytes()
    snapshot = json.loads(raw)
    records = snapshot.get('records')
    if snapshot.get('version') != 1 or not isinstance(records, dict) or not records:
        raise ValueError('Invalid finalized coordinate snapshot')
    changes = []
    for ref, item in records.items():
        if not re.fullmatch(r'PA[0-9AB]{8}', ref) or not isinstance(item, dict):
            raise ValueError('Invalid coordinate reference')
        for prefix in ('', 'original_'):
            for axis, limit in (('latitude', 90), ('longitude', 180)):
                value = item.get(prefix+axis)
                if type(value) not in (int, float) or not math.isfinite(value) or not -limit <= value <= limit:
                    raise ValueError('Invalid finalized coordinate for '+ref)
        if item.get('selection') not in ('monumentum', 'manual_final', 'original_restored'):
            raise ValueError('Unknown final coordinate selection')
        original = (item['original_latitude'], item['original_longitude'])
        target = (item['latitude'], item['longitude'])
        if item['selection'] == 'original_restored' and target != original:
            raise ValueError('Restored position differs from original for '+ref)
        current = db.execute('SELECT latitude,longitude FROM monuments WHERE reference=?', (ref,)).fetchone()
        if current is None or tuple(current) != original:
            raise ValueError('Original catalogue position changed or reference missing: '+ref)
        if target != original:
            changes.append((*target, ref))
    # Validate all records before applying any. Rebuilds always start from the
    # Ministry CSV, then reapply this snapshot, including explicit restorations.
    db.executemany('UPDATE monuments SET latitude=?,longitude=? WHERE reference=?', changes)
    return dict(snapshot_sha256=hashlib.sha256(raw).hexdigest(), review_sha256=snapshot.get('review_sha256'),
                finalized_at=snapshot.get('finalized_at'), reviewed_monuments=snapshot.get('reviewed_monuments'),
                reviewed_positions=len(records), changed_positions=len(changes),
                restored_positions=sum(item['selection']=='original_restored' for item in records.values()),
                records=records)
