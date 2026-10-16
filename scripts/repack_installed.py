"""Offline rebuild using an existing APK Revival PyInstaller distribution.

Run with CPython 3.12 (the embedded interpreter version). Preserve its licensed
bootloader and dependencies; replace every project module with compiled source.
Normal release builds continue to use packaging/apk-revival.spec.
"""
import argparse,pathlib,struct,marshal,zlib,shutil,sys

def repack(source,target,root):
    if sys.version_info[:2]!=(3,12):raise RuntimeError('Requires CPython 3.12')
    source=pathlib.Path(source);target=pathlib.Path(target);root=pathlib.Path(root)
    shutil.copytree(source,target,dirs_exist_ok=True)
    data=(source/'APK-Revival').read_bytes();cookie=data.rfind(b'MEI\014\013\012\013\016')
    magic,size,toc_offset,toc_length,version,library=struct.unpack('!8sIIII64s',data[cookie:cookie+88])
    start=cookie+88-size;position=start+toc_offset;entries=[]
    while position<start+toc_offset+toc_length:
        length,offset,packed,unpacked,flag,kind=struct.unpack('!iIIIBB',data[position:position+18])
        name=data[position+18:position+length].rstrip(b'\0');payload=data[start+offset:start+offset+packed]
        if kind==ord('z'):
            old=payload;toc=marshal.loads(old[struct.unpack('!i',old[8:12])[0]:]);modules=dict(toc)
            new=bytearray(old[:12]);table=[]
            source_modules={str(p.relative_to(root).with_suffix('')).replace('/','.').removesuffix('.__init__'):p for p in (root/'apk_revival').rglob('*.py')}
            for module in sorted(set(modules)|set(source_modules)):
                if module in source_modules:
                    path=source_modules[module];code=compile(path.read_text(),str(path),'exec');blob=zlib.compress(marshal.dumps(code));typ=1 if path.name=='__init__.py' else 0
                else:
                    typ,off,length=modules[module];blob=old[off:off+length]
                table.append((module,(typ,len(new),len(blob))));new.extend(blob)
            toc_position=len(new);new.extend(marshal.dumps(table));new[8:12]=struct.pack('!i',toc_position);payload=bytes(new);unpacked=len(payload);flag=0
        entries.append((name,payload,unpacked,flag,kind));position+=length
    archive=bytearray();toc=bytearray()
    for name,payload,unpacked,flag,kind in entries:
        offset=len(archive);archive.extend(payload);length=(18+len(name)+1+15)//16*16
        toc.extend(struct.pack('!iIIIBB',length,offset,len(payload),unpacked,flag,kind)+name+b'\0'*(length-18-len(name)))
    offset=len(archive);archive.extend(toc);archive.extend(struct.pack('!8sIIII64s',magic,len(archive)+88,offset,len(toc),version,library))
    (target/'APK-Revival').write_bytes(data[:start]+archive+data[cookie+88:]);(target/'APK-Revival').chmod(0o755)
    shutil.copytree(root/'resources',target/'_internal/resources',dirs_exist_ok=True)
    # Portable export copies the project source next to exporter.__file__.
    # PYZ modules alone have synthetic paths and cannot supply that source.
    for path in (root/'apk_revival').rglob('*.py'):
        destination=target/'_internal'/path.relative_to(root)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    (target/'_internal/resources/waydroid-askpass.sh').chmod(0o700)
    print('Rebuilt',target)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('target');parser.add_argument('--root',default=str(pathlib.Path(__file__).resolve().parents[1]));args=parser.parse_args();repack(args.source,args.target,args.root)
