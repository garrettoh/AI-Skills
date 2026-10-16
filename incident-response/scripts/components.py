"""Installable skills and explicit shared-library dependencies."""
from pathlib import Path

SKILLS = {
    'incident-diagrams': 'incident-diagrams',
    'investigation-orchestrator': 'investigation-orchestrator',
    'hindsight-orchestrator': 'hindsight-orchestrator',
    'kape-orchestrator': 'kape_analysis/kape-orchestrator',
    'ez-evtx-parser': 'kape_analysis/ez-evtx-parser',
    'ez-prefetch-parser': 'kape_analysis/ez-prefetch-parser',
    'ez-registry-parser': 'kape_analysis/ez-registry-parser',
    'ez-filesystem-parser': 'kape_analysis/ez-filesystem-parser',
    'ez-fileaccess-parser': 'kape_analysis/ez-fileaccess-parser',
    'ez-srum-parser': 'kape_analysis/ez-srum-parser',
    'ez-recyclebin-parser': 'kape_analysis/ez-recyclebin-parser',
    'ez-activity-parser': 'kape_analysis/ez-activity-parser',
}
HELPERS = {'kape_core': 'kape_analysis/kape_core', 'investigation_core': 'investigation_core'}


def select(names=None):
    if not names or names == ['all']:
        return list(SKILLS)
    unknown = set(names) - set(SKILLS)
    if unknown:
        raise ValueError('Unknown skills: ' + ', '.join(sorted(unknown)))
    return list(dict.fromkeys(names))


def dependencies(names):
    result = ['kape_core'] if any(name != 'incident-diagrams' for name in names) else []
    if any(name in {'investigation-orchestrator', 'hindsight-orchestrator', 'kape-orchestrator'} for name in names):
        result.append('investigation_core')
    return result


def component_path(root, name):
    """Support both repository and flat installed layouts."""
    direct = Path(root) / name
    return direct if direct.is_dir() else Path(root) / {**SKILLS, **HELPERS}[name]
