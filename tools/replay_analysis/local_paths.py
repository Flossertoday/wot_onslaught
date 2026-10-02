"""Machine-local input paths shared by the launcher and research commands."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / 'explorer.local.json'


def local_paths(game=None, source=None, config=DEFAULT_CONFIG):
    """CLI > environment > config; a game override also changes its default replays."""
    config = Path(config).expanduser().resolve()
    overridden_game = game or os.environ.get('WOT_GAME_DIR')
    settings = {}
    if not overridden_game and config.exists():
        settings = json.loads(config.read_text(encoding='utf-8-sig'))
        if not isinstance(settings, dict):
            raise ValueError(f'{config}: expected a JSON object')
        for key in ('game', 'replay_source'):
            if key in settings and (not isinstance(settings[key], str) or not settings[key].strip()):
                raise ValueError(f'{config}: {key} must be a nonempty path string')

    def configured(key):
        if key not in settings:
            return None
        path = Path(settings[key]).expanduser()
        return (path if path.is_absolute() else config.parent / path).resolve()

    game = Path(overridden_game).expanduser().resolve() if overridden_game else configured('game')
    source = source or os.environ.get('WOT_REPLAY_SOURCE')
    source = (Path(source).expanduser().resolve() if source
              else configured('replay_source') if not overridden_game else None)
    return game, source or (game / 'replays' if game else None)


def require_game(game, parser):
    if game is None:
        parser.error('Set --game, WOT_GAME_DIR, or game in explorer.local.json to your World of Tanks folder')
    if not (game / 'res/packages/scripts.pkg').is_file():
        parser.error(f'{game}: missing res/packages/scripts.pkg; select the installed game folder')
    return game
