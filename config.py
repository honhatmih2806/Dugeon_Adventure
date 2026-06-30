"""Game configuration constants and settings."""


class Config:
    """Stores global game configuration values."""

    def __init__(self) -> None:
        """Initialize default configuration."""
        # Path to a generic icon image to use for characters and monsters.
        # Place your icon file at this path or update it before launching the game.
        self.icon_path: str = "assets/sprites/icon.png"
