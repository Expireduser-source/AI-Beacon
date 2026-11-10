#!/usr/bin/env node
// Embed the static mobile UI into the standalone Cloudflare Worker module.
// Secret bindings are deployed separately; no credentials are read here.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const src=readFileSync(resolve(root,'src/index.mjs'),'utf8');
const html=readFileSync(resolve(root,'src/dashboard.html'),'utf8');
const js=readFileSync(resolve(root,'src/dashboard.js'),'utf8');
const htmlTag="const HTML = '';";
const jsTag="const APP_JS = '';";
if(!src.includes(htmlTag)||!src.includes(jsTag))throw Error('Embedded asset targets missing');
const generated=src.replace(htmlTag,'const HTML = '+JSON.stringify(html)+';')
  .replace(jsTag,'const APP_JS = '+JSON.stringify(js)+';');
const out=resolve(root,'dist/worker.mjs');
mkdirSync(dirname(out),{recursive:true});
writeFileSync(out,generated);
console.log('Built standalone Cloudflare Worker:',out,'bytes:',Buffer.byteLength(generated));
