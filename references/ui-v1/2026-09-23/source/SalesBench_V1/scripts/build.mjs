import {readFile,writeFile,mkdir} from 'node:fs/promises';
const read=file=>readFile(new URL('../'+file,import.meta.url),'utf8');
let html=await read('index.html');
let core=await read('src/core.js');
const app=await read('src/app.js');
for(const name of ['cup','headphones','tote']){const bytes=await readFile(new URL('../assets/'+name+'.webp',import.meta.url));core=core.replaceAll('assets/'+name+'.webp','data:image/webp;base64,'+bytes.toString('base64'));}
html=html.replace('<link rel="stylesheet" href="src/styles.css">',`<style>${await read('src/styles.css')}</style>`).replace('<script src="src/core.js"></script>',()=>`<script>${core}</script>`).replace('<script src="src/app.js"></script>',()=>`<script>${app}</script>`);
await mkdir(new URL('../dist/',import.meta.url),{recursive:true});
await writeFile(new URL('../dist/SalesBench.html',import.meta.url),html);
console.log('Built dist/SalesBench.html ('+(Buffer.byteLength(html)/1024/1024).toFixed(2)+' MiB); no external dependencies.');
