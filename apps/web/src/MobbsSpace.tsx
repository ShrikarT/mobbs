import React, {useEffect, useMemo, useRef, useState} from 'react';
import {animate} from 'animejs';
import {MobFace} from './Doodles';
import {roomLayout} from './room-layout';
import type {SimulationEvent} from './types';

interface PersonaView {
  status: 'watching'|'stopped'|'active';
  lastScene: number;
  atMs?: number;
  reason?: string;
  actions: string[];
}
interface Props {ids:string[]; states:Map<string,PersonaView>; events:SimulationEvent[]; paused:boolean; seed:string;}

function Mob({id,state,variant,angle,paused,motionAllowed,onInspect}: {id:string;state?:PersonaView;variant:number;angle:number;paused:boolean;motionAllowed:boolean;onInspect:(id:string)=>void}) {
  const ref = useRef<HTMLButtonElement>(null);
  const animation = useRef<ReturnType<typeof animate> | null>(null);
  const observed = !!state;
  useEffect(()=>{
    if(!ref.current || !observed || !motionAllowed) return;
    const a=animate(ref.current,{scale:[.45,1],rotate:[angle,0],opacity:[.2,1],duration:520,ease:'outBack',autoplay:!paused});
    animation.current=a;
    return ()=>{a.revert(); animation.current=null;};
  },[observed,motionAllowed,angle]);
  useEffect(()=>{ if(paused) animation.current?.pause(); else animation.current?.resume(); },[paused]);
  const label=state?.status==='stopped'?'left':state?'watching':'waiting';
  return <button ref={ref} type="button" className={`persona-node mob-node ${state?.status==='stopped'?'stopped':state?'watching':'pending'}`} onClick={()=>onInspect(id)} onFocus={()=>onInspect(id)} aria-label={`${id}: ${label}${state ? `, scene ${state.lastScene}`:''}${state?.reason ? `. Simulated reason: ${state.reason}`:''}`}>
    <MobFace variant={state?.status==='stopped'?5:variant}/>
    <span className="persona-id mono">{id}</span>
    <span className="persona-indicator">{label}</span>
    {!!state?.actions.length && <span className="mob-actions">{state.actions.map(action=><span key={action}>{action==='like'?'♡':action==='share'?'↗':action==='save'?'☆':action}</span>)}</span>}
  </button>;
}

export function MobbsSpace({ids,states,events,paused,seed}: Props) {
  const root=useRef<HTMLDivElement>(null);
  const [motionAllowed,setMotionAllowed] = useState(false);
  useEffect(()=>{
    const media=window.matchMedia('(prefers-reduced-motion: reduce)');
    const change=()=>setMotionAllowed(!media.matches);
    change(); media.addEventListener('change',change);
    return ()=>media.removeEventListener('change',change);
  },[]);
  const [width,setWidth]=useState(800);
  const [inspected,setInspected]=useState<string|null>(null);
  const [visible,setVisible]=useState(true);
  const [tabVisible,setTabVisible]=useState(!document.hidden);
  useEffect(()=>{
    const node=root.current;
    if(!node) return;
    const resize=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width));
    resize.observe(node);
    const intersection=new IntersectionObserver(entries=>setVisible(entries[0].isIntersecting));
    intersection.observe(node);
    const visibility=()=>setTabVisible(!document.hidden);
    document.addEventListener('visibilitychange',visibility);
    return ()=>{resize.disconnect();intersection.disconnect();document.removeEventListener('visibilitychange',visibility);};
  },[]);
  const layout=useMemo(()=>roomLayout(ids,width,seed),[ids,width,seed]);
  const latest = useMemo(()=>{
    for(let i=events.length-1;i>=0;i--) {
      const id=events[i].payload?.persona_id;
      if(id && states.get(id)?.reason) return id;
    }
    return null;
  },[events,states]);
  const chosen=inspected || latest;
  const selected=chosen?states.get(chosen):null;
  return <div className="mobbs-space-wrap">
    <div ref={root} className="persona-grid mobbs-space" role="region" aria-label="Simulated personas state grid" style={{height:layout.height}}>
      <span className="room-star room-star-a" aria-hidden="true">✧</span><span className="room-star room-star-b" aria-hidden="true">✳</span>
      {layout.positions.map(position=><div key={position.id} className="mob-position" style={{left:position.x,top:position.y}}><Mob id={position.id} state={states.get(position.id)} variant={position.variant} angle={position.angle} paused={paused || !visible || !tabVisible} motionAllowed={motionAllowed} onInspect={setInspected}/></div>)}
    </div>
    <div className="mob-reaction-inspector" aria-live={paused?"polite":"off"} aria-atomic="true">
      {selected?.reason ? <><div className="reaction-byline"><MobFace variant={selected.status==='stopped'?5:3}/><span>{chosen} · {selected.status==='stopped'?'left':'watching'} · scene {selected.lastScene}</span>{inspected && <button type="button" onClick={()=>setInspected(null)} className="text-button">latest reaction</button>}</div><blockquote className="handwritten-bubble">“{selected.reason}”</blockquote><p>saved simulated persona reason{selected.atMs!==undefined?` · ${(selected.atMs/1000).toFixed(1)}s`:''}</p></> : <p className="awaiting-reactions">{chosen?`${chosen} is waiting for a saved reaction.`:'the stage is ready. reactions appear when the actual events arrive.'}</p>}
    </div>
    <p className="room-caption">positions and character expressions are decorative. labels, actions and quotes reflect saved simulation events. Select a mob to inspect it.</p>
  </div>;
}
