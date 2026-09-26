import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';

const root=new URL('.',import.meta.url);
const read=async(relative)=>JSON.parse(await readFile(new URL(relative,root),'utf8'));

test('published map keeps its 36 completed road routes',async()=>{
  const routes=await read('./scenic-roads.json');
  assert.equal(routes.length,36);
  assert.ok(routes.every(route=>Array.isArray(route.points)&&route.points.length>=2));
});

test('all 34 spots and 91 referenced photos are in the public asset package',async()=>{
  const spots=await read('./data/scenic-spots.json');
  const catalog=await read('../../../../../knowledge/scenic/catalog.jinnan.json');
  assert.equal(spots.length,34);
  assert.equal(catalog.spots.length,spots.length);
  assert.equal(catalog.schema_version,'1.0.0');
  const urls=spots.flatMap(spot=>spot.photo_urls);
  assert.equal(urls.length,91);
  assert.equal(new Set(urls).size,91);
  for(const spot of spots){
    const converted=catalog.spots.find(item=>item.spot_id===spot.spot_id);
    assert.ok(converted,spot.name);
    assert.equal(converted.photos.length,spot.photo_urls.length);
    for(const [index,url] of spot.photo_urls.entries()){
      const file=path.basename(url);
      assert.match(file,/^[0-9a-f-]{36}\.webp$/);
      assert.equal(converted.photos[index].asset_path,'assets/scenic/'+file);
      const asset=new URL(`../../../../public/assets/scenic/${file}`,root);
      assert.ok((await stat(asset)).size>0);
    }
  }
});
