import { chromium } from 'playwright';
import assert from 'node:assert/strict';
const url='https://ai-beacon-control.yummyanime1026.workers.dev/';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try {
  const page=await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true});
  const errors=[];
  page.on('pageerror',err=>errors.push(err.message));
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  assert.equal(response?.status(),200);
  await page.locator('#key').fill('short');
  await page.locator('#unlock').click();
  await page.waitForFunction(()=>document.getElementById('auth-state').textContent.includes('минимум 32'),null,{timeout:10000});
  assert.equal(await page.locator('#login').isVisible(),true);
  console.log('PASS: Short key now displays explicit error after button click');
  const invalid='0'.repeat(64);
  await page.locator('#key').fill(invalid);
  const [denied]=await Promise.all([
    page.waitForResponse(res=>res.url().endsWith('/api/login')&&res.request().method()==='POST',{timeout:20000}),
    page.locator('#unlock').click()
  ]);
  assert.equal(denied.status(),401,'Incorrect test key must never log in');
  await page.waitForFunction(()=>/Не удалось войти|Вход не выполнен/.test(document.getElementById('auth-state').textContent),null,{timeout:10000});
  assert.equal(await page.locator('#login').isVisible(),true);
  assert.equal(await page.locator('#console').isVisible(),false);
  assert.equal(await page.locator('#key').inputValue(),invalid,'Wrong key should stay editable');
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS: Real Cloudflare authentication rejects incorrect key, UI visibly shows denial');
  console.log('PASS: Mobile Chromium has zero uncaught JavaScript errors; protected panel remains hidden');
}finally{await browser.close();}
