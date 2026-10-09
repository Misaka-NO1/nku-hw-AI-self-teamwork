// @vitest-environment jsdom
import { it,expect } from "vitest";
import { extractEamisGridFromDoc, eamisObservationToRawRows } from "../src/eamis";
const header='<tr><td>节次/周次</td>'+['一','二','三','四','五','六','日'].map(d=>`<td>星期${d}</td>`).join('')+'</tr>';
it('keeps rowSpan=3 occupied until its end, including empty merged cells',()=>{
 const doc=new DOMParser().parseFromString('<table id="manualArrangeCourseTable">'+header+'<tr><td>一</td><td rowspan="3">甲(0001) (某甲)(1-17,教室)</td>'+ '<td></td>'.repeat(6)+'</tr><tr><td>二</td><td>乙(0002) (某乙)(1-17,教室)</td>'+'<td></td>'.repeat(5)+'</tr><tr><td>三</td><td>丙(0003) (某丙)(1-17,教室)</td>'+'<td></td>'.repeat(5)+'</tr></table>','text/html');
 const grid=extractEamisGridFromDoc(doc)!;
 expect(grid.rows.map(r=>[r[1],r[2]])).toEqual([['星期一','1-3'],['星期二','2-2'],['星期二','3-3']]);
});
it('cancellation subtracts the cancelled week from an overlapping active entry',()=>{
 const converted=eamisObservationToRawRows({origin:'https://eamis.nankai.edu.cn',pathname:'/eams/courseTableForStd!courseTable.action',frameOrigin:null,tableHeaders:['课程条目','星期','节次'],rows:[['甲(0001) (某甲)(1-6,教室)甲(0001) (某甲)(3,停课)','星期一','1-2']],selectedTerm:null,selectedWeeks:[],hasPagination:false,hasVirtualRows:false});
 expect(converted.rows[0].weeksText).toBe('1,2,4,5,6');
});
