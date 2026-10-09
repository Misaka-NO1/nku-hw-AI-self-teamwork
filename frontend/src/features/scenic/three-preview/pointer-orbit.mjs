import * as THREE from 'three';

const worldUp=new THREE.Vector3(0,1,0);

// Rotate the camera and its look-at target together around a map point. Moving
// both keeps that point at the same screen pixel throughout the drag.
export function orbitAroundPoint(camera,target,pivot,dx,dy,viewportHeight,minPolar,maxPolar){
  const offset=camera.position.clone().sub(target);
  const polar=Math.acos(THREE.MathUtils.clamp(offset.y/offset.length(),-1,1));
  const yaw=-2*Math.PI*dx/viewportHeight;
  const pitch=THREE.MathUtils.clamp(-2*Math.PI*dy/viewportHeight,minPolar-polar,maxPolar-polar);
  if(!yaw&&!pitch)return;

  camera.updateMatrixWorld();
  const yawRotation=new THREE.Quaternion().setFromAxisAngle(worldUp,yaw);
  const right=new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld,0).applyQuaternion(yawRotation).normalize();
  const pitchRotation=new THREE.Quaternion().setFromAxisAngle(right,pitch);
  for(const point of [camera.position,target]){
    point.sub(pivot).applyQuaternion(yawRotation).applyQuaternion(pitchRotation).add(pivot);
  }
  camera.lookAt(target);
  camera.updateMatrixWorld();
}
