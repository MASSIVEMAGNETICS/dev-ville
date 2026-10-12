import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC=Path(__file__).parent/'devville_roles.py'
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.db=self.root/'state.sqlite3'
 def runcli(self,*args,ok=True):
  p=subprocess.run([sys.executable,str(SRC),'--db',str(self.db),'--workspace',str(self.root),*map(str,args)],capture_output=True,text=True)
  if ok:self.assertEqual(p.returncode,0,p.stderr)
  return p
 def ticket(self):
  return json.loads(self.runcli('new','--name','Example','--problem','Need working tests').stdout)['ticket_id']
 def attach(self,t,role,kind,path,ok=True):
  return self.runcli('attach','--ticket',t,'--role',role,'--kind',kind,'--file',path,'--actor','worker','--verifier','checker',ok=ok)
 def prepare(self):
  t=self.ticket()
  from devville_roles import ROLES, STAGES
  for role in STAGES[:5]:
   kind, filename=ROLES[role]; path=self.root/filename;path.write_text('Reviewed requirement for '+role)
   self.attach(t,role,kind,path)
  (self.root/'app.py').write_text('def answer(): return 42\n')
  (self.root/'test_app.py').write_text('import unittest\nfrom app import answer\nclass Contract(unittest.TestCase):\n def test_answer(self): self.assertEqual(answer(),42)\n')
  return t
 def qa(self,t,**kwargs):
  return self.runcli('test','--ticket',t,'--file',self.root/'app.py','--file',self.root/'test_app.py','--',sys.executable,'-m','unittest','-v','test_app',**kwargs)
 def test_missing_evidence_blocks_closure(self):
  t=self.ticket();p=self.runcli('close','--ticket',t,'--authorized-by','owner',ok=False)
  self.assertNotEqual(p.returncode,0)
  d=json.loads(self.runcli('audit','--ticket',t).stdout);self.assertEqual(d['next_role'],'product-manager')
 def test_self_verification_blocked(self):
  t=self.ticket();(self.root/'problem.md').write_text('real content')
  p=self.runcli('attach','--ticket',t,'--role','product-manager','--kind','problem','--file',self.root/'problem.md','--actor','worker','--verifier','worker',ok=False)
  self.assertNotEqual(p.returncode,0)
 def test_role_order_and_tamper_detection(self):
  t=self.ticket();(self.root/'problem.md').write_text('evidence')
  self.runcli('attach','--ticket',t,'--role','product-manager','--kind','problem','--file',self.root/'problem.md','--actor','worker','--verifier','checker')
  d=json.loads(self.runcli('audit','--ticket',t).stdout);self.assertTrue(d['role_gates']['product-manager'])
  (self.root/'problem.md').write_text('tampered')
  d=json.loads(self.runcli('audit','--ticket',t).stdout);self.assertFalse(d['role_gates']['product-manager']);self.assertTrue(d['invalid_evidence'])
 def test_real_process_runner(self):
  p=self.runcli('test','--','python','-c','print(42)')
  self.assertTrue(json.loads(p.stdout)['passed'])
  report=json.loads((self.root/'test_report.json').read_text());self.assertEqual(report['returncode'],0)
 def test_fake_deployment_rejected(self):
  t=self.ticket()
  # Deployment JSON is rejected even if called after stages, by its structural check.
  (self.root/'deployment.json').write_text('{"deployed":true,"externally_verified":false}')
  p=self.runcli('attach','--ticket',t,'--role','devops-engineer','--kind','deploy','--file',self.root/'deployment.json','--actor','worker','--verifier','checker',ok=False)
  self.assertNotEqual(p.returncode,0)
 def test_forged_passing_test_rejected(self):
  t=self.prepare(); path=self.root/'forged.json'
  path.write_text(json.dumps({'returncode':0,'verified_command':['python','-m','unittest']}))
  p=self.attach(t,'qa-engineer','test',path,ok=False)
  self.assertIn('runtime execution receipt',p.stderr)
 def test_real_qa_package_and_chronos(self):
  t=self.prepare();self.qa(t)
  self.attach(t,'qa-engineer','test',self.root/'test_report.json')
  self.runcli('package','--ticket',t,'--file',self.root/'app.py','--file',self.root/'test_app.py')
  self.attach(t,'release-manager','readiness',self.root/'release_report.json')
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertTrue(report['role_gates']['release-manager']);self.assertEqual(report['next_role'],'devops-engineer')
  self.assertFalse(report['releasable'])
  (self.root/'deployment.json').write_text('{"deployed":true,"externally_verified":true}')
  denied=self.attach(t,'devops-engineer','deploy',self.root/'deployment.json',ok=False)
  self.assertIn('not implemented',denied.stderr)
  self.runcli('chronos','--ticket',t)
  from trace0_chronos import ChronosLedger
  export=json.loads((self.root/'chronos_snapshot.json').read_text())
  ledger=ChronosLedger();ledger.restore(export['events'],export['receipts']);self.assertTrue(ledger.verify_chain())
  (self.root/'release.zip').write_bytes(b'tampered')
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertFalse(report['role_gates']['release-manager'])
 def test_input_edit_invalidates_qa(self):
  t=self.prepare();self.qa(t);self.attach(t,'qa-engineer','test',self.root/'test_report.json')
  (self.root/'app.py').write_text('def answer(): return 0\n')
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertFalse(report['role_gates']['qa-engineer'])
  denied=self.runcli('package','--ticket',t,'--file',self.root/'app.py',ok=False)
  self.assertNotEqual(denied.returncode,0)
 def test_predecessor_revision_invalidates_downstream(self):
  t=self.prepare(); path=self.root/'revised.md';path.write_text('New requirements')
  self.attach(t,'product-manager','problem',path)
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertTrue(report['role_gates']['product-manager'])
  self.assertFalse(report['role_gates']['product-owner'])
 def test_chain_corruption_blocks_close_and_execution(self):
  t=self.prepare()
  with sqlite3.connect(self.db) as db:db.execute("UPDATE events SET event_hash='tampered' WHERE type='CREATED'")
  self.assertFalse(json.loads(self.runcli('audit','--ticket',t).stdout)['event_chain_valid'])
  for command in [('close','--ticket',t,'--authorized-by','owner'),('chronos','--ticket',t)]:
   denied=self.runcli(*command,ok=False);self.assertIn('chain',denied.stderr)
  self.assertNotEqual(self.qa(t,ok=False).returncode,0)
 def test_failed_test_and_modified_report_rejected(self):
  t=self.prepare();(self.root/'app.py').write_text('def answer(): return 0\n')
  self.qa(t,ok=False)
  denied=self.attach(t,'qa-engineer','test',self.root/'test_report.json',ok=False)
  self.assertIn('Execution failed',denied.stderr)
  path=self.root/'test_report.json';report=json.loads(path.read_text());report['returncode']=0;path.write_text(json.dumps(report))
  denied=self.attach(t,'qa-engineer','test',path,ok=False)
  self.assertIn('runtime execution receipt',denied.stderr)
 def test_unverified_file_cannot_be_packaged(self):
  t=self.prepare();self.qa(t);self.attach(t,'qa-engineer','test',self.root/'test_report.json')
  path=self.root/'untested.py';path.write_text('print(1)')
  denied=self.runcli('package','--ticket',t,'--file',path,ok=False)
  self.assertIn('passing QA input hashes',denied.stderr)
 def test_timeout_and_output_escape(self):
  p=self.runcli('test','--timeout','1','--',sys.executable,'-c','import time; time.sleep(3)',ok=False)
  self.assertNotEqual(p.returncode,0)
  self.assertEqual(json.loads((self.root/'test_report.json').read_text())['returncode'],124)
  p=self.runcli('test','--output','../escape.json','--',sys.executable,'-c','print(1)',ok=False)
  self.assertIn('inside workspace',p.stderr)
 def test_output_limit_is_failure(self):
  p=self.runcli('test','--',sys.executable,'-c',"import sys; sys.stdout.write('x'*5000000)",ok=False)
  self.assertNotEqual(p.returncode,0)
  report=json.loads((self.root/'test_report.json').read_text())
  self.assertEqual(report['returncode'],125);self.assertLessEqual(len(report['stdout_tail']),20000)
 def test_empty_evidence_rejected(self):
  t=self.ticket();path=self.root/'empty.md';path.write_text('')
  denied=self.attach(t,'product-manager','problem',path,ok=False)
  self.assertIn('must not be empty',denied.stderr)
if __name__=='__main__':unittest.main()
