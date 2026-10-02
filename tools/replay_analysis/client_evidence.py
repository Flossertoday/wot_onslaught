"""Record selected current-client bytecode; disassemble only, never execute it.

Requires xdis. --dependencies supports an isolated pip --target directory.
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from local_paths import DEFAULT_CONFIG, local_paths, require_game


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--dependencies', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        args.game = require_game(local_paths(game=args.game, config=args.config)[0], parser)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.dependencies:
        sys.path.insert(0, str(args.dependencies.resolve()))
    from xdis.bytecode import Bytecode
    from xdis.load import load_module_from_file_object
    from xdis.opcodes import opcode_27
    targets = {
        'comp7/scripts/client/comp7/gui/impl/lobby/battle_results/submodel_presenters/comp7_progression.pyc': {'__packProgressionData': (0, 99)},
        'comp7/scripts/client/comp7/gui/impl/lobby/battle_results/comp7_packers.pyc': {'packModel': (130, 193)},
        'comp7/scripts/common/comp7_common/comp7_battle_results/comp7.pyc': {'<module>': (48, 120)},
    }
    result = {'package': 'res/packages/comp7.pkg', 'entries': {}}
    with zipfile.ZipFile(args.game / result['package']) as package:
        for entry, wanted in targets.items():
            raw = package.read(entry)
            version, _, _, code, *_ = load_module_from_file_object(io.BytesIO(raw))
            if version != (2, 7):
                raise ValueError('unreviewed bytecode version')
            evidence = {'sha256': hashlib.sha256(raw).hexdigest(), 'functions': {}}
            def walk(co, prefix=''):
                if not hasattr(co, 'co_code'):
                    return
                name = prefix + co.co_name
                if co.co_name in wanted:
                    low, high = wanted[co.co_name]
                    instructions = [{'offset': i.offset, 'op': i.opname, 'arg': i.argrepr}
                                    for i in Bytecode(co, opcode_27) if low <= i.offset < high]
                    if instructions:
                        evidence['functions'][name] = instructions
                for child in co.co_consts:
                    walk(child, name + '.')
            walk(code)
            result['entries'][entry] = evidence
    with zipfile.ZipFile(args.game / 'res/packages/scripts.pkg') as package:
        entry = 'scripts/common/constants.pyc'
        raw = package.read(entry)
        version, _, _, code, *_ = load_module_from_file_object(io.BytesIO(raw))
        if version != (2, 7):
            raise ValueError('unreviewed bytecode version')
        arena_period = next(c for c in code.co_consts if getattr(c, 'co_name', None) == 'ARENA_PERIOD')
        result['arena_period'] = {'package':'res/packages/scripts.pkg', 'entry':entry,
                                  'sha256':hashlib.sha256(raw).hexdigest(),
                                  'instructions':[{'offset':i.offset, 'op':i.opname, 'arg':i.argrepr}
                                                  for i in Bytecode(arena_period, opcode_27)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Saved', args.output)


if __name__ == '__main__':
    main()
