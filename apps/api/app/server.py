"""Web startup, with an opt-in supervised worker for a single free instance."""
import os
import subprocess
import sys
import threading
import uvicorn
from .bootstrap import main as bootstrap


def supervise_worker(stop):
    while not stop.is_set():
        process=subprocess.Popen([sys.executable,'-m','apps.api.app.worker'])
        try:
            while process.poll() is None and not stop.wait(1):
                pass
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait()
        stop.wait(2)


def main():
    bootstrap()
    stop=threading.Event();worker=None
    if os.environ.get('MOBBS_EMBEDDED_WORKER')=='1':
        worker=threading.Thread(target=supervise_worker,args=(stop,),daemon=True)
        worker.start()
    try:
        uvicorn.run('apps.api.app.main:app',host='0.0.0.0',port=int(os.environ.get('PORT','8000')),access_log=False)
    finally:
        stop.set()
        if worker:worker.join(timeout=28)


if __name__=='__main__':
    main()
