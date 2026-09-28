"""Audit-evidence checks only; no production mutations or provider calls.

Writes sibling recheck-results.json. Analysis mutations occur only in temporary copies.
"""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from fiction_compiler import tournament

spec = importlib.util.spec_from_file_location('record_analysis_recheck', Path(__file__).with_name('record_analysis.py'))
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)
observations = []
critiques = [{'candidate': c, 'critic': 'defaultness-lint', 'findings': []} for c in ('a.md', 'b.md')]
labels, _ = tournament.anonymize(['a.md', 'b.md'])
result = tournament.run_tournament(critiques, judgments=[{'scores': {
    labels['a.md']: {'voice': 4.0, 'agency': 4.0},
    labels['b.md']: {'voice': 3.9, 'agency': 3.9}}}])
observations.append({'case': 'within-rubric-strict-pareto', 'result': result['recommendation'],
                     'interpretation': 'correct strict dominance; no uncertainty policy, not a mathematical defect'})
with tempfile.TemporaryDirectory() as temp:
    temp_root = Path(temp)
    copied = temp_root / 'projects' / 'the-overnight'
    shutil.copytree(ROOT / 'projects/the-overnight', copied)
    analyzer.ROOT = temp_root
    rows = analyzer.scenes()
    first = next(r for r in rows if r['scene'] == 'ch01-sc01')
    selected = next(r for r in first['literary_records_on_promoted_bytes'] if r['critic'] == 'style-editor')
    path = temp_root / selected['file']
    data = json.loads(path.read_text())
    data['candidate_sha256'] = '0' * 64
    path.write_text(json.dumps(data))
    changed = next(r for r in analyzer.scenes() if r['scene'] == 'ch01-sc01')
    assert 'style-editor' not in changed['literary_critics_on_promoted_bytes']
    assert any(r['critic'] == 'style-editor' for r in changed['filename_only_unbound_literary_records'])
    observations.append({'case': 'analyzer-rejects-filename-only-binding', 'passed': True})
    data['candidate_sha256'] = first['candidate_sha256']
    data['verdict'] = 'revise'
    path.with_name('second-style-review.json').write_text(json.dumps(data))
    changed = next(r for r in analyzer.scenes() if r['scene'] == 'ch01-sc01')
    assert 'style-editor' in changed['literary_critics_on_promoted_bytes']
    # Both records must survive; a dict keyed by critic would silently overwrite one.
    all_style = [r for r in changed['literary_records_on_promoted_bytes'] + changed['filename_only_unbound_literary_records'] if r['critic'] == 'style-editor']
    assert len(all_style) == 2
    observations.append({'case': 'analyzer-preserves-multiple-records-per-role', 'passed': True})
analyzer.ROOT = ROOT
rows = analyzer.scenes()
observations.append({'case': 'accepted-byte-and-coverage-inventory',
    'accepted': len(rows), 'candidate_manuscript_bytes_match': all(r['candidate_matches_manuscript'] for r in rows),
    'three_named_roles_hash_bound': sum({'style-editor','character-simulator','adversarial-reader'} <= set(r['literary_critics_on_promoted_bytes']) for r in rows),
    'unbound_literary_records': sum(len(r['filename_only_unbound_literary_records']) for r in rows),
    'matching_tournament_label_maps': sum(r['labels_equal_filename_letter'] for r in analyzer.tournaments()),
    'stored_tournament_maps': len(analyzer.tournaments())})
Path(__file__).with_name('recheck-results.json').write_text(json.dumps(observations, indent=2) + '\n')
print(json.dumps(observations, indent=2))
