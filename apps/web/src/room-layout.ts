/** Presentation-only placement. No placement or face implies an observed reaction. */
export function hashIdentity(value: string): number {
  let hash = 2166136261;
  for (let i=0; i<value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
  return hash >>> 0;
}

export function roomLayout(ids: readonly string[], width: number, seed: string) {
  const usable = Math.max(192, width);
  const columns = Math.max(3, Math.min(10, Math.floor(usable/64)));
  const rows = Math.max(3, Math.ceil(ids.length/columns));
  const cell = usable/columns;
  const rowHeight = 78;
  const slots = Array.from({length:rows*columns},(_,i)=>i).sort((a,b)=>hashIdentity(`${seed}:slot:${a}`)-hashIdentity(`${seed}:slot:${b}`));
  return {
    height: rows*rowHeight+96,
    positions: ids.map((id,i)=>{
      const slot = slots[i];
      const h = hashIdentity(`${seed}:${id}`);
      return {id, x: (slot%columns+.5)*cell + (h%13-6), y: 58+Math.floor(slot/columns)*rowHeight+((h>>>4)%15-7), variant:h%8, angle:(h%13)-6};
    }),
  };
}
