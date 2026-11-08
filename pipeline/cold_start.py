"""Start the packaged pj-v3 UI with Python's standard library only."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.request import urlopen

HERE=Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',type=int,default=8000)
    ap.add_argument('--check',action='store_true',help='serve on a temporary port, fetch every app asset, then exit')
    args=ap.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',0 if args.check else args.port),partial(Handler,directory=str(HERE/'app')))
    url='http://127.0.0.1:'+str(server.server_port)+'/'
    if args.check:
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            files=sorted(p for p in (HERE/'app').rglob('*') if p.is_file())
            for p in files:
                rel=p.relative_to(HERE/'app').as_posix()
                with urlopen(url+rel,timeout=5) as response:
                    assert response.status==200 and response.read()==p.read_bytes(),rel
            with urlopen(url,timeout=5) as response:
                assert response.read()==(HERE/'app/index.html').read_bytes()
            print('COLD START PASS: served and fetched',len(files),'packaged app files; standard library only')
        finally:
            server.shutdown();server.server_close();worker.join()
    else:
        print('Jälki pj-v3: '+url,flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()

if __name__=='__main__': main()
