// Add guide strokes to the original binary road surface before triangulation.
// Unioning pixels keeps crossings seamless and gives new roads the same pixel
// contour resolution as the traced plan. No snapping, jitter, or width fitting.
function fillRects(mask, width, height, rectangles){
  for(const [x0,y0,x1,y1] of rectangles){
    for(let y=Math.max(0,y0);y<Math.min(height,y1);y++)
      mask.fill(1,y*width+Math.max(0,x0),y*width+Math.min(width,x1));
  }
}

function stroke(mask,width,height,points,radius){
  for(let i=1;i<points.length;i++){
    const [ax,ay]=points[i-1],[bx,by]=points[i];
    const dx=bx-ax,dy=by-ay,length2=dx*dx+dy*dy;
    const left=Math.max(0,Math.floor(Math.min(ax,bx)-radius));
    const right=Math.min(width-1,Math.ceil(Math.max(ax,bx)+radius));
    const top=Math.max(0,Math.floor(Math.min(ay,by)-radius));
    const bottom=Math.min(height-1,Math.ceil(Math.max(ay,by)+radius));
    for(let y=top;y<=bottom;y++)for(let x=left;x<=right;x++){
      const px=x+.5,py=y+.5;
      const t=length2?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/length2)):0;
      if((px-ax-t*dx)**2+(py-ay-t*dy)**2<=radius*radius)mask[y*width+x]=1;
    }
  }
}

export function maskRectangles(mask,width,height){
  const output=[];let active=new Map();
  for(let y=0;y<height;y++){
    const next=new Map();
    for(let x=0;x<width;){
      if(!mask[y*width+x]){x++;continue;}
      const start=x;while(x<width&&mask[y*width+x])x++;
      const key=start+':'+x,rectangle=active.get(key)||[start,y,x,y];
      rectangle[3]=y+1;next.set(key,rectangle);active.delete(key);
    }
    output.push(...active.values());active=next;
  }
  output.push(...active.values());return output;
}

export function mergeRoadSurfaces(source,routes){
  const [width,height]=source.image_size;
  const road=new Uint8Array(width*height),curb=new Uint8Array(width*height);
  fillRects(road,width,height,source.road_rects);
  fillRects(curb,width,height,source.road_edge_rects);
  for(const route of routes){
    const points=route.points.map(([x,y])=>[
      (x-.5)*source.spot_extent[0]/source.units_per_pixel+source.image_origin[0],
      (y-.5)*source.spot_extent[1]/source.units_per_pixel+source.image_origin[1],
    ]);
    const radius=(route.kind==='path'?5.5:9)/2;
    stroke(road,width,height,points,radius);
    stroke(curb,width,height,points,radius+2);
  }
  return {road:maskRectangles(road,width,height),curb:maskRectangles(curb,width,height)};
}

export function surfacePositions(rectangles,y,source){
  const positions=new Float32Array(rectangles.length*18);
  const [cx,cy]=source.image_origin,scale=source.units_per_pixel;
  for(let index=0;index<rectangles.length;index++){
    const [a,b,c,d]=rectangles[index];
    const x0=(a-cx)*scale,z0=(b-cy)*scale,x1=(c-cx)*scale,z1=(d-cy)*scale;
    positions.set([x0,y,z0,x0,y,z1,x1,y,z1,x0,y,z0,x1,y,z1,x1,y,z0],index*18);
  }
  return positions;
}
