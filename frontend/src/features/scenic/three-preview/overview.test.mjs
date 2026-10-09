import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildings,metadata,surfaceRects} from './overview-data.mjs';
import {createCampus} from './overview-model.mjs';

test('published overview keeps 46 positioned building groups and finite surfaces',()=>{
  assert.equal(metadata.id,'nku-jinnan-overview-pixels-v1');
  assert.equal(buildings.length,46);
  assert.equal(new Set(buildings.map(item=>item.id)).size,46);
  for(const building of buildings){
    assert.ok(building.anchor.every(Number.isFinite));
    assert.ok(building.footprints.length>0);
  }
  for(const rects of Object.values(surfaceRects))
    for(const rect of rects)assert.ok(rect.every(Number.isFinite));
  const {groups,clickable}=createCampus();
  assert.equal(groups.length,46);
  assert.ok(clickable.length>=46);
  assert.ok(clickable.every(mesh=>groups.includes(mesh.parent)));
});

test('downloadable current model is present',async()=>{
  const bytes=await readFile(new URL('./nku-jinnan-position-plan.glb',import.meta.url));
  assert.equal(bytes.toString('ascii',0,4),'glTF');
  assert.ok(bytes.length>1_000_000);
});
