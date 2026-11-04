import {test,expect} from '@playwright/test';
import {roomLayout} from '../../apps/web/src/room-layout';

test('the actual room placement keeps every target inside its stage without overlap',()=>{
  for(const width of [192,256,320,420,700,900,1280])for(let seed=1;seed<=20;seed++)for(const count of [3,50]){
    const ids=Array.from({length:count},(_,i)=>`p${i}`);
    const room=roomLayout(ids,width,String(seed));
    expect(room).toEqual(roomLayout(ids,width,String(seed)));
    const invalid=room.positions.filter(p=>p.x-24<0 || p.x+24>width || p.y-33<0 || p.y+33>room.height);
    expect(invalid).toEqual([]);
    const overlaps=[];
    for(let i=0;i<count;i++)for(let j=i+1;j<count;j++){
      const a=room.positions[i],b=room.positions[j];
      if(Math.abs(a.x-b.x)<48 && Math.abs(a.y-b.y)<66)overlaps.push([a.id,b.id]);
    }
    expect(overlaps).toEqual([]);
  }
});
