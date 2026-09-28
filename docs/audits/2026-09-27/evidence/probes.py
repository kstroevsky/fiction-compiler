import sys,json,tempfile,pathlib,shutil,subprocess
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src'))
from fiction_compiler import promote,integrity,critique,role_runner,tournament,prose_audit,hard_audit,revision,defaultness,schema,state,tools,premise,critic_eval
results=[]
def emit(name,**data):results.append({'probe':name,**data})
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
def make(base,sids=('ch01-sc01',)):
 p=base/'project';write(p/'canon/index.json',{'accepted_state_deltas':[]})
 write(p/'canon/characters/char-a.json',{'id':'char-a'})
 for sid in sids:
  s=p/'scenes'/sid
  spec={'id':sid,'chapter':'ch01','pov':'char-a','participants':['char-a'],'purpose':['test'],'entry_state':[],'desire':'test','conflict':'test','turn':'test','exit_state':[],'required_events':[],'forbidden_moves':[]}
  write(s/'spec.json',spec)
  write(s/'state-delta.json',dict(scene_id=sid,**{k:[] for k in ['facts_added','facts_removed','knowledge_changes','relationship_changes','promises_opened','promises_closed']}))
  (s/'candidates').mkdir();(s/'candidates/a.md').write_text('The door stayed shut.')
  for c in ['hard','literary','defaultness']:
   critique.record_critique(p,sid,'a.md','arbitrary-caller','pass',audit_class=c,filename=c)
 return p
with tempfile.TemporaryDirectory() as td:
 base=pathlib.Path(td)
 p=make(base/'spoof');s=p/'scenes/ch01-sc01';write(s/'spec.json',{'id':'ch01-sc01'})
 emit('spoofed-audits-invalid-spec',schema_errors=schema.validate_named({'id':'ch01-sc01'},'scene'),promotion=promote.promote_candidate(p,'ch01-sc01','a.md'))
 (p/'manuscript/chapters/ch01-sc01.md').write_text('Different unreviewed prose.')
 emit('mutated-manuscript',verifier_errors=integrity.verify_canon(p))
 promote.promote_candidate(p,'ch01-sc01','a.md');emit('repromotion',verifier_errors=integrity.verify_canon(p))
 p=make(base/'race',('ch01-sc01','ch01-sc02'));real=integrity.PromotionLock; fired=[False];inner=[]
 class Interleave(real):
  def __enter__(self):
   if not fired[0]:
    fired[0]=True;inner.append(promote.promote_candidate(p,'ch01-sc02','a.md'))
   return super().__enter__()
 with patch.object(integrity,'PromotionLock',Interleave):outer=promote.promote_candidate(p,'ch01-sc01','a.md')
 emit('interleaved-promotion',both_returned=True,index=json.loads((p/'canon/index.json').read_text()),manuscripts=[x.name for x in (p/'manuscript/chapters').glob('*')],verifier_errors=integrity.verify_canon(p))
 p=make(base/'vendor');s=p/'scenes/ch01-sc01';cand=s/'candidates/a.md';old=integrity.sha256_file(cand)
 def respond(*args):cand.write_text('Unreviewed replacement.');return '{"verdict":"pass","findings":[]}'
 roster={'style-editor':role_runner.Assignment('style-editor','offline','test',persona='Critic')}
 r=role_runner.run_role(str(p),'ch01-sc01','a.md','style-editor',roster=roster,transport=role_runner.OfflineTransport(respond),record=True)
 emit('vendor-mutation',sent_hash=old,reported_input_hash=r['provenance']['candidate_sha256'],recorded_hash=r['recorded']['candidate_sha256'],current_hash=integrity.sha256_file(cand))
 r=critique.record_critique(p,'ch01-sc01','a.md','style-editor','pass',filename='../escaped')
 emit('filename-traversal',record=r,escaped_exists=(s/'escaped.json').exists())
 fake={'dimension':'agency','severity':'material','evidence':'A quote absent from the candidate','diagnosis':'test','repair_layer':'scene'}
 emit('fabricated-evidence',result=critique.record_critique(p,'ch01-sc01','a.md','style-editor','revise',findings=[fake],filename='fabricated'))
 class Fail:
  def complete(self,*a,**kw):raise role_runner.VendorUnavailable('offline intentional failure')
 emit('all-roles-failed',result=role_runner.run_panel(str(p),'ch01-sc01','a.md',['style-editor'],roster=roster,transport_for=lambda _:Fail()))
 emit('empty-claims',result=prose_audit.audit_prose(p,'ch01-sc01',{}))
 delta=json.loads((s/'state-delta.json').read_text());delta['facts_added']=[{'id':'fact-secret','text':'Secret elsewhere'}];write(s/'state-delta.json',delta)
 claims={'scene_id':'ch99-sc99','candidate':'a.md','pov':'char-a','tense':'mixed','word_count':0,'claims':[{'type':'focalizer_knows','subject':'char-a','object':'fact-secret','evidence':'Invented quotation'}]}
 write(p/'planning/discourse-plan.json',{'time':{'tense':'past'}})
 emit('ungranted-fact-mixed-tense-wrong-scene',schema_errors=schema.validate_named(claims,'prose-claims'),result=prose_audit.audit_prose(p,'ch01-sc01',claims))
 p=make(base/'typed');s=p/'scenes/ch01-sc01';spec=json.loads((s/'spec.json').read_text());spec['required_events']=['evt-test'];write(s/'spec.json',spec)
 (p/'canon/world-state.jsonl').write_text(json.dumps({'predicate':'trusts','subject':'char-a','object':'char-b','value':'none'})+'\n')
 atom={'predicate':'trusts','subject':'char-a','object':'char-b','value':'total'}
 write(p/'planning/event-graph.json',{'events':[{'id':'evt-test','preconditions':[atom],'effects':[]}]})
 emit('typed-value-ignored',result=hard_audit.audit_scene(p,'ch01-sc01'))
 atom={'op':'add','predicate':'trusts','subject':'char-a','object':'char-b','value':True}
 write(p/'planning/event-graph.json',{'events':[{'id':'evt-test','preconditions':[],'effects':[atom]}]})
 d=json.loads((s/'state-delta.json').read_text());d['predicate_changes']=[{**atom,'value':False}];write(s/'state-delta.json',d)
 emit('effect-value-ignored',result=hard_audit.audit_scene(p,'ch01-sc01'))
 write(p/'planning/event-graph.json',{'events':[{'id':'evt-test','preconditions':['fact-nonexistent'],'effects':[],'causes':['evt-nonexistent']}]})
 emit('unresolved-string-precondition-cause',result=hard_audit.audit_scene(p,'ch01-sc01'))
 write(p/'planning/event-graph.json',{'events':[]})
 r=subprocess.run([sys.executable,str(ROOT/'scripts/hard_audit.py'),str(p),'ch01-sc01'],capture_output=True,text=True)
 emit('hard-audit-cli-material-exit',exit_code=r.returncode,output=r.stdout)
 p=make(base/'reused',('ch01-sc01','ch01-sc02'))
 (p/'canon/facts.jsonl').write_text(json.dumps({'id':'fact-code','text':'Door code is 1111'})+'\n');(p/'canon/knowledge-state.jsonl').write_text(json.dumps({'character':'char-a','fact':'fact-code'})+'\n')
 d=json.loads((p/'scenes/ch01-sc01/state-delta.json').read_text());d['facts_added']=[{'id':'fact-code','text':'Door code is 2222'}];write(p/'scenes/ch01-sc01/state-delta.json',d);write(p/'canon/index.json',{'accepted_state_deltas':['ch01-sc01']})
 st=state.reconstruct_state_before(p,'ch01-sc02');emit('fact-id-overwrite-knowledge',facts=st.facts,knows_new_code=st.knows('char-a','fact-code'),canon_audit=hard_audit.audit_canon(p))
clean=[{'candidate':'a.md','critic':'defaultness-lint','findings':[]},{'candidate':'b.md','critic':'defaultness-lint','findings':[{'dimension':'rhythm','severity':'minor'}]}]
hard={'candidate':'ch01-sc01','critic':'hard-audit','verdict':'reject','findings':[{'severity':'fatal','dimension':'knowledge'}]}
emit('tournament-ignores-scene-fatal',result=tournament.run_tournament(clean+[hard])['recommendation'])
labels=tournament.anonymize(['a.md','b.md'])[0];a,b=labels['a.md'],labels['b.md']
judges=[{'scores':{a:{'quality':5},b:{'quality':1}}},{'scores':{a:{'quality':2},b:{'quality':3}}}]
r=tournament.run_tournament(clean,judgments=judges);emit('tournament-asymmetric-dissent',recommendation=r['recommendation'],disagreement=r['disagreement'])
r=tournament.run_tournament(clean,judgments=[{'scores':{a:{'quality':1}}}]);emit('tournament-partial-matrix',recommendation=r['recommendation'],eligible=r['floor_eligible'],scored=list(r['scores']))
f=lambda ev,sev:{'dimension':'agency','severity':sev,'evidence':ev,'diagnosis':'test','repair_layer':'scene'}
emit('revision-wrong-issue-fixed',outcome=revision.evaluate_revision([f('target','material'),f('other','minor')],[f('target','material')],target_dimension='agency').decision)
for text in ['The tank was filled with water.','The label read: "deafening silence" — a phrase she hated.']:
 emit('literal-or-deliberate-lint',text=text,findings=defaultness.lint_text(text))
cs=[]
for i,c in enumerate(['internal','interpersonal','character-vs-society']):
 cs.append({'id':str(i),'logline':'Identical story premise.','pov_character':'a','transforming_character':'a','conflict_type':c,'obliqueness':'direct','resolution_type':'humble','theme_question':'Same','why_not_default':'Declared different.'})
emit('self-reported-diversity',result=premise.diversity_floor(cs))
case={'signals':['theme']};fict={'severity':'material','diagnosis':'No theme problem exists; the actual issue is spelling.'};emit('critic-keyword-negation',counted_as_caught=critic_eval.score_findings(case,[fict]))
emit('nan-schema',errors=schema.validate_named({'candidate':'a.md','critic':'style-editor','verdict':'pass','confidence':float('nan'),'findings':[]},'critique'))
path=pathlib.Path(__file__).with_name('probe-results.json');path.write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
