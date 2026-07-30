from components.embed import render_asset


def render_atrisk_tab():
    """Renders the At-Risk Nudges dashboard content. Call from inside a tab."""
    render_asset("atrisk_dashboard.html", height=1500)