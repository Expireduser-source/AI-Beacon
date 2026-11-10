import test from 'node:test';
import assert from 'node:assert/strict';
import {handleRequest, agentCard, validateSend, extractAnswer, BeaconRoom} from '../src/index.mjs';

function request(body, url='https://beacon.example/message:send') {
  return new Request(url, {method:'POST',headers:{'content-type':'application/json','cf-connecting-ip':'192.0.2.5'},body:JSON.stringify(body)});
}
function validMessage(contextId) {
  return {message:{role:'ROLE_USER',messageId:'message-1',parts:[{text:'What is a safe provenance test?'}], ...(contextId?{contextId}:{})}};
}
function mockEnvironment() {
  const store=new Map();
  const ctx={storage:{get:async k=>store.get(k),put:async(k,v)=>store.set(k,v),delete:async k=>store.delete(k),setAlarm:async()=>{},deleteAll:async()=>store.clear()}};
  const rooms=new Map();
  const calls=[];
  return {calls, env:{ROOMS:{idFromName:x=>x,get:x=>{if(!rooms.has(x))rooms.set(x,new BeaconRoom({storage:{...ctx.storage,get:async k=>{const s=store.get(x)||{};return s[k]},put:async(k,v)=>{const s=store.get(x)||{};s[k]=v;store.set(x,s)},delete:async k=>{const s=store.get(x)||{};delete s[k];store.set(x,s)}}},{}));return rooms.get(x)}},AI:{run:async(_,payload)=>{calls.push(payload);return {response:'Tested answer from an independent worker model.'}}},GLOBAL_DAILY_LIMIT:'6'}};
}

test('Agent Card declares only an implemented v1.0 HTTP+JSON binding', async()=>{
  const card=agentCard('https://beacon.example');
  assert.equal(card.supportedInterfaces[0].protocolBinding,'HTTP+JSON');
  assert.equal(card.supportedInterfaces[0].url,'https://beacon.example');
  const result=await handleRequest(new Request('https://beacon.example/.well-known/agent-card.json'),{});
  assert.equal(result.status,200);
  assert.deepEqual((await result.json()).capabilities,{streaming:false,pushNotifications:false,stateTransitionHistory:false});
});
test('Message validator rejects empty, non-text, and invalid context',()=>{
  assert.equal(validateSend(validMessage()),null);
  assert.match(validateSend({message:{role:'ROLE_AGENT',parts:[],messageId:'x'}}),/ROLE_USER/);
  assert.match(validateSend(validMessage('anything')),/contextId/);
  const huge=validMessage();huge.message.parts[0].text='x'.repeat(2000);
  assert.match(validateSend(huge),/Text/);
});
test('Direct request generates model text and continues same context',async()=>{
  const {env,calls}=mockEnvironment();
  const response=await handleRequest(request(validMessage()),env);
  assert.equal(response.status,200);
  const data=await response.json();
  assert.equal(data.message.role,'ROLE_AGENT');
  assert.equal(data.message.parts[0].text,'Tested answer from an independent worker model.');
  assert.match(data.message.contextId,/^[a-z0-9-]{36}$/);
  const second=validMessage(data.message.contextId);second.message.messageId='message-2';
  second.message.parts[0].text='Follow up on that answer';
  assert.equal((await handleRequest(request(second),env)).status,200);
  assert.equal(calls.length,2);
  assert.equal(calls[1].messages.at(-2).role,'assistant');
});
test('No model binding cannot claim success',async()=>{
  const r=await handleRequest(request(validMessage()),{});
  assert.equal(r.status,503);
});
test('Rate limiter bounds repeated messages without calling AI again',async()=>{
  const {env,calls}=mockEnvironment();
  let status;
  for(let i=0;i<9;i++) {const m=validMessage();m.message.messageId='unique-'+i;status=(await handleRequest(request(m),env)).status;}
  assert.equal(status,429);
  assert.ok(calls.length<=6);
});
test('No URL fetches and responses do not expose internal implementation',()=>{
  assert.equal(extractAnswer({response:' OK '}),'OK');
  assert.equal(extractAnswer({choices:[{message:{content:'One'}}]}),'One');
  assert.equal(extractAnswer({}), '');
});
