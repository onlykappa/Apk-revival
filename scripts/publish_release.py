#!/usr/bin/env python3
"""Publish checked CI assets without replacing an existing release or tag."""
import json,pathlib,subprocess,sys
from release_assets import ROOT,version,notes
LEGACY='7458887bf687eaaf8cf29242ba40be518e761abf'

def gh(*args,check=True):return subprocess.run(['gh',*args],cwd=ROOT,check=check,capture_output=True,text=True)
def exists(tag):
    result=gh('api','repos/{owner}/{repo}/releases/tags/'+tag,check=False)
    if result.returncode==0:return True
    if '404' in result.stderr:return False
    raise RuntimeError('Cannot inspect release: '+result.stderr)

def publish():
    tag='v'+version();dist=ROOT/'dist'
    if exists(tag):raise RuntimeError('Release '+tag+' already exists; bump the version instead of replacing downloads')
    # Retain the original engine milestone at its exact historical commit.
    if not exists('v0.1.0'):
        historical=dist/'APK-Revival-0.1.0-source.zip'
        subprocess.run(['git','archive','--format=zip','--prefix=APK-Revival/','-o',str(historical),LEGACY],cwd=ROOT,check=True)
        legacy_notes=dist/'V1-NOTES.md';legacy_notes.write_text(notes('0.1.0'))
        gh('release','create','v0.1.0',str(historical),'--target',LEGACY,'--title','APK Revival v0.1.0 | V1 engine','--notes-file',str(legacy_notes),'--prerelease')
    gh('release','create',tag,str(dist/('APK-Revival-'+version()+'-linux-x86_64.tar.gz')),str(dist/('APK-Revival-'+version()+'-source.zip')),str(dist/'SHA256SUMS.txt'),'--target',sys.argv[1],'--title','APK Revival '+tag+' | V2 launcher','--notes-file',str(dist/'RELEASE-NOTES.md'),'--prerelease')
    print('Published '+tag)

if __name__=='__main__':publish()
