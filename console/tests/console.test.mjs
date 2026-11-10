import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import worker,{ConsoleState,validTopic,tokenCorrect,makeSession,verifySession,extractAgentReply} from '../src/index.mjs';

globalThis.crypto ||= webcrypto;
const KEY='scope-private-24-byte-random-owner-secret-for-tests';

test('Topics sanitized and length bounded',()=>{
 assert.equal(validTopic('  Science   research    question?  '),'Science research question?');
 assert.throws(()=>validTopic('short'),/10/);
 assert.throws(()=>validTopic('x'.repeat(182)),/180/);
 assert.throws(()=>validTopic({topic:1}),/строкой/);
});

test('Owner HMAC session is bound to server secret and expires safely',async()=>{
 assert.equal(await tokenCorrect(KEY,KEY),true);
 assert.equal(await tokenCorrect('attack-not-the-key-1234567890',KEY),false);
 const cookie=await makeSession(KEY);
 const req=new Request('https://console.invalid/api/status',{headers:{cookie:'beacon_session='+cookie}});
 assert.equal(await verifySession(req,KEY),true);
 assert.equal(await verifySession(req,KEY+'wrong'),false);
 const bad=new Request('https://console.invalid/api/status',{headers:{cookie:'beacon_session='+cookie.slice(0,-1)+'A'}});
 assert.equal(await verifySession(bad,KEY),false);
});

test('Remote A2A parser requires real text rather than status-only confirmation',()=>{
 assert.deepEqual(extractAgentReply({
   message:{role:'ROLE_AGENT',contextId:'context-1',parts:[{text:'Research response'}]}
 }),{text:'Research response',context:'context-1'});
 assert.equal(extractAgentReply({status:{state:'working'}}),null);
 assert.equal(extractAgentReply({message:{parts:[{data:{a:1}}]}}),null);
});

class MockSql {
 constructor(){this.record=null;}
 exec(sql,...values){
   if(sql.startsWith('CREATE'))return [];
   if(sql.startsWith('SELECT'))return {toArray:()=>this.record?[{v:this.record}]:[]};
   if(sql.startsWith('INSERT')){this.record=values[0];return [];}
   throw new Error('Unknown SQL '+sql);
 }
}
class MockState {
 constructor(){this.storage={sql:new MockSql()};}
 blockConcurrencyWhile(fn){this.setup=Promise.resolve(fn());}
}
async function call(room,path,data){
 const r=await room.fetch(new Request('https://internal.local'+path,{method:data?'POST':'GET',
  body:data?JSON.stringify(data):undefined,
  headers:data?{'content-type':'application/json'}:{}}));
 return {status:r.status,body:await r.json()};
}

test('Durable room persists two authorized turns and rejects 3rd turn or daily overage',async()=>{
 const state=new MockState();
 const room=new ConsoleState(state,{});
 await state.setup;
 const first=await call(room,'/start',{topic:'Can two models check the same scientific claim?'});
 assert.equal(first.status,200);
 assert.equal(first.body.used,1);
 const id=first.body.run.id;
 const lock1=await call(room,'/lease',{runId:id});
 assert.equal(lock1.status,200);
 assert.equal((await call(room,'/lease',{runId:id})).status,409);
 const reply1=await call(room,'/complete',{runId:id,lease:lock1.body.lease,
  turn:{gemma:'Question one',emissary:'Answer one',context:'ctx-1'}});
 assert.equal(reply1.status,200);
 assert.equal(reply1.body.run.status,'running');
 const lock2=await call(room,'/lease',{runId:id});
 const reply2=await call(room,'/complete',{runId:id,lease:lock2.body.lease,
  turn:{gemma:'Question two',emissary:'Answer two',context:'ctx-1'}});
 assert.equal(reply2.status,200);
 assert.equal(reply2.body.run.status,'completed');
 assert.equal((await call(room,'/lease',{runId:id})).status,409);
 const second=await call(room,'/start',{topic:'What would be a reproducible second test?'});
 assert.equal(second.status,200);
 assert.equal((await call(room,'/start',{topic:'Third expensive dialogue attempt?'})).status,429);
 assert.equal((await call(room,'/status')).body.run.id,second.body.run.id);
});

test('Expired leases are explicit and stale workers cannot submit old replies',async()=>{
 const state=new MockState();const room=new ConsoleState(state,{});await state.setup;
 const started=await call(room,'/start',{topic:'Test how state persists across network errors.'});
 const id=started.body.run.id;
 const first=await call(room,'/lease',{runId:id});
 assert.equal((await call(room,'/fail',{runId:id,lease:'incorrect',error:'timeout'})).status,409);
 const failed=await call(room,'/fail',{runId:id,lease:first.body.lease,error:'timeout'});
 assert.equal(failed.body.run.status,'failed');
 assert.equal((await call(room,'/lease',{runId:id})).status,409);
});

test('Unauthenticated POST cannot initiate billing or third-party calls',async()=>{
 const result=await worker.fetch(new Request('https://my-worker.invalid/api/start',{
  method:'POST',headers:{origin:'https://my-worker.invalid','content-type':'application/json'},
  body:JSON.stringify({topic:'Could two models test this independently?'})
 }),{CONSOLE_KEY:KEY,AI:{run:()=>{throw Error('must not invoke model');}}},{});
 assert.equal(result.status,401);
 const res=await result.json();
 assert.match(res.error,/вход/);
});

test('All UI element IDs match browser controller',()=>{
 const html=readFileSync(new URL('../src/dashboard.html',import.meta.url),'utf8');
 const js=readFileSync(new URL('../src/dashboard.js',import.meta.url),'utf8');
 const ids=[...js.matchAll(/\$\('([a-z0-9-]+)'\)/g)].map(m=>m[1]);
 const missing=[...new Set(ids)].filter(id=>!html.includes('id="'+id+'"'));
 assert.deepEqual(missing,[]);
 assert.ok(!js.includes('localStorage'));
});
