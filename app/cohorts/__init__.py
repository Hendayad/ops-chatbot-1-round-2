"""Configuration-driven cohort onboarding and scoping."""


class CohortConfigLoader:
    def __init__(self, config_path: str):
        """Initialize the CohortConfigLoader with the given configuration file path."""
        self.config_path = config_path
