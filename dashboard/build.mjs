import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
const root = path.dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'appinfo.json')));
const out = path.join(root, 'dist');
fs.mkdirSync(out, {recursive:true});
function crc32(bytes) {
  let crc = -1;
  for (const byte of bytes) { crc ^= byte; for (let bit=0;bit<8;bit++) crc=(crc>>>1)^((crc&1)?0xedb88320:0); }
  return (crc ^ -1) >>> 0;
}
function pngChunk(type, data) {
  const name=Buffer.from(type), size=Buffer.alloc(4), crc=Buffer.alloc(4);
  size.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(Buffer.concat([name,data])));
  return Buffer.concat([size,name,data,crc]);
}
function icon(size) {
  const pixels=Buffer.alloc((size*4+1)*size);
  for(let y=0;y<size;y++) for(let x=0;x<size;x++) {
    const scaledX=x*80/size, scaledY=y*80/size;
    let rgb=[0,0,0];
    if(scaledX>=13&&scaledX<67&&scaledY>=18&&scaledY<62) rgb=[45,61,49];
    if(scaledX>=17&&scaledX<63&&scaledY>=22&&scaledY<58) rgb=[10,18,12];
    if(scaledX>=23&&scaledX<57&&scaledY>=29&&scaledY<35) rgb=[196,230,203];
    if(scaledX>=23&&scaledX<57&&scaledY>=43&&scaledY<49) rgb=[102,131,110];
    const i=y*(size*4+1)+1+x*4;
    pixels[i]=rgb[0];pixels[i+1]=rgb[1];pixels[i+2]=rgb[2];pixels[i+3]=255;
  }
  const header=Buffer.alloc(13);header.writeUInt32BE(size);header.writeUInt32BE(size,4);header[8]=8;header[9]=6;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),pngChunk('IHDR',header),pngChunk('IDAT',zlib.deflateSync(pixels)),pngChunk('IEND',Buffer.alloc(0))]);
}
function tar(entries) {
  const blocks=[];
  for(const [name,bytes] of entries) {
    if(Buffer.byteLength(name)>100) throw new Error('Tar name too long');
    const header=Buffer.alloc(512);
    header.write(name,0,100);header.write('0000644\0',100);header.write('0000000\0',108);header.write('0000000\0',116);
    header.write(bytes.length.toString(8).padStart(11,'0')+'\0',124);
    header.write('00000000000\0',136);header.fill(32,148,156);header[156]=48;
    header.write('ustar\0',257);header.write('00',263);
    const sum=header.reduce((a,b)=>a+b,0);header.write(sum.toString(8).padStart(6,'0')+'\0 ',148);
    blocks.push(header,bytes,Buffer.alloc((512-bytes.length%512)%512));
  }
  return Buffer.concat([...blocks,Buffer.alloc(1024)]);
}
function ar(entries) {
  const blocks=[Buffer.from('!<arch>\n')];
  for(const [name,bytes] of entries) {
    const header=name.padEnd(16)+'0'.padEnd(12)+'0'.padEnd(6)+'0'.padEnd(6)+'100644'.padEnd(8)+String(bytes.length).padEnd(10)+'`\n';
    if(Buffer.byteLength(header)!==60) throw new Error('Invalid ar header');
    blocks.push(Buffer.from(header),bytes);if(bytes.length%2)blocks.push(Buffer.from('\n'));
  }
  return Buffer.concat(blocks);
}
const assets=['appinfo.json','index.html','style.css','app.js','ports.js','xsx.png'].map(name=>[name,fs.readFileSync(path.join(root,name))]);
assets.push(['icon.png',icon(80)],['largeIcon.png',icon(130)]);
const data=assets.map(([name,bytes])=>['usr/palm/applications/'+manifest.id+'/'+name,bytes]);
data.push(['usr/palm/packages/'+manifest.id+'/packageinfo.json',Buffer.from(JSON.stringify({id:manifest.id,version:manifest.version,app:manifest.id}))]);
const control=Buffer.from(`Package: ${manifest.id}\nVersion: ${manifest.version}\nSection: misc\nPriority: optional\nArchitecture: all\nInstalled-Size: ${assets.reduce((sum,[,bytes])=>sum+bytes.length,0)}\nMaintainer: Local\nDescription: Local HDMI source selector for webOS TV.\nwebOS-Package-Format-Version: 2\nwebOS-Packager-Version: 1.0.0\n`);
const ipk=ar([['debian-binary',Buffer.from('2.0\n')],['control.tar.gz',zlib.gzipSync(tar([['control',control]]))],['data.tar.gz',zlib.gzipSync(tar(data))]]);
const output=path.join(out,`${manifest.id}_${manifest.version}_all.ipk`);
fs.writeFileSync(output,ipk);
fs.writeFileSync(path.join(out,'build-manifest.json'),JSON.stringify({id:manifest.id,version:manifest.version,ipk:path.basename(output),sha256:crypto.createHash('sha256').update(ipk).digest('hex'),appjs_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'app.js'))).digest('hex')},null,2)+'\n');
console.log(`Built ${output} (${ipk.length} bytes; no runtime dependencies)`);
export {tar,ar,crc32};
