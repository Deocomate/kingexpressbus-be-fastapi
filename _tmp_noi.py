import json
from pathlib import Path

rs = json.loads(
    Path("app/infrastructure/persistence/seed_data/route_stops.json").read_text(
        encoding="utf-8"
    )
)
stops = json.loads(
    Path("app/infrastructure/persistence/seed_data/stops.json").read_text(encoding="utf-8")
)
by = {s["id"]: s for s in stops}
noi = [r for r in rs if r["stop_id"] in (24, 25)]
lines = [f"noi bai route_stops in CURRENT seed: {len(noi)}"]
for r in sorted(noi, key=lambda x: (x["route_id"], x["stop_id"])):
    lines.append(
        f"  route={r['route_id']} stop={r['stop_id']} type={r['stop_type']} "
        f"prio={r['priority']} name={by[r['stop_id']]['name']}"
    )
lines.append(f"stop24 district={by[24]['district_id']}")
lines.append(f"stop25 district={by[25]['district_id']}")
lines.append(f"has stop26={26 in by}")
Path("_noi_bai_seed.txt").write_text("\n".join(lines), encoding="utf-8")
