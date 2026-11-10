import {
  frame,audioBits,decodeAudio,flashSymbols,decodeFlashSymbols,
  FREQ_ONE,FREQ_ZERO,SYMBOL_SECONDS
} from './codec.mjs';
import {ManualPeer} from './webrtc.mjs';

const $=id=>document.getElementById(id);
const set=(id,msg)=>{$(id).textContent=msg;};
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const COLORS=['#ff1038','#00ef46','#1763ff','#ffff23'];
let mic=null, camera=null, peer=null;
const channelLog=[];

function getMessage() {
  const text=$('payload').value.trim();
  frame(text);
  return text;
}
function displayError(statusId,error){
  set(statusId,(error && error.message) || String(error));
}
function updateLength(){
  const n=new TextEncoder().encode($('payload').value.trim()).length;
  set('size',n+' / 18 UTF-8 байт');
  $('size').style.color=n>18 || n===0?'#ff8f9a':'#9de8d3';
}
$('payload').addEventListener('input',updateLength);
updateLength();

async function sendAudio(){
  const button=$('audio-send');
  let ctx=null;
  try {
    const bits=audioBits(getMessage());
    button.disabled=true;
    ctx=new (window.AudioContext||window.webkitAudioContext)();
    await ctx.resume();
    const oscillator=ctx.createOscillator();
    const volume=ctx.createGain();
    volume.gain.value=0;
    oscillator.type='sine';
    oscillator.connect(volume).connect(ctx.destination);
    const start=ctx.currentTime+0.4;
    const stop=start+bits.length*SYMBOL_SECONDS;
    for(let i=0;i<bits.length;i++){
      oscillator.frequency.setValueAtTime(bits[i]==='1'?FREQ_ONE:FREQ_ZERO,start+i*SYMBOL_SECONDS);
    }
    volume.gain.setValueAtTime(0,start-.01);
    volume.gain.linearRampToValueAtTime(0.26,start+.02);
    volume.gain.setValueAtTime(0.26,stop-.025);
    volume.gain.linearRampToValueAtTime(0,stop);
    oscillator.start(start);
    oscillator.stop(stop+.01);
    set('audio-status','Передача '+bits.length+' бит, примерно '+(bits.length*SYMBOL_SECONDS).toFixed(1)+' сек. Не блокируй экран.');
    await new Promise(resolve=>{oscillator.onended=resolve;});
    set('audio-status','Передача завершена. На другом устройстве нажми «Остановить и распознать».');
  }catch(e){displayError('audio-status',e);}
  finally{if(ctx)await ctx.close().catch(()=>{});button.disabled=false;}
}
$('audio-send').addEventListener('click',sendAudio);

async function stopAudio() {
  if(!mic)return;
  const m=mic;mic=null;
  $('audio-listen').disabled=false;
  $('audio-stop').disabled=true;
  try{
    m.processor.onaudioprocess=null;
    m.source.disconnect();m.processor.disconnect();m.silent.disconnect();
    m.stream.getTracks().forEach(t=>t.stop());
    await m.context.close().catch(()=>{});
    const audio=new Float32Array(m.total);
    let pos=0;
    for(const part of m.chunks){audio.set(part,pos);pos+=part.length;}
    set('audio-status','Анализирую '+(audio.length/m.rate).toFixed(1)+' сек. звука...');
    const decoded=decodeAudio(audio,m.rate);
    if(decoded){
      set('audio-result',decoded.text);
      set('audio-status','Получено '+decoded.byteCount+' байт. CRC-16 пройдена; уверенность тона '+decoded.confidence+'.');
    } else {
      set('audio-status','Сообщение не обнаружено или CRC не совпала. Проверь тишину, расстояние и начало записи.');
    }
  }catch(e){displayError('audio-status',e);}
}
async function listenAudio(){
  if(mic)return;
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw new Error('Микрофон доступен только по HTTPS и с разрешением.');
    const stream=await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false},
      video:false
    });
    const context=new (window.AudioContext||window.webkitAudioContext)();
    await context.resume();
    const source=context.createMediaStreamSource(stream);
    const processor=context.createScriptProcessor(2048,1,1);
    const silent=context.createGain();silent.gain.value=0;
    source.connect(processor);processor.connect(silent);silent.connect(context.destination);
    mic={context,stream,source,processor,silent,rate:context.sampleRate,total:0,chunks:[]};
    $('audio-listen').disabled=true;$('audio-stop').disabled=false;
    set('audio-result','—');
    set('audio-status','Микрофон включён. Теперь начни передачу на другом устройстве. Максимум 40 секунд.');
    processor.onaudioprocess=event=>{
      if(!mic)return;
      const part=event.inputBuffer.getChannelData(0).slice();
      mic.chunks.push(part);mic.total+=part.length;
      if(mic.total>mic.rate*40)void stopAudio();
    };
  }catch(e){displayError('audio-status',e);$('audio-listen').disabled=false;}
}
$('audio-listen').addEventListener('click',listenAudio);
$('audio-stop').addEventListener('click',()=>{void stopAudio();});

function classify(r,g,b){
  if(Math.max(r,g,b)<50)return -1;
  if(r>g*1.35 && r>b*1.5 && r>85)return 0;
  if(g>r*1.32 && g>b*1.3 && g>85)return 1;
  if(b>r*1.35 && b>g*1.25 && b>80)return 2;
  if(r>75 && g>75 && r>b*1.35 && g>b*1.35)return 3;
  return null;
}
function sampleColor(ctx,v){
  if(!v.videoWidth || !v.videoHeight)return null;
  const size=Math.max(10,Math.min(v.videoWidth,v.videoHeight)*.10);
  ctx.drawImage(v,(v.videoWidth-size)/2,(v.videoHeight-size)/2,size,size,0,0,16,16);
  const p=ctx.getImageData(0,0,16,16).data;
  let r=0,g=0,b=0,n=0;
  for(let i=0;i<p.length;i+=4){r+=p[i];g+=p[i+1];b+=p[i+2];n++;}
  return classify(r/n,g/n,b/n);
}

async function showLight(){
  const button=$('light-send');
  let overlay=$('flash');
  try{
    const symbols=flashSymbols(getMessage());
    button.disabled=true;
    overlay.hidden=false;
    set('light-status','Передаю '+symbols.length+' цветовых символов. Держи экран перед камерой второго устройства.');
    for(const code of symbols){
      overlay.style.background=COLORS[code];
      await pause(280);
      overlay.style.background='#000';
      await pause(170);
    }
    set('light-status','Цветовая передача завершена.');
  }catch(e){displayError('light-status',e);}
  finally{overlay.hidden=true;button.disabled=false;}
}
$('light-send').addEventListener('click',showLight);

async function stopCamera(){
  if(!camera)return;
  const c=camera;camera=null;
  cancelAnimationFrame(c.frame);
  c.stream.getTracks().forEach(t=>t.stop());
  $('camera-preview').srcObject=null;
  $('light-listen').disabled=false;$('light-stop').disabled=true;
  set('light-status',c.done ? 'Сообщение принято, CRC-16 подтверждена. Камера выключена.' : 'Камера выключена. Получено '+c.events.length+' цветовых символов.');
}
async function startCamera(){
  if(camera)return;
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw new Error('Камера требует HTTPS и явного разрешения.');
    const stream=await navigator.mediaDevices.getUserMedia({
      video:{facingMode:{ideal:'environment'},width:{ideal:640},height:{ideal:480}},audio:false
    });
    const video=$('camera-preview');video.srcObject=stream;
    await video.play();
    const canvas=document.createElement('canvas');canvas.width=16;canvas.height=16;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    camera={stream,frame:0,events:[],state:null,stable:0,locked:null,armed:true,done:false};
    const c=camera;
    $('light-listen').disabled=true;$('light-stop').disabled=false;
    set('light-result','—');
    set('light-status','Направь камеру точно на центр второго экрана и начни передачу цветами.');
    const loop=()=>{
      if(camera!==c)return;
      const current=sampleColor(ctx,video);
      if(current===c.state)c.stable++;
      else {c.state=current;c.stable=1;}
      if(c.stable>=2 && current!==c.locked){
        c.locked=current;
        if(current===-1 || current===null)c.armed=true;
        else if(c.armed){
          c.armed=false;
          c.events.push(current);
          set('light-count','Символов: '+c.events.length);
          const decoded=decodeFlashSymbols(c.events);
          if(decoded) {
            c.done=true;
            set('light-result',decoded.text);
            set('light-status','Оптическое сообщение принято. CRC-16 пройдена.');
            void stopCamera();
            return;
          }
          if(c.events.length>160)c.events.splice(0,32);
        }
      }
      c.frame=requestAnimationFrame(loop);
    };
    c.frame=requestAnimationFrame(loop);
  }catch(e){displayError('light-status',e);$('light-listen').disabled=false;}
}
$('light-listen').addEventListener('click',startCamera);
$('light-stop').addEventListener('click',()=>{void stopCamera();});

function rtcState(value){set('rtc-status',value);}
function rtcMessage(value){
  channelLog.push('Собеседник: '+value);
  $('rtc-messages').textContent=channelLog.join('\n');
}
function newPeer(){
  if(peer)peer.close();
  peer=new ManualPeer({
    useStun:$('use-stun').checked,
    onState:rtcState,
    onMessage:rtcMessage,
    onLocal:value=>{$('local-sdp').value=value;}
  });
  return peer;
}
async function createOffer(){
  try{rtcState('Генерирую предложение. Собираю ICE-кандидаты...');await newPeer().offer();rtcState('Предложение готово. Передай его только доверенному собеседнику.');}
  catch(e){displayError('rtc-status',e);}
}
async function acceptOffer(){
  try{rtcState('Принимаю предложение...');await newPeer().answer($('remote-sdp').value.trim());rtcState('Ответ готов. Верни текст первому устройству.');}
  catch(e){displayError('rtc-status',e);}
}
async function acceptAnswer(){
  try{if(!peer)throw new Error('Сначала создай предложение на этом устройстве');await peer.acceptAnswer($('remote-sdp').value.trim());rtcState('Ответ принят. Проверяю соединение...');}
  catch(e){displayError('rtc-status',e);}
}
async function copyLocal(){
  try{await navigator.clipboard.writeText($('local-sdp').value);rtcState('Сигнал скопирован. Передавай его только выбранному собеседнику.');}
  catch(e){displayError('rtc-status',e);}
}
function sendRTC(){
  try{
    if(!peer)throw new Error('Сначала установи соединение.');
    const message=$('rtc-text').value;
    peer.send(message);
    channelLog.push('Вы: '+message);
    $('rtc-messages').textContent=channelLog.join('\n');
    $('rtc-text').value='';
    rtcState('Сообщение отправлено напрямую через WebRTC.');
  }catch(e){displayError('rtc-status',e);}
}
$('rtc-offer').addEventListener('click',createOffer);
$('rtc-answer').addEventListener('click',acceptOffer);
$('rtc-finalize').addEventListener('click',acceptAnswer);
$('rtc-copy').addEventListener('click',copyLocal);
$('rtc-send').addEventListener('click',sendRTC);
$('rtc-close').addEventListener('click',()=>{if(peer)peer.close();peer=null;rtcState('Соединение закрыто.');});
window.addEventListener('pagehide',()=>{
  if(mic){mic.stream.getTracks().forEach(t=>t.stop());mic.context.close().catch(()=>{});}
  if(camera)camera.stream.getTracks().forEach(t=>t.stop());
  if(peer)peer.close();
});
