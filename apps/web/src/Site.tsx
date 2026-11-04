import React,{lazy,Suspense,useEffect,useState} from 'react';
import {Brand,Doodle,MobFace} from './Doodles';
import {HeroLoop} from './HeroLoop';
const Workbench=lazy(()=>import('./App').then(module=>({default:module.App})));

export function Roadmap() {
  return <section className="roadmap-section" id="roadmap" aria-labelledby="roadmap-heading"><span className="eyebrow">what’s next / roadmap</span><h2 id="roadmap-heading">small steps. bigger possibilities.</h2><p>V03 is the current product. These are future plans, not available features.</p><div className="roadmap-list">{[
    ['V04','cut 1 vs cut 2','Matched casts, paired ranges and honest comparisons.'],
    ['V05','thumbnail lab','Owned-frame variants, simulated votes and clear provenance.'],
    ['next','deep + multi-platform','Richer context, more formats and comparative benchmarks.'],
    ['later','accounts + API','Personal libraries, collaboration and integrations.'],
    ['research','accuracy + calibration','Separate validation against real audience outcomes.'],
  ].map(([version,title,body])=><article key={version} className="roadmap-item"><span className="version-pill">{version}</span><div><h3>{title}</h3><p>{body}</p></div><span className="future-label">planned</span></article>)}</div></section>;
}

function SiteHeader() {
  return <header className="site-header"><Brand/><nav aria-label="Main navigation"><a href="#/app/new"><Doodle name="flower"/><span>scan</span></a><a href="#/sample"><Doodle name="mushroom"/><span>notes</span></a><a href="#/roadmap"><Doodle name="tree"/><span>later</span></a><a href="#/sample"><Doodle name="search"/><span>sample</span></a></nav><a className="sketch-button primary nav-cta" href="#/app/new">try it free <Doodle name="pencil"/></a></header>;
}
function Footer() {
  return <footer className="site-footer"><div className="wavy-divider"/><Brand/><p>mobbs.fun · a simulation, not a prediction · for people who make things.</p><a href="#/roadmap">see what’s next ↗</a></footer>;
}
function Landing() {
  return <><SiteHeader/><main id="main-content" className="landing-main"><section className="landing-hero" aria-labelledby="landing-title"><div className="landing-copy"><span className="eyebrow">made for the things you make</span><h1 id="landing-title">meet your <span className="squiggle-word">mobbs</span> before the internet does.</h1><p className="landing-description">upload a video. get reactions from a crowd of odd little AI personalities.</p><div className="hero-actions"><a className="sketch-button primary" href="#/app/new">drop a video <Doodle name="pencil"/></a><a className="sketch-button secondary" href="#/sample">see a sample</a></div><p className="honesty-note"><span aria-hidden="true">✳</span> simulation, not a crystal ball. it doesn’t predict real reach.</p><div className="mob-row" aria-hidden="true">{[0,1,2,3,4,5,6,7].map(variant=><MobFace key={variant} variant={variant}/>)}</div><p className="made-for">made for people who make things. built with a little chaos ♡</p></div><HeroLoop/></section><section className="how-it-works" aria-labelledby="steps-title"><h2 id="steps-title">three little steps. a lot of perspectives.</h2><div className="steps-grid">{[
    ['01','upload','drop something in','a video, a useful idea, or a thing you’re testing.'],['02','flower','summon the mobbs','different tastes, opinions and very questionable habits.'],['03','mushroom','hear the chaos','see where people lingered, left, loved it or got bored.'],
  ].map(([number,icon,title,body])=><article className="step-card" key={number}><Doodle name={icon as 'upload'|'flower'|'mushroom'}/><span className="step-number">{number}</span><h3>{title}</h3><p>{body}</p></article>)}</div><p className="steps-simulation">the crowd and its responses are simulated—not real viewer feedback.</p></section></main><Footer/></>;
}
function Sample() {
  return <><SiteHeader/><main id="main-content" className="sample-page"><span className="eyebrow">sample walkthrough / illustrative data</span><h1>a nudge for your next cut.</h1><p>This example explains the editing flow. No video was uploaded and no simulation is running.</p><div className="sample-layout"><div className="sample-reel"><Doodle/><span>sample video placeholder</span></div><article className="sample-note"><span className="eyebrow">DIRECTOR’S NOTE · SAMPLE · 0:07</span><h2>the mob left here. first 2s is a logo. open on the demo instead.</h2><blockquote className="handwritten-bubble">“wait, what is this?” <small>illustrative simulated reason</small></blockquote><p>In a real report, each supported note links to the uploaded video and saved evidence. Unsupported notes are withheld.</p><a className="sketch-button primary" href="#/app/new">try your own video <Doodle name="pencil"/></a></article></div></main><Footer/></>;
}
function routeFromHash() {
  const path=window.location.hash.replace(/^#/,'');
  if(path==='/app' || path.startsWith('/app/')) return path;
  if(path==='/sample') return 'sample';
  if(path==='/roadmap') return 'roadmap';
  return 'landing';
}
export function Site() {
  const [route,setRoute]=useState(routeFromHash);
  useEffect(()=>{
    const change=()=>{setRoute(routeFromHash());window.scrollTo(0,0);};
    window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);
  },[]);
  useEffect(()=>{document.title=route.startsWith('/app')?'mobbs.fun · your next cut':route==='roadmap'?'mobbs.fun · roadmap':'mobbs.fun · meet your mobbs';},[route]);
  const isApp=route.startsWith('/app');
  const requestedRunId=/^\/app\/run\/([^/]+)$/.exec(route)?.[1];
  return <><a className="skip-link" href="#main-content" onClick={event=>{event.preventDefault();const main=document.getElementById('main-content');main?.setAttribute('tabindex','-1');main?.focus();main?.scrollIntoView();}}>skip to content</a>{isApp?<Suspense fallback={<main id="main-content" className="route-loading">getting your mobbs ready…</main>}><Workbench key={route} startFresh={route!=='/app' && !requestedRunId} requestedRunId={requestedRunId} onRunStarted={id=>window.location.replace(`#/app/run/${encodeURIComponent(id)}`)} onNewUpload={()=>{window.location.hash='/app/new';}}/></Suspense>:route==='sample'?<Sample/>:route==='roadmap'?<><SiteHeader/><main id="main-content" className="roadmap-page"><Roadmap/></main><Footer/></>:<Landing/>}</>;
}
