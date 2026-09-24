import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import * as calibratedData from './calibrated-data.mjs';
import {buildingTypes,evidenceFor} from './building-evidence.mjs';

export function createCampus(dataSet=calibratedData){
  const {buildings,roads,lakes,waterways,fields,plazas,metadata,geoToScene}=dataSet;
  const root=new THREE.Group();root.name='Nankai_Jinnan_Calibrated_Rough_Model';root.userData=metadata;
  const colors={ground:'#cbd7a6',base:'#e4ddc6',wall:'#ddcfb2',roof:'#f6ecd3',window:'#8eaaa9',
    curb:'#eee8d7',road:'#b9bbae',water:'#82bfc8',field:'#92af83',track:'#c18f7e',white:'#f7f0da',leaf:'#96b77e',trunk:'#ad9778',...metadata.palette};
  const mats=Object.fromEntries(Object.entries(colors).map(([key,color])=>[key,new THREE.MeshStandardMaterial({color,roughness:.9})]));
  for(const [id,t] of Object.entries(buildingTypes))mats['roof-'+id]=new THREE.MeshStandardMaterial({color:metadata.minimal_buildings?colors.roof:t.color,roughness:.9});
  const clickable=[],groups=[],occupied=[];
  function mesh(geo,key,parent=root){const obj=new THREE.Mesh(geo,mats[key]);obj.castShadow=true;obj.receiveShadow=true;parent.add(obj);return obj;}
  function box(x,z,w,d,h,key,y=0,parent=root){const obj=mesh(new THREE.BoxGeometry(w,h,d),key,parent);obj.position.set(x,y+h/2,z);return obj;}
  function shape(points,holes=[]){const s=new THREE.Shape(points.map(([x,z])=>new THREE.Vector2(x,-z)));
    for(const h of holes)s.holes.push(new THREE.Path(h.map(([x,z])=>new THREE.Vector2(x,-z))));return s;}
  function flat(points,key,y=.16,parent=root){const o=mesh(new THREE.ShapeGeometry(shape(points)),key,parent);o.rotation.x=-Math.PI/2;o.position.y=y;o.castShadow=false;return o;}
  // Thousands of source-pixel surface runs become one mesh, not thousands of draw calls.
  function flatRectangles(rects,key,y){
    if(!rects.length)return;
    const positions=new Float32Array(rects.length*18);let i=0;
    for(const [x0,z0,x1,z1] of rects){
      positions.set([x0,y,z0,x0,y,z1,x1,y,z1,x0,y,z0,x1,y,z1,x1,y,z0],i);i+=18;
    }
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(positions,3));geo.computeVertexNormals();
    const obj=mesh(geo,key);obj.castShadow=false;obj.name='source-plan-'+key;
  }
  function path(points,w,key,y=.20){
    for(let i=1;i<points.length;i++){const [x,z]=points[i-1],[nx,nz]=points[i],len=Math.hypot(nx-x,nz-z);if(len<1e-8)continue;
      const obj=box((x+nx)/2,(z+nz)/2,w,len,.035,key,y);obj.rotation.y=Math.atan2(nx-x,nz-z);obj.castShadow=false;}
    for(const [x,z] of points){const o=mesh(new THREE.CylinderGeometry(w/2,w/2,.04,8),key);o.position.set(x,y+.02,z);o.castShadow=false;}
  }
  function inset(p,t){const c=p.reduce((a,v)=>[a[0]+v[0]/p.length,a[1]+v[1]/p.length],[0,0]);return p.map(v=>v.map((n,i)=>n+(c[i]-n)*t));}
  function rounded(p,cut=.17,steps=4){const out=[];
    for(let i=0;i<p.length;i++){const prev=p[(i+p.length-1)%p.length],cur=p[i],next=p[(i+1)%p.length];
      const a=[cur[0]+(prev[0]-cur[0])*cut,cur[1]+(prev[1]-cur[1])*cut];
      const b=[cur[0]+(next[0]-cur[0])*cut,cur[1]+(next[1]-cur[1])*cut];
      if(!out.length)out.push(a);
      for(let j=1;j<=steps;j++){const t=j/steps,s=1-t;out.push([s*s*a[0]+2*s*t*cur[0]+t*t*b[0],s*s*a[1]+2*s*t*cur[1]+t*t*b[1]]);}
      const following=p[(i+1)%p.length],end=[following[0]+(cur[0]-following[0])*cut,following[1]+(cur[1]-following[1])*cut];
      out.push(end);
    }
    return out;
  }
  function courtGrid(p,kind){
    if(p.length<4)return;
    const at=(u,v)=>{const blend=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
      const top=blend(p[0],p[1],u),bottom=blend(p[3],p[2],u);return blend(top,bottom,v);};
    const line=(a,b)=>path([a,b],.045,'white',.345);
    if(kind==='grid'){
      for(let i=0;i<=3;i++)line(at(i/3,0),at(i/3,1));
      for(let i=0;i<=3;i++)line(at(0,i/3),at(1,i/3));
      for(let x=0;x<3;x++)for(let z=0;z<3;z++){
        line(at(x/3+.06,z/3+.18),at(x/3+.94,z/3+.18));
        line(at(x/3+.06,z/3+.82),at(x/3+.94,z/3+.82));
      }
    }else if(kind==='tennis'){
      for(const u of [.08,.92])line(at(u,.04),at(u,.96));
      for(const v of [.08,.5,.92])line(at(.08,v),at(.92,v));
      line(at(.5,.28),at(.5,.72));
    }else if(kind==='football'){
      line(at(.5,.025),at(.5,.975));
      const size=.12;
      const circle=Array.from({length:24},(_,i)=>at(.5+Math.cos(i*Math.PI/12)*size,.5+Math.sin(i*Math.PI/12)*size));
      path([...circle,circle[0]],.045,'white',.345);
      for(const v of [.18,.82]){
        line(at(.29,v),at(.71,v));line(at(.29,v),at(.29,v+(v<.5?.13:-.13)));
        line(at(.71,v),at(.71,v+(v<.5?.13:-.13)));
      }
    }
  }
  const [groundWidth,groundDepth]=metadata.ground_size||[101,81];
  box(0,0,groundWidth+3,groundDepth+3,1.1,'base',-1.3);box(0,0,groundWidth,groundDepth,.28,dataSet.campusBoundary?'base':'ground',-.23);
  if(dataSet.campusBoundary)flat(dataSet.campusBoundary,'ground',.07);
  if(dataSet.surfaceRects){
    flatRectangles(dataSet.surfaceRects.water,'water',.13);
    flatRectangles(dataSet.surfaceRects.curb,'curb',.19);
    flatRectangles(dataSet.surfaceRects.road,'road',.24);
  }
  for(const l of lakes)flat(l.p,'water',.13).name=l.name;
  for(const r of waterways)path(r.p,r.w,'water',.12);
  // Draw every border first, then every road: crossing paths share a clean
  // junction rather than one route's curb cutting across another route.
  for(const r of roads)path(r.p,r.w+.22,'curb',.19);
  for(const r of roads)path(r.p,r.w,r.material||'road',.24);
  for(const p of plazas)flat(p.p,'curb',.3).name=p.name;
  for(const f of fields){
    const outline=f.track?rounded(f.p):f.p;
    flat(outline,'curb',.25).name=f.name;flat(inset(outline,.07),f.track?'track':'field',.27);
    const inner=inset(outline,f.track?.31:.13);flat(inner,'field',.30);path([...inner,inner[0]],.045,'white',.34);
    if(f.track){
      for(const offset of [.12,.17,.22,.27])path([...inset(outline,offset),inset(outline,offset)[0]],.035,'white',.34);
      courtGrid(inner,'football');
    }else courtGrid(inner,f.kind||'football');
    occupied.push(f.p);
  }
  for(const data of buildings){
    const evidence=data.evidence||evidenceFor(data);
    const group=new THREE.Group();group.name=data.name;root.add(group);
    for(const foot of data.footprints){
      const s=shape(foot.outer,foot.holes),body=mesh(new THREE.ExtrudeGeometry(s,{depth:data.height,bevelEnabled:false,steps:1}), 'wall',group);
      body.rotation.x=-Math.PI/2;body.position.y=.35;
      const roof=mesh(new THREE.ShapeGeometry(s),'roof-'+evidence.type,group);roof.rotation.x=-Math.PI/2;roof.position.y=data.height+.355;
      // Individually separated, simplified window bays give each mass a facade rhythm.
      // Floor count remains a visual shorthand derived from its existing rough height.
      const levels=Math.max(1,Math.min(3,Math.round((data.height-.4)/.65)));
      if(!metadata.minimal_buildings)for(const ring of [foot.outer,...foot.holes])for(let i=0;i<ring.length;i++){
        const a=ring[i],b=ring[(i+1)%ring.length],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);if(len<.15)continue;
        const bays=Math.max(1,Math.min(12,Math.floor(len/.55)));
        for(let bay=0;bay<bays;bay++)for(let floor=0;floor<levels;floor++){
          const t=(bay+.5)/bays,o=mesh(new THREE.BoxGeometry((len/bays)*.66,.18,.035),'window',group);
          o.position.set(a[0]+dx*t,.66+floor*.56,a[1]+dz*t);o.rotation.y=-Math.atan2(dz,dx);
        }
        // Continuous low parapet strips clarify the roof edge on the guide view.
        const rail=box((a[0]+b[0])/2,(a[1]+b[1])/2,len,.075,.13,'roof-'+evidence.type,data.height+.37,group);
        rail.rotation.y=Math.atan2(dx,dz);
      }
      occupied.push(foot.outer);
    }
    const vertices=data.footprints.flatMap(f=>f.outer);
    const anchor=data.anchor||(data.position?geoToScene(data.position):vertices.reduce((a,v)=>[a[0]+v[0]/vertices.length,a[1]+v[1]/vertices.length],[0,0]));
    group.userData={id:data.id,name:data.name,category:data.category,approximate:true,
      anchor:[anchor[0],data.height+1,anchor[1]],aliases:data.aliases,
      source:metadata.source,accuracy:data.accuracy,position:data.position,height_estimated:true,
      ...(data.image_placement?{image_placement:data.image_placement}:{})};
    Object.assign(group.userData,evidence);
    // Merge by material, maintaining independently selectable/exportable buildings.
    const buckets=new Map();
    for(const child of [...group.children]){child.updateMatrix();const geo=child.geometry.clone().applyMatrix4(child.matrix);
      const list=buckets.get(child.material)||[];list.push(geo);buckets.set(child.material,list);group.remove(child);child.geometry.dispose();}
    for(const [material,geos] of buckets){const obj=new THREE.Mesh(mergeGeometries(geos),material);obj.castShadow=true;obj.receiveShadow=true;group.add(obj);clickable.push(obj);for(const g of geos)g.dispose();}
    groups.push(group);
  }
  function inside(x,z,p){let yes=false;for(let i=0,j=p.length-1;i<p.length;j=i++){const [xi,zi]=p[i],[xj,zj]=p[j];if((zi>z)!==(zj>z)&&x<(xj-xi)*(z-zi)/(zj-zi)+xi)yes=!yes;}return yes;}
  function nearPaths(x,z){return [...roads,...waterways].some(({w,p})=>p.slice(1).some(([bx,bz],i)=>{const [ax,az]=p[i],dx=bx-ax,dz=bz-az,den=dx*dx+dz*dz;
    const t=den?Math.max(0,Math.min(1,((x-ax)*dx+(z-az)*dz)/den)):0;return Math.hypot(x-ax-dx*t,z-az-dz*t)<w/2+.4;}));}
  // Sparse illustrative planting only; does not imply satellite-derived tree positions.
  let seed=12023,count=0;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;};
  const foliage=[],trunks=[],crown=new THREE.IcosahedronGeometry(1,1),trunk=new THREE.CylinderGeometry(.06,.09,.65,5),transform=new THREE.Object3D();
  const campus=dataSet.campusBoundary||roads[0]?.p||[];
  for(let i=0;i<2000&&count<(metadata.vegetation_count??350);i++){
    const x=(random()-.5)*(groundWidth-6),z=(random()-.5)*(groundDepth-6);
    if(!inside(x,z,campus)||occupied.some(p=>inside(x,z,p))||lakes.some(l=>inside(x,z,l.p))||nearPaths(x,z))continue;
    const size=.3+random()*.27;
    transform.position.set(x,.55,z);transform.scale.set(1,1,1);transform.updateMatrix();trunks.push(trunk.clone().applyMatrix4(transform.matrix));
    transform.position.set(x,.95,z);transform.scale.set(size,size*1.3,size);transform.updateMatrix();foliage.push(crown.clone().applyMatrix4(transform.matrix));count++;
  }
  if(foliage.length)mesh(mergeGeometries(foliage),'leaf').name='示意绿化（非实景位置）';
  if(trunks.length)mesh(mergeGeometries(trunks),'trunk');
  root.updateMatrixWorld(true);return {root,groups,clickable,treeCount:count};
}
