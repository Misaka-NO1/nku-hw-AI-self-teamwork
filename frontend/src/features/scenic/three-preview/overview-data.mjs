// All surfaces below use the SAME pixels of the supplied 2025 plan.
// Roof positions are extracted from that image; no generic building envelopes
// or geographic POIs are used to move or enlarge the roofs.
const url=new URL('./overview-traces.json',import.meta.url);
const trace=typeof window==='undefined'
  ? JSON.parse(await (await import('node:fs/promises')).readFile(url,'utf8'))
  : await (await fetch(url)).json();
export const metadata={
  id:'nku-jinnan-overview-pixels-v1',revision:'0.8-restored',title:'南开大学 · 津南校区',
  coordinate_system:'2025-overview-image-pixels',status:'source-plan-traced',
  source:'用户提供的南开大学津南校区2025年地图（公共篇），1440 × 1062 像素',
  note:'建筑与道路按同一张2025总图对位。建筑为简化体块，名称由你添加；原图遮挡的小建筑可能缺失。',
  reference_image:'./references/campus-overview-2025.jpg',image_size:trace.image_size,
  image_origin:[720,531],units_per_pixel:.1,ground_size:[148,110],spot_extent:[148,110],
  guide_crop:{left:0,top:0,width:1440,height:1062},vegetation_count:0,
  palette:{ground:'#afc594',base:'#e5e4d9',wall:'#b9b09b',roof:'#a89d88',window:'#a3ada3',
    road:'#fbfcf5',curb:'#94a582',water:'#78b8d1',field:'#86aa7b',track:'#c88f8b'},
  minimal_buildings:true,validation:trace.validation,
};
export const pixelToScene=([x,y])=>[(x-720)*.1,(y-531)*.1];
export const sceneToPixel=([x,z])=>[x/.1+720,z/.1+531];
export const campusBoundary=trace.campus_boundary.map(pixelToScene);
const rects=list=>list.map(([x0,y0,x1,y1])=>[...pixelToScene([x0,y0]),...pixelToScene([x1,y1])]);
export const surfaceRects={road:rects(trace.road_rects),curb:rects(trace.road_edge_rects),water:rects(trace.water_rects)};
export const buildings=trace.buildings.map((b,i)=>{
  const [x0,y0,x1,y1]=b.bbox;
  const centre=[(x0+x1)/2,(y0+y1)/2];
  return {id:b.id,name:`建筑轮廓 ${String(i+1).padStart(2,'0')}`,category:'待标注建筑',
    height:b.source_class==='public'?.95:.7,height_estimated:true,position:null,
    anchor:pixelToScene(centre),aliases:[],accuracy:'2025总图的填色轮廓；图像级对位',
    image_placement:{centre,size:[x1-x0,y1-y0],source:'campus-overview-2025.jpg'},
    footprints:b.footprints.map(f=>({outer:f.outer.map(pixelToScene),holes:f.holes.map(h=>h.map(pixelToScene))})),
    evidence:{type:'faculty',typeLabel:'待标注',references:[],verification:'与原图轮廓同坐标',
      note:'此编号仅用于选中该轮廓。可在此添加你自己的景点名称。',
      geometryNote:'高度统一简化，平面位置来自原图。'},
  };
});
export const roads=[],waterways=[],lakes=[],plazas=[];
const field=(name,p,track,kind)=>({name,p:p.map(pixelToScene),track,kind});
export const fields=[
  field('北部跑道',[[903,280],[959,270],[982,379],[920,392]],true,'football'),
  field('西南跑道',[[333,708],[379,721],[349,814],[303,800]],true,'football'),
  field('北部球场',[[724,199],[772,208],[761,251],[709,241]],false,'tennis'),
  field('北部中球场',[[708,253],[763,264],[745,321],[688,309]],false,'grid'),
  field('北部南球场',[[694,316],[749,328],[730,381],[675,367]],false,'tennis'),
  field('西南球场',[[380,753],[411,761],[383,853],[354,844]],false,'grid'),
];
const regions=[
  ['overview-2025','2025总图 · 对位依据','campus-overview-2025.jpg',[0,0,1440,1062]],
  ['module-01','西北建筑参考','module-01-north-campus.jpg',[250,140,475,440]],
  ['module-02','北部宿舍参考','module-02-north-residences.jpg',[475,140,690,450]],
  ['module-03','中部教学区参考','module-03-teaching.jpg',[680,500,800,660]],
  ['module-04','体育与实验区参考','module-04-stadium-labs.jpg',[775,260,990,660]],
  ['module-05','中轴公共建筑参考','module-05-admin.jpg',[680,680,870,815]],
  ['module-06','南部院楼与宿舍参考','module-06-south-campus.jpg',[425,580,630,910]],
  ['module-07','西南运动与生活区参考','module-07-sports-housing.jpg',[245,710,600,910]],
  ['module-08','西侧院楼参考','module-08-medical-west.jpg',[200,450,330,800]],
];
export const sourceModules=regions.map(([id,label,file,[x0,y0,x1,y1]])=>({id,label,image:'./references/'+file,
  buildings:buildings.filter(b=>{const [x,y]=b.image_placement.centre;return x>=x0&&x<=x1&&y>=y0&&y<=y1;}).map(b=>b.id)}));
