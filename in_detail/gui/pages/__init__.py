"""The settings pages, in sidebar order."""

from .activity import ActivityPage
from .advanced import AdvancedPage
from .ai import AIPage
from .base import Context, Page
from .health import HealthPage
from .her import HerPage
from .peek import PeekPage
from .recaps import RecapsPage
from .setup import SetupPage
from .welcome import WelcomePage

PAGES = [
    WelcomePage,
    SetupPage,
    ActivityPage,
    AIPage,
    PeekPage,
    RecapsPage,
    HerPage,
    HealthPage,
    AdvancedPage,
]

__all__ = ["PAGES", "Context", "Page"]
