const vm = require('vm'), fs = require('fs'), assert = require('assert');
let clock = 1_700_000_000_000;
class FDate extends Date { constructor(...a){ super(...(a.length?a:[clock])); } static now(){ return clock; } }
function mkSheet(header){ const rows=[header]; return {
  rows,
  getLastRow:()=>rows.length,
  getRange:(r,c,nr=1,nc=1)=>({
    getValues:()=>{const out=[];for(let i=0;i<nr;i++){const src=rows[r-1+i]||[];out.push(Array.from({length:nc},(_,j)=>src[c-1+j]===undefined?'':src[c-1+j]));}return out;},
    setValues:(v)=>{for(let i=0;i<nr;i++){rows[r-1+i]=rows[r-1+i]||[];for(let j=0;j<nc;j++)rows[r-1+i][c-1+j]=v[i][j];}},
    setValue:(v)=>{rows[r-1]=rows[r-1]||[];rows[r-1][c-1]=v;}
  }),
  appendRow:(row)=>{rows.push(row.slice());}
};}
const sheets={ Supporters: mkSheet(['Timestamp','SupporterId','Name','RequestId','DeviceId','Status','Lang']),
               PushSubs: mkSheet(['Timestamp','DeviceId','Endpoint','P256dh','Auth','Lang','Status']) };
const store=new Map();
const ctx={ console, Date:FDate, Math, JSON, parseInt, String, Array, Object, Number, Boolean, RegExp, isNaN,
  SpreadsheetApp:{getActiveSpreadsheet:()=>({getSheetByName:n=>sheets[n]||null,insertSheet:n=>(sheets[n]=mkSheet([]))})},
  CacheService:{getScriptCache:()=>({
    get:k=>{const e=store.get(k);if(!e)return null;if(e.exp<=clock){store.delete(k);return null;}return e.v;},
    put:(k,v,ttl)=>store.set(k,{v:String(v),exp:clock+ttl*1000}),
    remove:k=>store.delete(k)})},
  LockService:{getScriptLock:()=>({waitLock(){},tryLock(){return true;},releaseLock(){}})},
  PropertiesService:{getScriptProperties:()=>({getProperty:k=>k==='ADMIN_KEY'?'secret':null,setProperty(){}})},
  Utilities:{getUuid:()=>'xxxxxxxx-'+Math.random().toString(16).slice(2,10)+'-aaaa-bbbb-cccccccccccc'.replace(/x/g,'1'), sleep(){ throw new Error('sleep must not be called'); }},
  ContentService:{MimeType:{JSON:'json'},createTextOutput:t=>({setMimeType(){return this;},getContent:()=>t})}
};
vm.createContext(ctx); vm.runInContext(fs.readFileSync(require('path').join(__dirname,'..','Code.gs'),'utf8'),ctx);
const post=(o)=>JSON.parse(ctx.doPost({postData:{contents:JSON.stringify(o)}}).getContent());
const get=(o)=>JSON.parse(ctx.doGet({parameter:{q:JSON.stringify(o)}}).getContent());
let n=0; const ok=(c,m)=>{assert.ok(c,m);n++;console.log('  ✓',m);};

// --- old-layout seed rows ---
sheets.Supporters.rows.push(['2026-10-01T10:00:00Z','CBM-111111','محمد علي','req-old','devA','active','ar']);
sheets.Supporters.rows.push(['2026-10-01T10:00:00Z','CBM-222222','سعيد بن علي','req-x','devB','revoked','ar']);
console.log('1) existing cards (old sheet layout)');
let r=post({v:2,a:'verify',supporterId:'CBM-111111'}); ok(r.ok&&r.status==='active'&&r.maskedName==='م*** ع***','verify active card, masked name, status read from correct column');
r=post({v:2,a:'verify',supporterId:'CBM-222222'}); ok(r.code==='revoked','revoked card detected');
r=get({v:2,a:'verify',supporterId:'CBM-111111'}); ok(r.ok,'GET verify still works');

console.log('2) verify rate limits');
let allOk=true; for(let i=0;i<300;i++){ if(!post({v:2,a:'verify',supporterId:'CBM-111111'}).ok) allOk=false; }
ok(allOk,'300 anonymous (no dev) scans in one window all succeed (old bug capped at 30)');
for(let i=0;i<60;i++) post({v:2,a:'verify',supporterId:'CBM-111111',dev:'scanner1'});
ok(post({v:2,a:'verify',supporterId:'CBM-111111',dev:'scanner1'}).code==='rate_limit','61st scan from one device is limited');
ok(post({v:2,a:'verify',supporterId:'CBM-111111',dev:'scanner2'}).ok,'other device unaffected');

console.log('3) fixed window (not sliding)');
store.clear(); clock+=0;
for(let i=0;i<60;i++){ post({v:2,a:'verify',supporterId:'CBM-111111',dev:'slide'}); clock+=14_000; } // 14 min of steady traffic
clock+=70_000; // pass 15 min since the first hit
ok(post({v:2,a:'verify',supporterId:'CBM-111111',dev:'slide'}).ok,'counter resets 15 min after first hit even with continuous traffic');

console.log('4) register');
store.clear();
const a=post({v:2,a:'register',name:'محمد علي',dev:'dev1',requestId:'r1',lang:'ar'});
const b=post({v:2,a:'register',name:'محمد علي',dev:'dev2',requestId:'r2',lang:'ar'});
ok(a.ok&&b.ok&&a.supporterId!==b.supporterId,'same name from different devices -> two separate cards (no "exists")');
const a2=post({v:2,a:'register',name:'محمد علي',dev:'dev1',requestId:'r9',lang:'ar'});
ok(a2.supporterId===a.supporterId,'same device + same name -> same card returned');
const f2=post({v:2,a:'register',name:'ياسين علي',dev:'dev1',requestId:'r3',lang:'ar'});
const f3=post({v:2,a:'register',name:'سارة علي',dev:'dev1',requestId:'r4',lang:'ar'});
ok(f2.ok&&f3.ok,'family: different names on one phone allowed (up to 3)');
ok(post({v:2,a:'register',name:'عمر علي',dev:'dev1',requestId:'r5',lang:'ar'}).code==='rate_limit','4th new card from same device is limited');
ok(post({v:2,a:'register',name:'محمد علي',dev:'dev1',requestId:'r1',lang:'ar'}).supporterId===a.supporterId,'retry with same requestId is idempotent even when limited');
const inj=post({v:2,a:'register',name:'=IMPORTXML("http://evil","//a")',dev:'dev7',requestId:'r7',lang:'ar'});
ok(inj.ok&&!/^[=+\-@]/.test(inj.name),'formula-injection prefix stripped from name: '+JSON.stringify(inj.name));

console.log('5) restore');
store.clear();
for(let i=0;i<5;i++) post({v:2,a:'restore',name:'غلط',supporterId:'CBM-111111',dev:'atk'+i});
ok(post({v:2,a:'restore',name:'محمد علي',supporterId:'CBM-111111',dev:'newphone'}).code==='rate_limit','card locked for foreign devices after 5 failures');
ok(post({v:2,a:'restore',name:'محمد علي',supporterId:'CBM-111111',dev:'devA'}).ok,'owner (registered device) is NOT locked out');
store.clear();
for(let i=0;i<60;i++) post({v:2,a:'restore',name:'غلط',supporterId:'CBM-9'+String(10000+i),dev:'atk'+i});
const t0=Date.now();
ok(post({v:2,a:'restore',name:'محمد علي',supporterId:'CBM-111111',dev:'honest'}).ok,'60 global failures do not block honest users, and no sleep() is used');

console.log('6) push');
const goodKeys={p256dh:'B'+'a'.repeat(86),auth:'a'.repeat(22)};
ok(post({v:2,a:'push_sub',dev:'d',sub:{endpoint:'https://evil.example.com/x',keys:goodKeys}}).code==='invalid_subscription','non-allow-listed endpoint rejected');
ok(post({v:2,a:'push_sub',dev:'d',sub:{endpoint:'https://fcm.googleapis.com/fcm/send/abc',keys:goodKeys}}).ok,'FCM endpoint accepted (old PushSubs layout)');
const pl=post({v:2,a:'push_list',key:'secret'}); ok(pl.ok&&pl.items.length===1&&pl.items[0].endpoint.includes('fcm'),'push_list returns {endpoint, keys, lang} as scraper.py expects');
ok(post({v:2,a:'push_list',key:'bad'}).code==='denied','admin key enforced');
console.log('\nALL',n,'CHECKS PASSED');
