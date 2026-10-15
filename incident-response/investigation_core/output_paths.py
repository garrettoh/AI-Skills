"""Choose case output folders from install settings or evidence layout."""
import json
import os
from pathlib import Path


def infer_artifact_parent(sources):
    anchors = []
    roots = []
    for value in sources.values():
        path = Path(value).resolve()
        if path.is_file():
            path = path.parent
        roots.append(path)
        # KAPE commonly points at <case>/<hostname>_KAPE/parse or _KAPE directly.
        for parent in (path, *path.parents):
            name = parent.name.casefold()
            if name.endswith('_kape'):
                anchors.append(parent.parent)
                break
            if name == 'hindsight_manual_drops':
                anchors.append(parent.parent)
                break
    if anchors:
        common = Path(os.path.commonpath([str(p) for p in anchors]))
        if all(p == common for p in anchors):
            return common
        return None
    return None


def configured_destination(args, sources):
    """Return the exact output folder; --output-root keeps its historical semantics."""
    legacy = getattr(args, 'output_root', None)
    if legacy:
        return (Path(legacy).expanduser().resolve() / args.case)
    direct = getattr(args, 'output_directory', None)
    if direct:
        return Path(direct).expanduser().resolve()
    helper_root = Path(__file__).resolve().parents[1]
    candidates = (helper_root / 'kape_core' / 'settings.json',
                  helper_root / 'kape_analysis' / 'kape_core' / 'settings.json')
    setting_file = next((path for path in candidates if path.exists()), candidates[0])
    settings = json.loads(setting_file.read_text(encoding='utf-8-sig')) if setting_file.exists() else {}
    configured = settings.get('output_directory', 'auto')
    if configured == 'auto':
        parent = infer_artifact_parent(sources)
        if parent:
            return parent / 'agent_output'
        # Preserve the familiar local layout when artifact folders provide no safe anchor.
        return Path.cwd() / 'agent_output' / args.case
    expanded = os.path.expandvars(str(configured)).replace('{case}', args.case)
    return Path(expanded).expanduser().resolve()
