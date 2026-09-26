import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeRoadSurfaces} from './road-surface.mjs';
import {createCampus,updateRoads} from './overview-model.mjs';

const source={image_size:[100,100],image_origin:[50,50],units_per_pixel:1,
  spot_extent:[100,100],road_rects:[],road_edge_rects:[]};
const horizontal={kind:'road',points:[[.2,.5],[.8,.5]]};
const vertical={kind:'road',points:[[.5,.2],[.5,.8]]};
const area=rects=>rects.reduce((sum,[x0,y0,x1,y1])=>sum+(x1-x0)*(y1-y0),0);
const contains=(rects,x,y)=>rects.some(([x0,y0,x1,y1])=>x>=x0&&x<x1&&y>=y0&&y<y1);

test('two-point roads keep a straight centre and fixed width without a fitting offset',()=>{
  const original=JSON.stringify(horizontal);
  const result=mergeRoadSurfaces(source,[horizontal]);
  let expected;
  for(let x=25;x<=75;x++){
    const ys=Array.from({length:100},(_,y)=>y).filter(y=>contains(result.road,x,y));
    expected??=ys;assert.deepEqual(ys,expected);assert.ok(ys.length<=10);
  }
  assert.equal(JSON.stringify(horizontal),original);
});

test('crossings and duplicate strokes are a union, not stacked surfaces or extra caps',()=>{
  const one=mergeRoadSurfaces(source,[horizontal]);
  assert.deepEqual(mergeRoadSurfaces(source,[horizontal,horizontal]),one);
  const crossing=mergeRoadSurfaces(source,[horizontal,vertical]);
  assert.ok(area(crossing.road)<2*area(one.road));
  for(let y=46;y<54;y++)for(let x=46;x<54;x++)assert.ok(contains(crossing.road,x,y));
});

test('old and new roads reuse the exact same mesh, material and elevation',()=>{
  const {root}=createCampus();
  const road=root.getObjectByName('source-plan-road'),curb=root.getObjectByName('source-plan-curb');
  const roadMaterial=road.material,curbMaterial=curb.material,oldGeometry=road.geometry;
  updateRoads(root,[horizontal]);
  assert.equal(root.getObjectByName('source-plan-road'),road);
  assert.equal(road.material,roadMaterial);assert.equal(curb.material,curbMaterial);
  assert.notEqual(road.geometry,oldGeometry);
  for(const [mesh,height] of [[road,.24],[curb,.19]]){
    const positions=mesh.geometry.attributes.position;
    for(let i=0;i<positions.count;i++)assert.ok(Math.abs(positions.getY(i)-height)<1e-6);
  }
});
