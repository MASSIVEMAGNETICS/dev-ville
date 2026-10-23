import json
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
  t=self.ticket();(self.root/'source.py').write_text('print(42)')
  p=self.runcli('test','--ticket',t,'--input','source.py','--',sys.executable,'source.py')
  self.assertTrue(json.loads(p.stdout)['passed'])
  report=json.loads((self.root/'test_report.json').read_text());self.assertEqual(report['returncode'],0)
 def test_fake_deployment_rejected(self):
  t=self.ticket()
  # Deployment JSON is rejected even if called after stages, by its structural check.
  (self.root/'deployment.json').write_text('{"deployed":true,"externally_verified":false}')
  p=self.runcli('attach','--ticket',t,'--role','devops-engineer','--kind','deploy','--file',self.root/'deployment.json','--actor','worker','--verifier','checker',ok=False)
  self.assertNotEqual(p.returncode,0)
 def attach_role(self,t,role,filename,kind=None):
  import devville_roles
  return self.runcli('attach','--ticket',t,'--role',role,
   '--kind',kind or devville_roles.ROLES[role][0],'--file',self.root/filename,
   '--actor','worker','--verifier','checker',ok=False)
 def fill_to_qa(self,t):
  import devville_roles
  for role in devville_roles.STAGES[:5]:
   name=role+'.md';(self.root/name).write_text(role)
   p=self.attach_role(t,role,name);self.assertEqual(p.returncode,0,p.stderr)
 def test_fabricated_passing_report_rejected(self):
  t=self.ticket();self.fill_to_qa(t)
  (self.root/'fake.json').write_text(json.dumps({'ticket_id':t,'returncode':0,'verified_command':['true']}))
  p=self.attach_role(t,'qa-engineer','fake.json')
  self.assertIn('no recorded execution',p.stderr)
 def test_execution_bound_to_ticket_and_source(self):
  t=self.ticket();self.fill_to_qa(t)
  (self.root/'source.py').write_text('print(42)')
  self.runcli('test','--ticket',t,'--input','source.py','--',sys.executable,'source.py')
  p=self.attach_role(t,'qa-engineer','test_report.json');self.assertEqual(p.returncode,0,p.stderr)
  (self.root/'source.py').write_text('print(99)')
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertFalse(report['role_gates']['qa-engineer'])
 def test_other_ticket_report_rejected(self):
  t=self.ticket();other=self.ticket();self.fill_to_qa(other)
  (self.root/'source.py').write_text('print(42)')
  self.runcli('test','--ticket',t,'--input','source.py','--',sys.executable,'source.py')
  self.assertIn('belong to this ticket',self.attach_role(other,'qa-engineer','test_report.json').stderr)
 def test_upstream_reattachment_invalidates_handoffs_and_recovers(self):
  t=self.ticket();self.fill_to_qa(t)
  p=self.attach_role(t,'product-manager','product-manager.md');self.assertEqual(p.returncode,0,p.stderr)
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertTrue(report['role_gates']['product-manager'])
  self.assertFalse(report['role_gates']['product-owner'])
  self.fill_to_qa(t)
  report=json.loads(self.runcli('audit','--ticket',t).stdout)
  self.assertFalse(report['invalid_evidence'])
  self.assertTrue(report['role_gates']['technical-program-manager'])
 def test_tampered_chain_blocks_closure_and_writes(self):
  import sqlite3
  t=self.ticket()
  with sqlite3.connect(self.db) as db:db.execute("UPDATE events SET event_hash='tampered'")
  self.assertIn('chain is invalid',self.runcli('close','--ticket',t,'--authorized-by','owner',ok=False).stderr)
  (self.root/'problem.md').write_text('problem')
  self.assertIn('chain is invalid',self.attach_role(t,'product-manager','problem.md').stderr)
 def test_deployment_booleans_rejected_at_actual_gate(self):
  t=self.ticket()
  (self.root/'deploy.json').write_text('{"deployed":true,"externally_verified":true}')
  self.assertIn('No external deployment verifier',self.attach_role(t,'devops-engineer','deploy.json').stderr)
 def test_output_escape_rejected_before_process_runs(self):
  t=self.ticket();(self.root/'source.py').write_text('print(42)')
  p=self.runcli('test','--ticket',t,'--input','source.py','--output','../escape.json','--',sys.executable,'-c','raise Exception("ran")',ok=False)
  self.assertIn('Output must remain',p.stderr)
 def test_failing_test_not_accepted(self):
  t=self.ticket();self.fill_to_qa(t)
  (self.root/'source.py').write_text('raise SystemExit(3)')
  p=self.runcli('test','--ticket',t,'--input','source.py','--',sys.executable,'source.py',ok=False)
  self.assertNotEqual(p.returncode,0)
  self.assertNotEqual(self.attach_role(t,'qa-engineer','test_report.json').returncode,0)
if __name__=='__main__':unittest.main()
