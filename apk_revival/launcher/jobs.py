"""Serialized jobs with actual steps, inspired by OmniPC's JobManager."""
from __future__ import annotations
from dataclasses import dataclass,field
import copy,threading,uuid
from ..util import RevivalError,now

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
    def __init__(self):self.lock=threading.Lock();self.active=None;self.history=[]
    def run(self,label,operation,notify=lambda _:None):
        if not self.lock.acquire(blocking=False):raise RevivalError('Another task is running. Wait for it to finish or cancel at the next safe stage.')
        job=Job(label);self.active=job;self.history.append(job)
        try:
            job.state='running';notify(job.snapshot());result=operation(Context(job,notify));job.state='succeeded'
            for s in job.steps:
                if s['state']=='running':s['state']='done'
            return result
        except Exception as e:
            job.state='cancelled' if isinstance(e,Cancelled) else 'failed';job.error=str(e)
            for s in job.steps:
                if s['state']=='running':s['state']='skipped' if job.state=='cancelled' else 'failed';s['detail']=str(e)
            raise
        finally:
            job.ended_at=now();notify(job.snapshot());self.active=None;self.lock.release()
    def cancel(self):
        if self.active:self.active.cancellation.set()
