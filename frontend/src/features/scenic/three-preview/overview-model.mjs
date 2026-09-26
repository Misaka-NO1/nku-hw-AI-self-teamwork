import * as data from './overview-data.mjs';
import * as THREE from 'three';
import {createCampus as renderCampus} from './calibrated-model.mjs';
import {mergeRoadSurfaces,surfacePositions} from './road-surface.mjs';

export function updateRoads(root,routes){
  const merged=mergeRoadSurfaces(data.roadSurfaceSource,routes);
  for(const [key,y] of [['curb',.19],['road',.24]]){
    const mesh=root.getObjectByName('source-plan-'+key);
    if(!mesh)continue;
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.BufferAttribute(surfacePositions(merged[key],y,data.roadSurfaceSource),3));
    geometry.computeVertexNormals();geometry.computeBoundingSphere();
    mesh.geometry.dispose();mesh.geometry=geometry;
  }
}

export function createCampus({roads=[]}={}){
  const campus=renderCampus(data);
  if(roads.length)updateRoads(campus.root,roads);
  return campus;
}
