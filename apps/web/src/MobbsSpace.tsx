import {useEffect,useRef,useState} from 'react';
import {animate} from 'animejs';
import {MobFace} from './Doodles';
import type {SimulationEvent} from './types';

interface Appearance {key:number;slot:number;born:number;variant:number;text:string;waiting:boolean;dx:number;dy:number;}
const hash=(value:string)=>Array.from(value).reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,7);
function littleReaction(event:SimulationEvent) {
  const p=event.payload;
  if(typeof p.quick_reaction==='string' && p.quick_reaction.trim())return p.quick_reaction.trim().slice(0,60);
  const actions=(p.actions || []).map(a=>typeof a==='string'?a:a.type);
  if(actions.includes('share'))return 'sending this ↗';
  if(actions.includes('save'))return 'saving this one ☆';
  if(actions.includes('like'))return 'love this ♡';
  if(actions.includes('comment'))return 'got a thought!';
  if(actions.includes('follow'))return 'more of this, please';
  return event.type==='persona.stopped'?'lost me a little…':'okay, i’m in!';
}
function Visitor({item,age,motion,paused,capacity}:{item:Appearance;age:number;motion:boolean;paused:boolean;capacity:number}) {
  const ref=useRef<HTMLDivElement>(null);
  const animation=useRef<ReturnType<typeof animate>|null>(null);
  useEffect(()=>{
    if(!ref.current || !motion)return;
    animation.current=animate(ref.current,{opacity:{from:0,to:1},scale:{from:.55,to:1},y:{from:14,to:0},duration:420,ease:'outBack'});
    return()=>{animation.current?.revert();};
  },[motion]);
  const leaving=age>4100;
  useEffect(()=>{
    if(leaving && motion && ref.current)animation.current=animate(ref.current,{opacity:0,scale:.8,y:-8,duration:260,ease:'inQuad'});
  },[leaving,motion]);
  useEffect(()=>{if(paused)animation.current?.pause();else animation.current?.resume();},[paused]);
  const x=(capacity===2?[28,72]:[18,50,82])[item.slot]+item.dx;
  const y=(capacity===2?[32,72]:[48,67,35])[item.slot]+item.dy;
  return <div className="mob-visitor-position" data-appearance={item.key} style={{left:`${x}%`,top:`${y}%`}}>
    <div ref={ref} className={`mob-visitor ${item.waiting?'warming':''}`} aria-label={item.waiting?'A decorative mob getting ready':`Stylised simulated reaction: ${item.text}`}>
      <span className="little-thought">{item.text}</span><MobFace variant={item.variant}/>
    </div>
  </div>;
}

export function MobbsSpace({events,paused,seed}:{events:SimulationEvent[];paused:boolean;seed:string}) {
  const root=useRef<HTMLDivElement>(null);
  const eventsRef=useRef(events);eventsRef.current=events;
  const pausedRef=useRef(paused);pausedRef.current=paused;
  const [width,setWidth]=useState(700);
  const [motion,setMotion]=useState(false);
  const [clock,setClock]=useState(0);
  const [visitors,setVisitors]=useState<Appearance[]>([]);
  const elapsed=useRef(0),serial=useRef(0),lastSpawn=useRef(-2000);
  const used=useRef(new Set<string>());
  const visitorsRef=useRef<Appearance[]>([]);
  const visibleRef=useRef(true);
  const [visible,setVisible]=useState(true);
  const capacity=width<520?2:3;
  useEffect(()=>{
    const node=root.current;if(!node)return;
    const observer=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width));observer.observe(node);
    const intersection=new IntersectionObserver(entries=>{visibleRef.current=entries[0].isIntersecting;setVisible(entries[0].isIntersecting&&!document.hidden);});intersection.observe(node);
    const visibility=()=>setVisible(visibleRef.current&&!document.hidden);document.addEventListener('visibilitychange',visibility);
    const preference=matchMedia('(prefers-reduced-motion: reduce)');
    const change=()=>setMotion(!preference.matches);change();preference.addEventListener('change',change);
    return()=>{observer.disconnect();intersection.disconnect();document.removeEventListener('visibilitychange',visibility);preference.removeEventListener('change',change);};
  },[]);
  useEffect(()=>{
    const timer=setInterval(()=>{
      if(pausedRef.current || document.hidden || !visibleRef.current)return;
      elapsed.current+=400;const now=elapsed.current;setClock(now);
      const update=()=>{
        const alive=visitorsRef.current.filter(v=>now-v.born<4600 && v.slot<capacity);
        if(alive.length>=capacity || now-lastSpawn.current<1400)return alive;
        const slot=Array.from({length:capacity},(_,i)=>i).find(i=>!alive.some(v=>v.slot===i))!;
        const reactions=eventsRef.current.filter(e=>e.type==='persona.continued'||e.type==='persona.stopped');
        const fresh=reactions.slice(-30).find(e=>!used.current.has(e.event_id));
        if(fresh)used.current.add(fresh.event_id);
        const key=serial.current++;lastSpawn.current=now;
        const waiting=['getting comfy…','popcorn ready','eyes on this…','hmm, let’s see'];
        const roll=hash(seed+key);
        return [...alive,{key,slot,born:now,variant:roll%8,text:fresh?littleReaction(fresh):waiting[key%waiting.length],waiting:!fresh,dx:(roll%5-2)*(capacity===2?.5:1.5),dy:(roll%11-5)}];
      };
      visitorsRef.current=update();setVisitors(visitorsRef.current);
    },400);
    return()=>clearInterval(timer);
  },[capacity,seed]);
  return <div className="mobbs-room-wrap">
    <div ref={root} className="mobbs-room" role="region" aria-label="The mobbs space">
      <span className="room-spark room-spark-one" aria-hidden="true">✳</span><span className="room-spark room-spark-two" aria-hidden="true">✧</span>
      <span className="room-floor" aria-hidden="true"/>
      {visitors.map(item=><Visitor key={item.key} item={item} age={clock-item.born} paused={paused || !visible} motion={motion} capacity={capacity}/>)}
    </div>
    <p className="room-note">{paused?'a little pause. your scan keeps going.':'little takes from a simulated crowd. big feelings included.'}</p>
  </div>;
}
