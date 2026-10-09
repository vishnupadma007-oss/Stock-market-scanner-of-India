const { chromium } = require('playwright');
const fs=require('fs');
// Usage: NODE_PATH=$(npm root -g) node fridge_scraper.js  -> writes deals.json (Flipkart India refrigerator listings with price, MRP, % off, link)
(async()=>{
  const b = await chromium.launch({proxy:{server:process.env.HTTPS_PROXY}});
  const ctx = await b.newContext({locale:'en-IN', userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'});
  const p = await ctx.newPage();
  const all = new Map();
  const bases = [
   'https://www.flipkart.com/search?q=refrigerator&p%5B%5D=facets.discount_range_v1%255B%255D%3D50%2525%2Bor%2Bmore',
   'https://www.flipkart.com/search?q=refrigerator&p%5B%5D=facets.discount_range_v1%255B%255D%3D40%2525%2Bor%2Bmore',
   'https://www.flipkart.com/search?q=refrigerator&sort=popularity',
   'https://www.flipkart.com/search?q=refrigerator&sort=price_desc',
  ];
  for (const base of bases) for (let pg=1; pg<=8; pg++){
    try{
      await p.goto(base+'&page='+pg,{waitUntil:'domcontentloaded',timeout:60000});
      await p.waitForTimeout(2500);
      const items = await p.evaluate(()=>{
        const out=[];
        for (const a of document.querySelectorAll('a[href*="/p/itm"]')){
          const leaves=[...a.querySelectorAll('div,span')].filter(e=>e.children.length===0||e.tagName==='SPAN');
          const rupees=[...a.querySelectorAll('div')].filter(e=>e.children.length===0 && /^₹[\d,]+$/.test(e.innerText.trim())).map(e=>+e.innerText.replace(/[₹,]/g,''));
          const offEl=[...a.querySelectorAll('span')].find(e=>/^\d+% off$/.test(e.innerText.trim()));
          const img=a.querySelector('img[alt]');
          const t=a.innerText;
          if(rupees.length<2||!offEl) continue;
          out.push({href:a.href, name:(img&&img.alt)||t.split('\n')[1], price:rupees[0], mrp:rupees[1], off:parseInt(offEl.innerText),
            rating:(t.match(/\n(\d\.\d)([\d,]+) Ratings/)||[])[1], ratings:(t.match(/(\d\.\d)([\d,]+) Ratings/)||[])[2],
            tag:/Lowest Price/.test(t)?'Lowest Price Live':'', exch:(t.match(/Upto ₹[\d,]+ Off on Exchange/)||[''])[0]});
        }
        return out;
      });
      let n=0;
      for (const it of items){ const key=it.href.split('?')[0]; if(!all.has(key)){ it.link=key; delete it.href; all.set(key,it); n++; } }
      console.error(base.slice(-40), pg, items.length, 'new', n);
      if(items.length===0) break;
    }catch(e){console.error('err',pg,e.message)}
  }
  const arr=[...all.values()].filter(x=>/refrigerator|fridge/i.test(x.name));
  fs.writeFileSync('deals.json', JSON.stringify(arr,null,1));
  console.error('total', all.size, 'fridges', arr.length);
  await b.close();
})();
