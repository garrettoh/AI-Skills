"""Validate install selection, approval gates and default-all behavior in isolated directories."""
import subprocess
import sys
import tempfile
from pathlib import Path
from components import SKILLS, dependencies


def main():
    installer = Path(__file__).with_name('install.py').resolve()
    with tempfile.TemporaryDirectory(prefix='installer-behavior-') as temporary:
        work = Path(temporary)
        def call(destination, options=(), response='', expected=0):
            command = [sys.executable, str(installer), '--skills-root', str(destination), *options]
            result = subprocess.run(command, input=response, text=True, capture_output=True, timeout=60)
            if result.returncode != expected:
                raise RuntimeError(f'{command}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
            return result.stdout
        for response in ('', '\n', 'n\n', 'maybe\n'):
            destination = work / f'cancel-{len(response)}-{response[:1].strip() or "empty"}'
            text = call(destination, response=response)
            if destination.exists() or 'Installation cancelled' not in text:
                raise RuntimeError('Cancellation or EOF wrote installation files')
            if text.index('Skills to install (11)') > text.index('Install this selection?'):
                raise RuntimeError('Confirmation appeared before the plan')
        preview = work / 'preview'
        call(preview, ['--skills', 'hindsight-orchestrator', '--preview'])
        if preview.exists():
            raise RuntimeError('Preview created the destination')
        unknown = work / 'unknown'
        call(unknown, ['--skills', 'does-not-exist'], expected=2)
        if unknown.exists():
            raise RuntimeError('Unknown selection wrote files')
        for name in SKILLS:
            destination = work / name
            text = call(destination, ['--skills', name], 'yes\n')
            expected = {name, *dependencies([name])}
            installed = {p.name for p in destination.iterdir()}
            if installed != expected or 'PASS:' not in text:
                raise RuntimeError(f'{name}: unexpected components {installed}, expected {expected}')
        full = work / 'all'
        text = call(full, response='y\n')
        if {p.name for p in full.iterdir()} != {*SKILLS, *dependencies(list(SKILLS))}:
            raise RuntimeError('Default install omitted components')
        # Installing an additional selection must preserve an existing skill and unrelated file.
        sentinel = full / 'existing-user-file.txt'
        sentinel.write_text('keep', encoding='utf-8')
        call(full, ['--skills', 'hindsight-orchestrator'], 'yes\n')
        if sentinel.read_text() != 'keep' or not (full / 'ez-evtx-parser/SKILL.md').exists():
            raise RuntimeError('Partial update removed unselected content')
    print('PASS: all 11 individual installs and verification, default all, explicit approval, cancellation/EOF, preview, unknown names and preserved unselected files')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
