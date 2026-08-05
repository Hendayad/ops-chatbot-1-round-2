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
        "Knowledge Base",
        "Cohorts",
        "Users",
        "Settings",
    ],

    "admin": [
        "Dashboard",
        "Escalations",
        "Analytics",
        "Guide",
        "Settings",
    ],

}