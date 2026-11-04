import {test,expect} from '@playwright/test';

test('live status leaves a stale queued poll when the stream reports actual progress',async({page})=>{
  const queued={run_id:'status-run',video_id:'status-video',status:'queued',stage:'queued',requested:50,effective:0,failed:0,pending:50,sequence:0};
  await page.route('**/sessions',r=>r.fulfill({json:{csrf:'test',provider_mode:'standard',retention_hours:24}}));
  await page.route('**/videos',r=>r.fulfill({json:[{id:'status-video',run_id:'status-run',metadata:{duration_ms:17000}}]}));
  await page.route('**/videos/*/analysis',r=>r.fulfill({json:{available_profiles:['test','flash']}}));
  await page.route('**/runs/status-run',r=>r.fulfill({json:queued}));
  await page.route('**/runs/status-run/events*',r=>r.fulfill({contentType:'text/event-stream',body:'event: run.snapshot\ndata: '+JSON.stringify({event_id:'snapshot',sequence:12,type:'run.snapshot',payload:{state:{...queued,status:'processing',stage:'simulating',sequence:12,observed_reactions:12}}})+'\n\n'}));
  await page.goto('/#/app/run/status-run');
  await expect(page.locator('.stage-badge')).toContainText(/watching|simulating/i);
  await page.waitForTimeout(1300);
  await expect(page.locator('.stage-badge')).not.toContainText(/queued/i);
  await expect(page.getByText(/full report can take/i)).toBeVisible();
});
