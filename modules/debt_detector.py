SEVERITY_WEIGHTS = {"High": 15, "Medium": 6, "Low": 2}

def classify_findings(findings):
    normalized = []
    for item in findings:
        finding = dict(item)
        severity = finding.get("severity", "Low")
        if severity not in SEVERITY_WEIGHTS:
            severity = "Low"
        finding["severity"] = severity
        finding["debt_points"] = SEVERITY_WEIGHTS[severity]
        normalized.append(finding)
    return normalized

def debt_summary(findings):
    summary = {"High": 0, "Medium": 0, "Low": 0, "total_debt_points": 0}
    for item in findings:
        severity = item.get("severity", "Low")
        summary[severity] += 1
        summary["total_debt_points"] += item.get("debt_points", SEVERITY_WEIGHTS.get(severity, 2))
    return summary
