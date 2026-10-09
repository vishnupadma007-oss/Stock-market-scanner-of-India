// Usage: NODE_PATH=$(npm root -g) node pincode_deals.js 560072 && node pincode_recheck.js 560072
// Scrapes Flipkart fridges <= Rs 30,000 and checks delivery to the pincode via Flipkart's serviceability API.
const {setup,svc}=require('./serviceability.js'); const fs=require('fs');
const PIN=process.argv[2]||'560072';
(async()=>{
  const {b,ctx}=await setup(); const p=await ctx.newPage();
  const all=new Map();
  const pf='&p%5B%5D=facets.price_range.from%3DMin&p%5B%5D=facets.price_range.to%3D30000';
  const bases=['popularity','price_asc','price_desc','recency_desc'].map(s=>'https://www.flipkart.com/search?q=refrigerator&sort='+s+pf);
  for(const base of bases) for(let pg=1;pg<=15;pg++){
    try{
      await p.goto(base+'&page='+pg,{waitUntil:'domcontentloaded',timeout:60000}); await p.waitForTimeout(2000);
      const items=await p.evaluate(()=>[...document.querySelectorAll('a[href*="/p/itm"]')].map(a=>{
        const rupees=[...a.querySelectorAll('div')].filter(e=>e.children.length===0&&/^₹[\d,]+$/.test(e.innerText.trim())).map(e=>+e.innerText.replace(/[₹,]/g,''));
        const offEl=[...a.querySelectorAll('span')].find(e=>/^\d+% off$/.test(e.innerText.trim()));
        const img=a.querySelector('img[alt]'); const t=a.innerText; const u=new URL(a.href);
        return {pid:u.searchParams.get('pid'), link:u.origin+u.pathname+'?pid='+u.searchParams.get('pid'), name:(img&&img.alt)||'', price:rupees[0], mrp:rupees[1]||rupees[0], off:offEl?parseInt(offEl.innerText):0,
          rating:(t.match(/(\d\.\d)([\d,]+) Ratings/)||[])[1], ratings:(t.match(/(\d\.\d)([\d,]+) Ratings/)||[])[2]};
      }).filter(x=>x.pid&&x.price));
      let n=0; for(const it of items) if(!all.has(it.pid)){all.set(it.pid,it);n++;}
      console.error(base.split('sort=')[1].slice(0,12),pg,items.length,'new',n);
      if(!items.length) break;
    }catch(e){console.error('err',e.message)}
  }
  const arr=[...all.values()].filter(x=>/refrigerator/i.test(x.name)&&x.price<=30000);
  console.error('candidates',arr.length); fs.writeFileSync('cands_'+PIN+'.json',JSON.stringify(arr));
  for(let i=0;i<arr.length;i+=5){
    const chunk=arr.slice(i,i+5); const j=await svc(ctx,chunk.map(x=>x.pid),PIN);
    for(const x of chunk){ const d=j&&j.RESPONSE&&j.RESPONSE[x.pid]; const ls=d&&d.listingSummary;
      x.serviceable=!!(ls&&ls.serviceable); x.available=!!(ls&&ls.available);
      x.delivery=ls&&ls.deliveryInfo&&ls.deliveryInfo.primaryOption&&ls.deliveryInfo.primaryOption.text||'';
      const fp=ls&&ls.pricing&&ls.pricing.finalPrice; if(fp) x.livePrice=fp.value; }
  }
  fs.writeFileSync('deals_'+PIN+'.json',JSON.stringify(arr,null,1));
  console.error('serviceable',arr.filter(x=>x.serviceable).length,'of',arr.length);
  await b.close();
})();
