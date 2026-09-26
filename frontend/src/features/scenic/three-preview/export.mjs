import { readFile,writeFile } from 'node:fs/promises';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
const plan=process.argv.includes('--plan');
const overview=process.argv.includes('--overview');
const {createCampus}=await import(overview?'./overview-model.mjs':plan?'./plan-model.mjs':'./calibrated-model.mjs');

// Node has Blob, while Three's browser exporter also needs this FileReader subset.
globalThis.FileReader=class {
  readAsArrayBuffer(blob){blob.arrayBuffer().then(value=>{this.result=value;this.onloadend?.();});}
  readAsDataURL(blob){blob.arrayBuffer().then(value=>{this.result=`data:${blob.type};base64,${Buffer.from(value).toString('base64')}`;this.onloadend?.();});}
};
let roads=[];
if(overview){
  try{roads=JSON.parse(await readFile(new URL('./scenic-roads.json',import.meta.url),'utf8'));}
  catch(error){if(error.code!=='ENOENT')throw error;}
}
const {root,treeCount,groups}=createCampus(overview?{roads}:undefined);
const binary=await new GLTFExporter().parseAsync(root,{binary:true,onlyVisible:true});
await writeFile(new URL(overview?'./nku-jinnan-position-plan.glb':plan?'./nku-jinnan-guide-plan.glb':'./nku-jinnan-calibrated.glb',import.meta.url),Buffer.from(binary));
console.log(`Exported ${groups.length} building groups, ${treeCount} trees; ${(binary.byteLength/1024/1024).toFixed(2)} MB GLB.`);
