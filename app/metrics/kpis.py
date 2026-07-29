from prometheus_client import Counter, Histogram, Gauge

# --- Existing Metrics ---

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

# --- Additional Bot & Escalation Metrics ---

DEFLECTION_RATE = Counter(
    "ops_bot_deflection_total",
    "Total queries resolved automatically without human intervention",
    ["cohort"]
)

ESCALATIONS_TOTAL = Counter(
    "ops_escalations_total",
    "Total queries escalated to human operators",
    ["cohort", "reason"]
)

CONNECTOR_SYNC_FAILURES = Counter(
    "ops_connector_sync_failures_total",
    "Total failed ticket synchronization attempts with external connectors",
    ["connector_name"]
)

FIRST_RESPONSE_TIME = Histogram(
    "ops_first_response_time_seconds",
    "Time taken to provide the initial response to a query",
    ["cohort"],
    buckets=(1, 2, 5, 10, 30, 60, 300)
)


# --- Helper Utility Functions ---

def track_ticket_created(cohort: str, severity: str = "normal") -> None:
    """Increment support volume metric upon ticket creation."""
    SUPPORT_VOLUME.labels(cohort=cohort, severity=severity).inc()


def track_resolution_time(cohort: str, duration_seconds: float) -> None:
    """Observe duration taken to resolve a support ticket."""
    RESOLUTION_TIME.labels(cohort=cohort).observe(duration_seconds)


def track_first_response_time(cohort: str, duration_seconds: float) -> None:
    """Observe time taken to send the first response to the learner."""
    FIRST_RESPONSE_TIME.labels(cohort=cohort).observe(duration_seconds)


def update_at_risk_count(cohort: str, risk_level: str, count: int) -> None:
    """Set current count of active at-risk issues for a specific cohort."""
    AT_RISK_ISSUES.labels(cohort=cohort, risk_level=risk_level).set(count)


def track_query_deflected(cohort: str) -> None:
    """Increment deflection counter when bot resolves a query without human intervention."""
    DEFLECTION_RATE.labels(cohort=cohort).inc()


def track_escalation(cohort: str, reason: str = "unknown") -> None:
    """Increment escalation counter when an issue is escalated to human Ops."""
    ESCALATIONS_TOTAL.labels(cohort=cohort, reason=reason).inc()


def track_connector_failure(connector_name: str) -> None:
    """Record a failure during external connector synchronization."""
    CONNECTOR_SYNC_FAILURES.labels(connector_name=connector_name).inc()