import streamlit as st

# --------------------------------------------------------------------------
# Design tokens
#
# Ink/navy primary (trust, precision) + teal accent for positive states.
# Space Grotesk for headings (structured, technical feel fitting an ops
# console), Inter for body copy, JetBrains Mono for IDs/timestamps/data.
# --------------------------------------------------------------------------

BADGE_STYLES = {
    "neutral":  ("#EEF1F6", "#4A5776"),
    "info":     ("#E7F0FE", "#1D5FD1"),
    "success":  ("#E5F6EF", "#1F7A54"),
    "warning":  ("#FBF0DE", "#94660F"),
    "danger":   ("#FBEAE8", "#A62F22"),
}

ROLE_BADGE = {
    "learner":      "info",
    "program_lead": "success",
    "admin":        "neutral",
}


def load_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

        :root{
            --bg:#F4F6FA;
            --surface:#FFFFFF;
            --ink:#16213A;
            --ink-soft:#5A6B87;
            --border:#E2E7F0;
            --primary:#2E4374;
            --primary-hover:#24355C;
            --blue:#2A63E4;
            --blue-hover:#1F4FC4;
            --blue-soft:rgba(42,99,228,.10);
            --accent:#2F9E77;
            --radius-lg:14px;
            --radius-md:10px;
            --shadow-sm:0 1px 2px rgba(16,24,40,.05);
            --shadow-md:0 4px 16px rgba(16,24,40,.07);
        }

        html, body, [class*="css"]{
            font-family:'Inter', sans-serif;
            color:var(--ink);
        }

        h1, h2, h3, h4 {
            font-family:'Space Grotesk', sans-serif !important;
            letter-spacing:-0.01em;
        }

        .main{
            background-color:var(--bg);
        }

        /* No sidebar in this app — hide it and its collapse control entirely */
        section[data-testid="stSidebar"],
        [data-testid="collapsedControl"]{
            display:none !important;
        }

        /* ---- Page header block ---- */
        .oa-eyebrow{
            font-family:'JetBrains Mono', monospace;
            font-size:11px;
            font-weight:500;
            letter-spacing:.14em;
            text-transform:uppercase;
            color:var(--ink-soft);
            margin-bottom:2px;
        }
        .oa-page-title{
            font-family:'Space Grotesk', sans-serif;
            font-size:30px;
            font-weight:700;
            color:var(--ink);
            margin:0 0 2px 0;
            line-height:1.2;
        }
        .oa-page-subtitle{
            color:var(--ink-soft);
            font-size:14.5px;
            margin-bottom:6px;
        }
        .oa-header-rule{
            border:none;
            border-top:1px solid var(--border);
            margin:14px 0 22px 0;
        }

        /* ---- Badges (status/priority/role pills) ---- */
        .oa-badge{
            display:inline-flex;
            align-items:center;
            gap:6px;
            padding:3px 11px;
            border-radius:999px;
            font-size:12.5px;
            font-weight:600;
            line-height:1.6;
        }
        .oa-dot{
            width:6px;height:6px;border-radius:50%;background:currentColor;
        }

        /* ---- Buttons ---- */
        .stButton>button{
            width:100%;
            border-radius:var(--radius-md);
            background:var(--blue);
            color:white;
            height:44px;
            border:none;
            font-size:15px;
            font-weight:600;
            transition:background .15s ease;
        }
        .stButton>button:hover{
            background:var(--blue-hover);
            color:white;
        }
        .stButton>button:disabled{
            background:#B9C2D6;
            color:#F4F6FA;
        }

        /* ---- Inputs ---- */
        .stTextInput>div>div>input, .stSelectbox>div>div, .stTextArea textarea{
            border-radius:var(--radius-md) !important;
            border:1px solid var(--border) !important;
        }

        /* ---- Metric cards ---- */
        div[data-testid="stMetric"]{
            background:var(--surface);
            border:1px solid var(--border);
            border-radius:var(--radius-lg);
            padding:18px 20px;
            box-shadow:var(--shadow-sm);
        }
        div[data-testid="stMetricLabel"]{
            font-size:13px;
            color:var(--ink-soft);
            font-weight:500;
        }

        /* ---- Generic surface card, used via st.container(border=True) ---- */
        div[data-testid="stVerticalBlockBorderWrapper"]{
            border-radius:var(--radius-lg) !important;
            border:1px solid var(--border) !important;
            background:var(--surface);
            box-shadow:var(--shadow-sm);
        }

        /* ---- Dataframes / tables ---- */
        div[data-testid="stDataFrame"]{
            border-radius:var(--radius-md);
            overflow:hidden;
            border:1px solid var(--border);
        }

        /* ---- Chat ---- */
        div[data-testid="stChatMessage"]{
            border-radius:16px;
            padding:16px 18px;
            margin-bottom:12px;
            background:var(--surface);
            border:1px solid var(--border);
            box-shadow:var(--shadow-sm);
        }
        div[data-testid="stChatMessageAvatarUser"]{
            background:var(--primary);
        }
        div[data-testid="stChatMessageAvatarAssistant"]{
            background:var(--accent);
        }

        /* ==================================================================
           TOP NAVBAR — light, minimal, edge-to-edge bar (not a floating
           card): thin bottom border, a single slim brand-colored top rule
           as the one restrained signature touch, underline-style nav
           instead of pill buttons.
           ================================================================== */
        div.st-key-oa_topbar{
            background:var(--surface);
            border-radius:0;
            border-top:2px solid var(--blue);
            border-bottom:1px solid var(--border);
            padding:14px 6px 12px 6px;
            margin:-1px 0 28px 0;
            position:sticky;
            top:0;
            z-index:999;
        }

        /* ---- Brand ---- */
        div.st-key-oa_topbar .oa-brand{
            display:flex;
            align-items:center;
            gap:10px;
        }
        div.st-key-oa_topbar .oa-brand-mark{
            width:30px;
            height:30px;
            min-width:30px;
            border-radius:8px;
            background:var(--blue-soft);
            color:var(--blue);
            display:flex;
            align-items:center;
            justify-content:center;
            font-family:'Space Grotesk', sans-serif;
            font-weight:700;
            font-size:13px;
            letter-spacing:.02em;
        }
        div.st-key-oa_topbar .oa-brand-title{
            font-family:'Space Grotesk', sans-serif;
            font-size:17px;
            font-weight:700;
            color:var(--ink);
            line-height:1.2;
        }

        /* ---- User chip (fallback path, no st.popover available) ---- */
        div.st-key-oa_topbar .oa-user-chip{
            display:flex;
            align-items:center;
            gap:10px;
        }
        div.st-key-oa_topbar .oa-avatar{
            width:30px;
            height:30px;
            min-width:30px;
            border-radius:50%;
            background:var(--blue);
            color:#FFFFFF;
            display:flex;
            align-items:center;
            justify-content:center;
            font-family:'Space Grotesk', sans-serif;
            font-weight:700;
            font-size:13px;
        }
        div.st-key-oa_topbar .oa-user-name{
            font-size:13.5px;
            font-weight:600;
            color:var(--ink);
            line-height:1.3;
        }

        /* ---- User menu button (st.popover trigger) ---- */
        div.st-key-oa_topbar div[data-testid="stPopover"] > div > button{
            background:transparent !important;
            border:1px solid var(--border) !important;
            color:var(--ink) !important;
            font-weight:600 !important;
            font-size:13px !important;
            height:38px;
            border-radius:999px !important;
            transition:background .15s ease, border-color .15s ease;
        }
        div.st-key-oa_topbar div[data-testid="stPopover"] > div > button:hover{
            background:var(--bg) !important;
            border-color:#C7CEDC !important;
        }

        /* ---- Pill navigation → restyled as understated underline tabs ----
           Streamlit's segmented control / radio ships with its own accent
           (a red/orange) and a pill shape. These overrides strip that back
           to plain text with a bottom-border indicator, across the handful
           of DOM shapes different Streamlit versions use. */
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"],
        div.st-key-oa_topbar div[role="radiogroup"]{
            display:flex;
            justify-content:center;
            gap:4px;
            border-bottom:1px solid var(--border);
        }
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] label,
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] button,
        div.st-key-oa_topbar div[role="radiogroup"] label{
            border-radius:0 !important;
            font-weight:600 !important;
            font-size:13.5px !important;
            color:var(--ink-soft) !important;
            background:transparent !important;
            border:none !important;
            border-bottom:2px solid transparent !important;
            padding:8px 14px 9px 14px !important;
            margin-bottom:-1px;
            transition:color .15s ease, border-color .15s ease;
        }
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] label:hover,
        div.st-key-oa_topbar div[role="radiogroup"] label:hover{
            color:var(--blue) !important;
            border-bottom-color:#B7C9F5 !important;
        }
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] label:focus-within,
        div.st-key-oa_topbar div[role="radiogroup"] label:focus-within{
            outline:2px solid var(--blue);
            outline-offset:2px;
        }
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] label[aria-checked="true"],
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] label[data-selected="true"],
        div.st-key-oa_topbar div[data-testid="stSegmentedControl"] button[aria-checked="true"],
        div.st-key-oa_topbar div[role="radiogroup"] label[data-checked="true"],
        div.st-key-oa_topbar div[role="radiogroup"] input:checked + div{
            color:var(--blue) !important;
            border-bottom-color:var(--blue) !important;
        }
        /* Hide the little circular radio dot in the fallback control — the
           underline alone communicates selection */
        div.st-key-oa_topbar div[role="radiogroup"] label > div:first-child{
            display:none;
        }

        /* Chat input stays clear of page content */
        .stChatInput{
            position:fixed;
            bottom:20px;
        }
        /* Inline Flex Alignment Fix */
        .oa-brand, .oa-user-chip, .oa-user-name, div[data-testid="stPopover"] {
            display: inline-flex !important;
            align-items: center !important;
            vertical-align: middle !important;
        }

        /* Ensure dropdown arrows and sub-elements don't drop down */
        div.st-key-oa_topbar span, 
        div.st-key-oa_topbar button, 
        div.st-key-oa_topbar div {
            vertical-align: middle !important;
        }

        /* Normalizes line height to prevent baseline drop */
        .oa-user-name, .oa-brand-title {
            line-height: 1 !important;
            margin: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "", eyebrow: str = ""):
    """Consistent header used at the top of every page."""
    eyebrow_html = f'<div class="oa-eyebrow">{eyebrow}</div>' if eyebrow else ""
    subtitle_html = f'<div class="oa-page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        {eyebrow_html}
        <div class="oa-page-title">{icon} {title}</div>
        {subtitle_html}
        <hr class="oa-header-rule" />
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "neutral") -> str:
    """Return HTML for a small colored status pill. Use with unsafe_allow_html."""
    bg, fg = BADGE_STYLES.get(kind, BADGE_STYLES["neutral"])
    return (
        f'<span class="oa-badge" style="background:{bg};color:{fg};">'
        f'<span class="oa-dot"></span>{text}</span>'
    )


def status_kind(value: str) -> str:
    """Map a common status/priority word to a badge color."""
    v = (value or "").strip().lower()
    if v in ("open", "high", "urgent", "pending"):
        return "warning" if v in ("pending",) else "danger"
    if v in ("closed", "resolved", "low"):
        return "success"
    if v in ("medium", "in progress", "in_progress"):
        return "info"
    return "neutral"


def role_badge_html(role: str) -> str:
    label = (role or "guest").replace("_", " ").title()
    return badge(label, ROLE_BADGE.get((role or "").lower(), "neutral"))