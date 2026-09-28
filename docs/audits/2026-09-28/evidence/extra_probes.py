"""Eight additional isolated probes for the 2026-09-28 review of the 2026-09-27 audit.

Every scenario runs in a temporary directory that is removed on exit. The only file written is the
sibling extra-probe-results.json. No network, no credentials. Observations, not assertions: once a
repair is authorised, convert each case into a maintained test with its expected SAFE outcome.
"""
import sys, json, tempfile, pathlib, subprocess, os
ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from fiction_compiler import state, hard_audit, tournament, defaultness, integrity, promote, prose_audit

out = []
def emit(name, **d): out.append({'probe': name, **d})
def write(p, v): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v))
DELTA_KEYS = ['facts_added','facts_removed','knowledge_changes','relationship_changes','promises_opened','promises_closed']

def project(base, sids):
    p = base / 'project'
    write(p / 'canon/index.json', {'accepted_state_deltas': []})
    write(p / 'canon/characters/char-a.json', {'id': 'char-a'})
    for sid in sids:
        s = p / 'scenes' / sid
        write(s / 'spec.json', {'id': sid, 'chapter': 'ch01', 'pov': 'char-a', 'participants': ['char-a'],
                                'purpose': ['t'], 'entry_state': [], 'desire': 't', 'conflict': 't', 'turn': 't',
                                'exit_state': [], 'required_events': [], 'forbidden_moves': []})
        write(s / 'state-delta.json', dict(scene_id=sid, **{k: [] for k in DELTA_KEYS}))
    return p

with tempfile.TemporaryDirectory() as td:
    base = pathlib.Path(td)

    # A. An event effect knows(a, fact) is "recorded" via predicate_changes, but knowledge queries never see it.
    p = project(base / 'knows', ['ch01-sc01', 'ch01-sc02'])
    (p / 'canon/facts.jsonl').write_text(json.dumps({'id': 'fact-x', 'text': 'X'}) + '\n')
    eff = {'op': 'add', 'predicate': 'knows', 'subject': 'char-a', 'object': 'fact-x'}
    write(p / 'planning/event-graph.json', {'events': [{'id': 'evt-learn', 'preconditions': [], 'effects': [eff]}]})
    s1 = p / 'scenes/ch01-sc01'
    spec = json.loads((s1 / 'spec.json').read_text()); spec['required_events'] = ['evt-learn']; write(s1 / 'spec.json', spec)
    d = json.loads((s1 / 'state-delta.json').read_text()); d['predicate_changes'] = [eff]; write(s1 / 'state-delta.json', d)
    write(p / 'canon/index.json', {'accepted_state_deltas': ['ch01-sc01']})
    s2 = p / 'scenes/ch01-sc02'
    spec2 = json.loads((s2 / 'spec.json').read_text()); spec2['knowledge_required'] = [{'character': 'char-a', 'fact': 'fact-x'}]; write(s2 / 'spec.json', spec2)
    st = state.reconstruct_state_before(p, 'ch01-sc02')
    emit('knows-effect-split-store',
         sc01_audit=hard_audit.audit_scene(p, 'ch01-sc01')['verdict'],
         holds_knows_after=st.holds('knows', 'char-a', 'fact-x'),
         stored_as_predicate=('knows', 'char-a', 'fact-x') in st.predicates,
         sc02_audit=[f['diagnosis'][:90] for f in hard_audit.audit_scene(p, 'ch01-sc02')['findings']])

    # B. A removed fact stays "known": knowledge is add-only and never checked against fact removal.
    p = project(base / 'removed', ['ch01-sc01', 'ch01-sc02'])
    (p / 'canon/facts.jsonl').write_text(json.dumps({'id': 'fact-alive', 'text': 'The dog is alive'}) + '\n')
    (p / 'canon/knowledge-state.jsonl').write_text(json.dumps({'character': 'char-a', 'fact': 'fact-alive'}) + '\n')
    d = json.loads((p / 'scenes/ch01-sc01/state-delta.json').read_text()); d['facts_removed'] = ['fact-alive']
    write(p / 'scenes/ch01-sc01/state-delta.json', d); write(p / 'canon/index.json', {'accepted_state_deltas': ['ch01-sc01']})
    st = state.reconstruct_state_before(p, 'ch01-sc02')
    claims = {'candidate': 'a.md', 'pov': 'char-a', 'claims': [{'type': 'focalizer_knows', 'subject': 'char-a', 'object': 'fact-alive', 'evidence': 'She knew the dog was fine.'}]}
    emit('removed-fact-still-known', fact_exists=st.fact_exists('fact-alive'), knows=st.knows('char-a', 'fact-alive'),
         prose_audit_verdict=prose_audit.audit_prose(p, 'ch01-sc02', claims)['verdict'])

    # C. ISO-ish times with 'T' vs ' ' separators compare lexically: a forward step reads as backward.
    p = project(base / 'time', ['ch01-sc01', 'ch01-sc02'])
    for sid, t in (('ch01-sc01', '2026-01-01T09:00'), ('ch01-sc02', '2026-01-01 10:00')):
        d = json.loads((p / 'scenes' / sid / 'state-delta.json').read_text()); d['time'] = t; write(p / 'scenes' / sid / 'state-delta.json', d)
    write(p / 'canon/index.json', {'accepted_state_deltas': ['ch01-sc01', 'ch01-sc02']})
    emit('time-separator-false-backward', findings=[f['evidence'] for f in hard_audit.audit_canon(p)['findings'] if f['dimension'] == 'temporal'])

    # D. Pareto on noisy means: a 0.1 difference on every dimension becomes an automatic 'select'.
    clean = [{'candidate': c, 'critic': 'defaultness-lint', 'findings': []} for c in ('a.md', 'b.md')]
    lab = tournament.anonymize(['a.md', 'b.md'])[0]
    j = [{'scores': {lab['a.md']: {'voice': 7.0, 'agency': 7.0}, lab['b.md']: {'voice': 6.9, 'agency': 6.9}}}]
    r = tournament.run_tournament(clean, judgments=j)
    emit('pareto-no-indifference-threshold', recommendation=r['recommendation'], disagreement=r['disagreement'])

    # E. Default-seed labels are a pure function of sorted filenames: identical mapping in every scene/project.
    emit('predictable-blind-labels', mappings=[tournament.anonymize(['candidate-a.md', 'candidate-b.md'])[0] for _ in range(3)],
         three=tournament.anonymize(['candidate-a.md', 'candidate-b.md', 'candidate-c.md'])[0])

    # F. Character speech is linted as narration: a mocking line of dialogue becomes a material finding.
    txt = '"Time stood still," he said, reading the brochure aloud in his flattest voice.'
    emit('dialogue-linted-as-narration', text=txt, findings=[(f['severity'], f['evidence']) for f in defaultness.lint_text(txt)])

    # G. A process killed while holding the promotion lock leaves a lock that blocks every later promotion.
    p = project(base / 'lock', ['ch01-sc01'])
    code = ("import sys,os,pathlib;sys.path.insert(0,%r);from fiction_compiler import integrity;"
            "l=integrity.PromotionLock(pathlib.Path(%r));l.__enter__();os._exit(9)") % (str(ROOT / 'src'), str(p))
    rc = subprocess.run([sys.executable, '-c', code]).returncode
    lock = p / '.promote.lock'
    try:
        with integrity.PromotionLock(p): blocked = None
    except ValueError as e: blocked = str(e)[:80]
    emit('stale-lock-after-kill', child_exit=rc, lock_left=lock.exists(), lock_bytes=lock.read_bytes().decode() if lock.exists() else None, next_promotion=blocked)

    # H. Negation cannot be expressed: value=False on a knows() precondition is ignored, so
    #    "char-a must NOT yet know the secret" fails exactly when it is satisfied.
    p = project(base / 'negation', ['ch01-sc01'])
    (p / 'canon/facts.jsonl').write_text(json.dumps({'id': 'fact-secret', 'text': 'The secret'}) + '\n')
    pre = {'predicate': 'knows', 'subject': 'char-a', 'object': 'fact-secret', 'value': False}
    write(p / 'planning/event-graph.json', {'events': [{'id': 'evt-ignorant', 'preconditions': [pre], 'effects': []}]})
    s = p / 'scenes/ch01-sc01'; spec = json.loads((s / 'spec.json').read_text()); spec['required_events'] = ['evt-ignorant']; write(s / 'spec.json', spec)
    emit('negated-knows-precondition', char_knows_secret=False,
         findings=[f['diagnosis'][:80] for f in hard_audit.audit_scene(p, 'ch01-sc01')['findings']])

print(json.dumps(out, indent=1))
pathlib.Path(__file__).with_name('extra-probe-results.json').write_text(json.dumps(out, indent=1))
