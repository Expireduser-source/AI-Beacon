import test from 'node:test';
import assert from 'node:assert/strict';
import {
  MAX_BYTES,PREAMBLE,crc16,frame,parseFrame,bitsOf,fromBits,
  audioBits,decodeBits,flashSymbols,decodeFlashSymbols,
  synthesizeFSK,decodeAudio
} from '../codec.mjs';

test('CRC framing roundtrip in UTF-8, no external dependencies',()=>{
  for (const msg of ['HELLO','ACK','Привет','你好','AI-BEACON','🥳']) {
    const encoded=frame(msg);
    assert.equal(parseFrame(encoded),msg);
    assert.equal(fromBits(bitsOf(encoded)).toString(),encoded.toString());
    assert.equal(decodeBits('00000'+audioBits(msg)+'1111').text,msg);
  }
  assert.throws(()=>frame(''),RangeError);
  assert.throws(()=>frame('a'.repeat(MAX_BYTES+1)),RangeError);
  assert.throws(()=>frame('🌍'.repeat(6)),RangeError);
  assert.equal(parseFrame(Uint8Array.from([1,2,3])),null);
  assert.equal(typeof crc16(new Uint8Array([1,2,3])),'number');
});

test('CRC rejects corrupted payload, version and truncation',()=>{
  const encoded=frame('HELLO');
  for (const at of [0,1,2,3,4,5,encoded.length-1]) {
    const changed=encoded.slice();
    changed[at]^=1;
    assert.equal(parseFrame(changed),null,'corruption at '+at);
  }
  assert.equal(parseFrame(encoded.slice(0,-1)),null);
});

test('Optical quaternary symbols allow physical blink gaps between events',()=>{
  for (const msg of ['HI','Привет','ACK','MULTICHANNEL']) {
    const symbols=flashSymbols(msg);
    assert.equal(decodeFlashSymbols([2,3,1,...symbols])?.text,msg);
    assert.equal(decodeFlashSymbols(symbols)?.text,msg);
    const bad=symbols.slice();bad[bad.length-3]=(bad[bad.length-3]+1)%4;
    assert.equal(decodeFlashSymbols(bad),null);
  }
});

test('Acoustic 960/1600 Hz FSK decoder recovers a framed text at 16kHz',()=>{
  const input=synthesizeFSK('HI',16000,0.37);
  const decoded=decodeAudio(input,16000);
  assert.equal(decoded?.text,'HI');
  assert.ok(decoded.confidence>0.2);
  assert.equal(PREAMBLE.length,24);
});

test('Acoustic FSK roundtrip survives variable capture phase and sample rate',()=>{
  const permutations=[
    ['ACK',8000,0.19],
    ['HELLO',16000,0.29],
    ['Привет',44100,0.41],
    ['N=123',48000,0.73]
  ];
  for(const [message,sr,lead] of permutations) {
    const pcm=synthesizeFSK(message,sr,lead);
    const actual=decodeAudio(pcm,sr);
    assert.equal(actual?.text,message,'round trip at '+sr+'Hz, lead '+lead);
  }
});

test('Decoder rejects silence and random noise',()=>{
  assert.equal(decodeAudio(new Float32Array(16000*3),16000),null);
  const rng=new Float32Array(16000*4);
  let state=42;
  for(let i=0;i<rng.length;i++){
    state=(Math.imul(state,1664525)+1013904223)>>>0;
    rng[i]=(state/4294967296-.5)*.2;
  }
  assert.equal(decodeAudio(rng,16000),null);
});

test('Decoder rejects invalid audio and empty bitstreams',()=>{
  assert.throws(()=>decodeAudio([],0),TypeError);
  assert.throws(()=>fromBits('101'),RangeError);
  assert.throws(()=>fromBits('abcdefgh'),RangeError);
});
