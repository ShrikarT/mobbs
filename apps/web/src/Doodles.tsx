import React from 'react';
import faces from './assets/mob-faces.json';

export type DoodleName = 'flower' | 'mushroom' | 'tree' | 'search' | 'upload' | 'pencil' | 'pause' | 'play';
export function Doodle({name = 'flower', className = ''}: {name?: DoodleName; className?: string}) {
  const paths: Record<DoodleName, string> = {
    flower: 'M15 16C-2 1 20-6 20 12C31-4 43 14 24 19C44 24 27 39 18 24C20 43 1 37 12 22C-7 30-8 8 12 14Z M17 23Q18 36 11 46 M14 36Q27 26 29 35Q23 42 14 40',
    mushroom: 'M5 24Q8 3 24 5Q40 4 43 24Q25 28 5 24Z M20 27L18 40Q25 45 30 40L28 27 M16 15L16 16 M29 12L29 13 M35 19L35 20',
    tree: 'M24 5L24 44 M10 10L24 19L36 9 M8 21L24 29L39 18 M11 32L24 39L36 29',
    search: 'M20 7C4 5 4 29 19 30C37 33 37 6 20 7Z M30 29L43 43',
    upload: 'M14 34C-2 34 0 13 13 15C15-2 39-1 42 16C57 14 58 34 44 34 M29 43L29 13 M18 24L29 13L40 24',
    pencil: 'M9 31L31 8Q35 5 40 10Q44 14 40 18L18 40L7 43Z M28 12L37 21 M9 31L18 40 M7 43L9 35',
    pause: 'M17 12L17 38 M31 12L31 38',
    play: 'M15 9L15 40L39 25Z',
  };
  return <svg width="48" height="48" viewBox={name === 'upload' ? '-3 -3 64 54' : '-4 -4 56 56'} className={`doodle ${className}`} fill="none" stroke="currentColor" strokeWidth="2.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

export function MobFace({variant = 3, className = ''}: {variant?: number; className?: string}) {
  const face = faces[((variant % faces.length) + faces.length) % faces.length];
  return <svg width="40" height="40" className={`mob-face ${className}`} viewBox="0 0 40 40" aria-hidden="true"><g transform={`translate(${-face.offset} 0)`}>{face.paths.map((p, index) => <path key={index} d={p.d} fill={p.fill || 'none'} stroke={p.stroke} strokeWidth={Number(p['stroke-width'])} strokeLinecap="round" strokeLinejoin="round"/>)}</g></svg>;
}

export function Brand({home = '#/'}: {home?: string}) {
  return <a href={home} className="mobbs-brand" aria-label="mobbs.fun home"><Doodle/><span className="brand-title">mobbs.fun</span><span className="brand-rays" aria-hidden="true">ˎˊ</span></a>;
}

export function SketchRect({x,y,w,h,fill='var(--paper)',stroke='currentColor',strokeWidth=3}: {x:number;y:number;w:number;h:number;fill?:string;stroke?:string;strokeWidth?:number}) {
  const r = Math.min(24, w/5, h/5);
  return <path d={`M${x+r} ${y+2}Q${x+w*.5} ${y-2} ${x+w-r} ${y+1}Q${x+w+2} ${y} ${x+w} ${y+r}L${x+w-1} ${y+h-r}Q${x+w+2} ${y+h+2} ${x+w-r} ${y+h}Q${x+w*.5} ${y+h-3} ${x+r} ${y+h-1}Q${x-2} ${y+h} ${x+1} ${y+h-r}L${x} ${y+r}Q${x-1} ${y+1} ${x+r} ${y+2}Z`} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"/>;
}
