"""Rasterize the project's geometric F/arrow mark without image dependencies."""
import struct,zlib
from pathlib import Path
n=512; bg=(18,27,21,255); green=(181,231,187,255); orange=(245,173,121,255)
pixels=bytearray(n*n*4)
for y in range(n):
 for x in range(n):
  dx=max(65-x,0,x-446);dy=max(65-y,0,y-446)
  color=bg if dx*dx+dy*dy<=65*65 else (0,0,0,0)
  if 108<=x<160 and 118<=y<390 or 108<=x<303 and 118<=y<170 or 108<=x<255 and 223<=y<275:color=green
  if 307<=x<403 and 210<=y<250 or 363<=x<403 and 210<=y<309 or 232<=x<388 and abs(y-(598-x))<23:color=orange
  pixels[(y*n+x)*4:(y*n+x+1)*4]=bytes(color)
def chunk(kind,payload):return struct.pack('!I',len(payload))+kind+payload+struct.pack('!I',zlib.crc32(kind+payload)&0xffffffff)
raw=b''.join(b'\x00'+pixels[y*n*4:(y+1)*n*4] for y in range(n))
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',n,n,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
Path('desktop/icon.png').write_bytes(png)
