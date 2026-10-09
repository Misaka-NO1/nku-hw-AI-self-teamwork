// Placement on the user's illustrated guide, NOT geographic/survey coordinates.
// Source: 1440 × 1017 campus guide + its two zoomed screenshots supplied by user.
// Pixel centres/envelopes are manually read: small roof edges remain approximate.
import {buildings as prototypes} from './calibrated-data.mjs';
import {evidenceFor} from './building-evidence.mjs';

export const metadata={id:'nku-jinnan-guide-plan-v1',revision:'0.7',title:'南开大学 · 津南校区',
  status:'illustrated-plan-placement',coordinate_system:'reference-image-pixels',
  source:'用户提供的 2026 校园导览图（1440 × 1017）、2025 公共版全校总图及八张 100 米比例尺局部地图截图；手绘图辅助核对',
  note:'依用户导览图、2025 公共版全校总图及八张局部地图截图，校核建筑组团名称/关系并细化屋顶轮廓、楼块组合和运动场线；位置为图示近似，不是实测坐标。2025 总图尚未与模型像素坐标配准。',
  reference_image:'./references/user-campus-guide.jpg',image_size:[1440,1017],
  image_origin:[715,595],units_per_pixel:.08,ground_size:[102,59],
  guide_crop:{left:90,top:245,width:1250,height:700},
};
export const sourceModules=[
  {id:'overview-2025',label:'2025年校区公共版总图',image:'./references/campus-overview-2025.jpg',buildings:['library','gym','student-centre','teaching-a','lab-north','lab-middle','lab-south','office-west','office-east']},
  {id:'module-01',label:'北区总览与宿舍',image:'./references/module-01-north-campus.jpg',buildings:['north-residence-0','north-residence-2','north-residence-3','north-residence-4','north-residence-5','teaching-a']},
  {id:'module-02',label:'宿舍、快递柜与食堂',image:'./references/module-02-north-residences.jpg',buildings:['north-residence-east','north-residence-6','canteen-1','canteen-2']},
  {id:'module-03',label:'公共教学楼区',image:'./references/module-03-teaching.jpg',buildings:['teaching-a','teaching-b','teaching-c','teaching-north']},
  {id:'module-04',label:'主体育场与实验楼',image:'./references/module-04-stadium-labs.jpg',buildings:['gym','lab-north','lab-d','lab-middle','student-centre']},
  {id:'module-05',label:'行政楼与图书馆',image:'./references/module-05-admin.jpg',buildings:['library','office-west','office-east']},
  {id:'module-06',label:'南区教学与生活',image:'./references/module-06-south-campus.jpg',buildings:['south-residence-0','south-residence-1','south-residence-2','south-residence-3','canteen-2']},
  {id:'module-07',label:'体育场、宿舍与食堂',image:'./references/module-07-sports-housing.jpg',buildings:['gym','north-residence-east','south-residence-0','south-residence-1']},
  {id:'module-08',label:'医学院与西南建筑',image:'./references/module-08-medical-west.jpg',buildings:['medicine','pharmacy','animal-centre','campus-hospital']},
];
export const pixelToScene=([x,y])=>[(x-715)*.08,(y-595)*.08];
export const sceneToPixel=([x,z])=>[x/.08+715,z/.08+595];
const byId=new Map(prototypes.map(b=>[b.id,b]));

// Roof outlines are local proportions inside each measured-by-eye image envelope.
// These forms are traced simplifications of the uploaded map modules, not BIM.
const rect=(x0,y0,x1,y1)=>({outer:[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],holes:[]});
const roofForms={
  hall:[rect(-.48,-.34,.48,.34)],
  wing:[{outer:[[-.48,-.43],[.22,-.43],[.22,-.22],[.48,-.22],[.48,.43],[-.48,.43]],holes:[]}],
  step:[{outer:[[-.48,-.36],[.33,-.36],[.33,-.48],[.48,-.48],[.48,.31],[.18,.31],[.18,.47],[-.48,.47]],holes:[]}],
  twin:[rect(-.48,-.36,-.06,.36),rect(.08,-.36,.48,.36)],
  triple:[rect(-.47,-.46,.47,-.24),rect(-.47,-.11,.47,.11),rect(-.47,.24,.47,.46)],
  courtyard:[{outer:[[-.48,-.46],[.48,-.46],[.48,.46],[-.48,.46]],holes:[[[-.22,-.19],[-.22,.19],[.22,.19],[.22,-.19]]]}],
  openCourt:[rect(-.47,-.46,.47,-.27),rect(-.47,.27,.47,.46),rect(-.47,-.24,-.29,.24),rect(.29,-.24,.47,.24)],
  cluster:[rect(-.48,-.45,.18,-.12),rect(.23,-.45,.48,-.12),rect(-.38,-.04,.38,.17),rect(-.48,.25,-.04,.46),rect(.06,.25,.48,.46)],
  housingCourt:[rect(-.48,-.46,.48,-.32),rect(-.48,.32,.48,.46),rect(-.48,-.25,-.34,.25),rect(.34,-.25,.48,.25),rect(-.17,-.27,.17,.27)],
};
const layoutById={
  library:'wing','office-west':'step','office-east':'courtyard',gym:'twin',
  'student-centre':'cluster','teaching-a':'openCourt','teaching-north':'openCourt',
  'lab-south':'triple','lab-middle':'cluster','lab-north':'twin',cs:'step',software:'wing',
  materials:'openCourt',electronics:'courtyard',medicine:'openCourt',pharmacy:'twin',
  environment:'courtyard',journalism:'cluster',finance:'twin',law:'wing',chinese:'twin',
  government:'courtyard',history:'wing',philosophy:'hall',marx:'twin',tourism:'step',
  exchange:'cluster','animal-centre':'hall','campus-hospital':'step',
  'canteen-halal':'hall','canteen-1':'wing','canteen-2':'step',
  'north-residence-0':'triple','north-residence-1':'triple','north-residence-2':'triple',
  'north-residence-east':'housingCourt','north-residence-6':'triple',
  'north-residence-3':'twin','north-residence-4':'triple','north-residence-5':'triple',
  'south-residence-0':'housingCourt','south-residence-1':'triple',
  'south-residence-2':'triple','south-residence-3':'triple',
  'teaching-c':'openCourt','teaching-b':'openCourt','lab-d':'twin','ai-guide':'wing',
};

// [existing model, source-image roof centre x/y, envelope width/depth, rotation].
// Width/depth are roof envelopes, not the centre of a printed text label.
export const placements=[
  ['library',776,708,122,39,0],
  ['office-west',721,759,68,54,0],['office-east',842,754,58,53,0],
  ['gym',750,397,69,97,-3],['student-centre',939,568,57,64,-8],
  ['teaching-a',718,642,79,26,-2],['teaching-north',682,535,80,30,-2],
  ['lab-south',830,632,93,33,-1],['lab-middle',817,586,90,43,-1],
  ['lab-north',815,487,83,41,-1],
  ['cs',594,699,101,40,-2],['software',502,635,65,38,0],
  ['materials',607,655,100,38,-1],['electronics',445,681,92,40,0],
  ['medicine',283,727,84,64,3],['pharmacy',341,668,64,43,2],
  ['environment',321,580,80,45,2],['journalism',466,580,104,46,0],
  ['finance',593,518,73,27,0],['law',503,518,68,28,0],
  ['chinese',476,490,69,26,0],['government',484,459,85,33,0],
  ['history',590,451,54,24,0],['philosophy',621,476,52,25,0],
  ['marx',647,452,58,27,0],['tourism',334,496,65,33,0],
  ['exchange',374,462,66,35,0],['animal-centre',372,790,43,91,3],
  ['campus-hospital',477,339,30,24,0],
  ['canteen-halal',501,391,63,21,0],['canteen-1',499,410,84,16,0],
  ['canteen-2',484,753,86,45,0],
  ['north-residence-0',551,311,94,19,0],
  ['north-residence-1',554,337,86,20,0],
  ['north-residence-2',550,365,90,18,0],
  ['north-residence-east',645,338,74,83,0],
  ['north-residence-6',558,426,162,19,0],
  ['north-residence-3',389,364,84,24,0],
  ['north-residence-4',379,397,100,31,0],
  ['north-residence-5',379,429,103,25,0],
  ['south-residence-0',585,770,111,30,0],
  ['south-residence-1',554,803,118,23,0],
  ['south-residence-2',552,834,109,22,0],
  ['south-residence-3',547,868,170,21,0],
];

// Reuse existing roofs/courtyards: de-rotate their old map orientation, then fit
// a source-image envelope. Apply the SAME transform to outer and inner rings.
function place(id,cx,cy,width,depth,angle=0,{newId=id,name,footIndices,aliases,layout}={}){
  const original=byId.get(id);
  if(!original)throw new Error('Missing building prototype: '+id);
  const feet=footIndices?footIndices.map(i=>original.footprints[i]):original.footprints;
  const style=layout||layoutById[newId]||'hall';
  const rad=angle*Math.PI/180;
  const transform=([u,v])=>pixelToScene([cx+u*width*Math.cos(rad)-v*depth*Math.sin(rad),
    cy+u*width*Math.sin(rad)+v*depth*Math.cos(rad)]);
  const sourceFeet=roofForms[style]||feet.map(f=>({outer:f.outer,holes:f.holes}));
  const data={...original,id:newId,name:name||original.name,position:null,
    aliases:aliases||(name?[]:original.aliases),
    anchor:pixelToScene([cx,cy]),source_ref:'user-campus-guide',
    image_placement:{centre:[cx,cy],size:[width,depth],angle,prototype:id,roof_layout:style,parts:sourceFeet.length},
    accuracy:'导览图人工对位；非测绘，体块形状仍为简化',
    footprints:sourceFeet.map(f=>({outer:f.outer.map(transform),holes:f.holes.map(r=>r.map(transform))}))};
  const type=evidenceFor(original);
  data.evidence={...type,references:[],verification:'按用户原图对位 · 人工近似',
    note:'屋顶中心按导览图和局部地图截图对位；楼体组合参考截图轮廓重组。图上标注与现场楼号仍需人工复核。',
    geometryNote:'图示平面位置；高度和立面不作实测依据。'};
  return data;
}
const overrides={
  'teaching-a':{name:'公共教学楼 A 区（图示）',layout:'openCourt'},
  'teaching-north':{name:'公共教学楼 D 区（图示）',layout:'openCourt'},
  'lab-north':{name:'基础实验楼（图示北部）',footIndices:[0],layout:'twin'},
  'lab-middle':{name:'综合实验楼中部（图示）'},
  'lab-south':{name:'综合实验楼 A 区（图示）'},
  cs:{name:'计算机学院 / 信息东楼（图示）'},
  'north-residence-0':{name:'北区公寓北排（图示，分栋待核对）'},
  'north-residence-2':{name:'文科宿舍 4A 楼（图示）'},
};
export const buildings=placements.map(p=>place(...p,overrides[p[0]]));
// The original coarse groups merged these distinguishable rows. Reuse the same
// model prototypes for the separate positions visible on the user's guide.
buildings.push(
  place('teaching-a',694,572,79,29,-2,{newId:'teaching-c',name:'公共教学楼 C 区（图示）',layout:'openCourt'}),
  place('teaching-a',706,610,80,27,-2,{newId:'teaching-b',name:'公共教学楼 B 区（图示）',layout:'openCourt'}),
  place('lab-north',815,537,91,32,-1,{newId:'lab-d',name:'综合实验楼 D 区（图示）',footIndices:[1],layout:'triple'}),
  place('history',565,493,61,26,0,{newId:'ai-guide',name:'人工智能学院（原图标注）',layout:'wing'}),
);
const traced=(name,p)=>({name,p:p.map(pixelToScene)});
const route=(name,w,p)=>({...traced(name,p),w:w*.08});
export const roads=[
  route('校内环路（依导览图）',8,[[270,286],[426,287],[710,300],[1030,296],[1227,314],[1264,555],[1290,868],[1100,887],[816,891],[653,884],[476,870],[138,827],[163,692],[196,539],[232,380],[270,286]]),
  route('西区南北道路',9,[[419,295],[410,349],[406,434],[389,472],[378,539],[356,612],[328,704],[310,821]]),
  route('教学楼西侧道路',8,[[711,307],[693,375],[680,453],[640,542],[642,606],[663,681],[659,825]]),
  route('教学与实验楼之间',10,[[777,449],[768,529],[779,602],[791,671],[868,684],[872,780],[844,827]]),
  route('人文院楼北路',7,[[277,451],[363,446],[427,438],[560,455],[687,474]]),
  route('人文院楼南路',7,[[287,523],[425,534],[539,537],[641,540]]),
  route('西门东西轴线',10,[[157,529],[238,529],[324,538],[428,548],[550,554],[641,554],[772,555],[896,549],[1007,551],[1112,574],[1294,562]]),
  route('西南学院区道路',7,[[211,622],[306,620],[375,621],[462,611],[545,622],[637,624]]),
  route('理科院楼中路',7,[[309,712],[390,714],[500,726],[646,729],[685,738]]),
  route('理科宿舍西路',6,[[438,709],[436,777],[449,854],[472,876]]),
  route('图书馆北路',8,[[646,677],[760,679],[849,675],[944,731],[1031,732]]),
  route('图书馆至南门中轴',11,[[779,733],[780,782],[782,835],[782,904]]),
  route('体育馆东侧道路',7,[[785,316],[783,405],[788,446],[862,447],[903,430]]),
  route('东区环路',8,[[916,304],[954,421],[993,495],[1064,547],[1116,577],[1100,694],[1067,724],[876,729]]),
];
export const lakes=[
  traced('西区湖面',[[401,620],[426,624],[441,639],[442,657],[427,670],[402,668],[382,656],[381,638],[390,628]]),
  traced('东北湖面',[[1073,309],[1142,309],[1204,328],[1229,361],[1244,416],[1253,452],[1236,483],[1215,497],[1185,492],[1165,465],[1128,443],[1104,425],[1081,399],[1060,356]]),
  traced('大通学生中心东侧湖面',[[963,545],[985,544],[1001,555],[1007,577],[996,596],[976,601],[953,594],[949,577]]),
];
export const waterways=[
  route('外围河道',12,[[1245,272],[1040,273],[732,269],[458,252],[245,242],[224,256],[191,385],[155,536],[120,694],[100,832],[126,848],[458,904],[650,921],[1033,920]]),
  route('东侧河道',12,[[1245,274],[1279,418],[1310,565],[1334,743],[1340,891]]),
  route('校园中部水系',4,[[424,636],[454,618],[482,613],[516,620],[546,630],[556,640],[582,638],[605,632],[642,638],[654,651],[669,661],[700,663],[732,670],[788,668],[842,666],[879,662],[891,650],[898,629],[924,622],[950,596]]),
  route('东区水系',5,[[1192,493],[1154,529],[1139,552],[1128,583],[1122,626],[1124,666],[1110,706],[1119,725],[1150,738]]),
  route('西区南段水系',4,[[391,659],[374,674],[361,704],[342,734],[335,778],[324,810],[320,862]]),
];
export const fields=[
  {...traced('主体育场',[[807,347],[865,334],[896,401],[833,423]]),track:true,kind:'football'},
  {...traced('北区网球场',[[651,374],[694,379],[689,440],[648,435]]),track:false,kind:'tennis'},
  {...traced('理科运动场',[[355,675],[394,684],[378,739],[339,730]]),track:true,kind:'football'},
  {...traced('东区北球场',[[936,634],[1037,634],[1039,712],[932,712]]),track:false,kind:'grid'},
  {...traced('东区南球场（遮挡部分按可见边界近似）',[[929,758],[1017,761],[1017,858],[925,853]]),track:false,kind:'grid'},
];
const circle=(x,y,r)=>Array.from({length:32},(_,i)=>[x+Math.cos(i*Math.PI/16)*r,y+Math.sin(i*Math.PI/16)*r]);
export const plazas=[traced('西门广场',circle(214,530,17)),traced('南门广场',circle(784,882,36)),
  traced('图书馆前中轴广场',[[760,738],[802,738],[804,827],[762,827]])];
