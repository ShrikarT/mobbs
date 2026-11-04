import {useEffect,useState} from 'react';
import {MobbsSpace} from './MobbsSpace';
import {MobFace} from './Doodles';
import type {ProvisionalVerdict,RunState,SimulationEvent} from './types';

const phases:Record<string,string>={queued:'waiting for a turn',decoding:'opening your video',reading_video:'watching the scenes',transcribing:'listening to the audio',simulating:'the mobbs are watching',reporting:'putting your report together',report:'your report is ready'};
export function ScanExperience({state,events,verdict,videoId,paused,onPause,connectionIssue}:{state:RunState|null;events:SimulationEvent[];verdict:ProvisionalVerdict|null;videoId:string|null;paused:boolean;onPause:()=>void;connectionIssue:boolean}) {
  const [now,setNow]=useState(Date.now());const [opened]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const seconds=Math.max(0,Math.floor((now-(state?.created_at?Date.parse(state.created_at):opened))/1000));
  const count=state?.observed_reactions ?? events.filter(e=>e.type.startsWith('persona.')).length;
  const retained=verdict?.retention_pct;
  const title=retained===undefined?'your first verdict is brewing…':retained>=75?'off to a good start.':retained>=45?'a mixed first impression.':'the opening needs a nudge.';
  return <section className="scan-experience running-container wide" aria-labelledby="scan-heading">
    <header className="scan-heading-row"><div><span className="eyebrow">a little work in progress</span><h1 id="scan-heading">the mobbs are on it.</h1></div><span className="scan-clock">{Math.floor(seconds/60)}:{String(seconds%60).padStart(2,'0')}</span></header>
    <div className="scan-status-row" role="status"><span className="stage-badge">{connectionIssue?'reconnecting to your scan…':phases[state?.stage || 'queued'] || 'watching your video'}</span><span>{count?`${count} reactions saved`:'getting the crowd ready'}</span></div>
    <div className="progress-track" role="progressbar" aria-label="Scanning your video" aria-valuetext={phases[state?.stage || 'queued']} aria-busy="true"><div className="progress-bar indeterminate"/></div>
    <p className="scan-patience">A full report can take several minutes. We’ll keep updating this screen.</p>
    <div className="scan-media-grid processing-body">
      <section className="scan-room-card"><div className="scan-card-top"><strong>the mobbs space</strong><button className="small-ink-button" type="button" onClick={onPause} aria-pressed={paused}>{paused?'▶ play':'Ⅱ pause'}</button></div><MobbsSpace events={events} paused={paused} seed={state?.run_id || 'warming'}/></section>
      <aside className="scan-video-card run-video-card"><div className="scan-card-top"><strong>your cut</strong><span aria-hidden="true">↗</span></div>{videoId?<video src={`/videos/${videoId}/media`} controls playsInline preload="metadata" aria-label="Your uploaded video"/>:<div className="video-warming">your video is getting ready</div>}<p>one video. a whole lot of opinions.</p></aside>
    </div>
    <section className="early-verdict" aria-label="Early verdict"><div><span className="eyebrow">verdict / first impressions</span><h2>{title}</h2><p>{verdict?`${verdict.retained_count} of ${verdict.total_personas} mobbs stayed past the opening. This is an early simulated result; the full video can change the story.`:'The first few seconds set the mood. Your opening verdict appears as soon as the mobbs have seen them.'}</p></div><div className="verdict-first-number">{retained===undefined?<MobFace variant={2}/>:<><strong>{Math.round(retained)}<small>%</small></strong><span>stayed for the opening</span></>}</div></section>
  </section>;
}
