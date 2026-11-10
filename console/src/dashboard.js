// AI Beacon Console — browser controller. The key is never persisted client-side.
const $=id=>document.getElementById(id);
let isRunning=false;
let activeId=null;
const set=(id,text)=>{$(id).textContent=text;};
function showConsole(authenticated){
  $('login').hidden=authenticated;
  $('console').hidden=!authenticated;
  if(!authenticated){
    activeId=null;
    $('chat').replaceChildren();
    const empty=document.createElement('div');
    empty.className='empty';
    empty.textContent='Войди в пульт, чтобы увидеть последний диалог.';
    $('chat').append(empty);
  }
}
async function jsonApi(path,data=undefined,timeoutMs=65000){
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),timeoutMs);
  const opts={credentials:'same-origin',cache:'no-store',signal:controller.signal};
  if(data!==undefined){
    opts.method='POST';
    opts.headers={'Content-Type':'application/json'};
    opts.body=JSON.stringify(data);
  }
  try{
    let response;
    try{response=await fetch(path,opts);}
    catch(error){
      if(error?.name==='AbortError')throw new Error('Сервер не ответил вовремя; состояние разговора сохранено. Обнови историю.');
      throw new Error('Нет связи с сервером. Проверь интернет или обнови историю.');
    }
    let result;
    try{result=await response.json();}
    catch(_){throw new Error('Сервер вернул повреждённый или не-JSON ответ (HTTP '+response.status+').');}
    if(!response.ok){
      if(response.status===401)showConsole(false);
      throw new Error(result.error||'Ошибка сервера HTTP '+response.status);
    }
    return result;
  }finally{
    clearTimeout(timeout);
  }
}
function appendBubble(container,speaker,text,kind){
  const article=document.createElement('article');
  article.className='bubble '+kind;
  const head=document.createElement('div');
  head.className='head';
  const name=document.createElement('span');
  name.textContent=speaker;
  const role=document.createElement('span');
  role.className='role';
  role.textContent=kind==='gemma'?'Cloudflare Workers AI':'Внешний A2A сервис';
  head.append(name,role);
  const body=document.createElement('div');
  body.className='body';
  body.textContent=text;
  article.append(head,body);
  container.append(article);
}
const stages={
  queued:'Разговор создан. Начинаю первый раунд.',
  generating:'Gemma 4 формирует вопрос…',
  contacting_emissary:'Gemma подготовила вопрос. Ждём ответа внешнего Emissary…',
  ready_for_followup:'Первый ответ Emissary получен. Следующий раунд готов.',
  completed:'Два раунда завершены, ответы сохранены.',
  failed:'Запрос завершился ошибкой. Детали ниже.'
};
let lastSnapshot=null;
function stageText(run){
  if(!run)return 'Готово к первому запуску.';
  const base=stages[run.stage]||'Состояние: '+run.status;
  if(run.status==='failed')return base+(run.error?' Причина: '+run.error:'');
  if(run.active&&run.active_since){
    const seconds=Math.floor((Date.now()-run.active_since)/1000);
    return base+' (этап выполняется '+Math.max(0,seconds)+' сек.)';
  }
  return base;
}
function render(data){
  if(!data)return;
  lastSnapshot=data;
  set('quota','Сегодня использовано '+data.used+' из '+data.limit+' запусков · '+data.day+' (UTC)');
  const record=data.run;
  const container=$('chat');
  container.replaceChildren();
  const items=Array.isArray(record?.turns)?record.turns:[];
  if(!items.length && !record?.draft_gemma){
    const empty=document.createElement('div');
    empty.className='empty';
    empty.textContent=record?
      'Разговор начат. Ответ ещё не получен. Этап обработки указан выше.':
      'Здесь появятся сообщения после первого запуска.';
    container.append(empty);
  }
  for(const turn of items){
    const label=document.createElement('div');
    label.className='turn';
    label.textContent='Раунд '+turn.round;
    container.append(label);
    if(typeof turn.gemma==='string')appendBubble(container,'Gemma 4',turn.gemma,'gemma');
    if(typeof turn.emissary==='string')appendBubble(container,'Emissary',turn.emissary,'emissary');
  }
  if(record?.draft_gemma){
    const label=document.createElement('div');
    label.className='turn';
    label.textContent='Раунд '+(items.length+1)+' · ответ ожидается';
    container.append(label);
    appendBubble(container,'Gemma 4',record.draft_gemma,'gemma');
  }
  if(record){
    activeId=record.id;
    const stamp=new Date(record.updated_at).toLocaleString();
    set('run-info','ID '+record.id.slice(0,8)+' · '+stamp+' · '+record.status+
      (record.error?' · Ошибка: '+record.error:''));
  }else{
    activeId=null;
    set('run-info','');
  }
  if(!isRunning){
    $('run').textContent=record?.status==='running'
      ?'▶ Продолжить начатый разговор'
      :'▶ Начать разговор двух ИИ';
    $('run').disabled=record?.status==='running'?false:data.used>=data.limit;
  }
}
async function refresh(){
  const data=await jsonApi('/api/status',undefined,15000);
  render(data);
  return data;
}
async function login(event){
  event.preventDefault();
  const keyInput=$('key');
  const key=keyInput.value.trim();
  if(key.length<32||key.length>160){
    set('auth-state','Ключ не отправлен. Вставь полный ключ из Cloudflare: минимум 32 символа.');
    keyInput.focus();
    return;
  }
  const button=$('unlock');
  button.disabled=true;
  set('auth-state','Проверяю ключ на сервере…');
  try{
    await jsonApi('/api/login',{key});
    showConsole(true);
    set('auth-state','Вход подтверждён.');
    const session=await refresh();
    keyInput.value='';
    generatedKey=null;
    $('generated-key').value='';
    $('copy-generated').disabled=true;
    set('status',session.run?stageText(session.run):'Готово. Выбери тему и начни беседу.');
  }catch(e){
    set('auth-state','Не удалось войти: '+e.message);
  }finally{button.disabled=false;}
}
function setBusy(active){
  isRunning=active;
  $('run').disabled=active;
  $('logout').disabled=active;
  if(!active&&lastSnapshot)render(lastSnapshot);
}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function awaitExistingStep(runId){
  const deadline=Date.now()+90000;
  while(Date.now()<deadline){
    const snapshot=await refresh();
    const run=snapshot.run;
    if(!run||run.id!==runId)throw new Error('Состояние разговора изменилось.');
    if(run.status!=='running'||!run.active)return run;
    const elapsed=Date.now()-(run.active_since||Date.now());
    set('status',stageText(run)+' Повторно оплачивать запуск не нужно.');
    if(elapsed>95000)return run;
    await pause(5000);
  }
  return (await refresh()).run;
}
async function sendStep(runId,index){
  set('status','Раунд '+index+'/2: запрашиваю ответ модели…');
  const heartbeat=setInterval(()=>{
    void refresh().then(snapshot=>{
      if(snapshot.run?.id===runId)
        set('status','Раунд '+index+'/2: '+stageText(snapshot.run));
    }).catch(()=>{});
  },5500);
  try{
    return await jsonApi('/api/step',{runId},88000);
  }finally{
    clearInterval(heartbeat);
  }
}
async function run(){
  if(isRunning)return;
  const topic=$('topic').value.trim();
  if(topic.length<10||topic.length>180){
    set('status','Тема должна содержать 10–180 символов.');
    return;
  }
  setBusy(true);
  try{
    let snapshot=await refresh();
    let record=snapshot.run;
    if(record?.status!=='running'){
      set('status','Создаю разговор. Один запуск будет списан из дневного лимита…');
      const created=await jsonApi('/api/start',{topic},18000);
      record=created.run;
      if(!record?.id)throw new Error('Сервер не выдал идентификатор разговора.');
      await refresh();
    }else{
      set('status','Продолжаю ранее созданный разговор без нового списания лимита.');
    }
    activeId=record.id;
    if(record.active){
      record=await awaitExistingStep(activeId);
    }
    for(let round=(record.turns||[]).length+1;round<=2;round++){
      if(record.status==='completed')break;
      if(record.status==='failed')
        throw new Error(record.error||'Предыдущий раунд завершился ошибкой.');
      if(record.active){
        record=await awaitExistingStep(activeId);
        if(record.status==='completed')break;
        if(record.status==='failed')throw new Error(record.error||'Сбой предыдущего раунда.');
        if(record.active&&Date.now()-(record.active_since||Date.now())<85000)
          throw new Error('Предыдущий запрос ещё выполняется; обнови историю, а не создавай новый запуск.');
      }
      const response=await sendStep(activeId,round);
      record=response.run;
      snapshot=await refresh();
      record=snapshot.run||record;
    }
    set('status',record.status==='completed'?
      'Диалог завершён: оба ответа получены и сохранены.':
      stageText(record));
  }catch(e){
    let latest=null;
    try{latest=(await refresh()).run;}catch(_){}
    set('status','Не удалось завершить запрос: '+e.message+
      (latest?.status==='running'
        ?' Сам разговор сохранён. Нажми «Показать историю» или «Продолжить» — новый запуск не потребуется.'
        :''));
  }finally{
    setBusy(false);
  }
}
async function logout(){
  try{await jsonApi('/api/logout',{});}
  catch(_){}
  showConsole(false);set('auth-state','Сессия закрыта. Для следующего входа потребуется личный ключ.');
}
let generatedKey=null;
$('generate-key').addEventListener('click',()=>{
  const bytes=crypto.getRandomValues(new Uint8Array(32));
  generatedKey=Array.from(bytes,n=>n.toString(16).padStart(2,'0')).join('');
  $('generated-key').value=generatedKey;
  $('copy-generated').disabled=false;
  set('auth-state','Ключ создан только на твоём устройстве. Добавь его в секрет CONSOLE_KEY в Cloudflare, затем выполни вход.');
});
$('copy-generated').addEventListener('click',async()=>{
  if(!generatedKey)return;
  try{await navigator.clipboard.writeText(generatedKey);set('auth-state','Ключ скопирован. Не отправляй его в публичные сообщения.');}
  catch(_){set('auth-state','Выдели и скопируй ключ вручную из поля.');}
});
$('login-form').addEventListener('submit',login);
$('run').addEventListener('click',run);
$('refresh').addEventListener('click',async()=>{
  try{const data=await refresh();set('status',data.run?'История обновлена.':'Пока нет разговоров.');}
  catch(e){set('status',e.message);}
});
$('logout').addEventListener('click',logout);
(async()=>{
  try{
    const x=await refresh();
    showConsole(true);
    set('status',x.run?stageText(x.run):'Готово к новому разговору.');
  }catch(e){
    showConsole(false);
    set('auth-state',e.message.includes('Нужен вход')?'Для запуска нужен личный ключ владельца.':e.message);
  }
})();
