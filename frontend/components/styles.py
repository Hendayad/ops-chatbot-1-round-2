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

            --blue:#2A63E4;
            --blue-hover:#1F4FC4;
            --blue-soft:rgba(42,99,228,.10);

            --accent:#2F9E77;

            --radius-lg:14px;
            --radius-md:10px;

            --shadow-sm:0 1px 2px rgba(16,24,40,.05);
        }


        /* ================= GENERAL ================= */

        html, body, [class*="css"]{
            font-family:'Inter', sans-serif;
            color:var(--ink);
        }


        h1,h2,h3,h4{
            font-family:'Space Grotesk',sans-serif !important;
        }


        .main{
            background-color:var(--bg);
        }



        /* ================= SIDEBAR ================= */

        [data-testid="stSidebarNav"],
        [data-testid="stSidebarNavSeparator"]{
            display:none !important;
        }

        /* Explicit background so an empty sidebar (e.g. before login,
           when show_sidebar() is never called) still matches the app
           instead of falling back to Streamlit's default color and
           showing a visible seam next to the main content. */
        section[data-testid="stSidebar"]{
            background:var(--bg) !important;
            border-right:1px solid var(--border);
        }



        /* ================= PAGE HEADER ================= */

        .oa-eyebrow{
            font-family:'JetBrains Mono',monospace;
            font-size:11px;
            letter-spacing:.14em;
            color:var(--ink-soft);
            text-transform:uppercase;
            margin-bottom:3px;
        }


        .oa-page-title{
            font-family:'Space Grotesk',sans-serif;
            font-size:30px;
            font-weight:700;
            color:var(--ink);
            margin-bottom:5px;
        }


        .oa-page-subtitle{
            color:var(--ink-soft);
            font-size:14px;
        }


        .oa-header-rule{
            border:none;
            border-top:1px solid var(--border);
            margin:14px 0 22px;
        }



        /* ================= BUTTONS ================= */

        .stButton > button{

            width:100%;
            height:44px;

            background:var(--blue);
            color:white;

            border:none;
            border-radius:var(--radius-md);

            font-weight:600;
            font-size:15px;

        }


        .stButton > button:hover{

            background:var(--blue-hover);
            color:white;

        }



        /* ================= INPUTS ================= */

        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox div{

            border-radius:var(--radius-md) !important;
            border:1px solid var(--border) !important;

        }



        /* ================= CARDS ================= */

        div[data-testid="stMetric"]{

            background:white;

            border:1px solid var(--border);

            border-radius:var(--radius-lg);

            padding:18px;

            box-shadow:var(--shadow-sm);

        }



        div[data-testid="stVerticalBlockBorderWrapper"]{

            background:white;

            border:1px solid var(--border) !important;

            border-radius:var(--radius-lg) !important;

        }



        /* ================= TABLE ================= */

        div[data-testid="stDataFrame"]{

            border:1px solid var(--border);

            border-radius:var(--radius-md);

            overflow:hidden;

        }



        /* ================= BADGES ================= */

        .oa-badge{

            display:inline-flex;

            align-items:center;

            gap:6px;

            padding:3px 11px;

            border-radius:999px;

            font-size:12px;

            font-weight:600;

        }


        .oa-dot{

            width:6px;
            height:6px;

            border-radius:50%;

            background:currentColor;

        }



        /* ================= TOP NAVBAR ================= */

        div.st-key-oa_topbar{

            background:white;

            border-top:2px solid var(--blue);

            border-bottom:1px solid var(--border);

            padding:14px 6px 12px;

            margin:-1px 0 28px;

        }



        /* Brand */

        .oa-brand{

            display:flex;

            align-items:center;

            gap:10px;

        }


        .oa-brand-mark{

            width:30px;
            height:30px;

            border-radius:8px;

            background:var(--blue-soft);

            color:var(--blue);

            display:flex;

            justify-content:center;

            align-items:center;

            font-weight:700;

        }


        .oa-brand-title{

            font-size:17px;

            font-weight:700;

        }



        /* User */

        .oa-user-chip{

            display:flex;

            align-items:center;

            gap:10px;

        }


        .oa-avatar{

            width:30px;
            height:30px;

            border-radius:50%;

            background:var(--blue);

            color:white;

            display:flex;

            justify-content:center;

            align-items:center;

            font-weight:700;

        }




        /* =====================================================
        STREAMLIT SIDEBAR RADIO NAV FIX
        REMOVE RED SELECT DOT
        ===================================================== */


        /* Hide radio input */      
        section[data-testid="stSidebar"] input[type="radio"] {
            display: none !important;
        }


        /* Remove the radio circle container */
        section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
            display: none !important;
        }


        /* Remove BaseWeb radio indicator */
        section[data-testid="stSidebar"] div[role="radiogroup"] [data-baseweb="radio"] {
            display: none !important;
        }


        /* Remove SVG circles/icons */
        section[data-testid="stSidebar"] div[role="radiogroup"] svg {
            display: none !important;
        }


        /* Remove generated dots */
        section[data-testid="stSidebar"] div[role="radiogroup"] label::before,
        section[data-testid="stSidebar"] div[role="radiogroup"] label::after {

            content: "" !important;

            display: none !important;

        }


        /* Radio group layout */
        section[data-testid="stSidebar"] div[role="radiogroup"] {

            display: flex !important;

            flex-direction: column !important;

            gap: 5px !important;

        }


        /* Navigation item */
        section[data-testid="stSidebar"] div[role="radiogroup"] label {

            display: flex !important;

            align-items: center !important;


            background: transparent !important;

            color: var(--ink-soft) !important;


            padding: 8px 14px !important;


            font-size: 13.5px !important;

            font-weight: 600 !important;


            border-radius: var(--radius-md) !important;


            cursor: pointer !important;

        }


        /* Hover */
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {

            background: var(--blue-soft) !important;

            color: var(--blue) !important;

        }


        /* Selected page */
        section[data-testid="stSidebar"] div[role="radiogroup"] label[aria-checked="true"] {

            background: var(--blue-soft) !important;

            color: var(--blue) !important;

            font-weight: 700 !important;

        }


        /* Chat */

        .stChatInput{

            position:fixed;

            bottom:20px;

        }
        /* =====================================================
        PIN USER CARD TO BOTTOM OF SIDEBAR
        ===================================================== */

        section[data-testid="stSidebar"] > div:first-child {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        section[data-testid="stSidebar"] > div:first-child > div {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        /* The first vertical block (title, menu...) grows */
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        /* Push the last block (user card + logout) down */
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:last-child {
            margin-top: auto !important;
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