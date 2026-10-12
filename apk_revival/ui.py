"""Native local desktop UI. Long jobs run off the Tk event loop."""
from __future__ import annotations
import json, pathlib, queue, subprocess, sys, threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from .analysis import analyze, markdown
from .exporter import export_game
from .restoration import Restorer
from .runtime import WaydroidRuntime
from .saves import Saves
from .util import RevivalError
from .verification import verify

BG='#0e1520';PANEL='#172130';TEXT='#e9edf5';MUTED='#a6b4c8';ACCENT='#75dfb4'

class App:
    def __init__(self,store):
        self.store=store;self.root=tk.Tk();self.root.title('APK Revival');self.root.geometry('1180x790');self.root.minsize(960,650);self.root.configure(bg=BG)
        self.events=queue.Queue();self.busy=False;self.runtime=None;self.rebuild=None;self.current=None;self.actions=[]
        style=ttk.Style(self.root);style.theme_use('clam')
        style.configure('.',background=PANEL,foreground=TEXT,font=('sans',10));style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=TEXT)
        style.configure('TButton',background=PANEL,foreground=TEXT,padding=(14,9),borderwidth=0);style.map('TButton',background=[('active','#2c3e52')],foreground=[('disabled','#657185')])
        style.configure('TNotebook',background=BG,borderwidth=0);style.configure('TNotebook.Tab',background=PANEL,padding=(20,12));style.map('TNotebook.Tab',background=[('selected','#294038')])
        style.configure('Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,rowheight=40,borderwidth=0);style.map('Treeview',background=[('selected','#294638')],foreground=[('selected',TEXT)])
        style.configure('Treeview.Heading',background=BG,foreground=MUTED)
        header=ttk.Frame(self.root);header.pack(fill='x',padx=26,pady=(22,18))
        ttk.Label(header,text='APK REVIVAL',font=('sans',24,'bold'),foreground=ACCENT).pack(side='left')
        ttk.Label(header,text='V1  /  LOCAL RESTORATION WORKBENCH',foreground=MUTED).pack(side='left',padx=22)
        self.button(header,'Dependency check',self.doctor).pack(side='right')
        body=ttk.Frame(self.root);body.pack(fill='both',expand=True,padx=26)
        left=ttk.Frame(body,width=280);left.pack(side='left',fill='y',padx=(0,22));left.pack_propagate(False)
        ttk.Label(left,text='GAME LIBRARY',foreground=MUTED).pack(anchor='w',pady=(0,12))
        self.tree=ttk.Treeview(left,columns=('status',),show='tree headings',selectmode='browse');self.tree.heading('#0',text='Game');self.tree.column('#0',width=145);self.tree.heading('status',text='Status');self.tree.column('status',width=120);self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda e:self.selected())
        self.button(left,'+ Import APK',self.import_apk).pack(fill='x',pady=(14,8))
        self.button(left,'Attach supporting files',self.attach).pack(fill='x')
        right=ttk.Frame(body);right.pack(side='left',fill='both',expand=True)
        self.title=ttk.Label(right,text='Bring an old game back to local play',font=('sans',19,'bold'));self.title.pack(anchor='w')
        self.subtitle=ttk.Label(right,text='Import an APK to begin. Originals are preserved.',foreground=MUTED);self.subtitle.pack(anchor='w',pady=(8,18))
        top=ttk.Frame(right);top.pack(fill='x',pady=(0,14))
        for label,action in [('Analyze',self.analyze),('Runtime settings',self.settings),('Play',self.play),('Stop',self.stop)]:self.button(top,label,action).pack(side='left',padx=(0,9))
        self.tabs=ttk.Notebook(right);self.tabs.pack(fill='both',expand=True)
        report_frame=ttk.Frame(self.tabs);path_frame=ttk.Frame(self.tabs);log_frame=ttk.Frame(self.tabs)
        self.tabs.add(report_frame,text='Evidence report');self.tabs.add(path_frame,text='Restoration');self.tabs.add(log_frame,text='Activity & diagnostics')
        self.report=self.text(report_frame);self.logs=self.text(log_frame)
        ttk.Label(path_frame,text='Choose the smallest supported change',font=('sans',15,'bold')).pack(anchor='w',padx=18,pady=(18,8))
        ttk.Label(path_frame,text='Adapters provide game-specific logic. Rebuilding is the last option.',foreground=MUTED).pack(anchor='w',padx=18,pady=(0,16))
        self.path=tk.StringVar(value='offline_patch')
        for val,title,desc in [('offline_patch','1  Offline APK patch','Modify a copy, rebuild, sign and verify its signature.'),('local_backend','2  Local backend','Preserve client gameplay with a documented local protocol.'),('rebuild','3  Separate rebuild','Assess feasibility, then implement a separate game.')]:
            row=ttk.Frame(path_frame);row.pack(fill='x',padx=18,pady=7)
            ttk.Radiobutton(row,text=title,variable=self.path,value=val).pack(anchor='w');ttk.Label(row,text=desc,foreground=MUTED).pack(anchor='w',padx=25,pady=(4,0))
        controls=ttk.Frame(path_frame);controls.pack(fill='x',padx=18,pady=15)
        for label,action in [('Review plan',self.plan),('Prepare selected path',self.prepare),('Reset profile',self.reset)]:self.button(controls,label,action).pack(side='left',padx=(0,8))
        self.plan_view=self.text(path_frame,height=8)
        bottom=ttk.Frame(right);bottom.pack(fill='x',pady=14)
        for label,action in [('Verify offline',self.verify),('Diagnostics',self.diagnostics),('Export',self.export),('Save backup',self.backup),('Restore save',self.restore)]:self.button(bottom,label,action).pack(side='left',padx=(0,7))
        footer=ttk.Frame(self.root);footer.pack(fill='x',padx=26,pady=(0,16));self.status=ttk.Label(footer,text='Ready. No game has been verified.',foreground=MUTED);self.status.pack(side='left');self.progress=ttk.Progressbar(footer,mode='indeterminate',length=160);self.progress.pack(side='right')
        self.refresh();self.root.protocol('WM_DELETE_WINDOW',self.close);self.poll_id=self.root.after(100,self.poll)
    def button(self,parent,text,command):
        b=ttk.Button(parent,text=text,command=command);self.actions.append(b);return b
    def text(self,parent,height=None):
        wrap=ttk.Frame(parent);wrap.pack(fill='both',expand=True,padx=14,pady=14)
        t=tk.Text(wrap,bg=PANEL,fg=TEXT,insertbackground=TEXT,font=('monospace',10),wrap='word',relief='flat',padx=16,pady=14,height=height or 12)
        sb=ttk.Scrollbar(wrap,command=t.yview);sb.pack(side='right',fill='y');t.configure(yscrollcommand=sb.set);t.pack(fill='both',expand=True);t.configure(state='disabled');return t
    def put(self,t,value,append=False):
        t.configure(state='normal')
        if not append:t.delete('1.0','end')
        t.insert('end',value);t.see('end' if append else '1.0');t.configure(state='disabled')
    def refresh(self,select=None):
        current=select or self.current
        self.tree.delete(*self.tree.get_children())
        for p in self.store.games():self.tree.insert('','end',iid=p['id'],text=p['title'],values=(p['status'],))
        if current and self.tree.exists(current):self.tree.selection_set(current);self.selected()
    def selected(self):
        if self.busy:return
        ids=self.tree.selection()
        if not ids:return
        new_game=self.current!=ids[0];self.current=ids[0];p=self.store.load(self.current,check=False);self.title.configure(text=p['title']);fixture=bool(p['analysis'] and p['analysis']['fixture'])
        self.subtitle.configure(text=p['status']+('  |  SELF-AUTHORED FIXTURE' if fixture else '')+'  |  '+p['id'][:12])
        self.put(self.report,markdown(p) if p['analysis'] else 'Not analyzed. Select Analyze to inspect metadata, assets and references.\n\nNo gameplay claims are made from import or static inspection.')
        if p['analysis'] and (new_game or p['restoration']['path']):self.path.set(p['restoration']['path'] or p['analysis']['recommended_path'])
        plan=p['restoration'].get('plan',{})
        candidate=self.store.directory(p['id'])/('plan-'+self.path.get()+'.json')
        if not plan and candidate.exists():
            from .util import read_json
            plan=read_json(candidate)
        self.put(self.plan_view,json.dumps(plan,indent=2))
        self.put(self.logs,'\n'.join(json.dumps(x,ensure_ascii=False) for x in p['logs'])+'\n'+json.dumps(p['verification'],indent=2))
    def game(self):
        if not self.current:raise RevivalError('Import/select a game first')
        return self.current
    def job(self,label,fn,callback=None):
        if self.busy:return
        self.busy=True;self.status.configure(text=label+'…');self.progress.start(12)
        for b in self.actions:b.configure(state='disabled')
        def worker():
            try:self.events.put(('ok',label,fn(),callback))
            except Exception as e:self.events.put(('error',label,str(e),None))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            kind,label,result,callback=self.events.get_nowait();self.busy=False;self.progress.stop()
            for b in self.actions:b.configure(state='normal')
            if kind=='error':self.status.configure(text=label+' failed');messagebox.showerror('Actionable error',result);self.put(self.logs,'\n'+label+': '+result,append=True)
            else:
                self.refresh();self.status.configure(text=label+' completed')
                if callback:callback(result)
                else:self.put(self.logs,'\n'+label+'\n'+json.dumps(result,indent=2,default=str),append=True)
        except queue.Empty:pass
        self.poll_id=self.root.after(100,self.poll)
    def safe(self,fn):
        try:fn()
        except (RevivalError,OSError) as e:messagebox.showerror('APK Revival',str(e))
    def import_apk(self):
        file=filedialog.askopenfilename(title='Select base APK',filetypes=[('Android APK','*.apk'),('All files','*')])
        if file:self.job('Import',lambda:self.store.import_game(file),lambda p:self.refresh(p['id']))
    def attach(self):
        self.safe(lambda:self._attach())
    def _attach(self):
        game=self.game();files=filedialog.askopenfilenames(title='Attach OBBs, splits, assets, logs or saves')
        if files:self.job('Attach files',lambda:self.store.attach(game,files))
    def analyze(self):self.safe(lambda:self.job('Analyze',lambda:analyze(self.store,self.game())))
    def plan(self):
        game=self.current;path=self.path.get()
        self.safe(lambda:self.job('Review plan',lambda:Restorer(self.store).plan(game or self.game(),path),lambda value:self.put(self.plan_view,json.dumps(value,indent=2))))
    def prepare(self):
        game=self.current;path=self.path.get();self.safe(lambda:self.job('Prepare '+path,lambda:Restorer(self.store).prepare(game or self.game(),path)))
    def settings(self):
        def run():
            p=self.store.load(self.game());serial=simpledialog.askstring('Runtime','Exact ADB serial, such as 192.168.240.112:5555',initialvalue=p['runtime']['serial'] or '',parent=self.root)
            if not serial:return
            port=simpledialog.askinteger('Backend port','Host/guest loopback port',initialvalue=p['runtime']['backend_port'],minvalue=1024,maxvalue=65535,parent=self.root)
            if port is None:return
            changed=port!=p['runtime']['backend_port'];p['runtime'].update(serial=serial,backend_port=port)
            if changed and p['restoration']['path']=='local_backend':p['restoration']={'path':None,'operations':[],'artifact':None};p['verification']=[];p['status']='Analyzed'
            self.store.save(p);self.refresh()
        self.safe(run)
    def doctor(self):
        serial=self.store.load(self.current)['runtime']['serial'] if self.current else None
        self.job('Dependency/runtime check',lambda:WaydroidRuntime(serial).probe(),lambda value:(self.tabs.select(2),self.put(self.logs,json.dumps(value,indent=2))))
    def stop_owned(self):
        if self.runtime:self.runtime.stop();self.runtime=None
        if self.rebuild:
            if self.rebuild.poll() is None:self.rebuild.terminate();self.rebuild.wait(timeout=5)
            self.rebuild=None
    def play(self):
        def start():
            p=self.store.load(self.game());self.stop_owned()
            if p['restoration']['path']=='rebuild':
                if not p['rebuild']['feasibility']:raise RevivalError('Prepare rebuild first')
                self.rebuild=subprocess.Popen([sys.executable,'-m','apk_revival.rebuild_game','--save',str(self.store.directory(p['id'])/'saves/rebuild.json')]);return {'started':'Separate self-authored fixture rebuild'}
            self.runtime=WaydroidRuntime(p['runtime']['serial']);return self.runtime.start(self.store,p)
        self.safe(lambda:self.job('Play',start))
    def stop(self):self.job('Stop',lambda:(self.stop_owned(),{'stopped':True})[1])
    def verify(self):
        def run():self.stop_owned();return verify(self.store,self.game())
        self.safe(lambda:self.job('Verify offline',run))
    def diagnostics(self):
        def run():
            self.stop_owned();p=self.store.load(self.game());r=WaydroidRuntime(p['runtime']['serial'])
            try:return r.diagnostics(self.store,p,original=not bool(p['restoration'].get('artifact')))
            finally:r.stop()
        self.safe(lambda:self.job('Capture runtime diagnostics',run))
    def export(self):
        def run():
            game=self.game();output=filedialog.asksaveasfilename(title='Export portable package',defaultextension='.zip',initialfile='APK-Revival-'+game[:8]+'.zip')
            if output:self.job('Export',lambda:export_game(self.store,game,output))
        self.safe(run)
    def backup(self):self.safe(lambda:self.job('Save backup',lambda:Saves(self.store).backup(self.game())))
    def restore(self):
        def run():
            game=self.game();backup=filedialog.askopenfilename(title='Select matching save backup',filetypes=[('Backup ZIP','*.zip')])
            if backup:
                def restore():self.stop_owned();return Saves(self.store).restore(game,backup)
                self.job('Restore save',restore)
        self.safe(run)
    def reset(self):
        def run():self.stop_owned();return self.store.reset(self.game())
        self.safe(lambda:self.job('Reset profile',run))
    def close(self):
        if self.busy:messagebox.showinfo('Work in progress','Wait for the current operation to finish before closing.');return
        self.safe(self.stop_owned);self.root.after_cancel(self.poll_id);self.root.destroy()
    def run(self):self.root.mainloop()

def run(store):App(store).run()
