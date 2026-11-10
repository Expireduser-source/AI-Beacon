// AI Beacon local WebRTC DataChannel; manual, operator-consented signaling.
// SDP contains host/network addresses: share it ONLY with an intended peer.
// Optional Google STUN reveals connection metadata to that external service.
export class ManualPeer {
  constructor({onState=()=>{},onMessage=()=>{},onLocal=()=>{},useStun=false}={}) {
    if(typeof RTCPeerConnection==='undefined')
      throw new Error('WebRTC DataChannel is not supported by this browser');
    this.pc = new RTCPeerConnection({
      iceServers:useStun?[{urls:'stun:stun.l.google.com:19302'}]:[]
    });
    this.channel=null;
    this.onState=onState;
    this.onMessage=onMessage;
    this.onLocal=onLocal;
    this.pc.onconnectionstatechange=()=>{
      this.onState(this.pc.connectionState);
    };
    this.pc.ondatachannel=e=>this.attachChannel(e.channel);
    this.pc.oniceconnectionstatechange=()=>{
      this.onState('ICE: '+this.pc.iceConnectionState);
    };
  }
  attachChannel(channel) {
    this.channel=channel;
    channel.binaryType='arraybuffer';
    channel.onopen=()=>this.onState('connected');
    channel.onclose=()=>this.onState('channel closed');
    channel.onerror=()=>this.onState('channel error');
    channel.onmessage=e=>{
      if(typeof e.data==='string' && new TextEncoder().encode(e.data).length<=512)
        this.onMessage(e.data);
    };
  }
  async gather() {
    if(this.pc.iceGatheringState!=='complete') {
      await new Promise(resolve=>{
        let done=false;
        const stop=()=>{
          if(done)return;
          done=true;
          this.pc.removeEventListener('icegatheringstatechange',check);
          clearTimeout(timer);
          resolve();
        };
        const check=()=>{if(this.pc.iceGatheringState==='complete')stop();};
        const timer=setTimeout(stop,18000);
        this.pc.addEventListener('icegatheringstatechange',check);
        check();
      });
    }
    if(!this.pc.localDescription)throw new Error('No WebRTC local description');
    const desc={type:this.pc.localDescription.type,sdp:this.pc.localDescription.sdp};
    const text=JSON.stringify(desc);
    this.onLocal(text);
    return text;
  }
  static parseSignal(raw,expectedType) {
    if(typeof raw!=='string' || raw.length>60000 || raw.length<25)
      throw new Error('Invalid SDP message size');
    let x;
    try{x=JSON.parse(raw);}catch(_){throw new Error('Paste a valid JSON SDP message');}
    if(!x || x.type!==expectedType || typeof x.sdp!=='string' ||
       x.sdp.length<20 || x.sdp.length>55000 || !x.sdp.startsWith('v=0'))
      throw new Error('Expected a '+expectedType+' WebRTC description');
    return {type:x.type,sdp:x.sdp};
  }
  async offer() {
    if(this.pc.signalingState!=='stable')throw new Error('Create a new connection first');
    this.attachChannel(this.pc.createDataChannel('ai-beacon-text',{ordered:true}));
    await this.pc.setLocalDescription(await this.pc.createOffer());
    return await this.gather();
  }
  async answer(offerText) {
    await this.pc.setRemoteDescription(ManualPeer.parseSignal(offerText,'offer'));
    await this.pc.setLocalDescription(await this.pc.createAnswer());
    return await this.gather();
  }
  async acceptAnswer(answerText) {
    await this.pc.setRemoteDescription(ManualPeer.parseSignal(answerText,'answer'));
  }
  send(text) {
    if(typeof text!=='string'||!text.trim())throw new Error('Write a message first');
    if(new TextEncoder().encode(text).length>512)throw new Error('Max 512 UTF-8 bytes');
    if(!this.channel || this.channel.readyState!=='open')
      throw new Error('DataChannel is not connected');
    this.channel.send(text);
  }
  close() {
    if(this.channel)this.channel.close();
    this.pc.close();
    this.onState('disconnected');
  }
}
