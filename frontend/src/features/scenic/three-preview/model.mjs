import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { buildings, roads, lakes, metadata } from './campus-data.mjs';

export function createCampus() {
  const root=new THREE.Group(); root.name='Nankai_Jinnan_Reference_Model'; root.userData=metadata;
  const mats={};
  for(const [key,color] of Object.entries({ground:'#c6d496',base:'#e4ddc6',stone:'#ede6d0',wall:'#dec9a2',
    roof:'#f3e4bf',trim:'#bfa581',window:'#769695',road:'#b2b7a5',curb:'#f3efda',water:'#7cbac4',
    field:'#88aa72',track:'#c48c76',white:'#f0ecce',trunk:'#ae9571',leaf:'#8eb77a',leaf2:'#a6c484',
    leaf3:'#6a9c76',pink:'#d5a3ae',gold:'#c0a75d'})) {
    mats[key]=new THREE.MeshStandardMaterial({color,roughness:key==='water'?.48:.9,metalness:0});
  }
  const occupied=[];
  function mesh(geo,key,parent=root,name=''){
    const obj=new THREE.Mesh(geo,mats[key]); obj.name=name; obj.castShadow=true; obj.receiveShadow=true;
    parent.add(obj); return obj;
  }
  function box(x,z,w,d,h,key,y=0,parent=root,name='') {
    const obj=mesh(new THREE.BoxGeometry(w,h,d),key,parent,name); obj.position.set(x,y+h/2,z); return obj;
  }
  function polygon(points,key,y,parent=root,name=''){
    const shape=new THREE.Shape(points.map(([x,z])=>new THREE.Vector2(x,-z)));
    const obj=mesh(new THREE.ShapeGeometry(shape),key,parent,name); obj.rotation.x=-Math.PI/2; obj.position.y=y;
    obj.castShadow=false; return obj;
  }
  function path(points,w,key,y=.1,parent=root){
    for(let i=1;i<points.length;i++){
      const [x,z]=points[i-1], [nx,nz]=points[i]; const len=Math.hypot(nx-x,nz-z);
      const obj=box((x+nx)/2,(z+nz)/2,w,len,.06,key,y,parent);
      obj.rotation.y=Math.atan2(nx-x,nz-z);
    }
    for(const [x,z] of points){ const obj=mesh(new THREE.CylinderGeometry(w/2,w/2,.065,10),key,parent);
      obj.position.set(x,y+.03,z); obj.castShadow=false; }
  }
  function disk(x,z,r,key,y=.15,parent=root,sx=1,sz=1){
    const obj=mesh(new THREE.CylinderGeometry(r,r,.08,64),key,parent); obj.position.set(x,y,z);obj.scale.set(sx,1,sz);
    return obj;
  }
  box(0,0,104,84,1.1,'base',-1.3,root,'模型底座');
  box(0,0,101,81,.28,'ground',-.23,root,'校园地面');
  path([[-48,-39],[48,-39],[48,39],[-48,39],[-48,-39]],2.4,'water',.07);
  path([[-46.5,-37.5],[46.5,-37.5],[46.5,37.5],[-46.5,37.5],[-46.5,-37.5]],.35,'stone',.12);
  for(const lake of lakes) polygon(lake.p,'water',.14,root,lake.name);
  for(const road of roads){path(road.p,road.w+.65,'curb',.13);path(road.p,road.w,'road',.2);}
  // Central south entry and its circular plaza.
  disk(1,35,4,'stone',.27);disk(1,35,2.7,'ground',.34);disk(1,35,.9,'water',.42);
  box(1,38,4.8,3.9,.15,'stone',.27,root,'南门桥');
  for(const x of [-1,3]) box(x,38,.65,.65,2.8,'wall',.4);
  box(1,38,5.6,.85,.65,'roof',3.1,root,'南门示意');
  box(-48,-5,5,3,.16,'stone',.25,root,'西门桥');box(-6,-39,3.2,5,.16,'stone',.25,root,'北门桥');
  // Library forecourt and monument as simplified masses.
  box(0,24,13,3,.12,'stone',.2);box(0,25.5,1.1,1.1,.8,'trim',.25);box(0,25.5,.35,.35,1.2,'gold',1.05);

  function sports(x,z,w,d,track=false){
    box(x,z,w+.8,d+.8,.12,'curb',.19);
    if(track){disk(x,z,1,'track',.34,root,w/2,d/2);disk(x,z,1,'field',.42,root,w*.36,d*.4);}
    else box(x,z,w,d,.15,'field',.29);
    const fw=w*.65,fd=d*.64;
    path([[x-fw/2,z-fd/2],[x+fw/2,z-fd/2],[x+fw/2,z+fd/2],[x-fw/2,z+fd/2],[x-fw/2,z-fd/2]],.075,'white',.51);
    path([[x-fw/2,z],[x+fw/2,z]],.075,'white',.51);
    const ring=new THREE.Mesh(new THREE.RingGeometry(.85,.91,32),mats.white);
    ring.rotation.x=-Math.PI/2;ring.position.set(x,.59,z);root.add(ring);
    occupied.push([x,z,w+2,d+2]);
  }
  sports(10,-27,9,14,true);sports(24,22,9,11);sports(24,33,9,8);
  sports(-41,-27,5,9);sports(-40,20,4,7);
  for(let i=0;i<3;i++)sports(-4+i*3,-32,2.2,3.5);

  const clickable=[];
  function building([id,name,x,z,w,d,h,type,category]) {
    const group=new THREE.Group();group.name=name;group.userData={id,name,category,approximate:true};root.add(group);
    occupied.push([x,z,w+1.6,d+1.6]);
    box(x,z,w+.6,d+.6,.16,'stone',.25,group);
    function block(bx,bz,bw,bd,bh){
      box(bx,bz,bw,bd,bh,'wall',.4,group);
      box(bx,bz,bw+.3,bd+.3,.22,'roof',bh+.4,group);
      box(bx,bz,bw*.84,bd*.78,.16,'stone',bh+.62,group);
      // Shallow ribbons suggest windows without pretending to reconstruct facades.
      for(let floor=.9;floor<bh;floor+=.66){
        box(bx,bz-bd/2-.018,bw*.86,.035,.24,'window',floor,group);
        box(bx,bz+bd/2+.018,bw*.86,.035,.24,'window',floor,group);
        box(bx-bw/2-.018,bz,.035,bd*.7,.24,'window',floor,group);
        box(bx+bw/2+.018,bz,.035,bd*.7,.24,'window',floor,group);
      }
    }
    if(type==='court'){
      const t=Math.min(w,d)*.26;
      block(x,z-d/2+t/2,w,t,h);block(x,z+d/2-t/2,w,t,h);
      block(x-w/2+t/2,z,t,d-2*t,h);block(x+w/2-t/2,z,t,d-2*t,h);
      box(x,z,w-2*t,d-2*t,.08,'ground',.42,group);
    } else if(type==='library'){
      block(x,z,w,d,h);block(x,z,w*.33,d*1.14,h+.8);
      for(let i=0;i<7;i++)box(x-2.4+i*.8,z+d/2+.4,.28,.5,2,'roof',.4,group);
      box(x,z+d/2+1,w*.54,1,.2,'stone',.3,group);
    }else block(x,z,w,d,h);
    // Merge per material per building: keeps each building selectable and Blender-editable.
    const buckets=new Map();
    for(const child of [...group.children]){
      child.updateMatrix();const geo=child.geometry.clone().applyMatrix4(child.matrix);
      const entries=buckets.get(child.material)||[];entries.push(geo);buckets.set(child.material,entries);group.remove(child);
    }
    for(const [material,geos] of buckets){const obj=new THREE.Mesh(mergeGeometries(geos),material);
      obj.castShadow=true;obj.receiveShadow=true;group.add(obj);clickable.push(obj);}
    group.userData.anchor=[x,h+1,z];
    return group;
  }
  const groups=buildings.map(building);
  // Deterministic vegetation, avoiding buildings, roads, playing fields and lake interiors.
  let seed=39017;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
  function inside(x,z,poly){let result=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){
    const [xi,zi]=poly[i],[xj,zj]=poly[j];if((zi>z)!==(zj>z)&&x<(xj-xi)*(z-zi)/(zj-zi)+xi)result=!result;
  }return result;}
  function nearRoad(x,z){return roads.some(({w,p})=>p.slice(1).some(([bx,bz],i)=>{
    const [ax,az]=p[i],dx=bx-ax,dz=bz-az,t=Math.max(0,Math.min(1,((x-ax)*dx+(z-az)*dz)/(dx*dx+dz*dz)));
    return Math.hypot(x-ax-t*dx,z-az-t*dz)<w/2+.8;
  }));}
  const foliage={trunk:[],leaf:[],leaf2:[],leaf3:[]};let count=0;
  const crownGeo=new THREE.IcosahedronGeometry(1,1),trunkGeo=new THREE.CylinderGeometry(.09,.12,.8,5);
  const transform=new THREE.Object3D();
  for(let i=0;i<2600 && count<650;i++){
    const x=random()*90-45,z=random()*72-36;
    if(occupied.some(([bx,bz,w,d])=>Math.abs(x-bx)<w/2&&Math.abs(z-bz)<d/2)
      ||lakes.some(l=>inside(x,z,l.p))||nearRoad(x,z)||Math.hypot(x-1,z-35)<4)continue;
    const size=.5+random()*.55;
    transform.position.set(x,.8,z);transform.scale.set(1,1,1);transform.rotation.set(0,0,0);transform.updateMatrix();
    foliage.trunk.push(trunkGeo.clone().applyMatrix4(transform.matrix));
    transform.position.set(x,1.25+size*.3,z);transform.scale.set(size,size*1.25,size);transform.rotation.y=random()*6;transform.updateMatrix();
    foliage[['leaf','leaf2','leaf3'][Math.floor(random()*3)]].push(crownGeo.clone().applyMatrix4(transform.matrix));count++;
  }
  const treeGroup=new THREE.Group();treeGroup.name='示意绿化';root.add(treeGroup);
  for(const [key,geos] of Object.entries(foliage))if(geos.length)mesh(mergeGeometries(geos),key,treeGroup);
  root.updateMatrixWorld(true);
  return {root,clickable,groups,treeCount:count};
}
