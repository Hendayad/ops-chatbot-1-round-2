def build_dedup_key(
    recipient_id: str,
    reminder_event_id: int,
    lead_time_label: str,
) -> str:
    """Return a stable deduplication key for one reminder eventand one lead-time bucket."""
    return f"{recipient_id}:{reminder_event_id}:{lead_time_label}"
