import {test,expect,type Page} from '@playwright/test';

const old={id:'old-video',run_id:'old-run',created_at:'2026-11-04T08:00:00Z',metadata:{duration_ms:17000,width:320,height:240,audio_present:false,bytes:1000,caveats:[]}};
const fresh={...old,id:'new-video',run_id:'new-run'};
async function setup(page:Page){
  await page.route('**/sessions',r=>r.fulfill({json:{csrf:'ui-only',expires_at:'2026-11-05T00:00:00Z',retention_hours:24,provider_mode:'recorded'}}));
  await page.route('**/deletions',r=>r.fulfill({json:[]}));
  await page.route('**/videos/*/analysis',r=>r.fulfill({json:{available_profiles:['flash','test']}}));
  await page.route('**/videos/*/media',r=>r.fulfill({status:204}));
  await page.route('**/runs/*/events*',r=>r.fulfill({contentType:'text/event-stream',body:': waiting\n\n'}));
}

test('drop a video stays on a fresh upload even when this session owns a previous scan',async({page})=>{
  await setup(page);
  await page.route('**/videos',r=>r.fulfill({json:[old]}));
  let oldReads=0;
  await page.route('**/runs/old-run',r=>{oldReads++;return r.fulfill({json:{run_id:'old-run',video_id:'old-video',status:'simulating',stage:'simulating',requested:3,pending:3,effective:0,failed:0,sequence:0}});});
  await page.goto('/');await page.getByRole('link',{name:'drop a video',exact:true}).click();
  await expect(page.locator('#file-upload')).toBeVisible();
  await expect(page.getByText('previous scans (1)',{exact:true})).toBeVisible();
  await page.reload();await expect(page.getByText('previous scans (1)',{exact:true})).toBeVisible();
  await expect(page.locator('#file-upload')).toBeVisible();expect(oldReads).toBe(0);
  await page.getByText('previous scans (1)',{exact:true}).click();
  await page.getByRole('link',{name:/previous scan/}).click();
  await expect(page.locator('.running-container')).toBeVisible();
  await expect.poll(()=>oldReads).toBeGreaterThan(0);
});

test('a late previous-scan response cannot replace the new run; reload keeps the new run',async({page})=>{
  await setup(page);
  let created=false,uploads=0,runs=0,oldReads=0,firstList=true;
  let sessionRequests=0,sessionsAtUpload=0;
  await page.route('**/sessions',async r=>{
    sessionRequests++;await new Promise(resolve=>setTimeout(resolve,300));
    await r.fulfill({json:{csrf:'ui-only',expires_at:'2026-11-05T00:00:00Z',retention_hours:24,provider_mode:'recorded'}});
  });
  await page.route('**/videos',async r=>{
    if(r.request().method()==='POST'){uploads++;sessionsAtUpload=sessionRequests;return r.fulfill({status:201,json:{video_id:'new-video',status:'accepted'}});}
    const list=created?[fresh,old]:[old];
    if(firstList){firstList=false;await new Promise(resolve=>setTimeout(resolve,700));}
    await r.fulfill({json:list});
  });
  await page.route('**/runs',r=>{created=true;runs++;return r.fulfill({status:202,json:{run_id:'new-run',status:'queued'}});});
  await page.route('**/runs/*',r=>{
    const isOld=r.request().url().endsWith('/old-run');if(isOld)oldReads++;
    return r.fulfill({json:{run_id:isOld?'old-run':'new-run',video_id:isOld?'old-video':'new-video',status:'simulating',stage:'simulating',requested:3,pending:3,effective:0,failed:0,sequence:0}});
  });
  await page.goto('/');await page.getByRole('link',{name:'drop a video',exact:true}).click();
  await page.locator('#file-upload').setInputFiles({name:'new.mp4',mimeType:'video/mp4',buffer:Buffer.from('UI-only controlled HTTP fixture')});
  await expect(page).toHaveURL(/#\/app\/run\/new-run$/);
  await expect(page.locator('video')).toHaveAttribute('src','/videos/new-video/media');
  await page.waitForTimeout(850);expect(oldReads).toBe(0);
  await page.reload();await expect(page.locator('video')).toHaveAttribute('src','/videos/new-video/media');
  expect(uploads).toBe(1);expect(runs).toBe(1);expect(oldReads).toBe(0);
  expect(sessionsAtUpload).toBe(1);
});
