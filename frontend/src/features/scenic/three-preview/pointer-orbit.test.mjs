import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {orbitAroundPoint} from './pointer-orbit.mjs';

function setup(position){
  const camera=new THREE.OrthographicCamera(-75,75,55,-55,.1,600);
  const target=new THREE.Vector3();camera.position.set(...position);camera.lookAt(target);
  camera.updateProjectionMatrix();camera.updateMatrixWorld();return {camera,target};
}

test('the pointed ground location stays at the same screen pixel while rotating',()=>{
  for(const position of [[37,115,106],[0,145,.01]]){
    const {camera,target}=setup(position),pivot=new THREE.Vector3(24,.3,-18);
    const before=pivot.clone().project(camera);
    orbitAroundPoint(camera,target,pivot,82,-34,620,.015,Math.PI*.47);
    const after=pivot.clone().project(camera);
    assert.ok(before.distanceTo(after)<1e-9,`pivot moved ${before.distanceTo(after)}`);
    assert.ok(camera.position.distanceTo(new THREE.Vector3(...position))>0.01);
  }
});

test('vertical dragging respects the polar limits',()=>{
  const {camera,target}=setup([37,115,106]),pivot=new THREE.Vector3(12,.3,8);
  orbitAroundPoint(camera,target,pivot,0,-10000,620,.015,Math.PI*.47);
  let offset=camera.position.clone().sub(target);
  assert.ok(Math.acos(offset.y/offset.length())<=Math.PI*.47+1e-9);
  orbitAroundPoint(camera,target,pivot,0,10000,620,.015,Math.PI*.47);
  offset=camera.position.clone().sub(target);
  assert.ok(Math.acos(offset.y/offset.length())>=.015-1e-9);
});
