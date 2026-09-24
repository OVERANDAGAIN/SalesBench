"""Host-only fact exports. No raw journal, message bodies, requests or credentials."""
import csv
import json
from pathlib import Path


def export_metrics(report, directory: Path, format: str):
    if format not in ("json", "csv"):
        raise ValueError("Supported formats: json, csv")
    directory.mkdir(parents=True, exist_ok=False)  # Never overwrite an earlier export.
    files = []
    if format == "json":
        target = directory / "metrics.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files.append(target.name)
    else:
        tables = {"session": [report["summary"]], "sellers": report["sellers"], "buyers": report["buyers"],
                  "ticks": report["tick_history"], "prices": report["price_trajectory"], "profits": report["profit_trajectory"],
                  "ranks": [{"leaderboard_snapshot_id": board["leaderboard_snapshot_id"],
                             "source_publication_version": board["source_publication_version"],
                             "round_index": board["round_index"], "tick_index": board["tick_index"], **row}
                            for board in report["leaderboard_history"] for row in board["rows"]]}
        for name, rows in tables.items():
            target = directory / f"{name}.csv"
            with target.open("x", encoding="utf-8-sig", newline="") as file:
                if rows:
                    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                    writer.writeheader()
                    # Keep integer negatives numeric; only neutralize untrusted CSV text.
                    writer.writerows({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v
                                      for k, v in row.items()} for row in rows)
            files.append(target.name)
        manifest = {key: report[key] for key in ("session_id", "metric_schema_version", "policy", "source_publication_version", "consistency_errors")}
        manifest["csv_text_safety"] = "Spreadsheet formula-leading text is apostrophe-prefixed; numeric negative profits are unchanged."
        (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        files.append("manifest.json")
    return {"session_id": report["session_id"], "format": format, "directory": str(directory.resolve()), "files": files}
