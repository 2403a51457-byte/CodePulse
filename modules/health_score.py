"""Transparent heuristic project health score."""

def calculate_health_score(findings, files_scanned=0):
    if files_scanned <= 0:
        return 0
    weights = {"High": 15, "Medium": 6, "Low": 2}
    penalty = sum(weights.get(item.get("severity", "Low"), 2) for item in findings)
    # Normalize by scanned files so scores remain comparable across repository sizes.
    normalized_penalty = penalty / max(files_scanned, 1)
    return max(0, min(100, round(100 - normalized_penalty)))
