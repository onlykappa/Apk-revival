#!/usr/bin/env python3
"""Build actual Android DEX/AXML APK using SDK tools, without Gradle."""
import argparse, os, pathlib, subprocess, sys, tempfile, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from apk_revival.util import RevivalError, command, tool


def build(android_jar,ecj,out):
    java=tool('java');aapt=tool('aapt');d8=tool('d8')
    with tempfile.TemporaryDirectory() as temp:
        temp=pathlib.Path(temp);classes=temp/'classes';classes.mkdir();dex=temp/'dex';dex.mkdir()
        sources=list((ROOT/'fixtures/android/src').rglob('*.java'))
        command([java,'-jar',ecj,'-8','-proc:none','-classpath',android_jar,'-d',classes,*sources])
        command([d8,'--lib',android_jar,'--min-api','23','--output',dex,*classes.rglob('*.class')])
        command([aapt,'package','-f','-M',ROOT/'fixtures/android/AndroidManifest.xml','-I',android_jar,'-A',ROOT/'fixtures/android/assets','-F',temp/'unsigned.apk'])
        with zipfile.ZipFile(temp/'unsigned.apk','a') as z:z.write(dex/'classes.dex','classes.dex')
        command([tool('zipalign'),'-f','-p','4',temp/'unsigned.apk',temp/'aligned.apk'])
        env=dict(os.environ);env['APKR_BUILD_PASS']='fixture-build-ephemeral'
        command([tool('keytool'),'-genkeypair','-keystore',temp/'key.p12','-alias','fixture','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=Self-authored fixture','-storepass:env','APKR_BUILD_PASS'],env=env)
        out=pathlib.Path(out);out.parent.mkdir(parents=True,exist_ok=True)
        command([tool('apksigner'),'sign','--ks',temp/'key.p12','--ks-pass','env:APKR_BUILD_PASS','--out',out,temp/'aligned.apk'],env=env)
        print(command([tool('apksigner'),'verify','--verbose',out]));print(out.resolve())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--android-jar',required=True);p.add_argument('--ecj',required=True);p.add_argument('--out',default=str(ROOT/'build/tapquest-original.apk'));a=p.parse_args()
    try:build(a.android_jar,a.ecj,a.out)
    except RevivalError as e:print(e,file=sys.stderr);sys.exit(1)
