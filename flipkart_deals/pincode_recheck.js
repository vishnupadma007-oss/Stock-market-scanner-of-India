const {setup,svc}=require('./serviceability.js'); const fs=require('fs');
const PIN=process.argv[2]||'560072'; const F='deals_'+PIN+'.json';
(async()=>{
  const arr=JSON.parse(fs.readFileSync(F)); let {b,ctx}=await setup();
  for (let pass=0; pass<3; pass++){
    const todo=arr.filter(x=>!x.checked);
    console.error('pass',pass,'todo',todo.length);
    for(let i=0;i<todo.length;i+=5){
      const chunk=todo.slice(i,i+5); const j=await svc(ctx,chunk.map(x=>x.pid),PIN);
      for(const x of chunk){ const d=j&&j.RESPONSE&&j.RESPONSE[x.pid]; if(!d) continue; const ls=d.listingSummary||{};
        x.checked=true; x.serviceable=!!ls.serviceable; x.available=!!ls.available;
        x.delivery=(ls.deliveryInfo&&ls.deliveryInfo.primaryOption&&ls.deliveryInfo.primaryOption.text)||'';
        const fp=ls.pricing&&ls.pricing.finalPrice; if(fp) x.livePrice=fp.value; }
      await new Promise(r=>setTimeout(r,400));
    }
    fs.writeFileSync(F,JSON.stringify(arr,null,1));
  }
  console.error('checked',arr.filter(x=>x.checked).length,'serviceable',arr.filter(x=>x.serviceable).length,'of',arr.length);
  await b.close();
})();
