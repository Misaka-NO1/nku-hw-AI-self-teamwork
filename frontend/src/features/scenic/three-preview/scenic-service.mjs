import {randomUUID} from 'node:crypto';
import {mkdir,readFile,rename,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('.',import.meta.url));
const dataDir=path.join(root,'data');
const photoDir=path.join(dataDir,'scenic-photos');
const spotFiles=new Map([
  ['nku-jinnan-overview-pixels-v1','scenic-spots.json']
]);
const photoName=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|webp)$/;

function reply(res,status,body){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}).end(JSON.stringify(body));}
async function body(req,maxBytes){
  const chunks=[];let size=0;
  for await(const chunk of req){size+=chunk.length;if(size>maxBytes)throw Object.assign(new Error('文件过大'),{status:413});chunks.push(chunk);}
  return Buffer.concat(chunks);
}
function imageType(bytes){
  if(bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))return ['png','image/png'];
  if(bytes[0]===255&&bytes[1]===216&&bytes[2]===255)return ['jpg','image/jpeg'];
  if(bytes.toString('ascii',0,4)==='RIFF'&&bytes.toString('ascii',8,12)==='WEBP')return ['webp','image/webp'];
  return null;
}
function validPhoto(url){return typeof url==='string'&&url.length<100&&photoName.test(url.replace(/^\/media\/scenic\//,''))&&url.startsWith('/media/scenic/');}
function validSpot(spot){
  return spot&&typeof spot==='object'&&typeof spot.spot_id==='string'&&spot.spot_id.length<100&&
    typeof spot.name==='string'&&spot.name.trim().length>0&&spot.name.length<=80&&
    ['description','flower','season_note'].every(k=>typeof spot[k]==='string'&&spot[k].length<=({description:1000,flower:80,season_note:120}[k]))&&
    Number.isFinite(spot.x_norm)&&spot.x_norm>=0&&spot.x_norm<=1&&
    Number.isFinite(spot.y_norm)&&spot.y_norm>=0&&spot.y_norm<=1&&
    Array.isArray(spot.photo_urls)&&spot.photo_urls.length<=100&&spot.photo_urls.every(validPhoto)&&
    typeof spot.photo_data_url==='string'&&spot.photo_data_url.length===0;
}
export async function handleScenic(req,res,url,{authoring=false}={}){
  if(url.pathname.startsWith('/media/scenic/')){
    const name=url.pathname.slice('/media/scenic/'.length);
    if(req.method!=='GET'||!photoName.test(name)){reply(res,404,{error:'找不到图片'});return true;}
    try{const file=path.join(photoDir,name),bytes=await readFile(file),kind=imageType(bytes);
      if(!kind){reply(res,404,{error:'找不到图片'});return true;}
      res.writeHead(200,{'Content-Type':kind[1],'Content-Length':bytes.length,'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff'}).end(bytes);
    }catch{reply(res,404,{error:'找不到图片'});}return true;
  }
  if(!url.pathname.startsWith('/api/scenic/'))return false;
  try{
    if(url.pathname==='/api/scenic/config'&&req.method==='GET'){
      reply(res,200,{authoring});return true;
    }
    if(req.method!=='GET'&&!authoring)
      throw Object.assign(new Error('公测版只允许浏览景点'),{status:403});
    const model=url.searchParams.get('model')||'nku-jinnan-overview-pixels-v1';
    const spotName=spotFiles.get(model);
    if(!spotName)throw Object.assign(new Error('未知模型版本'),{status:400});
    const spotFile=path.join(dataDir,spotName);
    if(req.method!=='GET'&&req.headers.origin&&new URL(req.headers.origin).host!==req.headers.host)
      throw Object.assign(new Error('来源不符'),{status:403});
    if(url.pathname==='/api/scenic/photos'&&req.method==='POST'){
      const bytes=await body(req,8*1024*1024),kind=imageType(bytes);
      if(!kind)throw Object.assign(new Error('仅支持 PNG、JPEG 和 WebP 图片'),{status:415});
      await mkdir(photoDir,{recursive:true});const name=randomUUID()+'.'+kind[0];
      await writeFile(path.join(photoDir,name),bytes,{flag:'wx'});
      reply(res,201,{url:'/media/scenic/'+name});return true;
    }
    if(url.pathname==='/api/scenic/spots'&&req.method==='GET'){
      try{const spots=JSON.parse(await readFile(spotFile,'utf8'));reply(res,200,{exists:true,spots});}
      catch(error){if(error.code==='ENOENT')reply(res,200,{exists:false,spots:[]});else throw error;}
      return true;
    }
    if(url.pathname==='/api/scenic/spots'&&req.method==='PUT'){
      const submitted=JSON.parse((await body(req,1024*1024)).toString('utf8'));
      const spots=submitted?.spots;
      if(!Array.isArray(spots)||spots.length>300||!spots.every(validSpot)||
          new Set(spots.map(s=>s.spot_id)).size!==spots.length||
          spots.reduce((n,s)=>n+s.photo_urls.length,0)>100)
        throw Object.assign(new Error('景点数据无效，最多支持 100 张照片'),{status:400});
      await mkdir(dataDir,{recursive:true});const temp=spotFile+'.'+randomUUID()+'.tmp';
      await writeFile(temp,JSON.stringify(spots,null,2),'utf8');await rename(temp,spotFile);
      reply(res,200,{saved:spots.length});return true;
    }
    reply(res,405,{error:'不支持的请求'});
  }catch(error){reply(res,error.status||500,{error:error.status?error.message:'保存失败'});}
  return true;
}
