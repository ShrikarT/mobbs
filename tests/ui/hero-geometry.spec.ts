import {test,expect} from '@playwright/test';

test('animated SVG characters keep their intended size through every hero beat',async({page})=>{
  await page.setViewportSize({width:1911,height:1000});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.goto('/');
  await expect(page.locator('.hero-loop')).toHaveClass(/is-ready/);
  for(const time of [1000,3300,4800,7000,10000,14000,17000,19000,19210]){
    const oversized=await page.locator('.hero-loop').evaluate((root,time)=>{
      for(const animation of root.getAnimations({subtree:true})){animation.pause();animation.currentTime=time;}
      const width=root.getBoundingClientRect().width;
      return [...root.querySelectorAll('.hero-laptop .mob-face,.hero-laptop .doodle')].filter(el=>{
        const bounds=el.getBoundingClientRect();return bounds.width>width*.16 || bounds.height>width*.16;
      }).length;
    },time);
    expect(oversized,`oversized SVG at ${time}ms`).toBe(0);
  }
});
