"""Preview, confirm, install and verify any selection of incident response skills."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode = True
from components import SKILLS, HELPERS, select, dependencies


def main():
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10+ is required')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', help='Legacy positional destination')
    parser.add_argument('--skills-root', type=Path)
    parser.add_argument('--skills', nargs='+', metavar='NAME', help='Skill names; default: all')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--preview', '--dry-run', action='store_true', help='Show plan without changing files')
    parser.add_argument('--yes', action='store_true', help='Use only after explicit user approval of the displayed plan')
    parser.add_argument('--timezone', help='Default display timezone: IANA name, UTC or fixed offset')
    parser.add_argument('--list-timezones', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'kape_analysis'))
    from kape_core.timezones import zone, list_zones, default_timezone
    if args.list_timezones:
        print('\n'.join(list_zones()))
        return 0
    if args.timezone:
        zone(args.timezone)
    if args.list:
        print('Available skills (default: all):')
        for name in SKILLS:
            print(f'  {name}')
        return 0
    if args.destination and args.skills_root:
        parser.error('Use a positional destination or --skills-root, not both')
    names = select(args.skills)
    helpers = dependencies(names)
    base = Path(os.environ['CODEX_HOME']).expanduser() if os.environ.get('CODEX_HOME') else Path.home() / '.codex'
    chosen = args.skills_root or (Path(args.destination) if args.destination else base / 'skills')
    destination = chosen.expanduser().resolve()
    package = Path(__file__).resolve().parents[1]
    if destination == package or destination.is_relative_to(package):
        raise ValueError('Install outside the source package')
    paths = {**SKILLS, **HELPERS}
    for name in names + helpers:
        source = package / paths[name]
        if not source.is_dir() or (name in SKILLS and not (source / 'SKILL.md').is_file()):
            raise ValueError(f'Missing source component: {source}')
    timezone_name = args.timezone or default_timezone(destination / 'kape_core/settings.json')
    print(f'Default display timezone: {timezone_name}')
    print(f'Installation destination: {destination}')
    print(f'Skills to install ({len(names)}):')
    for name in names:
        action = 'update existing' if (destination / name).exists() else 'new'
        print(f'  {name} ({action})')
    print('Required shared helpers:')
    for name in helpers:
        action = 'update existing' if (destination / name).exists() else 'new'
        print(f'  {name} ({action})')
    print('Selected component files will be copied; existing same-name files will be overwritten.')
    print('Existing unselected skills will be retained. No evidence or Python packages are installed.')
    print('Verification: selected script imports/help and applicable synthetic evidence workflows.')
    sys.stdout.flush()
    if args.preview:
        print('Preview only. No files changed.')
        return 0
    if not args.yes:
        try:
            response = input('Install this selection? [y/N]: ').strip().casefold()
        except EOFError:
            response = ''
        if response not in {'y', 'yes'}:
            print('Installation cancelled. No files changed.')
            return 0
    destination.mkdir(parents=True, exist_ok=True)
    for name in names + helpers:
        shutil.copytree(package / paths[name], destination / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
    if 'kape_core' in helpers:
        (destination / 'kape_core/settings.json').write_text(json.dumps({'display_timezone': timezone_name}, indent=2), encoding='utf-8')
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('verify_install.py')),
                             '--skills-root', str(destination), '--skills', *names])
    if result.returncode:
        print('Installation copied files but verification failed. Review the errors above.', file=sys.stderr)
        return result.returncode
    print(f'Installed and verified {len(names)} skill(s) in {destination}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
