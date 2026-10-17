"""Serialized jobs with actual steps, inspired by OmniPC's JobManager."""
from __future__ import annotations
from dataclasses import dataclass,field
import copy,pathlib,threading,uuid
from ..util import RevivalError,now,atomic_json

class Cancelled(RevivalError):pass

@dataclass
class Job:
    label:str
    id:str=field(default_factory=lambda:uuid.uuid4().hex)
    state:str='queued'
    steps:list=field(default_factory=list)
    error:str|None=None
    started_at:str=field(default_factory=now)
    ended_at:str|None=None
    cancellation:threading.Event=field(default_factory=threading.Event,repr=False)
    def snapshot(self):return {k:copy.deepcopy(getattr(self,k)) for k in ['id','label','state','steps','error','started_at','ended_at']}

class Context:
    def __init__(self,job,notify):self.job=job;self.notify=notify
    def check(self):
        if self.job.cancellation.is_set():raise Cancelled('Cancelled between safe stages. Completed work and originals are preserved.')
    def step(self,label):
        self.check()
        for s in self.job.steps:
            if s['state']=='running':s['state']='done'
        self.job.steps.append({'label':label,'state':'running','time':now()});self.notify(self.job.snapshot())
    def skipped(self,label,reason):self.job.steps.append({'label':label,'state':'skipped','detail':reason});self.notify(self.job.snapshot())

class Jobs:
    def __init__(self,history_dir=None):
        self.lock=threading.Lock();self.active=None;self.history=[]
        self.history_dir=pathlib.Path(history_dir) if history_dir is not None else None
        self.last_history_error=None
        self.prune()
    def prune(self,keep=200):
        """Keep the newest job logs only; older versions logged every game check."""
        if self.history_dir is None or not self.history_dir.is_dir():return
        try:
            logs=sorted(self.history_dir.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
            for old in logs[keep:]:old.unlink(missing_ok=True)
        except OSError:pass
    def run(self,label,operation,notify=lambda _:None,record=True):
        """record=False runs frequent background checks without history or job-log files."""
        if not self.lock.acquire(blocking=False):raise RevivalError('Another task is running. Wait for it to finish or cancel at the next safe stage.')
        job=Job(label);self.active=job
        if record:self.history.append(job);del self.history[:-100]
        def emit(snapshot):
            if record and self.history_dir is not None:
                try:
                    self.history_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
                    atomic_json(self.history_dir/(job.id+'.json'),snapshot)
                except OSError as error:self.last_history_error=str(error)
            notify(snapshot)
        try:
            job.state='running';emit(job.snapshot());result=operation(Context(job,emit));job.state='succeeded'
            for s in job.steps:
                if s['state']=='running':s['state']='done'
            return result
        except Exception as e:
            job.state='cancelled' if isinstance(e,Cancelled) else 'failed';job.error=str(e)
            for s in job.steps:
                if s['state']=='running':s['state']='skipped' if job.state=='cancelled' else 'failed';s['detail']=str(e)
            raise
        finally:
            job.ended_at=now();emit(job.snapshot());self.active=None;self.lock.release()
    def cancel(self):
        if self.active:self.active.cancellation.set()

