from app.config import Settings
from app.extract.base import Extractor
from app.extract.heuristic import HeuristicExtractor


def get_extractor(settings: Settings) -> Extractor:
    choice = settings.extractor
    if choice == "auto":
        choice = "claude" if settings.anthropic_api_key else "heuristic"
    if choice == "claude":
        from app.extract.claude import ClaudeExtractor

        return ClaudeExtractor(
            api_key=settings.anthropic_api_key,
            model=settings.model,
            price_in_per_mtok=settings.price_in_per_mtok,
            price_out_per_mtok=settings.price_out_per_mtok,
        )
    if choice == "heuristic":
        return HeuristicExtractor()
    raise ValueError("Unknown CLAIMPILOT_EXTRACTOR: {}".format(choice))
