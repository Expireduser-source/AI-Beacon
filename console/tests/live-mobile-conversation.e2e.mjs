import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const URL='https://ai-beacon-control.yummyanime1026.workers.dev/';
const RUN='a8e57052-0d47-49f3-8903-d131d4f2d719';
const KEY='0'.repeat(64);
function setup(page){
  let loggedIn=false;
  let used=0;
  let starts=0;
  let steps=0;
  let run=null;
  const err=[];
  page.on('pageerror',e=>err.push(e.message));
  page.route('**/api/**',async route=>{
    const pathname=new URL(route.request().url()).pathname;
    const method=route.request().method();
    const data=method==='POST'?JSON.parse(route.request().postData()||'{}'):{};
    let status=200;
    let body={};
    if(pathname==='/api/login'){
      loggedIn=data.key===KEY;
      if(!loggedIn){status=401;body={error:'Неверный ключ доступа'};}
      else body={ok:true};
    }else if(!loggedIn){
      status=401;
      body={error:'Нужен вход владельца.'};
    }else if(pathname==='/api/status'){
      body={day:'2026-11-10',used,limit:2,run};
    }else if(pathname==='/api/preflight'){
      body={ok:true,gemma:'configured',storage:'ok',emissary:'reachable'};
    }else if(pathname==='/api/start'){
      starts++;
      used++;
      run={id:RUN,topic:data.topic,status:'running',stage:'queued',active:false,
        started_at:Date.now(),updated_at:Date.now(),turns:[],error:null,draft_gemma:null};
      body={run,used,limit:2};
    }else if(pathname==='/api/step'){
      steps++;
      assert.equal(data.runId,RUN);
      run={...run,stage:steps>=2?'completed':'ready_for_followup',
        status:steps>=2?'completed':'running',updated_at:Date.now(),
        turns:[...run.turns,{round:steps,gemma:'Question '+steps+' by Gemma 4',
          emissary:'Answer '+steps+' from Emissary'}]};
      body={run};
    }else{
      status=404;body={error:'unknown'};
    }
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  });
  return {get starts(){return starts;},get steps(){return steps;},get run(){return run;},
    setRun(x){run=x;},setAuth(x){loggedIn=x;},setUsed(x){used=x;},errors:err};
}
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
  const page=await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true});
  const state=setup(page);
  const loaded=await page.goto(URL,{waitUntil:'domcontentloaded',timeout:30000});
  assert.equal(loaded?.status(),200);
  await page.locator('#key').fill(KEY);
  await page.locator('#unlock').click();
  await page.waitForFunction(()=>!document.getElementById('console').hidden,null,{timeout:12000});

  await page.locator('#preflight').click();
  await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Соединения проверены'),null,{timeout:10000});

  await page.locator('#run').click();
  await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Диалог завершён'),null,{timeout:16000});
  assert.equal(await page.locator('.bubble').count(),4);
  assert.equal(state.starts,1);
  assert.equal(state.steps,2);
  assert.match(await page.locator('#quota').textContent(),/1 из 2/);
  assert.equal(state.errors.length,0,state.errors.join('\n'));
  console.log('PASS: Mobile UI runs full two-turn simulated A2A exchange, showing all four messages');

  // Model a previously interrupted conversation after a browser reload.
  state.setUsed(1);
  state.setRun({id:RUN,topic:'Previously approved topic',status:'running',stage:'ready_for_followup',
    active:false,started_at:Date.now()-15000,updated_at:Date.now(),error:null,
    turns:[{round:1,gemma:'First Gemma message',emissary:'First Emissary reply'}]});
  state.setAuth(true);
  const startsBefore=state.starts;
  const stepsBefore=state.steps;
  await page.reload({waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>document.getElementById('run').textContent.includes('Продолжить'),null,{timeout:12000});
  await page.locator('#run').click();
  await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Диалог завершён'),null,{timeout:16000});
  assert.equal(state.starts,startsBefore,'Resume must not spend another daily run');
  assert.equal(state.steps,stepsBefore+1,'Resume should perform only the missing second turn');
  assert.equal(await page.locator('.bubble').count(),4);
  assert.equal(state.errors.length,0,state.errors.join('\n'));
  console.log('PASS: Mobile UI resumes incomplete conversation with no new paid start');
}finally{
  await browser.close();
}
