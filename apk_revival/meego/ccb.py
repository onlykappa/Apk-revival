"""Strict CCBI v3 reader for the reviewed Meego countdown panel.

Format reference: https://github.com/cocos2d/CCBReader/blob/master/CCBReader/CCBReader.m
Original implementation; preserves raw property data and refuses unknown layouts.
"""
import struct
class Reader:
 def __init__(self,b):self.b=b;self.p=0;self.cache=[]
 def byte(self):v=self.b[self.p];self.p+=1;return v
 def take(self,n):v=self.b[self.p:self.p+n];assert len(v)==n;self.p+=n;return v
 def integer(self,signed=False):
  bit=0;pos=self.p
  def get():
   nonlocal bit
   v=(self.b[pos+bit//8]>>(bit%8))&1;bit+=1;return v
  n=0
  while not get():
   n+=1;assert n<32
  v=1<<n
  for i in range(n-1,-1,-1):v|=get()<<i
  self.p+=(bit+7)//8
  return (v//2 if v%2 else -v//2) if signed else v-1
 def flt(self):
  t=self.byte()
  if t<4:return (0.,1.,-1.,.5)[t]
  if t==4:return self.integer(True)
  assert t==5,(self.p,t)
  return struct.unpack('<f',self.take(4))[0]
 def string(self):return self.cache[self.integer()]
 def prop(self):
  start=self.p;t=self.integer();name=self.string();platform=self.byte()
  if t in (0,1,4):v=(self.flt(),self.flt(),self.integer())
  elif t in (2,3,8,27):v=(self.flt(),self.flt())
  elif t in (5,7):v=self.flt()
  elif t in (6,20):v=self.integer(True)
  elif t in (9,12):v=self.byte()
  elif t in (10,22):v=(self.string(),self.string())
  elif t in (11,17,18,19,23,24):v=self.string()
  elif t==13:v=tuple(self.take(3))
  elif t==15:v=(self.byte(),self.byte())
  elif t==16:v=(self.integer(),self.integer())
  elif t==21:v=(self.string(),self.integer())
  elif t==26:v=(self.flt(),self.integer())
  else:raise ValueError((start,t,name))
  return dict(type=t,name=name,platform=platform,value=v,raw=self.b[start:self.p])
 def node(self,depth=0):
  start=self.p;cls=self.string();atype=self.integer();name=self.string() if atype else ''
  seq=self.integer();assert seq==0,(self.p,seq)
  reg=self.integer();extra=self.integer()
  props=[self.prop() for _ in range(reg+extra)]
  n=self.integer();children=[self.node(depth+1) for _ in range(n)]
  return dict(cls=cls,name=name,assignment=atype,props=props,extra=extra,children=children)
 def read(self):
  assert self.take(4)==b'ibcc';version=self.integer();assert version==3
  n=self.integer()
  for i in range(n):self.cache.append(self.take(struct.unpack('>H',self.take(2))[0]).decode())
  seqstart=self.p;n=self.integer();sequences=[]
  for i in range(n):sequences.append((self.flt(),self.string(),self.integer(),self.integer(True)))
  auto=self.integer(True);self.prefix=self.b[:self.p]
  self.sequences=self.b[seqstart:self.p]
  node=self.node();assert self.p==len(self.b)
  return node

 def dump(self, tree):
  def integer(value,signed=False):
   v=(2*value+1 if value>=0 else -2*value) if signed else value+1
   assert v>0
   n=v.bit_length()-1;bits=[0]*n+[1]+[(v>>i)&1 for i in range(n-1,-1,-1)]
   out=bytearray((len(bits)+7)//8)
   for i,bit in enumerate(bits):out[i//8]|=bit<<(i%8)
   return bytes(out)
  def string(value):
   if value not in self.cache:self.cache.append(value)
   return integer(self.cache.index(value))
  def flt(value):return b'\x05'+struct.pack('<f',value)
  def prop(p):
   if p.get('raw') is not None:return p['raw']
   t,v=p['type'],p['value']
   if t in (0,1,4):data=flt(v[0])+flt(v[1])+integer(v[2])
   elif t in (2,3,8,27):data=flt(v[0])+flt(v[1])
   elif t in (5,7):data=flt(v)
   elif t in (9,12):data=bytes([v])
   elif t in (17,18,19,24):data=string(v)
   else:raise ValueError('Writing unsupported CCB property')
   return integer(t)+string(p['name'])+bytes([p['platform']])+data
  def node(n):
   head=string(n['cls'])+integer(n['assignment'])
   if n['assignment']:head+=string(n['name'])
   head+=integer(0)+integer(len(n['props'])-n['extra'])+integer(n['extra'])
   return head+b''.join(prop(p) for p in n['props'])+integer(len(n['children']))+b''.join(node(c) for c in n['children'])
  body=node(tree)
  cache=b''.join(struct.pack('>H',len(s.encode()))+s.encode() for s in self.cache)
  return b'ibcc'+integer(3)+integer(len(self.cache))+cache+self.sequences+body
