/** Presentation-only placement. No placement or face implies an observed reaction. */
export function hashIdentity(value: string): number {
  let hash = 2166136261;
  for (let i=0; i<value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
  return hash >>> 0;
}

export function roomLayout(ids: readonly string[], width: number, seed: string) {
  const usable = Math.max(192, width);
  const columns = Math.max(3, Math.min(10, Math.floor(usable/84)));
  const rows = Math.max(3, Math.ceil(ids.length/columns));
  const cell = usable/columns;
  const rowHeight = 104;
  let randomState=hashIdentity(seed) || 1;
  const random=()=>{
    randomState ^= randomState<<13;randomState ^= randomState>>>17;randomState ^= randomState<<5;
    return (randomState>>>0)/4294967296;
  };
  const slots = Array.from({length:rows*columns},(_,i)=>i);
  for(let i=slots.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[slots[i],slots[j]]=[slots[j],slots[i]];}
  const jitterX=Math.min(18,(cell-64)/2);
  return {
    height: rows*rowHeight+72,
    positions: ids.map((id,i)=>{
      const slot = slots[i];
      const h = hashIdentity(`${seed}:${id}`);
      return {id, x: (slot%columns+.5)*cell + (random()*2-1)*jitterX, y: 64+Math.floor(slot/columns)*rowHeight+(random()*32-16), variant:h%8, angle:(h%13)-6};
    }),
  };
}
