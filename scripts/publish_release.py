#!/usr/bin/env python3
"""Publish checked CI assets without replacing an existing release or tag."""
import subprocess,sys
from release_assets import ROOT,version,notes

def gh(*args,check=True):
    result=subprocess.run(['gh',*args],cwd=ROOT,capture_output=True,text=True)
    if check and result.returncode:raise RuntimeError('GitHub publishing failed: '+result.stderr.strip())
    return result
def exists(tag):
    result=gh('api','repos/{owner}/{repo}/releases/tags/'+tag,check=False)
    if result.returncode==0:return True
    if '404' in result.stderr:return False
    raise RuntimeError('Cannot inspect release: '+result.stderr)

def publish():
    tag='v'+version();dist=ROOT/'dist'
    if exists(tag):raise RuntimeError('Release '+tag+' already exists; bump the version instead of replacing downloads')
    gh('release','create',tag,str(dist/('APK-Revival-'+version()+'-linux-x86_64.tar.gz')),str(dist/('APK-Revival-'+version()+'-source.zip')),*[str(p) for p in sorted(dist.glob('APK-Revival-plugin-*-'+version()+'.zip'))],str(dist/'SHA256SUMS.txt'),'--target',sys.argv[1],'--title','APK Revival '+tag+' | V2 launcher','--notes-file',str(dist/'RELEASE-NOTES.md'),'--prerelease')
    print('Published '+tag)

if __name__=='__main__':publish()

