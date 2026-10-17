#!/usr/bin/env python3
"""Dev-Ville role execution kernel: local-first, auditable, no third-party dependencies.

Repository integration slice; it does not replace Victor's authority system.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
import uuid
import signal
import threading
import time
from datetime import datetime, timezone

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

def chain_valid(db, ticket):
    previous = 'GENESIS'
    try:
        events = db.execute('SELECT * FROM events WHERE ticket_id=? ORDER BY id', (ticket,)).fetchall()
        for event in events:
            msg = {k: event[k] for k in ('ticket_id', 'type', 'previous_hash', 'recorded')}
            msg['payload'] = json.loads(event['payload'])
            if event['previous_hash'] != previous or event['event_hash'] != digest(canonical(msg).encode()):
                return False
            previous = event['event_hash']
        return bool(events) and events[0]['type'] == 'CREATED'
    except (TypeError, ValueError):
        return False

def require_open(db, ticket):
    if check_ticket(db, ticket)['status'] != 'OPEN':
        raise ValueError('Closed ticket cannot be changed')
    if not chain_valid(db, ticket):
        raise ValueError('Event chain is invalid')

def snapshot(workspace, files):
    root = Path(workspace).resolve(strict=True)
    if not files or len(files) > 128:
        raise ValueError('Provide 1..128 explicit input files')
    result = {}
    total = 0
    for file in files:
        path = safe_file(root, file)
        rel = path.relative_to(root).as_posix()
        if rel in result:
            raise ValueError('Duplicate input file')
        data = path.read_bytes()
        total += len(data)
        if total > 32 * 1024 * 1024:
            raise ValueError('Input bundle exceeds 32 MiB')
        result[rel] = digest(data)
    return result

def verify_snapshot(workspace, files):
    return snapshot(workspace, [Path(workspace) / f for f in files]) == files

def output_path(workspace, file):
    root = Path(workspace).resolve(strict=True)
    target = (root / file).resolve()
    if root not in target.parents:
        raise ValueError('Output must remain inside workspace')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Output already exists; choose a new path')
    return target

def atomic_json(target, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2)
        handle.write('\n')
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

def bounded_command(command, root, timeout):
    """Cap wall time and captured output; terminate the POSIX process group."""
    proc = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=(os.name == 'posix'))
    tails = [bytearray(), bytearray()]
    totals = [0, 0]
    exceeded = threading.Event()
    def reader(stream, index):
        try:
            while chunk := stream.read(8192):
                totals[index] += len(chunk)
                tails[index].extend(chunk)
                del tails[index][:-20000]
                if sum(totals) > 4 * 1024 * 1024:
                    exceeded.set()
        finally:
            stream.close()
    threads = [threading.Thread(target=reader, args=(stream, i), daemon=True)
               for i, stream in enumerate((proc.stdout, proc.stderr))]
    for thread in threads: thread.start()
    deadline = time.monotonic() + timeout
    code = None
    try:
        while proc.poll() is None:
            if exceeded.is_set(): code = 125; break
            if time.monotonic() >= deadline: code = 124; break
            exceeded.wait(min(0.02, max(0, deadline-time.monotonic())))
    finally:
        if os.name == 'posix':
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        elif proc.poll() is None:
            proc.kill()
        proc.wait()
        for thread in threads: thread.join(timeout=1)
    if code is None: code = 125 if exceeded.is_set() else proc.returncode
    out, err = [bytes(tail).decode('utf-8', errors='replace') for tail in tails]
    if code == 124: err += f'\ntimed out after {timeout}s'
    if code == 125: err += '\noutput limit exceeded (4 MiB)'
    return code, out, err

def execution_valid(db, ticket, role, report, workspace, preceding):
    if not isinstance(report, dict):
        raise ValueError('Report must be a JSON object')
    row = db.execute('SELECT * FROM executions WHERE id=? AND ticket_id=? AND role=?',
                     (report.get('execution_id'), ticket, role)).fetchone()
    if row is None or row['report'] != canonical(report):
        raise ValueError('Report does not match a runtime execution receipt')
    expected = {r: preceding[r]['id'] for r in STAGES[:STAGES.index(role)]}
    if report.get('predecessors') != expected:
        raise ValueError('Execution belongs to an earlier handoff revision')
    if report.get('returncode') != 0 or report.get('inputs_unchanged') is not True:
        raise ValueError('Execution failed or inputs changed during execution')
    if not verify_snapshot(workspace, report['inputs']):
        raise ValueError('Execution inputs changed since verification')
    if role == 'release-manager' and not verify_snapshot(workspace, report['outputs']):
        raise ValueError('Packaged release changed')

def now():
    return datetime.now(timezone.utc).isoformat()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

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
    CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id), role TEXT NOT NULL, report TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS dependencies(evidence_id INTEGER NOT NULL REFERENCES evidence(id), predecessor_id INTEGER NOT NULL REFERENCES evidence(id), PRIMARY KEY(evidence_id,predecessor_id));
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

def safe_file(workspace, file):
    root=Path(workspace).resolve(strict=True)
    path=Path(file).resolve(strict=True)
    if path == root or root not in path.parents: raise ValueError('Evidence must be inside workspace')
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES: raise ValueError('Evidence must be a file <= 8 MiB')
    return path

def evidence_state(db, ticket, workspace):
    rows=db.execute('SELECT * FROM evidence WHERE ticket_id=? AND id IN (SELECT MAX(id) FROM evidence WHERE ticket_id=? GROUP BY role) ORDER BY id',(ticket,ticket)).fetchall()
    valid={}
    invalid=[]
    for row in rows:
        r=dict(row)
        try:
            if r['role'] not in ROLES or r['kind'] != ROLES[r['role']][0]:
                raise ValueError('Unknown role or mismatched kind')
            if not r['actor'].strip() or not r['verified_by'] or not r['verified_by'].strip() or r['actor'].strip().casefold() == r['verified_by'].strip().casefold():
                raise ValueError('Independent reviewer label required')
            idx = STAGES.index(r['role'])
            if any(role not in valid for role in STAGES[:idx]):
                raise ValueError('Preceding role evidence is invalid')
            deps = db.execute('SELECT predecessor_id FROM dependencies WHERE evidence_id=?', (r['id'],)).fetchall()
            if {d['predecessor_id'] for d in deps} != {valid[role]['id'] for role in STAGES[:idx]}:
                raise ValueError('Preceding role evidence was replaced or is legacy evidence')
            p=safe_file(workspace, Path(workspace)/r['path'])
            if digest(p.read_bytes()) != r['sha256']: raise ValueError('Hash mismatch')
            if r['kind']=='test':
                report=json.loads(p.read_text())
                execution_valid(db, ticket, r['role'], report, workspace, valid)
            if r['kind']=='readiness':
                execution_valid(db, ticket, r['role'], json.loads(p.read_text()), workspace, valid)
            if r['kind']=='deploy':
                raise ValueError('External deployment verifier is not implemented')
            valid[r['role']]=r
        except (OSError, ValueError, KeyError, TypeError) as exc:
            invalid.append({'evidence_id':r['id'],'reason':str(exc)})
            valid.pop(r['role'],None)
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
    if not args.actor.strip() or not args.verifier.strip() or args.actor.strip().casefold() == args.verifier.strip().casefold(): raise ValueError('Executor cannot self-verify or use empty identities')
    p=safe_file(args.workspace,args.file)
    if p.stat().st_size == 0:
        raise ValueError('Evidence must not be empty')
    root=Path(args.workspace).resolve()
    with connect(args.db) as db:
        db.execute('BEGIN IMMEDIATE')
        require_open(db,args.ticket)
        existing, bad=evidence_state(db,args.ticket,args.workspace)
        idx=STAGES.index(args.role)
        missing=[r for r in STAGES[:idx] if r not in existing]
        if missing: raise ValueError('Missing preceding role evidence: '+', '.join(missing))
        if args.kind=='test':
            data=json.loads(p.read_text())
            execution_valid(db,args.ticket,args.role,data,args.workspace,existing)
        if args.kind=='readiness':
            execution_valid(db,args.ticket,args.role,json.loads(p.read_text()),args.workspace,existing)
        if args.kind=='deploy':
            raise ValueError('External deployment verifier is not implemented')
        h=digest(p.read_bytes())
        rel=p.relative_to(root).as_posix()
        cur=db.execute('INSERT INTO evidence(ticket_id,role,kind,path,sha256,actor,verified_by,recorded) VALUES (?,?,?,?,?,?,?,?)', (args.ticket,args.role,args.kind,rel,h,args.actor,args.verifier,now()))
        for predecessor in STAGES[:idx]:
            db.execute('INSERT INTO dependencies VALUES (?,?)', (cur.lastrowid,existing[predecessor]['id']))
        record(db,args.ticket,'EVIDENCE_RECORDED',{'role':args.role,'kind':args.kind,'sha256':h,'path':rel,'actor':args.actor,'verifier':args.verifier})
        print(canonical({'ticket_id':args.ticket,'role':args.role,'sha256':h,'accepted':True,'claim':'artifact hash and structural gate accepted; external truth not inferred'}))

def test_run(args):
    # Trusted local commands only: this is not an OS security sandbox.
    root=Path(args.workspace).resolve(strict=True)
    if not args.command: raise ValueError('Provide a test command after --')
    command=list(args.command)
    if command[0]=='--':command=command[1:]
    if not command:raise ValueError('Missing executable')
    if args.timeout<1 or args.timeout>600:raise ValueError('Timeout must be 1..600 seconds')
    target = output_path(root, args.output)
    inputs = snapshot(root, args.file) if args.ticket else {}
    if args.ticket:
        with connect(args.db) as db:
            require_open(db, args.ticket)
            valid, _ = evidence_state(db, args.ticket, root)
            if any(r not in valid for r in STAGES[:5]):
                raise ValueError('Test execution requires the first five role handoffs')
        if target.relative_to(root).as_posix() in inputs:
            raise ValueError('Test report cannot overwrite an input')
    try:
        code,out,err=bounded_command(command, root, args.timeout)
    except OSError as exc:
        code=127;out='';err=str(exc)
    report={'verified_command':command,'returncode':code,'stdout_tail':out,'stderr_tail':err,'timestamp':now(),'execution_environment':'local-process-not-sandboxed'}
    report.update(execution_id=uuid.uuid4().hex, ticket_id=args.ticket, inputs=inputs,
                  inputs_unchanged=verify_snapshot(root, inputs) if inputs else True)
    if args.ticket:
        report['predecessors'] = {r:valid[r]['id'] for r in STAGES[:5]}
    atomic_json(target, report)
    if args.ticket:
        with connect(args.db) as db:
            db.execute('BEGIN IMMEDIATE')
            require_open(db, args.ticket)
            db.execute('INSERT INTO executions VALUES (?,?,?,?)',
                       (report['execution_id'], args.ticket, 'qa-engineer', canonical(report)))
            record(db,args.ticket,'TEST_EXECUTED',report)
    print(canonical({'report':str(target),'returncode':code,'passed':code==0}))
    if code!=0 or not report['inputs_unchanged']:sys.exit(1)

def package(args):
    root = Path(args.workspace).resolve(strict=True)
    target = output_path(root, args.output)
    archive = output_path(root, args.archive)
    if target == archive:
        raise ValueError('Report and archive must be different files')
    inputs = snapshot(root, args.file)
    for path in (target, archive):
        if path.relative_to(root).as_posix() in inputs:
            raise ValueError('Package output cannot overwrite an input')
    with connect(args.db) as db:
        db.execute('BEGIN IMMEDIATE')
        require_open(db, args.ticket)
        valid, _ = evidence_state(db, args.ticket, root)
        if any(r not in valid for r in STAGES[:6]):
            raise ValueError('Packaging requires independently attached passing QA evidence')
        qa = json.loads((root / valid['qa-engineer']['path']).read_text())
        if any(qa['inputs'].get(path) != sha for path, sha in inputs.items()):
            raise ValueError('Every packaged file must be bound to passing QA input hashes')
        with tempfile.NamedTemporaryFile(dir=archive.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
                for path, sha in sorted(inputs.items()):
                    data = safe_file(root, root / path).read_bytes()
                    if digest(data) != sha:
                        raise ValueError('Input changed during packaging')
                    info = zipfile.ZipInfo(path, date_time=(1980,1,1,0,0,0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    z.writestr(info, data)
            os.replace(temporary, archive)
        finally:
            temporary.unlink(missing_ok=True)
        report = {'execution_id':uuid.uuid4().hex, 'ticket_id':args.ticket,
                  'returncode':0, 'inputs':inputs, 'inputs_unchanged':verify_snapshot(root, inputs),
                  'outputs':snapshot(root, [archive]), 'qa_evidence_id':valid['qa-engineer']['id'],
                  'predecessors':{r:valid[r]['id'] for r in STAGES[:6]},
                  'timestamp':now(), 'status':'RELEASE_CANDIDATE', 'deployed':False}
        atomic_json(target, report)
        db.execute('INSERT INTO executions VALUES (?,?,?,?)',
                   (report['execution_id'],args.ticket,'release-manager',canonical(report)))
        record(db,args.ticket,'RELEASE_PACKAGED',report)
    print(canonical({'report':str(target), 'archive':str(archive), 'status':'RELEASE_CANDIDATE'}))

def chronos_export(args):
    # Derived snapshot through existing TRACE-0; SQLite remains the ticket record.
    from trace0_chronos import ChronosLedger, Trace0Observer
    target = output_path(args.workspace, args.output)
    with connect(args.db) as db:
        check_ticket(db, args.ticket)
        if not chain_valid(db, args.ticket):
            raise ValueError('Cannot export an invalid event chain')
        events = db.execute('SELECT * FROM events WHERE ticket_id=? ORDER BY id', (args.ticket,)).fetchall()
    ledger = ChronosLedger()
    observer = Trace0Observer(ledger)
    for event in events:
        observer.observe(actor='devville-role-runtime', action=event['type'],
                         entity_id=f'devville-ticket:{args.ticket}',
                         payload=json.loads(event['payload']),
                         provenance={'source_event_hash':event['event_hash'],
                                     'source_timestamp':event['recorded'], 'source':'sqlite-ticket-ledger'},
                         authority='observation_only')
    atomic_json(target, {'events':ledger.events(), 'receipts':ledger.receipts(),
                         'chain_valid':ledger.verify_chain(), 'authority':'observation_only'})
    print(canonical({'report':str(target), 'chain_valid':ledger.verify_chain()}))

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
        require_open(db,args.ticket)
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
    p=sub.add_parser('test');p.add_argument('--ticket',type=int);p.add_argument('--file',action='append',default=[]);p.add_argument('--output',default='test_report.json');p.add_argument('--timeout',type=int,default=60);p.add_argument('command',nargs=argparse.REMAINDER)
    p=sub.add_parser('package');p.add_argument('--ticket',type=int,required=True);p.add_argument('--file',action='append',required=True);p.add_argument('--archive',default='release.zip');p.add_argument('--output',default='release_report.json')
    p=sub.add_parser('chronos');p.add_argument('--ticket',type=int,required=True);p.add_argument('--output',default='chronos_snapshot.json')
    p=sub.add_parser('audit');p.add_argument('--ticket',type=int,required=True);p.add_argument('--strict',action='store_true')
    p=sub.add_parser('close');p.add_argument('--ticket',type=int,required=True);p.add_argument('--authorized-by',required=True)
    args=parser.parse_args()
    try: {'roles':roles,'new':create,'attach':attach,'test':test_run,'package':package,'chronos':chronos_export,'audit':audit,'close':close}[args.action](args)
    except (ValueError,sqlite3.Error,OSError) as exc:
        print('ERROR:',str(exc),file=sys.stderr);sys.exit(2)
if __name__=='__main__':main()
