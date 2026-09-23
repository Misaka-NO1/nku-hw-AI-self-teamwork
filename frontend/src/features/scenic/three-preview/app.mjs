import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {orbitAroundPoint} from './pointer-orbit.mjs';
import {createCampus} from './overview-model.mjs';
import {metadata,sceneToPixel} from './overview-data.mjs';
import {buildingTypes} from './building-evidence.mjs';

const $=id=>document.getElementById(id),storeKey='nku-jinnan-model-spots-overview-v1';
const [spotWidth,spotDepth]=metadata.spot_extent||[100,80];
const spotToScene=spot=>[(spot.x_norm-.5)*spotWidth,(spot.y_norm-.5)*spotDepth];
const sceneToSpot=(x,z)=>({x_norm:x/spotWidth+.5,y_norm:z/spotDepth+.5});
document.body.classList.add('position-model');
$('version-badge').textContent='总图对位 · v'+metadata.revision;
$('model-download').href='nku-jinnan-position-plan.glb';
const host=$('canvas-host'),scene=new THREE.Scene();scene.background=new THREE.Color('#eceee1');
const camera=new THREE.OrthographicCamera(-75,75,55,-55,.1,600);
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.setClearColor('#eceee1');host.append(renderer.domElement);
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.8;
scene.add(new THREE.HemisphereLight('#fff9e7','#bdc8aa',1.8));
const sun=new THREE.DirectionalLight('#fff2d9',2.4);sun.position.set(-40,95,-30);sun.castShadow=true;
sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-90,right:90,top:85,bottom:-85,near:1,far:240});
sun.shadow.bias=-.0003;sun.shadow.normalBias=.15;scene.add(sun);
const {root,groups,clickable,treeCount}=createCampus();scene.add(root);
$('building-controls').hidden=true;
for(const [id,t] of Object.entries(buildingTypes)){
  const count=groups.filter(g=>g.userData.type===id).length;if(!count)continue;
  const option=document.createElement('option');option.value=id;option.textContent=t.label+' · '+count+' 组';$('building-type').append(option);
}
let activeType='all';
const stage=new THREE.Mesh(new THREE.PlaneGeometry(1000,1000),new THREE.MeshStandardMaterial({color:'#eceee1',roughness:1}));
stage.rotation.x=-Math.PI/2;stage.position.y=-1.32;stage.receiveShadow=true;scene.add(stage);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
controls.dampingFactor=.085;controls.minZoom=.5;controls.maxZoom=14;controls.maxPolarAngle=Math.PI*.47;
controls.minPolarAngle=.015;controls.screenSpacePanning=true;
const labels=[],markers=new THREE.Group();scene.add(markers);
let spots=[],selected=null,placing=false,pending=null,editingId=null,photoData='',photoUrls=[],photoFiles=[],view='oblique',authoring=false;
function status(message){$('status').textContent=message;}
async function loadMode(){
  try{
    const response=await fetch('/api/scenic/config');
    if(!response.ok)throw new Error('录入状态不可用');
    authoring=(await response.json()).authoring===true;
  }catch{authoring=false;}
  $('add').hidden=!authoring;
  $('data-tools').hidden=!authoring;
  $('scenic-actions').hidden=!authoring;
}
function validate(items){
  if(!Array.isArray(items)||items.length>300)throw new Error('景点列表无效，最多支持 300 个景点。');
  const ids=new Set();
  const safe=items.map(item=>{
    if(!item||typeof item.spot_id!=='string'||item.spot_id.length>100||ids.has(item.spot_id)
      ||typeof item.name!=='string'||!item.name.trim()||item.name.length>80
      ||!Number.isFinite(item.x_norm)||!Number.isFinite(item.y_norm)
      ||item.x_norm<0||item.x_norm>1||item.y_norm<0||item.y_norm>1)throw new Error('景点名称、编号或位置不合法。');
    ids.add(item.spot_id);
    for(const [field,max] of [['description',1000],['flower',80],['season_note',120]])
      if(typeof item[field]!=='string'||item[field].length>max)throw new Error('景点说明格式或长度不合法。');
    const photo_urls=item.photo_urls??[],photo_data_url=item.photo_data_url??'';
    if(!Array.isArray(photo_urls)||photo_urls.length>100||photo_urls.some(url=>typeof url!=='string'||
      !/^\/media\/scenic\/[0-9a-f-]{36}\.(png|jpg|webp)$/.test(url))||
      typeof photo_data_url!=='string'||photo_data_url.length>2900000||
      (photo_data_url&&!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(photo_data_url)))
      throw new Error('照片必须是本地图库中的 PNG、JPEG 或 WebP 图片。');
    return {spot_id:item.spot_id,name:item.name.trim(),description:item.description,flower:item.flower,
      season_note:item.season_note,x_norm:item.x_norm,y_norm:item.y_norm,photo_urls,photo_data_url};
  });
  if(safe.reduce((n,s)=>n+s.photo_urls.length+(s.photo_data_url?1:0),0)>100)throw new Error('图库最多保存 100 张照片。');
  return safe;
}
async function sendSpots(items){
  const response=await fetch('/api/scenic/spots?model='+encodeURIComponent(metadata.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({spots:items})});
  if(!response.ok){const detail=await response.json().catch(()=>({}));throw new Error(detail.error||'景点保存失败');}
}
async function loadSpots(){
  let cached=[];
  try{const raw=localStorage.getItem(storeKey);if(raw)cached=validate(JSON.parse(raw));}
  catch{status('浏览器旧数据读取失败，请检查导出的备份。');}
  try{
    const response=await fetch('/api/scenic/spots?model='+encodeURIComponent(metadata.id));if(!response.ok)throw new Error('景点服务暂不可用');
    const result=await response.json();
    if(result.exists){
      spots=validate(result.spots);
      try{localStorage.setItem(storeKey,JSON.stringify(spots));}catch{ /* Server remains the source of truth. */ }
    }
    else if(authoring&&cached.length){
      spots=[];
      for(const spot of cached){
        const migrated={...spot,photo_urls:[...spot.photo_urls]};
        if(spot.photo_data_url){const blob=await (await fetch(spot.photo_data_url)).blob();
          migrated.photo_urls.push(await uploadPhoto(blob));migrated.photo_data_url='';}
        spots.push(migrated);
      }
      await sendSpots(spots);localStorage.setItem(storeKey,JSON.stringify(spots));
      status('原有景点已迁移到本地项目文件。');
    }
  }catch(error){spots=authoring?cached:[];status(authoring?'景点服务暂不可用，正在显示浏览器缓存：'+error.message:'景点服务暂不可用，请稍后重试。');}
}
async function save(next){
  if(!authoring)throw new Error('公测版只允许浏览景点。');
  const safe=validate(next);
  if(safe.some(s=>s.photo_data_url))throw new Error('旧照片尚未迁移，请刷新页面后重试。');
  await sendSpots(safe);
  try{localStorage.setItem(storeKey,JSON.stringify(safe));}catch{status('景点已保存到项目文件，浏览器缓存写入失败。');}
  spots=safe;refreshMarkers();renderList();
}
await loadMode();
await loadSpots();
// Building geometry is intentionally left unlabelled; the user will add names.
// Internal IDs/names remain available to search, select, and edit the model.
function addLabel(text,position,type,group=null){
  const el=document.createElement('span');el.className='place-label'+(type==='spot'?' spot':'');el.textContent=text;
  $('labels').append(el);labels.push({el,position,type,group});
}
function refreshMarkers(){
  for(const obj of [...markers.children]){markers.remove(obj);obj.traverse(node=>{node.geometry?.dispose();if(node.material)node.material.dispose();});}
  for(let i=labels.length-1;i>=0;i--)if(labels[i].type==='spot'){labels[i].el.remove();labels.splice(i,1);}
  for(const spot of spots){
    const [x,z]=spotToScene(spot);
    const group=new THREE.Group();group.position.set(x,.4,z);group.userData.spotId=spot.spot_id;
    const stem=new THREE.Mesh(new THREE.CylinderGeometry(.1,.1,3.7,8),new THREE.MeshStandardMaterial({color:'#8b627e'}));
    stem.position.y=1.85;group.add(stem);
    const head=new THREE.Mesh(new THREE.SphereGeometry(.8,16,12),new THREE.MeshStandardMaterial({color:'#985f8e'}));
    head.position.y=4.2;head.castShadow=true;group.add(head);
    const centre=new THREE.Mesh(new THREE.SphereGeometry(.23,10,8),new THREE.MeshStandardMaterial({color:'#fff6e5'}));
    centre.position.set(0,4.9,0);group.add(centre);markers.add(group);
    addLabel(spot.name,new THREE.Vector3(x,6,z),'spot');
  }
  $('spot-count').textContent=String(spots.length).padStart(2,'0');
}
function el(tag,text,className){const node=document.createElement(tag);if(text)node.textContent=text;if(className)node.className=className;return node;}
function action(text,handler){const button=el('button',text);button.type='button';button.addEventListener('click',handler);return button;}
function focus(x,z){const delta=new THREE.Vector3(x,0,z).sub(controls.target);camera.position.add(delta);controls.target.set(x,0,z);camera.zoom=2.1;camera.updateProjectionMatrix();controls.update();}
function renderList(){
  const list=$('spot-list');list.replaceChildren();const term=$('search').value.trim().toLowerCase();
  const found=spots.filter(s=>[s.name,s.description,s.flower].some(v=>v.toLowerCase().includes(term)));
  if(!spots.length&&!term&&activeType==='all')list.append(el('p',authoring?'还没有景点，点击上方按钮添加。':'景点资料整理中，敬请期待。','empty-hint'));
  for(const spot of found){const button=action('',()=>selectSpot(spot.spot_id,true));button.className='list-item'+(selected===spot.spot_id?' selected':'');
    button.append(el('strong',spot.name),el('small',[spot.flower,spot.season_note].filter(Boolean).join(' · ')||'未填写分类与时间'));list.append(button);}
  const filtered=groups.filter(g=>activeType==='all'||g.userData.type===activeType);
  $('building-summary').textContent=(activeType==='all'?'当前模型：':buildingTypes[activeType].label+'：')+filtered.length+' 组建筑 / 组团';
  if(term||activeType!=='all'){const matched=filtered.filter(g=>[g.userData.name,g.userData.typeLabel||'',...(g.userData.aliases||[])].some(name=>name.toLowerCase().includes(term)));
    if(matched.length)list.append(el('p','校园建筑 · 布局参考','section-label'));
    for(const group of matched){const b=action('',()=>selectBuilding(group,true));b.className='list-item';b.append(el('strong',group.userData.name),el('small',(group.userData.typeLabel||group.userData.category)+' · '+(group.userData.verification||'布局参考')));list.append(b);}
    if(!found.length&&!matched.length)list.append(el('p','没有找到匹配的地点。','empty'));
  }
}
function selectSpot(id,move=false){
  const spot=spots.find(s=>s.spot_id===id);if(!spot)return;selected=id;renderList();
  if(move)focus(...spotToScene(spot));
  $('detail').hidden=true;
  $('scenic-title').textContent=spot.name;
  $('scenic-flower').textContent=spot.flower||'校园风景';
  $('scenic-description').textContent=spot.description||'这处景色的故事，等待你补充。';
  $('scenic-season').textContent=spot.season_note?'推荐时节 · '+spot.season_note:'推荐时节 · 待补充';
  const photos=[...spot.photo_urls,...(spot.photo_data_url?[spot.photo_data_url]:[])];
  const hero=$('scenic-hero'),thumbs=$('scenic-thumbs');hero.replaceChildren();thumbs.replaceChildren();
  if(!photos.length)hero.append(el('div','实景照片待上传','scenic-placeholder'));
  for(const [index,url] of photos.entries()){
    const thumb=action('',()=>{
      const image=el('img');image.src=url;image.alt=spot.name+'的实景照片 '+(index+1);
      hero.replaceChildren(image);
      for(const b of thumbs.children)b.classList.toggle('active',b===thumb);
    });
    thumb.className='scenic-thumb'+(index===0?' active':'');
    const image=el('img');image.src=url;image.alt='查看第 '+(index+1)+' 张实景照片';thumb.append(image);thumbs.append(thumb);
  }
  if(photos.length){const image=el('img');image.src=photos[0];image.alt=spot.name+'的实景照片';hero.append(image);}
  $('scenic-edit').onclick=()=>{$('scenic-dialog').close();openForm(...spotToScene(spot),spot);};
  $('scenic-delete').onclick=async()=>{
    if(!confirm(`删除“${spot.name}”？`))return;
    try{await save(spots.filter(s=>s.spot_id!==id));selected=null;$('scenic-dialog').close();status('景点已删除。');}
    catch(error){status(error.message);}
  };
  $('scenic-dialog').showModal();
}
$('scenic-close').onclick=()=>$('scenic-dialog').close();
function selectBuilding(group,move=false){
  selected=null;renderList();const {name,category,anchor}=group.userData;const detail=$('detail');detail.hidden=false;
  detail.replaceChildren(el('span',category+' · 建筑体块','eyebrow'),el('h3',name),el('p',metadata.note));
  detail.append(el('p','用途：'+group.userData.typeLabel),el('p',group.userData.verification),el('p',group.userData.note));
  for(const source of group.userData.references||[]){const link=el('a',source.label);link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';const p=el('p');p.append(link);detail.append(p);}
  if(group.userData.position)detail.append(el('p','地图服务标注点（非入口，GCJ-02）：'+group.userData.position.join(', ')));
  if(group.userData.image_placement)detail.append(el('p','原图屋顶中心（像素）：'+group.userData.image_placement.centre.join(', ')));
  if(authoring){const actions=el('div',null,'detail-actions');actions.append(action('在此添加景点',()=>openForm(anchor[0],anchor[2])));detail.append(actions);}
  if(move)focus(anchor[0],anchor[2]);
}
function setPlacing(value){if(value&&!authoring)return;placing=value;$('placing').hidden=!value;$('add').textContent=value?'请在地图上选位置':'＋ 添加景点';renderer.domElement.style.cursor=value?'crosshair':'grab';}
$('add').onclick=()=>setPlacing(!placing);$('cancel-place').onclick=()=>setPlacing(false);
const dialog=$('spot-dialog'),form=$('spot-form');
const previewObjectUrls=[];
function photoPreview(){
  for(const url of previewObjectUrls)URL.revokeObjectURL(url);previewObjectUrls.length=0;
  const preview=$('photo-preview');preview.replaceChildren();
  const count=photoUrls.length+photoFiles.length+(photoData?1:0);
  preview.hidden=!count;if(!count)return;
  preview.append(el('p',`已选 ${count} 张照片，保存时写入本地图片目录。`,'photo-count'));
  function tile(src,label,onRemove){
    const wrap=el('div',null,'photo-draft'),image=el('img');image.src=src;image.alt=label;
    const remove=action('移除',onRemove);wrap.append(image,remove);preview.append(wrap);
  }
  photoUrls.forEach((url,index)=>tile(url,'已保存的实景照片',()=>{photoUrls.splice(index,1);photoPreview();}));
  if(photoData)tile(photoData,'原有实景照片',()=>{photoData='';photoPreview();});
  photoFiles.forEach((file,index)=>{
    const url=URL.createObjectURL(file);previewObjectUrls.push(url);
    tile(url,'新选择的实景照片',()=>{photoFiles.splice(index,1);photoPreview();});
  });
}
async function uploadPhoto(file){
  const bitmap=await createImageBitmap(file);
  const scale=Math.min(1,1920/Math.max(bitmap.width,bitmap.height));
  const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));
  canvas.height=Math.max(1,Math.round(bitmap.height*scale));
  canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.86));
  if(!blob||blob.size>8*1024*1024)throw new Error('照片处理失败，请换一张较小的图片。');
  const response=await fetch('/api/scenic/photos',{method:'POST',headers:{'Content-Type':blob.type},body:blob});
  const result=await response.json().catch(()=>({}));
  if(!response.ok||!result.url)throw new Error(result.error||'照片上传失败');
  return result.url;
}
function openForm(x,z,spot=null){
  if(!authoring)return;
  setPlacing(false);pending={x,z};editingId=spot?.spot_id??null;form.reset();$('form-error').textContent='';
  $('dialog-title').textContent=spot?'编辑这处风景':'添加一处风景';
  const relative=sceneToSpot(x,z);
  $('point-coordinate').textContent=`地图相对位置 · 横向 ${(relative.x_norm*100).toFixed(1)}% / 纵向 ${(relative.y_norm*100).toFixed(1)}%`;
  if(sceneToPixel)$('point-coordinate').textContent+=' · 原图像素 '+sceneToPixel([x,z]).map(Math.round).join(', ');
  for(const key of ['name','description','flower','season_note'])form.elements[key].value=spot?.[key]??'';
  photoData=spot?.photo_data_url??'';photoUrls=[...(spot?.photo_urls||[])];photoFiles=[];
  photoPreview();dialog.showModal();form.elements.name.focus();
}
for(const id of ['cancel-dialog','close-dialog'])$(id).onclick=()=>dialog.close();
dialog.addEventListener('close',()=>{for(const url of previewObjectUrls)URL.revokeObjectURL(url);previewObjectUrls.length=0;});
$('photo-file').onchange=()=>{
  const files=[...$('photo-file').files];$('photo-file').value='';if(!files.length)return;
  if(files.some(file=>!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>12*1024*1024)){
    $('form-error').textContent='请选择不超过 12 MB 的 PNG、JPEG 或 WebP 图片。';return;
  }
  const otherCount=spots.filter(s=>s.spot_id!==editingId).reduce((n,s)=>n+s.photo_urls.length+(s.photo_data_url?1:0),0);
  if(otherCount+photoUrls.length+photoFiles.length+files.length+(photoData?1:0)>100){
    $('form-error').textContent='整个图库最多保存 100 张照片。';return;
  }
  photoFiles.push(...files);$('form-error').textContent='';photoPreview();
};
form.onsubmit=async event=>{
  event.preventDefault();if(!pending)return;
  const saveButton=form.querySelector('button[type=submit]');saveButton.disabled=true;saveButton.textContent='正在保存…';
  try{
    const uploaded=[];
    for(const file of photoFiles)uploaded.push(await uploadPhoto(file));
    const photo_urls=[...photoUrls,...uploaded];
    if(photoData){photo_urls.push(await uploadPhoto(await (await fetch(photoData)).blob()));photoData='';}
    const spot={spot_id:editingId??crypto.randomUUID(),name:form.elements.name.value.trim(),
      description:form.elements.description.value.trim(),flower:form.elements.flower.value.trim(),
      season_note:form.elements.season_note.value.trim(),...sceneToSpot(pending.x,pending.z),photo_urls,photo_data_url:''};
    await save(editingId?spots.map(s=>s.spot_id===editingId?spot:s):[...spots,spot]);
    dialog.close();selectSpot(spot.spot_id);status('景点与照片已保存到本地项目。');
  }catch(error){$('form-error').textContent=error.message;}
  finally{saveButton.disabled=false;saveButton.textContent='保存景点';}
};
const ray=new THREE.Raycaster(),mouse=new THREE.Vector2(),ground=new THREE.Plane(new THREE.Vector3(0,1,0),-.3);
let down=null,moved=false;
let pointerOrbit=null;
// Capture before OrbitControls sees the mouse press, so its fixed-centre
// rotation is inactive for this drag. Touch gestures keep their usual control.
renderer.domElement.addEventListener('pointerdown',event=>{
  if(event.pointerType!=='mouse'||event.button!==0||placing||pointerOrbit)return;
  const rect=renderer.domElement.getBoundingClientRect();
  mouse.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
  ray.setFromCamera(mouse,camera);
  const pivot=ray.ray.intersectPlane(ground,new THREE.Vector3());
  if(!pivot)return;
  pointerOrbit={id:event.pointerId,x:event.clientX,y:event.clientY,pivot,
    rotate:controls.enableRotate,damping:controls.enableDamping};
  controls.enableRotate=false;
  controls.enableDamping=false;
},true);
renderer.domElement.addEventListener('pointermove',event=>{
  if(!pointerOrbit||event.pointerId!==pointerOrbit.id)return;
  const dx=event.clientX-pointerOrbit.x,dy=event.clientY-pointerOrbit.y;
  pointerOrbit.x=event.clientX;pointerOrbit.y=event.clientY;
  orbitAroundPoint(camera,controls.target,pointerOrbit.pivot,dx,dy,
    renderer.domElement.clientHeight,controls.minPolarAngle,controls.maxPolarAngle);
  controls.update();
},true);
function endPointerOrbit(event){
  if(!pointerOrbit||event.pointerId!==pointerOrbit.id)return;
  controls.enableRotate=pointerOrbit.rotate;
  controls.enableDamping=pointerOrbit.damping;
  pointerOrbit=null;
}
renderer.domElement.addEventListener('pointerup',endPointerOrbit,true);
renderer.domElement.addEventListener('pointercancel',endPointerOrbit,true);
renderer.domElement.addEventListener('pointerdown',event=>{if(event.button!==0)return;down={x:event.clientX,y:event.clientY};moved=false;});
renderer.domElement.addEventListener('pointermove',event=>{if(down&&Math.hypot(event.clientX-down.x,event.clientY-down.y)>6)moved=true;});
renderer.domElement.addEventListener('pointercancel',()=>{down=null;});
renderer.domElement.addEventListener('pointerup',event=>{
  if(!down||moved||event.button!==0){down=null;return;}down=null;
  const rect=renderer.domElement.getBoundingClientRect();mouse.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
  ray.setFromCamera(mouse,camera);
  if(placing){const point=ray.ray.intersectPlane(ground,new THREE.Vector3());
    const [w,d]=metadata.ground_size||[100,80];
    if(point&&Math.abs(point.x)<=Math.min(w,spotWidth)/2&&Math.abs(point.z)<=Math.min(d,spotDepth)/2)openForm(point.x,point.z);else status('请在校园底座范围内选择位置。');return;}
  const marker=ray.intersectObjects(markers.children,true)[0];if(marker){let target=marker.object;while(target&&!target.userData.spotId)target=target.parent;if(target)selectSpot(target.userData.spotId);return;}
  const hit=ray.intersectObjects(clickable.filter(o=>o.parent.visible),false)[0];if(hit)selectBuilding(hit.object.parent);
});
function setView(mode){view=mode;controls.target.set(0,0,0);camera.position.set(mode==='top'?0:37,mode==='top'?145:115,mode==='top'?.01:106);camera.zoom=1;camera.lookAt(0,0,0);camera.updateProjectionMatrix();controls.update();$('top').classList.toggle('active',mode==='top');$('oblique').classList.toggle('active',mode==='oblique');}
$('top').onclick=()=>setView('top');$('oblique').onclick=()=>setView('oblique');$('reset').onclick=()=>setView(view);
function zoom(factor){camera.zoom=Math.max(.5,Math.min(14,camera.zoom*factor));camera.updateProjectionMatrix();}
$('zoom-in').onclick=()=>zoom(1.25);$('zoom-out').onclick=()=>zoom(.8);$('search').oninput=renderList;
$('building-type').onchange=()=>{
  activeType=$('building-type').value;
  for(const group of groups)group.visible=activeType==='all'||group.userData.type===activeType;
  selected=null;$('detail').hidden=true;setView(view);renderList();
};
function download(filename,text){const url=URL.createObjectURL(new Blob([text],{type:'application/json'}));const a=el('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-json').onclick=()=>{download('津南景点资料.json',JSON.stringify({format:'nku-scenic-model-draft/v1',model_id:metadata.id,spots},null,2));status('已导出景点信息；照片原文件请同时备份 data/scenic-photos 文件夹。');};
$('import-json').onclick=()=>$('json-file').click();
$('json-file').onchange=async()=>{
  const file=$('json-file').files[0];if(!file)return;
  try{if(file.size>12*1024*1024)throw new Error('导入文件请控制在 12 MB 以内。');
    const data=JSON.parse(await file.text());if(data.format!=='nku-scenic-model-draft/v1'||data.model_id!==metadata.id)throw new Error('文件不属于这一版校园模型。');
    const incoming=validate(data.spots),merged=new Map(spots.map(s=>[s.spot_id,s]));
    if(incoming.some(s=>merged.has(s.spot_id))&&!confirm('导入文件含同编号景点。是否用文件中的版本替换这些景点？'))return;
    for(const s of incoming){
      if(s.photo_data_url){s.photo_urls.push(await uploadPhoto(await (await fetch(s.photo_data_url)).blob()));s.photo_data_url='';}
      merged.set(s.spot_id,s);
    }
    await save([...merged.values()]);selected=null;$('detail').hidden=true;status(`已导入 ${incoming.length} 个景点。图片地址需与本地图库配套使用。`);
  }catch(error){status('导入失败：'+error.message);}finally{$('json-file').value='';}
};
document.addEventListener('keydown',e=>{if(e.key==='Escape')setPlacing(false);});
function resize(){const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);const span=Math.max(128,160/(w/h));
  camera.left=-span*w/h/2;camera.right=span*w/h/2;camera.top=span/2;camera.bottom=-span/2;camera.updateProjectionMatrix();}
new ResizeObserver(resize).observe(host);resize();setView('top');refreshMarkers();renderList();
$('model-stats').textContent=`${groups.length} 个建筑轮廓 · 道路与建筑同图对位`;
const projected=new THREE.Vector3();
renderer.setAnimationLoop(()=>{
  controls.update();renderer.render(scene,camera);
  const occupiedLabels=[];
  for(const item of [...labels].sort((a,b)=>(a.type==='spot'?-1:1)-(b.type==='spot'?-1:1))){
    projected.copy(item.position).project(camera);const x=(projected.x*.5+.5)*host.clientWidth,y=(-projected.y*.5+.5)*host.clientHeight;
    let visible=$('show-labels').checked&&item.group?.visible!==false&&Math.abs(projected.x)<.98&&Math.abs(projected.y)<.93&&Math.abs(projected.z)<=1;
    if(visible&&item.type==='building'&&occupiedLabels.some(([px,py])=>Math.abs(px-x)<95&&Math.abs(py-y)<24))visible=false;
    item.el.hidden=!visible;if(visible){item.el.style.left=x+'px';item.el.style.top=y+'px';occupiedLabels.push([x,y]);}
  }
  $('north-arrow').style.transform=`rotate(${controls.getAzimuthalAngle()*180/Math.PI}deg)`;
});
