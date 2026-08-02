PAGE_ICONS = {
    "Dashboard": "📊",
    "Chat Viewer": "💬",
    "Escalations": "🎫",
    "Knowledge Base": "📚",
    "Reminders": "⏰",
    "Analytics": "📈",
    "Settings": "⚙️",
    "Guide": "📘",
    "Users": "👥",
    "Cohorts": "📂"
}

# Learner tabs vs. Admin-exclusive tabs
ROLE_PAGES = {

    "learner": [
        "Chat Viewer",
        "Reminders",
        "Settings",
    ],

    "program_lead": [
        "Dashboard",
        "Cohorts",
        "Settings",
    ],

    "admin": [
        "Dashboard",
        "Escalations",
        "Knowledge Base",
        "Analytics",
        "Users",
        "Guide",
        "Settings",
    ],

}