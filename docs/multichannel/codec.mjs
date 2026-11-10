// AI Beacon multichannel framing and tone receiver primitives, v0.1.
// This module uses browser-compatible ECMAScript without dependencies.
// CRC protects against accidental corruption; it does NOT authenticate sender identity.
export const MAX_BYTES = 18;
export const PREAMBLE = '101010101010101011110000';
export const FLASH_PREAMBLE = [0,1,2,3,0,1,2,3];
export const SYMBOL_SECONDS = 0.09;
export const FREQ_ZERO = 960;
export const FREQ_ONE = 1600;
const MAGIC = [0xb6, 0x51, 1];

export function crc16(bytes) {
  let crc = 0xffff;
  for (const byte of bytes) {
    crc ^= byte << 8;
    for (let i=0; i<8; i++) {
      crc = crc & 0x8000 ? ((crc<<1)^0x1021)&0xffff : (crc<<1)&0xffff;
    }
  }
  return crc;
}

export function frame(text) {
  const bytes = new TextEncoder().encode(String(text));
  if (bytes.length < 1 || bytes.length > MAX_BYTES) {
    throw new RangeError('Message must be 1–18 UTF-8 bytes.');
  }
  const content = Uint8Array.from([...MAGIC,bytes.length,...bytes]);
  const sum = crc16(content);
  return Uint8Array.from([...content,(sum>>8)&255,sum&255]);
}

export function parseFrame(input) {
  const bytes = Uint8Array.from(input);
  if (bytes.length < 7 || bytes.length > MAX_BYTES+6) return null;
  if (bytes[0]!==MAGIC[0] || bytes[1]!==MAGIC[1] || bytes[2]!==MAGIC[2]) return null;
  const n=bytes[3];
  if(n<1 || n>MAX_BYTES || bytes.length!==n+6) return null;
  const check=crc16(bytes.subarray(0,bytes.length-2));
  if (bytes[bytes.length-2]!==(check>>8) || bytes[bytes.length-1]!==(check&255)) return null;
  try {
    return new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(4,bytes.length-2));
  } catch (_) {
    return null;
  }
}

export function bitsOf(bytes) {
  let result='';
  for(const b of bytes) result += b.toString(2).padStart(8,'0');
  return result;
}

export function fromBits(bits) {
  if (bits.length%8!==0 || /[^01]/.test(bits)) throw new RangeError('Invalid bitstream');
  const arr=new Uint8Array(bits.length/8);
  for(let i=0;i<arr.length;i++) arr[i]=parseInt(bits.slice(i*8,(i+1)*8),2);
  return arr;
}

export function audioBits(text) {
  return PREAMBLE + bitsOf(frame(text));
}

export function decodeBits(bits) {
  let start=bits.indexOf(PREAMBLE);
  while(start!==-1) {
    const pos=start+PREAMBLE.length;
    if(bits.length>=pos+32) {
      const head=fromBits(bits.slice(pos,pos+32));
      const size=head[3];
      if (head[0]===MAGIC[0] && head[1]===MAGIC[1] && head[2]===MAGIC[2]
          && size>=1 && size<=MAX_BYTES) {
        const end=pos+(size+6)*8;
        if(bits.length>=end) {
          const decoded=parseFrame(fromBits(bits.slice(pos,end)));
          if(decoded!==null) return {text:decoded,bitOffset:start,byteCount:size};
        }
      }
    }
    start=bits.indexOf(PREAMBLE,start+1);
  }
  return null;
}

export function flashSymbols(text) {
  const bits=bitsOf(frame(text));
  const symbols=FLASH_PREAMBLE.slice();
  for(let i=0;i<bits.length;i+=2) symbols.push(parseInt(bits.slice(i,i+2),2));
  return symbols;
}

export function decodeFlashSymbols(values) {
  for(let start=0;start<=values.length-FLASH_PREAMBLE.length;start++){
    if(!FLASH_PREAMBLE.every((s,i)=>s===values[start+i])) continue;
    const data=values.slice(start+FLASH_PREAMBLE.length);
    if(data.length<16 || data.some(x=>!Number.isInteger(x)||x<0||x>3)) continue;
    let bits='';
    for(const symbol of data) bits+=symbol.toString(2).padStart(2,'0');
    const head=fromBits(bits.slice(0,32));
    const size=head[3];
    if(head[0]!==MAGIC[0] || head[1]!==MAGIC[1] || head[2]!==MAGIC[2]
       || size<1 || size>MAX_BYTES) continue;
    const length=(size+6)*8;
    if(bits.length<length) continue;
    const decoded=parseFrame(fromBits(bits.slice(0,length)));
    if(decoded!==null) return {text:decoded,symbolOffset:start,byteCount:size};
  }
  return null;
}

// Goertzel power at one frequency; coefficient is constant throughout each window.
export function tonePower(samples,offset,count,frequency,sampleRate) {
  const w=2*Math.PI*frequency/sampleRate;
  const coefficient=2*Math.cos(w);
  let a=0,b=0;
  const end=Math.min(offset+count,samples.length);
  for(let i=offset;i<end;i++){
    const x=samples[i]+coefficient*a-b;
    b=a;
    a=x;
  }
  return Math.max(0,a*a+b*b-coefficient*a*b);
}

// Offline FSK decoder. All possible symbol phase offsets are tested.
// No microphone data is transmitted or stored on a server.
export function decodeAudio(samples,sampleRate) {
  if (!samples || typeof sampleRate!=='number' || sampleRate<8000 || sampleRate>192000)
    throw new TypeError('Invalid audio samples or sample rate');
  const hop=Math.round(sampleRate*0.015);
  const window=Math.round(sampleRate*0.046);
  const steps=Math.floor((samples.length-window)/hop)+1;
  if(steps<60) return null;
  const labels=new Array(steps);
  const confidence=new Float32Array(steps);
  for(let i=0;i<steps;i++){
    const pos=i*hop;
    const p0=tonePower(samples,pos,window,FREQ_ZERO,sampleRate);
    const p1=tonePower(samples,pos,window,FREQ_ONE,sampleRate);
    labels[i]=p1>p0?'1':'0';
    confidence[i]=Math.abs(p1-p0)/(p1+p0+1e-9);
  }
  const stepsPerBit=Math.round(SYMBOL_SECONDS*sampleRate/hop);
  const startSlots=Math.max(0,Math.floor(steps/stepsPerBit));
  for(let phase=0;phase<stepsPerBit;phase++){
    let stream='';
    let strengths=[];
    for(let k=0;k<startSlots;k++){
      const pos=phase+k*stepsPerBit+Math.floor((stepsPerBit-3)/2);
      if(pos>=steps) break;
      stream+=labels[pos];
      strengths.push(confidence[pos]);
    }
    const decoded=decodeBits(stream);
    if(decoded) {
      const first=decoded.bitOffset;
      const sampleConfidence=strengths.slice(first,first+PREAMBLE.length+48);
      const mean=sampleConfidence.reduce((a,b)=>a+b,0)/Math.max(1,sampleConfidence.length);
      if(mean>0.15)
        return {...decoded,confidence:Number(mean.toFixed(3)),phase};
    }
  }
  return null;
}

// Used exclusively for offline deterministic unit tests; real transmission
// uses Web Audio output scheduling rather than this array generator.
export function synthesizeFSK(text,sampleRate=16000,leadingSilence=0.37) {
  const bits=audioBits(text);
  const initial=Math.round(leadingSilence*sampleRate);
  const spb=Math.round(SYMBOL_SECONDS*sampleRate);
  const audio=new Float32Array(initial+spb*bits.length+Math.round(0.15*sampleRate));
  for(let b=0;b<bits.length;b++){
    const hz=bits[b]==='1'?FREQ_ONE:FREQ_ZERO;
    for(let s=0;s<spb;s++){
      const t=s/sampleRate;
      audio[initial+b*spb+s]=0.6*Math.sin(2*Math.PI*hz*t);
    }
  }
  return audio;
}
