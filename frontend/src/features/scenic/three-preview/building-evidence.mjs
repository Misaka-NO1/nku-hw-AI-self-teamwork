// Purpose classifications are independent of simplified roof geometry.
export const buildingTypes={
  faculty:{label:'学院教学科研',color:'#e5d7b9'},teaching:{label:'公共教学',color:'#c5d9e5'},
  lab:{label:'实验科研',color:'#d7cbe2'},dorm:{label:'宿舍',color:'#dec4b7'},
  dining:{label:'食堂餐饮',color:'#e8c58e'},medical:{label:'医疗服务',color:'#c1ded7'},
  office:{label:'行政服务',color:'#becfdf'},library:{label:'图书馆',color:'#e9d99f'},
  activity:{label:'学生活动',color:'#c9dba9'},sports:{label:'体育建筑',color:'#b6d6c0'},
  exchange:{label:'交流接待',color:'#d5cdbd'},
};
const categoryType={'教学':'faculty','公共教学':'teaching','实验':'lab','宿舍':'dorm','餐饮':'dining','医疗':'medical','行政服务':'office','运动':'sports'};
const links={
  campus:{label:'学校校区总体介绍（2015，建筑用途背景）',url:'https://news.nankai.edu.cn/ztbd/system/2015/09/07/000247177.shtml'},
  service:{label:'师生服务中心位置说明',url:'https://www.nankai.edu.cn/2015/0913/c17471a238099/page.htm'},
  office:{label:'学校组织部办公地址说明',url:'https://rsc.nankai.edu.cn/2019/0525/c13695a164409/page.htm'},
  library:{label:'南开大学图书馆馆藏分布',url:'https://lib.nankai.edu.cn/gzfb/listm.htm'},
  animal:{label:'实验动物中心官方介绍',url:'https://lac.nankai.edu.cn/11952/list.htm'},
  ai:{label:'信息东楼相关学院活动记录（2024）',url:'https://news.nankai.edu.cn/ywsd/system/2024/06/17/030062243.shtml'},
  dorm:{label:'学校宿舍分布（2022，仅核对用途和编号存在）',url:'https://xgb.nankai.edu.cn/shenghuo/news/info/id/363.html'},
};
export function evidenceFor(b){
  const type=({library:'library','student-centre':'activity',exchange:'exchange'})[b.id]||categoryType[b.category]||'faculty';
  let note=b.position?'名称参考高德 POI；标注坐标不等于建筑中心或入口。':'位置按参考图人工对应，暂无独立地点坐标核验。';
  let references=[];
  if(type==='dorm'){references=[links.dorm];note+=' 单栋编号、入住用途可能调整，不据此推断住户。';}
  if(b.id==='library')references=[links.library];
  if(b.id==='office-west'){references=[links.service];note='已从图书馆模型中分离；学校说明确认用途，轮廓按卫星影像及参考图对应。';}
  if(b.id==='office-east'){references=[links.office];note='已从图书馆模型中分离，为综合业务东楼，不作为图书馆附楼。';}
  if(b.id==='animal-centre'){references=[links.animal];note='高德地点对应的西南侧实验建筑；轮廓根据卫星视图近似描绘，不是医学院或宿舍。';}
  if(b.id==='campus-hospital')note='北区医疗服务建筑，与西南侧医学院教学科研楼区分。';
  if(b.id==='cs'){references=[links.ai];note='信息东楼相关组团，学院存在共址与分楼使用，不把同址机构生成重复建筑；具体房间归属未核验。';}
  if(type==='teaching'||type==='lab'){if(!references.length)references=[links.campus];note+=' 组团可能包含多栋，不能把粗模边界当作 A/B/C/D 分区边界。';}
  return {type,typeLabel:buildingTypes[type].label,color:buildingTypes[type].color,
    verification:b.name.includes('待核对')?'组团已定位 · 分栋待核对':b.position?'POI 对照 · 轮廓粗描':'参考图对应 · 轮廓粗描',
    note,references,geometryNote:'外轮廓和高度是简化表达，不能用于测量或确认入口。'};
}
