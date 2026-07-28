from prometheus_client import Counter, Histogram, Gauge

SUPPORT_VOLUME = Counter(
    "ops_support_volume_total",
    "Total support tickets received",
    ["cohort", "severity"]
)

RESOLUTION_TIME = Histogram(
    "ops_resolution_time_seconds",
    "Time taken to resolve support tickets",
    ["cohort"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 86400)
)

AT_RISK_ISSUES = Gauge(
    "ops_at_risk_issues_count",
    "Count of currently active or at-risk tickets",
    ["cohort", "risk_level"]
)
