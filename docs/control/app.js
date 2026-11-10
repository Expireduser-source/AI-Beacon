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
async function jsonApi(path,data=undefined){
  const opts={credentials:'same-origin',cache:'no-store'};
  if(data!==undefined){
    opts.method='POST';
    opts.headers={'Content-Type':'application/json'};
    opts.body=JSON.stringify(data);
  }
  let response;
  try{response=await fetch(path,opts);}
  catch(_){throw new Error('Нет связи с сервером. Проверь интернет.');}
  let result;
  try{result=await response.json();}
  catch(_){throw new Error('Сервер вернул неожиданный ответ.');}
  if(!response.ok) {
    if(response.status===401){showConsole(false);}
    throw new Error(result.error || 'HTTP '+response.status);
  }
  return result;
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
function render(data){
  if(!data)return;
  set('quota','Сегодня использовано '+data.used+' из '+data.limit+' запусков · '+data.day+' (UTC)');
  const record=data.run;
  const container=$('chat');container.replaceChildren();
  if(!record||!Array.isArray(record.turns)||!record.turns.length){
    const empty=document.createElement('div');
    empty.className='empty';
    empty.textContent=record?'Разговор начат. Первый ответ ещё не получен.':'Здесь появится первый разговор после запуска.';
    container.append(empty);
  }else{
    for(const turn of record.turns){
      const label=document.createElement('div');
      label.className='turn';label.textContent='Раунд '+turn.round;
      container.append(label);
      if(typeof turn.gemma==='string')appendBubble(container,'Gemma 4',turn.gemma,'gemma');
      if(typeof turn.emissary==='string')appendBubble(container,'Emissary',turn.emissary,'emissary');
    }
  }
  if(record){
    activeId=record.id;
    const stamp=new Date(record.updated_at).toLocaleString();
    const label='ID '+record.id.slice(0,8)+' · '+stamp+' · '+record.status;
    set('run-info',label+(record.error?' · Ошибка: '+record.error:''));
  }else{set('run-info','');}
}
async function refresh(){
  const data=await jsonApi('/api/status');
  render(data);
  return data;
}
async function login(event){
  event.preventDefault();
  const button=$('unlock');
  button.disabled=true;set('auth-state','Проверяю ключ владельца…');
  const key=$('key').value;
  try{
    await jsonApi('/api/login',{key});
    $('key').value='';
    showConsole(true);
    set('auth-state','Сеанс подтверждён.');
    await refresh();
    set('status','Готово. Выбери тему и нажми «Начать разговор».');
  }catch(e){set('auth-state',e.message);}
  finally{button.disabled=false;$('key').value='';}
}
function setBusy(active){
  isRunning=active;
  $('run').disabled=active;
  $('refresh').disabled=active;
  $('logout').disabled=active;
}
async function run(){
  if(isRunning)return;
  const topic=$('topic').value.trim();
  if(topic.length<10||topic.length>180){
    set('status','Тема должна содержать 10–180 символов.');return;
  }
  setBusy(true);
  try{
    set('status','Создаю новый исследовательский разговор…');
    const start=await jsonApi('/api/start',{topic});
    const runId=start.run?.id;
    if(!runId)throw new Error('Не получен идентификатор разговора');
    activeId=runId;
    await refresh();
    for(let n=1;n<=2;n++){
      set('status','Раунд '+n+'/2: Gemma формирует вопрос, Emissary отвечает. Запрос может длиться до минуты…');
      const response=await jsonApi('/api/step',{runId});
      await refresh();
      const record=response.run;
      if(record?.status==='completed')break;
      if(record?.status==='failed')throw new Error(record.error||'Раунд прерван.');
    }
    set('status','Диалог завершён. Ответы обоих ИИ сохранены в журнале.');
  }catch(e){
    set('status','Разговор не завершён: '+e.message);
    try{await refresh();}catch(_){}
  }finally{setBusy(false);}
}
async function logout(){
  try{await jsonApi('/api/logout',{});}
  catch(_){}
  showConsole(false);set('auth-state','Сессия закрыта. Для следующего входа потребуется личный ключ.');
}
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
    set('status',x.run?'Последняя беседа загружена.':'Готово к новому разговору.');
  }catch(e){
    showConsole(false);
    set('auth-state',e.message.includes('Нужен вход')?'Для запуска нужен личный ключ владельца.':e.message);
  }
})();
