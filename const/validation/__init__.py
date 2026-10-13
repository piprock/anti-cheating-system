from .bounds import *
from . import bounds

# Backward-compatibility alias
extremes = bounds

__all__ = list(bounds.__all__) + ["bounds", "extremes"]
