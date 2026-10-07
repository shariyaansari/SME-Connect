const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  
  page.on('pageerror', err => console.log('PAGE ERROR:', err.toString()));
  page.on('console', msg => {
    if(msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });
  
  await page.goto('http://localhost:5173');
  
  await page.waitForSelector('button');
  
  // Click Admin Demo
  const buttons = await page.$$('button');
  for(let btn of buttons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if(text.includes('Admin Demo')) {
      await btn.click();
      break;
    }
  }
  
  await new Promise(r => setTimeout(r, 3000));
  
  await browser.close();
})();
