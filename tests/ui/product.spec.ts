import {test,expect,type Page} from '@playwright/test';
const metric=(observed:number)=>({kind:'simulation_range',unit:'percent',observed,denominator:50,range:{low:observed-4,high:observed+4,method:'illustrative'},evidence_ids:[]});
const report={duration_ms:17000,cast:{profile:'flash',requested:50,effective:50,failed:0,pending:0,stopped:18,status:'complete'},
  manifest:{profile:'flash',provider_mode:'synthetic',requested:50},
  scores:{hook:metric(96),pacing:metric(78),clarity:metric(82),cta:metric(76)},completion:metric(64),
  engagement:{like:metric(36),share:metric(6),save:metric(22),comment:metric(10),follow:metric(14)},
  retention:[{scene_id:0,start_ms:0,end_ms:3000,entrants:50,stopped:2,continued:48,survival:metric(96),drop_rate:metric(4)},{scene_id:1,start_ms:3000,end_ms:8000,entrants:48,stopped:9,continued:39,survival:metric(78),drop_rate:metric(19)},{scene_id:2,start_ms:8000,end_ms:17000,entrants:39,stopped:7,continued:32,survival:metric(64),drop_rate:metric(18)}],
  notes:[{id:'note1',start_ms:3000,end_ms:8000,interpretation:'The screen changes before the payoff is clear.',fix:'Hold the useful moment a little longer.',quotes:[{text:'wait, show me that again',evidence_id:'quote1'}],evidence_refs:['quote1']}],
  comments:[{evidence_id:'comment1',text:'wait, that’s actually handy',start_ms:3000},{evidence_id:'comment2',text:'show me one more example',start_ms:8000}],
  observations:[],evidence:[],coverage:{transcript:true,ocr:true},methodology:{range_kind:'simulation_resampling_not_confidence',assumptions:[]},caveats:[],
  trust:{mode:'synthetic',model_ids:['muse-spark-1.3','muse-voice-transcribe-1.0'],total_cost_usd:'illustrative preview',limitations:[]}};
async function setup(page:Page,ready=false){
 await page.route('**/sessions',r=>r.fulfill({json:{csrf:'test',provider_mode:'standard',retention_hours:24}}));
 await page.route('**/videos',r=>r.fulfill({json:[{id:'product-video',run_id:'product-run',metadata:{duration_ms:17000}}]}));
 await page.route('**/videos/*/analysis',r=>r.fulfill({json:{available_profiles:['flash','test']}}));
 await page.route('**/videos/*/media',r=>r.fulfill({status:204}));
 await page.route('**/runs/product-run',r=>r.fulfill({json:{run_id:'product-run',video_id:'product-video',status:ready?'complete':'processing',stage:ready?'report':'simulating',sequence:20,requested:50,effective:ready?50:5,pending:ready?0:45,failed:0,observed_reactions:20}}));
 const events=Array.from({length:20},(_,i)=>({event_id:`e${i}`,sequence:i+1,type:'persona.continued',payload:{persona_id:`p${String(i+1).padStart(3,'0')}`,scene_id:0,reason:'A long underlying reason is retained for evidence, not shown as a giant inspector.',quick_reaction:['okay, i’m in!','that’s handy ♡','show me more'][i%3],actions:['like']}}));
 await page.route('**/runs/product-run/events*',r=>r.fulfill({contentType:'text/event-stream',body:events.map(e=>`event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join('')}));
 await page.route('**/runs/product-run/report',r=>r.fulfill({json:report}));
}
test('mobbs visit briefly with nearby tiny thoughts, pause, and never become a 50-node roster',async({page})=>{
 await setup(page);await page.goto('/#/app/run/product-run');
 await expect(page.locator('.mob-visitor').first()).toBeVisible();
 await page.waitForTimeout(3000);
 expect(await page.locator('.mob-visitor').count()).toBeLessThanOrEqual(3);
 await expect(page.locator('.mob-reaction-inspector')).toHaveCount(0);
 await expect(page.locator('body')).not.toContainText(/p00[1-9]/);
 await page.getByRole('button',{name:/pause/}).click();
 const before=await page.locator('.mobbs-room').textContent();
 await page.waitForTimeout(2000);expect(await page.locator('.mobbs-room').textContent()).toBe(before);
 await page.getByRole('button',{name:/play/}).click();
 const key=await page.locator('.mob-visitor-position').first().getAttribute('data-appearance');
 await page.waitForTimeout(5500);
 expect(await page.locator('.mob-visitor-position').first().getAttribute('data-appearance')).not.toBe(key);
 await page.screenshot({path:'C:/Users/Shrikar/.codex/tmp/mobbs-app-design/scan-product-preview.png',fullPage:true});
});
test('report presents a verdict, real counts, attention and next edits without empty developer cards',async({page})=>{
 await setup(page,true);await page.goto('/#/app/run/product-run');
 await expect(page.locator('.product-report')).toBeVisible();
 await expect(page.locator('.action-like')).toContainText('18');
 await expect(page.locator('.action-follow')).toContainText('7');
 await expect(page.locator('body')).not.toContainText('Unavailable');
 await expect(page.locator('body')).not.toContainText('Executive finding');
 await expect(page.getByRole('img',{name:/Audience retention/})).toBeVisible();
 await expect(page.getByText('Design preview · illustrative data.')).toBeVisible();
 await page.screenshot({path:'C:/Users/Shrikar/.codex/tmp/mobbs-app-design/report-product-preview.png',fullPage:true});
 for(const width of [375,320]){
  await page.setViewportSize({width,height:850});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
 }
});
