import {createServer} from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {handleScenic} from './scenic-service.mjs';
const root=fileURLToPath(new URL('.',import.meta.url));
const types={'.html':'text/html; charset=utf-8','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.json':'application/json','.glb':'model/gltf-binary'};
const scenicAuthoring=process.env.SCENIC_AUTHORING==='1';
const port=Number(process.env.PORT||5178);
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid preview port');
const allowedHosts=new Set([`127.0.0.1:${port}`,`localhost:${port}`]);
createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    if(!allowedHosts.has(req.headers.host||'')){res.writeHead(403).end();return;}
    if(await handleScenic(req,res,url,{authoring:scenicAuthoring}))return;
    const pathname=decodeURIComponent(url.pathname).replaceAll('\\','/');
    const segments=pathname.split('/').filter(Boolean);
    if(segments.some(segment=>segment.startsWith('.')||segment==='..')||
        segments[0]?.toLowerCase()==='data'||
        ['serve.mjs','scenic-service.mjs'].includes(segments.at(-1))){res.writeHead(404).end();return;}
    const file=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
    const relative=path.relative(root,file);
    if(relative.startsWith('..')||path.isAbsolute(relative)||!(await stat(file)).isFile()){res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});
    res.end(await readFile(file));
  }catch{res.writeHead(404).end('Not found');}
}).listen(port,'127.0.0.1',()=>console.log(`Campus model: http://127.0.0.1:${port}`));
