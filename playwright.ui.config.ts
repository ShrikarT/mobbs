import {defineConfig} from '@playwright/test';
import {existsSync} from 'node:fs';

const localBrowser='C:/Users/Shrikar/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe';
export default defineConfig({
  testDir:'./tests/ui', timeout:30000, workers:1, retries:0,
  webServer:process.env.MOBBS_UI_BASE_URL?undefined:{
    command:'npm exec vite -- --config apps/web/vite.config.ts --host 127.0.0.1 --port 58100 --strictPort',
    url:'http://127.0.0.1:58100',reuseExistingServer:!process.env.CI,
  },
  use:{
    baseURL:process.env.MOBBS_UI_BASE_URL || 'http://127.0.0.1:58100',
    launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync(localBrowser)?localBrowser:undefined)},
    screenshot:'only-on-failure',trace:'retain-on-failure',
  },
});
