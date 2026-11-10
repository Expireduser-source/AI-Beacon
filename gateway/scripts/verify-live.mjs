// Manually invoked deployment verification: DO NOT mark A2A live unless
// the agent card and two actual Cloudflare AI round trips succeed.
const urlText = (process.env.A2A_GATEWAY_URL || '').trim();
const repo = process.env.GITHUB_REPOSITORY || 'Expireduser-source/AI-Beacon';
const token = process.env.GH_TOKEN;
function requireTrue(ok, reason) { if (!ok) throw new Error(reason); }
async function getJSON(url, opts) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 50000);
  try {
    const response = await fetch(url, { ...opts, signal:controller.signal });
    requireTrue(response.ok, 'Request failed, HTTP '+response.status);
    return await response.json();
  } finally { clearTimeout(timer); }
}
async function verify() {
  const origin = new URL(urlText);
  requireTrue(origin.protocol === 'https:' && origin.username === '' && origin.password === '', 'Only public HTTPS accepted');
  requireTrue(origin.pathname === '/' && !origin.search && !origin.hash, 'Use only an origin without path/query');
  requireTrue(/^ai-beacon-a2a\.[a-z0-9-]+\.workers\.dev$/i.test(origin.hostname), 'Expected an ai-beacon-a2a workers.dev hostname');
  const card = await getJSON(origin.origin+'/.well-known/agent-card.json');
  requireTrue(card.name === 'AI Beacon · Independent Research Agent','Wrong agent card name');
  requireTrue(card.supportedInterfaces?.some(x => x.url === origin.origin && x.protocolBinding === 'HTTP+JSON' && x.protocolVersion === '1.0'), 'No real matching HTTP+JSON v1.0 interface');
  let contextId;
  for (const [i,question] of [
    'Please suggest one safe, reproducible experiment for two independently operated AI agents.',
    'Please build on your preceding answer and name one limitation.'
  ].entries()) {
    const request = {message: {
      role:'ROLE_USER', messageId: crypto.randomUUID(), parts:[{text:question}],
      ...(contextId?{contextId}:{})
    }};
    const reply = await getJSON(origin.origin+'/message:send', {
      method:'POST',headers:{'content-type':'application/a2a+json'},body:JSON.stringify(request)
    });
    requireTrue(reply.message?.role === 'ROLE_AGENT', 'No A2A ROLE_AGENT response');
    requireTrue(typeof reply.message.parts?.[0]?.text === 'string' && reply.message.parts[0].text.trim().length > 2, 'No real model answer');
    requireTrue(typeof reply.message.contextId === 'string' && reply.message.contextId.length === 36, 'Missing contextId');
    if (contextId) requireTrue(reply.message.contextId === contextId,'Follow-up did not preserve context');
    contextId = reply.message.contextId;
    console.log('Verified real A2A reply',i+1,'characters',reply.message.parts[0].text.length);
  }
  return origin.origin;
}
async function publish(base) {
  requireTrue(token,'No GitHub token: cannot publish verified A2A URL');
  const endpoint='https://api.github.com/repos/'+repo+'/contents/docs/.well-known/ai-beacon.json';
  const head={'authorization':'Bearer '+token,'accept':'application/vnd.github+json','x-github-api-version':'2022-11-28'};
  for(let i=0;i<5;i++){
    const f=await getJSON(endpoint,{headers:head});
    const m=JSON.parse(Buffer.from(f.content.replace(/\s/g,''),'base64').toString('utf8'));
    const wanted={transport:'a2a-http-json',availability:'available',endpoint:base,message_endpoint:base+'/message:send',agent_card:base+'/.well-known/agent-card.json',protocol_version:'1.0',verified_by:'two live HTTP+JSON message exchanges'};
    const old=Array.isArray(m.communications)?m.communications:[];
    m.communications=[...old.filter(x=>x.transport!=='a2a-http-json'),wanted];
    m.a2a_verified_at=new Date().toISOString();
    m.a2a_gateway_origin=base;
    const payload={message:'feat: publish A2A gateway after verified live round trips',sha:f.sha,content:Buffer.from(JSON.stringify(m,null,2)+'\n').toString('base64')};
    const response=await fetch(endpoint,{method:'PUT',headers:{...head,'content-type':'application/json'},body:JSON.stringify(payload)});
    if(response.ok){console.log('Published verified endpoint in GitHub discovery manifest',base);return;}
    if(![409,422].includes(response.status))throw new Error('Manifest update failed HTTP '+response.status);
  }
  throw new Error('Repeated concurrent manifest changes');
}
const base=await verify();
console.log('A2A end-to-end success at',base);
await publish(base);
