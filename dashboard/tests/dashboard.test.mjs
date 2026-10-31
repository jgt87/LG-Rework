import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=fs.readFileSync(path.join(root,'app.js'),'utf8');
const appids={'apple-tv':'com.apple.appletv',youtube:'youtube.leanback.v4',browser:'com.webos.app.browser',xbox:'com.webos.app.hdmi2',hdmi1:'com.webos.app.hdmi1',hdmi3:'com.webos.app.hdmi3',hdmi4:'com.webos.app.hdmi4','tv-settings':'com.palm.app.settings',game:'com.webos.app.gameoptimizer','lg-home':'com.webos.app.home'};
const labels={'apple-tv':'Apple TV',youtube:'YouTube',browser:'Browser',xbox:'Xbox Series X',hdmi1:'HDMI 1',hdmi3:'HDMI 3',hdmi4:'HDMI 4','tv-settings':'TV Settings',game:'Game Optimizer','lg-home':'LG Home'};
const statusText={'apple-tv':'Apple TV',youtube:'YouTube',browser:'Browser',xbox:'Switch to HDMI 2','tv-settings':'TV Settings',game:'Game Optimizer','lg-home':'LG Home'};
function classList(){const set=new Set();return {set,add:x=>set.add(x),remove:x=>set.delete(x),has:x=>set.has(x)};}
function fixture({preview=false,native=true,ports}={}) {
  const events={},windowEvents={},timers=new Map(),calls=[],bridges=[];
  let sequence=0;
  const body=classList();
  const document={hidden:false,activeElement:{id:''},body:{classList:body},addEventListener:(name,fn)=>events[name]=fn};
  const nodes={};
  for(const id of ['notice','sleep-cover','preview-banner','clock-time','clock-date'])nodes[id]={id,hidden:true,textContent:'',addEventListener(){}};
  for(const id of Object.keys(appids)) {
    const listeners={},attrs={'data-app':appids[id],'data-label':labels[id],'data-busy':'Busy…'};
    const status={textContent:statusText[id]||''},strong={textContent:labels[id]},use={attrs:{href:'#port'},setAttribute(k,v){this.attrs[k]=v;}};
    nodes[id]={id,hidden:false,listeners,status,strong,use,classList:classList(),addEventListener:(name,fn)=>listeners[name]=fn,
      getAttribute:key=>attrs[key],setAttribute:(key,value)=>attrs[key]=value,
      querySelector:selector=>({'[data-status]':status,'.secondary-label':status,strong,use})[selector],
      focus(){document.activeElement=this;listeners.focus?.();},
      click(){listeners.click?.({preventDefault(){},stopPropagation(){}});}};
  }
  document.getElementById=id=>nodes[id];document.querySelectorAll=()=>Object.keys(appids).map(id=>nodes[id]);
  const window={location:{search:preview?'?preview=1':''},HDMI_PORTS:ports,
    setTimeout(fn,ms){timers.set(++sequence,{fn,ms});return sequence;},clearTimeout:id=>timers.delete(id),
    addEventListener:(name,fn)=>windowEvents[name]=fn};
  if(native) window.PalmServiceBridge=function(){this.cancel=()=>this.cancelled=true;this.call=(url,payload)=>calls.push({url,payload:JSON.parse(payload)});bridges.push(this);};
  vm.runInNewContext(source,{window,document,URLSearchParams,console,Date});
  return {nodes,events,windowEvents,document,classes:body.set,calls,bridges,timers,
    key(code){events.keydown({keyCode:code,preventDefault(){},stopPropagation(){}});},
    fire(ms){const match=[...timers].find(([,timer])=>timer.ms===ms);assert.ok(match,`timer ${ms}`);timers.delete(match[0]);match[1].fn();}};
}
test('Opening the dashboard focuses Xbox without changing HDMI or making a service call',()=>{
  const f=fixture();assert.equal(f.document.activeElement.id,'xbox');assert.equal(f.calls.length,0);
});
test('D-pad reaches every input and the three recovery/tools controls',()=>{
  const f=fixture();for(const [code,id] of [[39,'hdmi1'],[40,'hdmi3'],[40,'hdmi4'],[38,'hdmi3'],[38,'hdmi1'],[38,'tv-settings'],[37,'game'],[37,'lg-home'],[40,'xbox']]){f.key(code);assert.equal(f.document.activeElement.id,id);}
});
test('Each control launches only its declared local app and blocks duplicate launches',()=>{
  for(const [id,appid] of Object.entries(appids)){const f=fixture();f.nodes[id].click();f.nodes[id].click();assert.equal(f.calls.length,1);if(id==='lg-home'){assert.equal(f.calls[0].url,'luna://org.webosbrew.hbchannel.service/exec');assert.match(f.calls[0].payload.command,/home-router\.py stock-home/);assert.match(f.calls[0].payload.command,/else luna-send/);}else{assert.equal(f.calls[0].url,'luna://com.webos.applicationManager/launch');assert.equal(f.calls[0].payload.id,appid);}f.bridges[0].onservicecallback('{"returnValue":true}');assert.equal(f.classes.has('is-busy'),false);}
});
test('The activated control shows its busy text and restores it when the TV replies',()=>{
  const f=fixture();f.key(461);
  assert.equal(f.nodes.xbox.classList.has('is-launching'),true);assert.equal(f.nodes.xbox.status.textContent,'Busy…');
  f.bridges[0].onservicecallback('{"returnValue":true}');
  assert.equal(f.nodes.xbox.classList.has('is-launching'),false);assert.equal(f.nodes.xbox.status.textContent,'Switch to HDMI 2');
});
test('Back returns to HDMI2 even after selecting another input',()=>{
  const f=fixture();f.key(39);f.key(461);assert.equal(f.calls[0].payload.id,'com.webos.app.hdmi2');
});

test('App row is reachable from sources and returns to the correct source',()=>{
  const f=fixture();
  for(const [code,id] of [[40,'apple-tv'],[39,'youtube'],[39,'browser'],[38,'hdmi4'],[40,'browser'],[37,'youtube'],[37,'apple-tv'],[38,'xbox']]){
    f.key(code);assert.equal(f.document.activeElement.id,id);
  }
  const none=fixture({ports:{hdmi1:{unused:true},hdmi3:{unused:true},hdmi4:{unused:true}}});
  none.key(40);none.key(39);none.key(39);none.key(38);
  assert.equal(none.document.activeElement.id,'xbox');
});
test('Preview and missing native bridge never claim to switch a physical TV',()=>{
  const p=fixture({preview:true});p.nodes.xbox.click();assert.equal(p.calls.length,0);assert.match(p.nodes.notice.textContent,/Preview/);
  p.fire(1500);assert.equal(p.nodes.xbox.classList.has('is-launching'),false);
  const desktop=fixture({native:false});desktop.nodes.xbox.click();assert.match(desktop.nodes.notice.textContent,/unavailable/);
});
test('Permission errors, malformed replies and timeouts recover the controls',()=>{
  for(const reply of ['{"returnValue":false,"errorCode":-1}','invalid-json']){const f=fixture();f.nodes.xbox.click();f.bridges[0].onservicecallback(reply);assert.equal(f.classes.has('is-busy'),false);assert.equal(f.nodes.notice.hidden,false);}
  const timeout=fixture();timeout.nodes.xbox.click();timeout.fire(8000);assert.equal(timeout.bridges[0].cancelled,true);assert.equal(timeout.classes.has('is-busy'),false);assert.equal(timeout.nodes.xbox.classList.has('is-launching'),false);
});
test('OLED idle cover consumes the first wake key without switching inputs',()=>{
  const f=fixture();f.fire(45000);assert.equal(f.classes.has('is-idle'),true);f.fire(120000);assert.equal(f.nodes['sleep-cover'].hidden,false);f.key(461);assert.equal(f.calls.length,0);assert.equal(f.nodes['sleep-cover'].hidden,true);f.key(461);assert.equal(f.calls.length,1);
});
test('Backgrounding stops idle and clock work; reopening returns focus to Xbox',()=>{
  const f=fixture();f.document.hidden=true;f.events.visibilitychange();assert.equal(f.timers.size,0);f.document.hidden=false;f.events.visibilitychange();assert.equal(f.document.activeElement.id,'xbox');assert.equal(f.timers.size,3);
});
test('The clock shows local 24-hour time',()=>{
  const f=fixture();assert.match(f.nodes['clock-time'].textContent,/^\d\d:\d\d$/);assert.notEqual(f.nodes['clock-date'].textContent,'');
});
test('Named ports show the name, the port number underneath and their icon; unnamed ports show no icon',()=>{
  const f=fixture({ports:{hdmi1:{name:'PC',icon:'pc'},hdmi3:{icon:'pc'}}});
  assert.equal(f.nodes.hdmi1.strong.textContent,'PC');assert.equal(f.nodes.hdmi1.status.textContent,'HDMI 1');assert.equal(f.nodes.hdmi1.use.attrs.href,'#pc');
  assert.equal(f.nodes.hdmi1.classList.has('has-icon'),true);
  assert.equal(f.nodes.hdmi3.strong.textContent,'HDMI 3');assert.equal(f.nodes.hdmi3.use.attrs.href,'#port');assert.equal(f.nodes.hdmi3.classList.has('has-icon'),false);
  f.nodes.hdmi1.click();assert.equal(f.calls[0].payload.id,'com.webos.app.hdmi1');
});
test('Unused ports are hidden, skipped by the D-pad and cannot launch',()=>{
  const f=fixture({ports:{hdmi3:{unused:true}}});assert.equal(f.nodes.hdmi3.hidden,true);
  for(const [code,id] of [[39,'hdmi1'],[40,'hdmi4'],[40,'browser'],[38,'hdmi4'],[38,'hdmi1'],[38,'tv-settings'],[37,'game'],[37,'lg-home'],[40,'xbox']]){f.key(code);assert.equal(f.document.activeElement.id,id);}
  f.nodes.hdmi3.click();assert.equal(f.calls.length,0);
  const none=fixture({ports:{hdmi1:{unused:true},hdmi3:{unused:true},hdmi4:{unused:true}}});none.key(39);assert.equal(none.document.activeElement.id,'xbox');none.key(38);none.key(39);none.key(39);assert.equal(none.document.activeElement.id,'tv-settings');none.key(40);assert.equal(none.document.activeElement.id,'xbox');
  assert.equal(none.classes.has('no-ports'),true);assert.equal(f.classes.has('no-ports'),false);
});

import zlib from 'node:zlib';
function members(buffer) {
  assert.equal(buffer.subarray(0,8).toString(),'!<arch>\n');const result={};
  for(let p=8;p<buffer.length;){const h=buffer.subarray(p,p+60).toString();assert.equal(h.slice(58),'`\n');const n=Number(h.slice(48,58));result[h.slice(0,16).trim()]=buffer.subarray(p+60,p+60+n);p+=60+n+(n%2);}
  return result;
}
function untar(bytes) {
  const files={};
  for(let p=0;p<bytes.length;){const h=bytes.subarray(p,p+512);const name=h.subarray(0,100).toString().split('\0')[0];if(!name)break;const size=parseInt(h.subarray(124,136).toString(),8);const expected=parseInt(h.subarray(148,156).toString(),8);const copy=Buffer.from(h);copy.fill(32,148,156);assert.equal(copy.reduce((a,b)=>a+b,0),expected);files[name]=bytes.subarray(p+512,p+512+size);p+=512+Math.ceil(size/512)*512;}
  return files;
}
test('IPK contains a valid control archive, package metadata, local assets and no services',()=>{
  const build=JSON.parse(fs.readFileSync(path.join(root,'dist/build-manifest.json')));
  const archive=members(fs.readFileSync(path.join(root,'dist',build.ipk)));assert.equal(archive['debian-binary'].toString(),'2.0\n');
  const control=untar(zlib.gunzipSync(archive['control.tar.gz']));assert.match(control.control.toString(),/webOS-Package-Format-Version: 2/);
  const data=untar(zlib.gunzipSync(archive['data.tar.gz']));assert.equal(Object.keys(data).length,9);
  const prefix='usr/palm/applications/com.local.hdmihome/';const info=JSON.parse(data[prefix+'appinfo.json']);assert.equal(info.main,'index.html');assert.deepEqual(info.requiredACG,['application.launcher']);
  for(const file of ['index.html','style.css','app.js','ports.js','icon.png','largeIcon.png','xsx.png'])assert.ok(data[prefix+file]);
  assert.deepEqual(data[prefix+'xsx.png'],fs.readFileSync(path.join(root,'xsx.png')));
  assert.equal(JSON.parse(data['usr/palm/packages/com.local.hdmihome/packageinfo.json']).app,info.id);
  assert.equal(Object.keys(data).some(name=>name.includes('/services/')),false);
});
