"""Verify the packaged Jälki app from this directory alone: every screen state, every source drawer,
signing gates, approval guards, record re-import, tamper and bad-input refusal.
Needs Python 3 and Node.js (any current LTS) for the headless check. The app itself needs neither.
Run: python3 verify_app.py
Writes nothing inside the repo; one temp file is created and removed.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
APP = HERE / 'app'
HARNESS = HERE / 'validation' / 'ui_harness.js'


def fail(msg, code=1):
    print('VERIFY FAIL: ' + msg)
    raise SystemExit(code)


def main():
    if not APP.is_dir() or not HARNESS.is_file():
        fail('run this from a complete Jälki repo (app/ and validation/ui_harness.js are required).', 2)
    node = shutil.which('node') or shutil.which('bun') or next((str(p) for p in [Path.home() / '.bun/bin/bun'] if p.exists()), None)
    if not node:
        fail('Node.js was not found on PATH. Install Node.js (LTS) to run the headless UI check. '
             'Opening the app (python3 cold_start.py) does not need Node.', 3)
    idx = (APP / 'index.html').read_text()
    missing = [r for r in re.findall(r'(?:src|href)="([^"#]+)"', idx) if not r.startswith('http') and not (APP / r).exists()]
    if missing:
        fail('index.html references missing files: ' + ', '.join(missing))
    js = HARNESS.read_text()
    anchor = "path.join(__dirname, '..', 'app')"
    if anchor not in js:
        fail('validation/ui_harness.js no longer has its app path anchor; it was edited.', 2)
    js = js.replace(anchor, json.dumps(str(APP)))
    fd, tmp = tempfile.mkstemp(suffix='.js', prefix='pjv3-verify-')
    os.close(fd)
    try:
        Path(tmp).write_text(js)
        r = subprocess.run([node, tmp], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(tmp)
    if r.returncode:
        fail('headless harness exited ' + str(r.returncode) + ': ' + r.stderr.strip()[-600:])
    H = json.loads(r.stdout)
    reg = H['reg']
    checks = {
        'pages render without exceptions': not H['errors'],
        'source drawers resolve (no NaN/undefined)': not H['views_bad'],
        'finite figures on every screen': all(not re.search(r'NaN|undefined|Infinity', re.sub('<[^>]+>', ' ', p)) for p in H['pages'].values()),
        'open expert review blocks signing': H['review']['before'] is False and H['review']['sign_blocked'],
        'individual decisions unlock; a rejection signs and replays red': H['review']['accepted'] and H['ready'] and H['review'].get('reject_replay_red') is True,
        'signed record re-imports with approval': reg['reimport'],
        'tampered file refused': reg['bad_import_refused'],
        'tampered approval refused': reg['bad_approval_refused'],
        'tamper detected on replay': reg['tamper_detected'],
        'self-approval blocked': not reg['self_approve'] and not reg['signer_role_approve'],
        'second-role approval works once': reg['approve'] and not reg['approved_twice'],
        'signed record replays green': all(v[1] for v in reg['replay_sign']),
        'hold record replays green': all(v[1] for v in reg['replay_hold']),
        'changed factor breaks seal': reg['seal_test']['same'] is False,
    }
    bad = [k for k, ok in checks.items() if not ok]
    print(json.dumps({'screen_states': len(H['pages']), 'drawer_views': H.get('n_views'), 'checks': len(checks),
                      'failed': bad}, indent=1))
    if bad:
        fail(', '.join(bad))
    print('VERIFY PASS: ' + str(len(checks)) + ' checks over ' + str(len(H['pages'])) + ' screen states')


if __name__ == '__main__':
    main()
