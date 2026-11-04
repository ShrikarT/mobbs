import {test,expect,type Page} from '@playwright/test';

// Presentation checks exercise the production React application. HTTP responses
// are controlled here; these checks do not establish API/provider integration.
async function session(page:Page, recovering=false) {
  await page.route('**/sessions',r=>r.fulfill({json:{csrf:'ui-fixture',expires_at:'2026-11-05T00:00:00Z',retention_hours:24,provider_mode:'standard'}}));
  await page.route('**/deletions',r=>r.fulfill({json:[]}));
  await page.route('**/videos',r=>r.fulfill({json:recovering?[{id:'ui-video',run_id:'ui-run',metadata:{duration_ms:4000,width:320,height:240,audio_present:false,bytes:1000,caveats:[]}}]:[]}));
}
async function noOverflow(page:Page) {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
}

test('landing CTA opens the actual app; sample and roadmap are explicit',async({page})=>{
  await session(page);
  let writes=0;
  page.on('request',r=>{if(r.method()==='POST' && /\/(videos|runs)$/.test(r.url()))writes++;});
  await page.goto('/');
  await expect(page.getByRole('heading',{level:1})).toContainText('meet your mobbs');
  await expect(page.locator('.site-footer')).toBeVisible();
  await page.getByRole('link',{name:'drop a video',exact:true}).click();
  await expect(page.locator('#file-upload')).toBeAttached();
  await expect(page.locator('.hero-heading')).toHaveText('what are we watching?');
  await expect(page.locator('.dropzone-hint')).toHaveText('MP4 · up to 60 seconds · up to 200 MB');
  await page.reload();await expect(page.locator('#file-upload')).toBeAttached();
  await page.goto('/#/sample');
  await expect(page.locator('.sample-page')).toContainText('No video was uploaded and no simulation is running.');
  await page.goto('/#/roadmap');
  await expect(page.locator('.roadmap-section')).toContainText('future plans, not available features');
  await expect(page.locator('.roadmap-item')).toHaveCount(5);
  expect(writes).toBe(0);
});

test('hero motion pauses, resumes, and respects reduced motion',async({page})=>{
  await page.setViewportSize({width:1440,height:1000});
  await page.goto('/');
  const hero=page.locator('.hero-loop');
  await expect(hero).toHaveAttribute('data-playing','true');
  await page.getByRole('button',{name:'Pause demo animation'}).click();
  await expect(hero).toHaveAttribute('data-playing','false');
  expect(await page.locator('.hero-phone').evaluate(el=>getComputedStyle(el).animationPlayState)).toBe('paused');
  await page.getByRole('button',{name:'Play demo animation'}).click();
  await expect(hero).toHaveAttribute('data-playing','true');
  await page.emulateMedia({reducedMotion:'reduce'});
  await expect(page.locator('.hero-poster')).toBeVisible();
  expect(await page.locator('.hero-phone').evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
  await expect(page.getByRole('button',{name:'Pause demo animation'})).toBeHidden();
});

test('320px routes and keyboard upload stay usable',async({page})=>{
  await session(page);
  await page.setViewportSize({width:320,height:800});
  for(const route of ['/','/#/app','/#/sample','/#/roadmap']){
    await page.goto(route);await page.getByRole('heading').first().waitFor();await noOverflow(page);
  }
  await page.goto('/#/app');
  await page.locator('#file-upload').focus();
  await expect(page.locator('#file-upload')).toBeFocused();
  await page.locator('.disclosure-box summary').click();
  await expect(page.locator('.disclosure-list')).toBeVisible();
  await page.locator('.skip-link').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  expect(new URL(page.url()).hash).toBe('#/app');
});

test('50 mobs bind saved streamed reasons, remain placed, and pause the display',async({page})=>{
  await session(page,true);
  await page.route('**/videos/ui-video/analysis',r=>r.fulfill({json:{available_profiles:['flash','test']}}));
  await page.route('**/videos/ui-video/media',r=>r.fulfill({status:204}));
  await page.route('**/runs/ui-run',r=>r.fulfill({json:{run_id:'ui-run',video_id:'ui-video',status:'simulating',stage:'simulating',sequence:2,requested:50,effective:0,failed:0,pending:50}}));
  const quote='I like the tiny demo. <img src=x onerror=alert(1)>';
  let eventNumber=1;
  await page.route('**/runs/ui-run/events*',async r=>{
    const n=eventNumber;
    const stopped=n>1;
    const data={event_id:`ui-${n}`,sequence:n,type:stopped?'persona.stopped':'persona.continued',payload:{persona_id:stopped?'p002':'p001',scene_id:0,at_ms:1200,reason:stopped?'The opening feels too slow.':quote,actions:stopped?[]:[{type:'like'}]}};
    await r.fulfill({status:200,contentType:'text/event-stream',body:`retry: 100\nevent: ${data.type}\nid: ${n}\ndata: ${JSON.stringify(data)}\n\n`});
  });
  await page.setViewportSize({width:1440,height:1100});
  await page.goto('/#/app');
  await expect(page.locator('.mob-node')).toHaveCount(50);
  await expect(page.locator('.mob-node.watching')).toHaveCount(1);
  await expect(page.locator('.handwritten-bubble')).toHaveText(`“${quote}”`);
  await expect(page.locator('.handwritten-bubble img')).toHaveCount(0);
  const positions=await page.locator('.mob-position').evaluateAll(els=>els.map(el=>(el as HTMLElement).style.cssText));
  expect(new Set(positions).size).toBe(50);
  const boxes=await page.locator('.mob-node').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};}));
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i],b=boxes[j];expect(a.x+a.w<=b.x || b.x+b.w<=a.x || a.y+a.h<=b.y || b.y+b.h<=a.y).toBeTruthy();
  }
  await page.getByRole('button',{name:/Pause view/}).click();eventNumber=2;
  await expect(page.getByText('Live display paused.',{exact:false})).toBeVisible();
  await page.waitForTimeout(650);
  await expect(page.locator('.mob-node.stopped')).toHaveCount(0);
  await page.getByRole('button',{name:/Resume view/}).click();
  await expect(page.locator('.mob-node.stopped')).toHaveCount(1);
  await page.locator('.mob-node').filter({hasText:'p001'}).focus();
  await expect(page.locator('.handwritten-bubble')).toHaveText(`“${quote}”`);
  expect(await page.locator('.mob-position').evaluateAll(els=>els.map(el=>(el as HTMLElement).style.cssText))).toEqual(positions);
  await page.setViewportSize({width:320,height:800});await noOverflow(page);
  await expect(page.locator('.mob-node')).toHaveCount(50);
});
