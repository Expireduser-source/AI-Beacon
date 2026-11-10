import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ManualPeer} from '../webrtc.mjs';

const OFFER=JSON.stringify({type:'offer',sdp:'v=0\r\no=- 123 1 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0'});
const ANSWER=JSON.stringify({type:'answer',sdp:'v=0\r\no=- 456 1 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0'});

test('SDP parser accepts a well-formed operator-provided description only',()=>{
  assert.equal(ManualPeer.parseSignal(OFFER,'offer').type,'offer');
  assert.equal(ManualPeer.parseSignal(ANSWER,'answer').type,'answer');
  assert.throws(()=>ManualPeer.parseSignal(OFFER,'answer'),/Expected a answer/);
  assert.throws(()=>ManualPeer.parseSignal('{"type":"offer","sdp":"bad"}','offer'));
  assert.throws(()=>ManualPeer.parseSignal('x'.repeat(60001),'offer'));
  assert.throws(()=>ManualPeer.parseSignal('{"type":"offer"}','offer'));
});

class FakeChannel {
  constructor(){this.readyState='open';this.sent=[];this.closed=false;}
  send(message){this.sent.push(message);}
  close(){this.closed=true;this.readyState='closed';}
}
class FakePC {
  constructor(cfg){
    this.config=cfg;
    this.iceGatheringState='complete';
    this.signalingState='stable';
    this.connectionState='new';
    this.iceConnectionState='new';
    this.channel=new FakeChannel();
    this.closed=false;
  }
  createDataChannel(){return this.channel;}
  async createOffer(){return JSON.parse(OFFER);}
  async createAnswer(){return JSON.parse(ANSWER);}
  async setLocalDescription(d){this.localDescription=d;}
  async setRemoteDescription(d){this.remoteDescription=d;}
  addEventListener(){}
  removeEventListener(){}
  close(){this.closed=true;}
}
test('Manual peer offer/answer and text dispatch work with fake browser WebRTC API',async()=>{
  const saved=globalThis.RTCPeerConnection;
  globalThis.RTCPeerConnection=FakePC;
  try{
    const initiator=new ManualPeer();
    const offer=await initiator.offer();
    assert.equal(ManualPeer.parseSignal(offer,'offer').type,'offer');
    const recipient=new ManualPeer({useStun:true});
    assert.equal(recipient.pc.config.iceServers[0].urls,'stun:stun.l.google.com:19302');
    const answer=await recipient.answer(offer);
    await initiator.acceptAnswer(answer);
    assert.equal(initiator.pc.remoteDescription.type,'answer');
    assert.equal(recipient.pc.remoteDescription.type,'offer');
    initiator.send('HELLO');
    assert.deepEqual(initiator.channel.sent,['HELLO']);
    assert.throws(()=>initiator.send('a'.repeat(513)),/Max 512/);
    initiator.close();recipient.close();
    assert.equal(initiator.pc.closed,true);
    assert.equal(recipient.pc.closed,true);
  }finally{globalThis.RTCPeerConnection=saved;}
});

test('Multichannel HTML includes every element referenced by browser controller',()=>{
  const app=readFileSync(new URL('../browser.mjs',import.meta.url),'utf-8');
  const html=readFileSync(new URL('../index.html',import.meta.url),'utf-8');
  const ids=[...app.matchAll(/\$\('([a-z0-9-]+)'\)/g)].map(x=>x[1]);
  const missing=[...new Set(ids)].filter(id=>!html.includes('id="'+id+'"'));
  assert.deepEqual(missing,[]);
  assert.match(html,/script type="module" src="\.\/browser\.mjs"/);
  assert.match(html,/href="https:\/\/ai-beacon-a2a/);
  assert.ok(!app.includes('localStorage'));
});
