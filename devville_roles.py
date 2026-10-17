#!/usr/bin/env python3
"""Dev-Ville role execution kernel: local-first, auditable, no third-party dependencies.

This is a standalone integration slice, not a replacement for existing Victor/Dev-Ville.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from trace0_chronos import canonical_json

ROLES = {
 'product-manager': ('problem', 'problem.md'),
 'product-owner': ('acceptance', 'acceptance.md'),
 'software-architect': ('architecture', 'architecture.md'),
 'engineering-lead': ('implementation', 'implementation.md'),
 'technical-program-manager': ('delivery', 'delivery.md'),
 'qa-engineer': ('test', 'test_report.json'),
 'release-manager': ('readiness', 'release.md'),
 'devops-engineer': ('deploy', 'deployment.json'),
 'product-marketing-manager': ('launch', 'launch.md'),
 'product-operations-manager': ('operations', 'operations.md'),
}
STAGES = list(ROLES)
STAGES_REQUIRED = {k: v[0] for k,v in ROLES.items()}
MAX_FILE_BYTES = 8 * 1024 * 1024

def now():
    return datetime.now(timezone.utc).isoformat()

def canonical(obj):
    return canonical_json(obj)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, name TEXT NOT NULL, problem TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), role TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, actor TEXT NOT NULL, verified_by TEXT, recorded TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), type TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, recorded TEXT NOT NULL);
    ''')
    return db

def record(db, ticket, kind, payload):
    previous = db.execute('SELECT event_hash FROM events WHERE ticket_id=? ORDER BY id DESC LIMIT 1',(ticket,)).fetchone()
    prev = previous['event_hash'] if previous else 'GENESIS'
    stamp=now()
    msg={'ticket_id':ticket,'type':kind,'payload':payload,'previous_hash':prev,'recorded':stamp}
    h=digest(canonical(msg).encode())
    db.execute('INSERT INTO events(ticket_id,type,payload,previous_hash,event_hash,recorded) VALUES (?,?,?,?,?,?)', (ticket,kind,canonical(payload),prev,h,stamp))
    return h

def check_ticket(db, ticket):
    row=db.execute('SELECT * FROM tickets WHERE id=?',(ticket,)).fetchone()
    if row is None: raise ValueError('Unknown ticket')
    return row

def chain_valid(db, ticket):
    previous = 'GENESIS'
    events = db.execute('SELECT * FROM events WHERE ticket_id=? ORDER BY id', (ticket,)).fetchall()
    if not events or events[0]['type'] != 'CREATED':
        return False
    for event in events:
        try:
            msg = {'ticket_id': event['ticket_id'], 'type': event['type'],
                   'payload': json.loads(event['payload']),
                   'previous_hash': event['previous_hash'], 'recorded': event['recorded']}
        except (ValueError, TypeError):
            return False
        if event['previous_hash'] != previous or event['event_hash'] != digest(canonical(msg).encode()):
            return False
        previous = event['event_hash']
    return True

def mutable_ticket(db, ticket):
    row = check_ticket(db, ticket)
    if row['status'] != 'OPEN':
        raise ValueError('Ticket is closed')
    if not chain_valid(db, ticket):
        raise ValueError('Event chain is invalid')
    return row

def test_receipt_valid(db, ticket, path, workspace):
    report = json.loads(path.read_text())
    if report.get('ticket_id') != ticket or report.get('returncode') != 0:
        raise ValueError('Test report must belong to this ticket and pass')
    report_sha = digest(path.read_bytes())
    recorded = False
    for event in db.execute("SELECT payload FROM events WHERE ticket_id=? AND type='TEST_EXECUTED'", (ticket,)):
        if json.loads(event['payload']).get('report_sha256') == report_sha:
            recorded = True
    if not recorded:
        raise ValueError('Test report has no recorded execution receipt')
    if not report.get('inputs'):
        raise ValueError('Test report has no bound input files')
    for item in report['inputs']:
        p = safe_file(workspace, Path(workspace) / item['path'])
        if digest(p.read_bytes()) != item['sha256']:
            raise ValueError('Tested input changed: ' + item['path'])

def safe_file(workspace, file):
    root=Path(workspace).resolve(strict=True)
    path=Path(file).resolve(strict=True)
    if path == root or root not in path.parents: raise ValueError('Evidence must be inside workspace')
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES: raise ValueError('Evidence must be a file <= 8 MiB')
    return path

def evidence_state(db, ticket, workspace):
    rows=db.execute('SELECT * FROM evidence WHERE ticket_id=? ORDER BY id',(ticket,)).fetchall()
    latest = {row['role']: row for row in rows}
    bindings = {}
    for event in db.execute("SELECT payload FROM events WHERE ticket_id=? AND type='EVIDENCE_RECORDED'", (ticket,)):
        payload = json.loads(event['payload'])
        bindings[payload.get('evidence_id')] = payload
    valid={}
    invalid=[]
    for role in STAGES:
        row = latest.get(role)
        if row is None: continue
        r=dict(row)
        try:
            prior = STAGES[:STAGES.index(role)]
            expected = [valid[k]['id'] for k in prior if k in valid]
            binding = bindings.get(r['id'], {})
            for field, column in [('role','role'), ('kind','kind'), ('sha256','sha256'),
                                  ('path','path'), ('actor','actor'), ('verifier','verified_by')]:
                if binding.get(field) != r[column]:
                    raise ValueError('Evidence row differs from recorded receipt')
            if len(expected) != len(prior) or binding.get('predecessors') != expected:
                raise ValueError('Missing or changed predecessor evidence; reattach this handoff')
            p=safe_file(workspace, Path(workspace)/r['path'])
            if digest(p.read_bytes()) != r['sha256']: raise ValueError('Hash mismatch')
            if r['kind']=='test':
                test_receipt_valid(db, ticket, p, workspace)
            if r['kind']=='deploy':
                raise ValueError('No external deployment verifier is configured')
            valid[r['role']]=r
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid.append({'evidence_id':r['id'],'reason':str(exc)})
            valid.pop(r['role'],None)
    # Only the uninterrupted prefix is accepted. Upstream changes invalidate handoffs.
    missing = False
    for role in STAGES:
        missing = missing or role not in valid
        if missing:
            valid.pop(role, None)
    return valid,invalid

def create(args):
    with connect(args.db) as db:
        cur=db.execute('INSERT INTO tickets(name,problem,created) VALUES (?,?,?)',(args.name,args.problem,now()))
        record(db,cur.lastrowid,'CREATED',{'name':args.name,'problem':args.problem})
        print(canonical({'ticket_id':cur.lastrowid,'status':'OPEN'}))

def roles(args):
    for name, (kind, filename) in ROLES.items(): print(f'{name:29} {kind:17} {filename}')

def attach(args):
    if args.role not in ROLES: raise ValueError('Unknown role')
    if args.kind != ROLES[args.role][0]: raise ValueError('Evidence kind does not match role')
    if args.actor == args.verifier: raise ValueError('Executor cannot self-verify')
    if not args.actor.strip() or not args.verifier.strip(): raise ValueError('Actor and verifier must be non-empty')
    if args.kind == 'deploy': raise ValueError('No external deployment verifier is configured')
    p=safe_file(args.workspace,args.file)
    root=Path(args.workspace).resolve()
    with connect(args.db) as db:
        db.execute('BEGIN IMMEDIATE')
        mutable_ticket(db,args.ticket)
        existing, bad=evidence_state(db,args.ticket,args.workspace)
        idx=STAGES.index(args.role)
        missing=[r for r in STAGES[:idx] if r not in existing]
        if missing: raise ValueError('Missing preceding role evidence: '+', '.join(missing))
        if args.kind=='test':
            test_receipt_valid(db,args.ticket,p,args.workspace)
        h=digest(p.read_bytes())
        rel=p.relative_to(root).as_posix()
        cur=db.execute('INSERT INTO evidence(ticket_id,role,kind,path,sha256,actor,verified_by,recorded) VALUES (?,?,?,?,?,?,?,?)', (args.ticket,args.role,args.kind,rel,h,args.actor,args.verifier,now()))
        record(db,args.ticket,'EVIDENCE_RECORDED',{'evidence_id':cur.lastrowid,'predecessors':[existing[r]['id'] for r in STAGES[:idx]],'role':args.role,'kind':args.kind,'sha256':h,'path':rel,'actor':args.actor,'verifier':args.verifier})
        print(canonical({'ticket_id':args.ticket,'role':args.role,'sha256':h,'accepted':True,'claim':'artifact hash and structural gate accepted; external truth not inferred'}))

def test_run(args):
    # No shell invocation; explicit command array, bounded timeout, cwd confined to workspace.
    root=Path(args.workspace).resolve(strict=True)
    target=root/args.output
    if root not in target.resolve().parents:
        raise ValueError('Output must remain inside workspace')
    inputs = []
    for name in args.input:
        p = safe_file(root, root / name)
        if p == target.resolve(): raise ValueError('Report cannot be a test input')
        inputs.append({'path':p.relative_to(root).as_posix(), 'sha256':digest(p.read_bytes())})
    if not inputs: raise ValueError('At least one --input is required')
    with connect(args.db) as db:
        mutable_ticket(db, args.ticket)
    if not args.command: raise ValueError('Provide a test command after --')
    command=list(args.command)
    if command[0]=='--':command=command[1:]
    if not command:raise ValueError('Missing executable')
    if args.timeout<1 or args.timeout>600:raise ValueError('Timeout must be 1..600 seconds')
    try:
        proc=subprocess.run(command,cwd=root,text=True,capture_output=True,timeout=args.timeout,check=False)
        code=proc.returncode
        out=proc.stdout[-20000:]; err=proc.stderr[-20000:]
    except subprocess.TimeoutExpired as exc:
        code=124;out='';err=f'timed out after {args.timeout}s'
    except OSError as exc:
        code=127;out='';err=str(exc)
    for item in inputs:
        try:
            p = safe_file(root, root / item['path'])
            unchanged = digest(p.read_bytes()) == item['sha256']
        except (OSError, ValueError):
            unchanged = False
        if not unchanged:
            code = 125
            err += '\nTest input changed during execution: ' + item['path']
    report={'ticket_id':args.ticket,'inputs':inputs,'verified_command':command,'returncode':code,'stdout_tail':out,'stderr_tail':err,'timestamp':now(),'execution_environment':'local-process-not-sandboxed'}
    if target.resolve()!=root and root in target.resolve().parents:
        target.parent.mkdir(parents=True,exist_ok=True)
        with connect(args.db) as db:
            db.execute('BEGIN IMMEDIATE')
            mutable_ticket(db, args.ticket)
            target.write_text(json.dumps(report,indent=2)+'\n')
            record(db,args.ticket,'TEST_EXECUTED',{'report_sha256':digest(target.read_bytes()),'returncode':code,'inputs':inputs})
    else:raise ValueError('Output must remain inside workspace')
    print(canonical({'report':str(target),'returncode':code,'passed':code==0}))
    if code!=0:sys.exit(1)

def audit(args):
    with connect(args.db) as db:
        row=check_ticket(db,args.ticket)
        valid,invalid=evidence_state(db,args.ticket,args.workspace)
        chain_ok=chain_valid(db,args.ticket)
        report={'ticket_id':args.ticket,'name':row['name'],'status':row['status'],'role_gates':{r:r in valid for r in STAGES},'next_role':next((r for r in STAGES if r not in valid),None),'invalid_evidence':invalid,'event_chain_valid':chain_ok,'all_role_gates':len(valid)==len(STAGES),'releasable':len(valid)==len(STAGES) and chain_ok and not invalid}
        print(json.dumps(report,indent=2))
        if args.strict and not report['releasable']:sys.exit(2)

def close(args):
    with connect(args.db) as db:
        db.execute('BEGIN IMMEDIATE')
        mutable_ticket(db,args.ticket)
        valid,invalid=evidence_state(db,args.ticket,args.workspace)
        if invalid or len(valid)!=len(STAGES):raise ValueError('Ticket not releasable: missing or invalid evidence')
        if not args.authorized_by:raise ValueError('Independent owner authorization required')
        db.execute('UPDATE tickets SET status=? WHERE id=?',('CLOSED',args.ticket))
        record(db,args.ticket,'CLOSED',{'authorized_by':args.authorized_by,'evidence_ids':[valid[r]['id'] for r in STAGES]})
        print(canonical({'ticket_id':args.ticket,'status':'CLOSED','authorized_by':args.authorized_by}))

def main():
    parser=argparse.ArgumentParser(description='Dev-Ville evidence-gated role runner')
    parser.add_argument('--db',default='devville.sqlite3')
    parser.add_argument('--workspace',default='.')
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('roles')
    p=sub.add_parser('new');p.add_argument('--name',required=True);p.add_argument('--problem',required=True)
    p=sub.add_parser('attach');p.add_argument('--ticket',type=int,required=True);p.add_argument('--role',required=True,choices=STAGES);p.add_argument('--kind',required=True);p.add_argument('--file',required=True);p.add_argument('--actor',required=True);p.add_argument('--verifier',required=True)
    p=sub.add_parser('test');p.add_argument('--ticket',type=int,required=True);p.add_argument('--input',action='append',required=True);p.add_argument('--output',default='test_report.json');p.add_argument('--timeout',type=int,default=60);p.add_argument('command',nargs=argparse.REMAINDER)
    p=sub.add_parser('audit');p.add_argument('--ticket',type=int,required=True);p.add_argument('--strict',action='store_true')
    p=sub.add_parser('close');p.add_argument('--ticket',type=int,required=True);p.add_argument('--authorized-by',required=True)
    args=parser.parse_args()
    try: {'roles':roles,'new':create,'attach':attach,'test':test_run,'audit':audit,'close':close}[args.action](args)
    except (ValueError,sqlite3.Error,OSError) as exc:
        print('ERROR:',str(exc),file=sys.stderr);sys.exit(2)
if __name__=='__main__':main()
