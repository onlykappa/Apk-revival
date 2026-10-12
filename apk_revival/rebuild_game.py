"""Independent, self-authored Tap Quest rebuild. Not restoration of an APK."""
from pathlib import Path
from .backend import Progress

def run(save_path):
    import tkinter as tk
    state=Progress(save_path);window=tk.Tk();window.title('Tap Quest | separate rebuild');window.geometry('480x460');window.configure(bg='#101722')
    tk.Label(window,text='TAP QUEST',font=('sans',28,'bold'),bg='#101722',fg='#74dbb1').pack(pady=(40,10))
    tk.Label(window,text='Independent rebuild of the included fixture',bg='#101722',fg='#b4bdcd').pack()
    label=tk.Label(window,font=('sans',20),bg='#101722',fg='white');label.pack(pady=35)
    def refresh():
        s=state.get();label.config(text=f'Coins: {s["coins"]}    Level: {s["level"]}')
    def collect():state.collect();refresh()
    tk.Button(window,text='Collect coin',command=collect,font=('sans',18),bg='#74dbb1',fg='#101722',padx=25,pady=15).pack();refresh()
    tk.Label(window,text='Every 10 coins raises your level.\nProgress saves after every action.',bg='#101722',fg='#b4bdcd').pack(pady=30)
    window.mainloop()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--save',default=str(Path.home()/'.local/share/apk-revival/rebuild/tapquest.json'));args=parser.parse_args();run(Path(args.save))
