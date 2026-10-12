from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, tempfile, time, zipfile

class RevivalError(Exception):
    pass

def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def atomic_json(path, data):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def read_json(path):
    with open(path, encoding='utf-8') as f: return json.load(f)

def safe_member(name):
    p = pathlib.PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or '..' in p.parts or ':' in name:
        raise RevivalError('Unsafe archive member: ' + name)
    return p

def inspect_zip(path, max_total=4*1024**3):
    try:
        with zipfile.ZipFile(path) as z:
            seen=set(); total=0
            for i in z.infolist():
                safe_member(i.filename)
                if i.filename in seen: raise RevivalError('Duplicate ZIP member: ' + i.filename)
                seen.add(i.filename); total += i.file_size
                if (i.external_attr >> 16) & 0o170000 == 0o120000: raise RevivalError('ZIP symlinks are unsupported')
                if i.flag_bits & 1: raise RevivalError('Encrypted ZIP members are unsupported')
                if total > max_total or i.file_size > 512*1024**2: raise RevivalError('Archive exceeds inspection limit (4 GiB total, 512 MiB/member)')
            return z.namelist()
    except (zipfile.BadZipFile, OSError) as e: raise RevivalError(f'Invalid archive: {e}') from e

def command(args, timeout=90, env=None, input=None):
    try:
        p = subprocess.run([str(x) for x in args], input=input, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError as e: raise RevivalError(f'Missing tool: {args[0]}. Run doctor for setup instructions.') from e
    except subprocess.TimeoutExpired as e: raise RevivalError(f'Command timed out after {timeout}s: {args[0]} '+ ' '.join(str(x) for x in args[1:4]) + '. Check runtime/tool status and retry.') from e
    if p.returncode:
        raise RevivalError(f'{args[0]} failed ({p.returncode}): {(p.stderr or p.stdout)[-4000:]}')
    return p.stdout

def tool(name):
    explicit=os.getenv('APKR_' + name.upper())
    if explicit:
        p=pathlib.Path(explicit)
        if p.is_file(): return str(p)
    found=shutil.which(name)
    if found:return found
    sdk=os.getenv('ANDROID_HOME') or os.getenv('ANDROID_SDK_ROOT')
    if sdk:
        root=pathlib.Path(sdk)
        for p in sorted(root.glob('build-tools/*/'+name), reverse=True):
            if p.is_file():return str(p)
        p=root/'platform-tools'/name
        if p.is_file():return str(p)
    raise RevivalError(f'{name} is missing. Install Android SDK tools or set APKR_{name.upper()} to its executable.')

def apktool(*args):
    jar=os.getenv('APKR_APKTOOL_JAR')
    if jar:return command([tool('java'),'-jar',jar,*args],timeout=180)
    return command([tool('apktool'),*args],timeout=180)
