"""First-run console setup for the Windows launcher; no game files are modified."""
import json
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11 or newer is required')

import server
from game_detection import detect_game_folders
from local_paths import DEFAULT_CONFIG, local_paths


def select_game_folder(replay_source=None):
    print('First run: looking for your World of Tanks installation (up to 2 seconds)...')
    matches = detect_game_folders()
    if matches:
        for index, game in enumerate(matches, 1):
            print(f'  {index}. {game}')
            print(f'     Replay folder: {replay_source or game / "replays"} (recordings may not exist yet)')
        default = 'Enter to use 1' if len(matches) == 1 else 'Enter for manual entry'
        while True:
            value = input(f'Select 1-{len(matches)}, paste a game path, or 0 for manual entry ({default}): ').strip().strip('"')
            if not value and len(matches) == 1:
                return matches[0]
            if not value or value == '0':
                break
            if value.isdecimal():
                choice = int(value)
                if 1 <= choice <= len(matches):
                    return matches[choice - 1]
                print('Please select one of the listed numbers, or 0 for manual entry.')
                continue
            return Path(value).expanduser().resolve()
    else:
        print('No installation found in the quick search. Enter the game folder manually.')
    print('It must contain res/packages/scripts.pkg. Your game and replays stay local.')
    value = input('Game folder (Enter to open an empty explorer): ').strip().strip('"')
    return Path(value).expanduser().resolve() if value else None


def main():
    if not sys.argv[1:]:
        try:
            game, source = local_paths()
        except (OSError, ValueError) as error:
            print(f'Cannot read local settings: {error}', file=sys.stderr)
            return 1
        if game is None and sys.stdin.isatty():
            game = select_game_folder(source)
            if game is not None:
                if not (game / 'res/packages/scripts.pkg').is_file():
                    print(f'Missing {game / "res/packages/scripts.pkg"}', file=sys.stderr)
                    return 1
                try:
                    settings = (json.loads(DEFAULT_CONFIG.read_text(encoding='utf-8-sig'))
                                if DEFAULT_CONFIG.exists() else {})
                    settings['game'] = str(game)
                    DEFAULT_CONFIG.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
                except (OSError, ValueError) as error:
                    print(f'Cannot save local settings: {error}', file=sys.stderr)
                    return 1
                print(f'Saved settings to {DEFAULT_CONFIG}')
    return server.main(['--open-browser', *sys.argv[1:]])


if __name__ == '__main__':
    raise SystemExit(main())
