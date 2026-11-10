#!/usr/bin/env node
// The Worker is deployed as a small API module and fetches public UI assets
// from GitHub Pages. Secret values are managed only in Cloudflare bindings.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const source=readFileSync(resolve(root,'src/index.mjs'),'utf8');
const html=readFileSync(resolve(root,'src/dashboard.html'),'utf8');
const js=readFileSync(resolve(root,'src/dashboard.js'),'utf8');
if(!html.includes('src="./app.js"'))throw Error('The UI must load same-origin app.js');
if(!source.includes('WEB_ROOT'))throw Error('Worker must serve the frontend');
if(html.length>35000||js.length>35000)throw Error('Static assets too big');
const target=resolve(root,'dist/worker.mjs');
mkdirSync(dirname(target),{recursive:true});
writeFileSync(target,source);
console.log('Prepared Cloudflare Worker source without secrets:',target,'bytes:',Buffer.byteLength(source));
