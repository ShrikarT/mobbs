import React, {useEffect,useRef,useState} from 'react';
import phone from './assets/hero-phone.svg?raw';
import poster from './assets/hero-poster.svg?raw';
import laptopPaths from './assets/laptop-paths.json';
import {Doodle,MobFace,SketchRect} from './Doodles';

function Face({x,y,variant=3,size=40}: {x:number;y:number;variant?:number;size?:number}) {
  return <g transform={`translate(${x} ${y}) scale(${size/40})`}><MobFace variant={variant}/></g>;
}
function Bubble({x,y,text,w=126}: {x:number;y:number;text:string;w?:number}) {
  return <g><SketchRect x={x} y={y} w={w} h={34} fill="#EEE9FA" stroke="#B8A8ED" strokeWidth={2}/><text x={x+12} y={y+23} className="svg-hand">{text}</text></g>;
}
function Reel({x=28,y=64,w=150,h=266,logo=false}: {x?:number;y?:number;w?:number;h?:number;logo?:boolean}) {
  return <g><SketchRect x={x} y={y} w={w} h={h}/><SketchRect x={x+14} y={y+18} w={w-28} h={h*.56} fill={logo?'var(--ink)':'var(--lavender)'} strokeWidth={2}/>{logo?<text x={x+w/2} y={y+93} textAnchor="middle" fill="var(--paper)" fontSize="13">logo</text>:<g transform={`translate(${x+w/2-28} ${y+49})`}><Doodle/></g>}<path d={`M${x+24} ${y+h*.72}l${w-48} 2 M${x+24} ${y+h*.79}l${w*.35} 1`} stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round"/><Face x={x+17} y={y+h-51} variant={logo?5:4} size={25}/>{!logo&&<Face x={x+w-45} y={y+h-51} size={25}/>}</g>;
}
function Note({compare=false}: {compare?:boolean}) {
  return <g transform="rotate(-3 617 684)"><SketchRect x={500} y={590} w={236} h={186} fill="var(--paper)" strokeWidth={2.5}/><text x="519" y="622" fontSize="12" fontWeight="700">DIRECTOR’S NOTE</text><text x="683" y="621" fontSize="11">0:07</text><text x="519" y="655" fontSize="14">{compare?<><tspan x="519">cut 2 holds the mob</tspan><tspan x="519" dy="25">past 0:07. opening on</tspan><tspan x="519" dy="25">the demo works.</tspan></>:<><tspan x="519">the mob left here.</tspan><tspan x="519" dy="25">first 2s is a logo.</tspan><tspan x="519" dy="25">open on the demo</tspan><tspan x="519" dy="25">instead.</tspan></>}</text><text x="519" y="759" fontSize="10">● ● ● ● ●  sample note</text></g>;
}

export function HeroLoop() {
  const root=useRef<HTMLDivElement>(null);
  const [paused,setPaused]=useState(false);
  const [visible,setVisible]=useState(false);
  const [hidden,setHidden]=useState(document.hidden);
  const [ready,setReady]=useState(false);
  useEffect(()=>{
    const target=root.current;
    if(!target)return;
    const io=new IntersectionObserver(entries=>setVisible(entries[0].isIntersecting),{threshold:.1});io.observe(target);
    const change=()=>setHidden(document.hidden);
    document.addEventListener('visibilitychange',change);
    const timer=window.setTimeout(()=>setReady(true),350);
    return ()=>{io.disconnect();document.removeEventListener('visibilitychange',change);clearTimeout(timer);};
  },[]);
  const playing=ready&&visible&&!hidden&&!paused;
  return <div ref={root} className={`hero-loop ${ready?'is-ready':''} ${playing?'is-playing':'is-paused'}`} data-playing={playing}>
    <div role="img" aria-label="Sample simulated demo: upload a video, the mobbs react, a timeline shows where they left, and a Director’s Note suggests an edit. Sample data; no prediction of real reach." className="hero-loop-art">
      <div className="hero-phone hero-anim" aria-hidden="true" dangerouslySetInnerHTML={{__html:phone}}/>
      <div className="hero-poster" aria-hidden="true" dangerouslySetInnerHTML={{__html:poster}}/>
      <svg className="hero-laptop hero-anim" viewBox="0 0 760 840" aria-hidden="true">
        <defs><clipPath id="demo-screen-clip"><rect x="50" y="210" width="660" height="410" rx="16"/></clipPath></defs>
        <path d={laptopPaths["Laptop lid"]} fill="var(--sheet)" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d={laptopPaths["Laptop base"]} fill="var(--lavender)" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/><path d="M340 640q40 10 80 0" fill="none" stroke="currentColor" strokeWidth="3"/>
        <rect x="50" y="210" width="660" height="410" fill="var(--screen)" stroke="#B8A8ED" strokeWidth="2" rx="16"/>
        <g clipPath="url(#demo-screen-clip)"><g transform="translate(50 210)">
          <g transform="translate(18 10) scale(.45)"><Doodle/></g><text x="48" y="29" fontSize="13" fontWeight="700">mobbs.fun ˎˊ</text><g transform="translate(526 9) scale(.65)"><Doodle name="mushroom"/></g><g transform="translate(574 9) scale(.65)"><Doodle name="tree"/></g><g transform="translate(622 9) scale(.6)"><Doodle name="search"/></g><path d="M16 48q320 3 628 0" fill="none" stroke="#B8A8ED" strokeWidth="2"/>
          <g className="hero-scene hero-drop hero-anim">
            <SketchRect x={40} y={64} w={584} h={328} fill="#EDE8FA" strokeWidth={2.5}/><SketchRect x={60} y={83} w={544} h={288} fill="var(--screen)" stroke="#B8A8ED" strokeWidth={2}/>
            <g transform="translate(287 118) scale(1.6)"><Doodle name="upload"/></g><text className="svg-hand svg-drop-heading" x="332" y="248" textAnchor="middle">drop your video here</text><text x="332" y="279" textAnchor="middle" fontSize="15">or click to upload</text><rect x="212" y="305" width="240" height="31" rx="15" fill="var(--lavender)"/><text x="332" y="326" textAnchor="middle" fontSize="11">MP4 · UP TO 60 SEC</text><g className="hero-tumbling-reel hero-anim"><SketchRect x={470} y={95} w={70} h={124}/><path d="M491 130v45l31-23Z" fill="none" stroke="currentColor" strokeWidth="3"/></g>
          </g>
          <g className="hero-scene hero-gather hero-anim"><Reel x={257} y={64}/><Face x={80} y={90} variant={1} size={46}/><Face x={120} y={210} variant={2} size={46}/><Face x={70} y={295} variant={4} size={46}/><Face x={520} y={100} variant={3} size={46}/><Face x={505} y={252} variant={5} size={46}/><Bubble x={125} y={60} text="ooh, a video!"/><Bubble x={432} y={318} text="play it play it"/></g>
          <g className="hero-scene hero-react hero-anim"><Reel/>{['too long maybe?','wait, what is this?',"haha ok that’s good","i’d watch this! ♡",'skipping this.'].map((quote,i)=><g key={quote} className={`hero-reaction hero-reaction-${i} hero-anim`}><Face x={214} y={64+i*46} variant={[7,2,4,3,5][i]} size={34}/><Bubble x={260} y={64+i*46} text={quote} w={146}/><text x="425" y={86+i*46} fontSize="10">{['bored','confused','laughed','loved','left'][i]}</text><circle cx={296+i*44} cy="337" r="5" fill={['#E8730C','#8F7BEA','#4C9A0A','#0A84D6','#DC143C'][i]}/></g>)}<path d="M214 330q130-5 260 1t150-1" fill="none" stroke="currentColor" strokeWidth="3"/><text x="580" y="371" fontSize="10">sample</text></g>
          <g className="hero-scene hero-dip hero-anim"><Reel logo/><Face x={214} y={64} variant={5}/><Bubble x={268} y={66} text="skipping this."/><Face x={214} y={130} variant={7}/><Bubble x={268} y={132} text="too long maybe?"/><text x="300" y="225" className="svg-hand">0:07 · the mob left</text><path d="M420 232q37 30 61 80" fill="none" stroke="#DC143C" strokeWidth="2.5"/><path d="M214 320q100-5 240 0q32-5 47 18q12-19 35-16l88-2" fill="none" stroke="currentColor" strokeWidth="3"/><circle cx="501" cy="338" r="6" fill="#DC143C"/><text x="484" y="370" fontSize="10">0:07</text><text x="580" y="370" fontSize="10">sample</text></g>
          <g className="hero-scene hero-compare hero-anim"><Reel x={32} w={130} h={230} logo/><Reel x={352} w={130} h={230}/><text x="182" y="93" fontSize="23" fontWeight="700">cut 1</text><text x="182" y="124" fontSize="12">62% stayed · sample</text><path d="M182 163h62q21-1 29 19q8-20 39-19" fill="none" stroke="currentColor" strokeWidth="3"/><text x="502" y="93" fontSize="23" fontWeight="700">cut 2</text><text x="502" y="124" fontSize="12">78% stayed · sample</text><path d="M502 174q70-2 130-22" fill="none" stroke="currentColor" strokeWidth="3"/><path d="M330 64v240" stroke="#B8A8ED" strokeWidth="2"/><Face x={330} y={318} size={40}/><Bubble x={376} y={318} text="i’d watch this! ♡"/></g>
        </g></g>
        <g className="hero-note-dip hero-anim"><Note/></g><g className="hero-note-compare hero-anim"><Note compare/></g>
        <g className="hero-peeks hero-anim"><Face x={100} y={140} variant={7} size={52}/><Face x={230} y={130} variant={4} size={52}/><Face x={540} y={134} variant={2} size={52}/><Face x={640} y={142} variant={3} size={52}/></g>
      </svg>
    </div>
    <button type="button" className="hero-play-control" onClick={()=>setPaused(value=>!value)} aria-label={paused?'Play demo animation':'Pause demo animation'} aria-pressed={paused}><Doodle name={paused?'play':'pause'}/>{paused?'play':'pause'}</button>
  </div>;
}
