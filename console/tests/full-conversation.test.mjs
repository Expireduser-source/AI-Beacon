import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import worker,{ConsoleState,scrubOutput} from '../src/index.mjs';

globalThis.crypto ||= webcrypto;
const KEY='testing-only-key-0123456789012345678901234567';
const ORIGIN='https://console.example.invalid';

class FakeDB {
  constructor(){this.content=null;}
  exec(sql,...params){
    if(sql.startsWith('CREATE TABLE'))return {};
    if(sql.startsWith('SELECT'))return {toArray:()=>this.content==null?[]:[{v:this.content}]};
    if(sql.startsWith('INSERT')){this.content=params[0];return {};}
    throw new Error('Unexpected SQL '+sql);
  }
}
class FakeDOState {
  constructor(){this.storage={sql:new FakeDB()};}
  blockConcurrencyWhile(cb){this.startup=Promise.resolve(cb());}
}
function environment({modelFails=false}={}){
  const state=new FakeDOState();
  const room=new ConsoleState(state,{});
  const remoteCalls=[];
  const aiCalls=[];
  const env={
    CONSOLE_KEY:KEY,
    AI:{async run(model,args){
      aiCalls.push({model,arguments:args});
      if(modelFails)throw new Error('Fake model unavailable');
      return aiCalls.length===1
        ? {choices:[{message:{content:'How can two peer models evaluate a false positive?' }}]}
        : {response:'Which independent control would falsify your proposed test?'};
    }},
    CONSOLE_STATE:{
      idFromName(name){assert.equal(name,'owner-only');return name;},
      get(){return {fetch:async request=>{await state.startup;return room.fetch(request);}};}
    }
  };
  return {env,remoteCalls,aiCalls};
}
async function request(env,path,method='GET',body=null,cookie=null,origin=ORIGIN){
  const headers={};
  if(cookie)headers.cookie=cookie;
  if(method!=='GET'){headers['content-type']='application/json';headers.origin=origin;}
  const response=await worker.fetch(new Request(ORIGIN+path,{
    method,headers,body:body?JSON.stringify(body):undefined
  }),env,{waitUntil(){}});
  let parsed;
  try{parsed=await response.json();}catch(_){parsed=null;}
  return {status:response.status,body:parsed,cookie:response.headers.get('set-cookie')};
}
function stubExternal(fake,mode='success'){
  const original=globalThis.fetch;
  globalThis.fetch=async (url,options={})=>{
    const u=String(url);
    if(u==='https://emissaryproject.org/.well-known/agent-card.json'){
      return Response.json({name:'Emissary',supportedInterfaces:[
        {url:'https://emissaryproject.org',protocolBinding:'HTTP+JSON'}
      ]});
    }
    if(u==='https://emissaryproject.org/message:send'){
      assert.equal(options.method,'POST');
      fake.remoteCalls.push(JSON.parse(options.body));
      if(mode==='error')return Response.json({error:'temporary outage'},{status:503});
      const n=fake.remoteCalls.length;
      return Response.json({message:{role:'ROLE_AGENT',contextId:'ctx-001',parts:[{
        text:n===1?'A control should isolate a shared resource.':'Blindly randomize trial conditions and preregister success.'}]}});
    }
    throw new Error('Unexpected outbound URL '+u);
  };
  return ()=>{globalThis.fetch=original;};
}

test('Gemma output accepts Workers AI response or OpenAI-compatible choices',()=>{
  assert.equal(scrubOutput({response:'Gemma asks a question'}),'Gemma asks a question');
  assert.equal(scrubOutput({choices:[{message:{content:'Another question'}}]}),'Another question');
  assert.equal(scrubOutput({result:{output:[{content:'Deeply nested answer'}]}}),'Deeply nested answer');
});

test('Real owner browser flow with a fake model and a fake A2A service stores both turns',async()=>{
  const fake=environment();
  const restore=stubExternal(fake);
  try{
    const denied=await request(fake.env,'/api/start','POST',{topic:'A serious scientific question'});
    assert.equal(denied.status,401);
    const login=await request(fake.env,'/api/login','POST',{key:KEY});
    assert.equal(login.status,200);
    assert.match(login.cookie,/HttpOnly/);
    const cookie=login.cookie.split(';')[0];
    const start=await request(fake.env,'/api/start','POST',
      {topic:'How can models independently audit scientific claims?'},cookie);
    assert.equal(start.status,200);
    assert.equal(start.body.used,1);
    const id=start.body.run.id;
    assert.equal(start.body.run.stage,'queued');

    const one=await request(fake.env,'/api/step','POST',{runId:id},cookie);
    assert.equal(one.status,200,JSON.stringify(one.body));
    assert.equal(one.body.run.status,'running');
    assert.equal(one.body.run.stage,'ready_for_followup');
    assert.equal(one.body.run.turns.length,1);
    assert.equal(one.body.run.turns[0].gemma,'How can two peer models evaluate a false positive?');
    assert.match(one.body.run.turns[0].emissary,/isolate a shared resource/);
    const two=await request(fake.env,'/api/step','POST',{runId:id},cookie);
    assert.equal(two.status,200,JSON.stringify(two.body));
    assert.equal(two.body.run.status,'completed');
    assert.equal(two.body.run.stage,'completed');
    assert.equal(two.body.run.turns.length,2);
    assert.equal(fake.aiCalls.length,2);
    assert.equal(fake.remoteCalls.length,2);
    assert.equal(fake.remoteCalls[1].message.contextId,'ctx-001');
    const status=await request(fake.env,'/api/status','GET',null,cookie);
    assert.equal(status.status,200);
    assert.equal(status.body.used,1,'two turns must count as only one conversation');
    assert.equal(status.body.run.turns.length,2);
    assert.equal(status.body.run.draft_gemma,null);
    const third=await request(fake.env,'/api/step','POST',{runId:id},cookie);
    assert.equal(third.status,409,'two is an absolute maximum');
    const csrf=await request(fake.env,'/api/start','POST',
      {topic:'A third party attempt to launch extra inference'},cookie,'https://evil.example');
    assert.equal(csrf.status,403);
  }finally{restore();}
});

test('Remote A2A failure preserves Gemma-generated question and readable stage',async()=>{
  const fake=environment();
  const restore=stubExternal(fake,'error');
  try{
    const login=await request(fake.env,'/api/login','POST',{key:KEY});
    const cookie=login.cookie.split(';')[0];
    const start=await request(fake.env,'/api/start','POST',
      {topic:'How to identify hidden common causes in timing?'},cookie);
    const step=await request(fake.env,'/api/step','POST',{runId:start.body.run.id},cookie);
    assert.equal(step.status,502);
    assert.match(step.body.error,/HTTP 503/);
    const status=await request(fake.env,'/api/status','GET',null,cookie);
    assert.equal(status.body.run.status,'failed');
    assert.equal(status.body.run.stage,'failed');
    assert.match(status.body.run.draft_gemma,/false positive/);
    assert.equal(status.body.run.turns.length,0,
      'Never count a drafted question as an external model answer');
  }finally{restore();}
});
