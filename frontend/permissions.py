from components.nav_config import ROLE_PAGES


def can_access(role: str, page: str) -> bool:
    return page in ROLE_PAGES.get((role or "").lower(), [])