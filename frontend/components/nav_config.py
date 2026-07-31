PAGE_ICONS = {
    "Dashboard": "📊",
    "Chat Viewer": "💬",
    "Escalations": "🎫",
    "Knowledge Base": "📚",
    "Reminders": "🔔",
    "Analytics": "📈",
    "Settings": "⚙️",
    "Guide": "📘",
    "Users": "👥",
}

# Learner tabs vs. Admin-exclusive tabs
ROLE_PAGES = {
    "learner": [
        "Chat Viewer",
        "Reminders",
        "Settings",
    ],
    "admin": [
        "Dashboard",
        "Escalations",
        "Analytics",
        "Knowledge Base",
        "Users",
        "Guide",
        "Settings",
    ],
}