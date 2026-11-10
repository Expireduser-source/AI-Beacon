// Real Chromium E2E: two independent tabs negotiate peer WebRTC over localhost.
// No external peer servers, no Google STUN and no camera/microphone needed.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const url='http://127.0.0.1:8765/multichannel/';
const browser=await chromium.launch({
  headless:true,
  args:['--no-sandbox']
});
try{
  const a=await browser.newPage();
  const b=await browser.newPage();
  const errors=[];
  a.on('pageerror',e=>errors.push('A: '+e.message));
  b.on('pageerror',e=>errors.push('B: '+e.message));
  await Promise.all([a.goto(url),b.goto(url)]);
  await Promise.all([a.locator('#payload').waitFor(),b.locator('#payload').waitFor()]);
  assert.equal(await a.locator('#use-stun').isChecked(),false);
  await a.locator('#rtc-offer').click();
  await a.waitForFunction(()=>document.getElementById('local-sdp').value.startsWith('{"type":"offer"'),null,{timeout:25000});
  const offer=await a.locator('#local-sdp').inputValue();

  await b.locator('#remote-sdp').fill(offer);
  await b.locator('#rtc-answer').click();
  await b.waitForFunction(()=>document.getElementById('local-sdp').value.startsWith('{"type":"answer"'),null,{timeout:25000});
  const answer=await b.locator('#local-sdp').inputValue();

  await a.locator('#remote-sdp').fill(answer);
  await a.locator('#rtc-finalize').click();
  await Promise.all([
    a.waitForFunction(()=>document.getElementById('rtc-status').textContent.includes('connected'),null,{timeout:25000}),
    b.waitForFunction(()=>document.getElementById('rtc-status').textContent.includes('connected'),null,{timeout:25000})
  ]);

  await a.locator('#rtc-text').fill('HELLO FROM A');
  await a.locator('#rtc-send').click();
  await b.waitForFunction(()=>document.getElementById('rtc-messages').textContent.includes('HELLO FROM A'),null,{timeout:10000});

  await b.locator('#rtc-text').fill('ACK FROM B');
  await b.locator('#rtc-send').click();
  await a.waitForFunction(()=>document.getElementById('rtc-messages').textContent.includes('ACK FROM B'),null,{timeout:10000});

  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS: WebRTC no-STUN browser-to-browser full-duplex text exchange');
  console.log('PASS: manual SDP offer / answer, no external signaling server');
  console.log('PASS: all UI modules loaded without uncaught browser errors');
  await a.locator('#rtc-close').click();
  await b.locator('#rtc-close').click();
}finally{
  await browser.close();
}
