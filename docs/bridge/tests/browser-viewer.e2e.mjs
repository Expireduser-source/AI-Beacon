import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage();
 const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const response=await page.goto('http://127.0.0.1:8765/bridge/',{waitUntil:'load'});
 assert.equal(response?.status(),200);
 assert.match(await page.title(),/Один телефон/);
 await page.waitForFunction(
   ()=>document.getElementById('messages').querySelectorAll('.bubble').length>=4,
   null,{timeout:20000}
 );
 const bubbles=await page.locator('.bubble').count();
 assert.equal(bubbles,4,'Latest successful transcript has four real model messages');
 const text=await page.locator('#messages').innerText();
 assert.match(text,/Gemma 4/);
 assert.match(text,/Emissary/);
 assert.ok(text.length>250);
 assert.match(await page.locator('#status').innerText(),/ответов Emissary: 2 \/ 2/);
 await page.locator('#reload').click();
 await page.waitForFunction(
   ()=>document.getElementById('messages').querySelectorAll('.bubble').length===4,
   null,{timeout:20000}
 );
 assert.equal(errors.length,0,errors.join('\n'));
 console.log('PASS: actual GitHub-published Gemma ↔ Emissary transcript renders on mobile browser page');
 console.log('PASS: four model messages load and can be refreshed without browser exceptions');
}finally{await browser.close();}
