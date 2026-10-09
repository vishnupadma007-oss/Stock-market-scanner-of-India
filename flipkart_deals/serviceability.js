const { chromium } = require('playwright'); const fs=require('fs');
const UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
async function setup(){
  const b = await chromium.launch({proxy:{server:process.env.HTTPS_PROXY}});
  const ctx = await b.newContext({locale:'en-IN',userAgent:UA});
  const p = await ctx.newPage();
  await p.goto('https://www.flipkart.com/voltas-beko-243-l-frost-free-double-door-2-star-refrigerator/p/itm04fcb2947e3cf',{waitUntil:'domcontentloaded'}); await p.waitForTimeout(2000);
  return {b,ctx};
}
let host='2';
async function svc(ctx, pids, pin){
  for(let t=0;t<6;t++){
    let r; try{ r = await ctx.request.post(`https://${host}.rome.api.flipkart.com/api/3/product/serviceability`,{
      headers:{'Content-Type':'application/json','flipkart_secure':'true','X-User-Agent':UA+' FKUA/msite/0.0.4/msite/Mobile','Origin':'https://www.flipkart.com','Referer':'https://www.flipkart.com/'},
      data:{requestContext:{products:pids.map(id=>({productId:id})),marketplace:'FLIPKART'},locationContext:{pincode:pin}},timeout:30000}); }catch(e){ console.error('svc err',e.message.split('\n')[0]); await new Promise(r=>setTimeout(r,3000)); continue; }
    const j = await r.json().catch(()=>null);
    if(j && j.ERROR_MESSAGE==='DC Change'){ host=j.RESPONSE.id; continue; }
    return j;
  }
}
module.exports={setup,svc};
if (require.main===module) (async()=>{
  const {b,ctx}=await setup();
  for (const pin of ['560072','110001']){ const j=await svc(ctx,['RFRHM2WH3ZUAQ6XB'],pin); fs.writeFileSync('svc_'+pin+'.json',JSON.stringify(j)); console.log(pin, host, JSON.stringify(j).slice(0,200)); }
  await b.close();
})();
