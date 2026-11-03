# DGFT portal snippets

Each block is the body of an async function run by `scripts/browser_server.js`.
Save it to a file in the work dir and send it with
`curl -s --max-time 180 localhost:9555 --data-binary @file.js`.
In scope: `page`, `ctx`, `WORK`, `fs`. Replace `<<...>>` placeholders first.

Facts learned the hard way:
- Login popup button id is `#skip`; fields `#username`, `#password`, `#txt_Captcha`; CAPTCHA image `img[alt=Captcha]` (refresh: `.fa-refresh` / `[onclick*=aptcha]`). The image sometimes fails to load: check `naturalWidth > 0` and refresh before screenshotting.
- After login DGFT may show a **Change Password** page. "Your password will expire in N days" has a **Cancel** button (`fn_cancel`) – click it. "Your password has expired" has no Cancel: stop and ask the user to change it themselves on their own device, then log in with the new password. Never invent or set a password.
- Officer search page: `menuAct('web?requestType=ApplicationRH&actionVal=RCMCProcessingPage&screenId=9000012381&menuCode=306000052&auditUSFlag=true&menuCode=306000059&auditUSFlag=true')`. Results are a jQuery DataTable whose row objects have `iecId, firmName, fileDate, fileNo (html), rcmcNumber, applicationType_Value, status_Value, pendingWith, action (html)`.
- Open a file: `fileDataRCMC('<<FILE_NO>>')`. Tabs are `button.editDesc` / `button.custom-collapse-btn` with text Basic Details, RCMC Details, Attachments, Declaration, e-Sign Details, Payment Details, File History, Details to be printed in RCMC Certificate. Clicking a tab toggles it; click again if its content is not visible.
- File history: `viewFileHistory(...)` call is inside each row's `action` html. Set the `select[name$=_length]` to 100 to see all rows.
- Downloading the application PDF: `#printBtn` (the file-number link on the file page). PDF attachments download via a popup tab; JPG attachments open in a viewer popup – screenshot the `<img>` there. Close extra tabs after each download or the page hangs.
- Text limits: deficiency remark 200 chars, attachment remark 40 chars, send remark 200 chars.
- Two Reji accounts exist in the Send list: "K REJI,Administrator" and "reji k,Administrator". Files have been coming from and going to **reji k,Administrator**. Confirm with the user if unsure.

## 1. Open login and capture CAPTCHA
```js
await page.goto('https://www.dgft.gov.in/CP/', {waitUntil:'domcontentloaded', timeout:60000});
await page.waitForTimeout(4000);
await page.click('#skip'); await page.waitForTimeout(4000);
await page.fill('#username', '<<USER_ID>>');
await page.fill('#password', '<<PASSWORD>>');
const img = page.locator('img[alt=Captcha]');
for (let i=0;i<5;i++){ if (await img.evaluate(i=>i.complete&&i.naturalWidth>0)) break;
  await page.locator('.fa-refresh:visible, [onclick*=aptcha]:visible').first().click().catch(()=>{}); await page.waitForTimeout(3000); }
const b = await img.boundingBox();
await page.screenshot({path: WORK+'/captcha.png', clip:{x:b.x-25,y:b.y-20,width:b.width+50,height:b.height+40}});
await page.screenshot({path: WORK+'/loginpage.png'});
return 'ok';
```
Send both PNGs to the user with SendUserFile and ask them to type the CAPTCHA. Do not solve it yourself.

## 2. Submit CAPTCHA
```js
await page.fill('#txt_Captcha','<<CAPTCHA>>');
await page.click('button:has-text("Login"):visible >> nth=0');
await page.waitForTimeout(9000);
let t = await page.innerText('body');
if (/will expire in/i.test(t) && /Current Password/.test(t)) { await page.click('text=Cancel >> visible=true'); await page.waitForTimeout(8000); t = await page.innerText('body'); }
const err = await page.evaluate(()=>[...document.querySelectorAll('span,div,p,label')].filter(e=>e.offsetParent && e.children.length==0 && /incorrect|correct Captcha|invalid/i.test(e.innerText)).map(e=>e.innerText.trim()));
return {loggedIn: /Password Expires|Dashboard/.test(t) && !/Current Password/.test(t), expired: /password has expired/i.test(t), err};
```
"Please enter correct Captcha" → refresh and re-capture (snippet 1 from the CAPTCHA lines).

## 3. Dashboard counts and "pending with" a person (In Progress)
```js
await page.evaluate(()=>menuAct('web?requestType=ApplicationRH&actionVal=RCMCProcessingPage&screenId=9000012381&menuCode=306000052&auditUSFlag=true&menuCode=306000059&auditUSFlag=true'));
await page.waitForTimeout(7000);
const ip = await page.evaluate(()=>[...document.querySelector('#status').options].find(o=>/InProgress/i.test(o.text)).value);
await page.selectOption('#status', ip);
await page.click('button:has-text("Search"):visible'); await page.waitForTimeout(9000);
return await page.evaluate(()=>{ const rows = jQuery('table.dataTable').first().DataTable().rows().data().toArray();
  const counts = {}; rows.forEach(r=>{ const k=(r.pendingWith||'').trim()||'(unassigned)'; counts[k]=(counts[k]||0)+1; });
  const mine = rows.filter(r=>/<<NAME_REGEX e.g. vishnu>>/i.test(r.pendingWith||'')).map(r=>[r.firmName,r.iecId,r.fileDate,r.fileNo.replace(/<[^>]+>/g,''),r.applicationType_Value,r.status_Value]);
  return {total: rows.length, counts, mine}; });
```

## 4. Search by firm name and read file history
```js
await page.evaluate(()=>menuAct('web?requestType=ApplicationRH&actionVal=RCMCProcessingPage&screenId=9000012381&menuCode=306000052&auditUSFlag=true&menuCode=306000059&auditUSFlag=true'));
await page.waitForTimeout(7000);
await page.fill('#firmName','<<FIRM_FRAGMENT>>');
await page.click('button:has-text("Search"):visible'); await page.waitForTimeout(7000);
const rows = await page.evaluate(()=>jQuery('table.dataTable').first().DataTable().rows({search:'applied'}).data().toArray().map(r=>({iec:r.iecId, firm:r.firmName, date:r.fileDate, file:r.fileNo.replace(/<[^>]+>/g,''), rcmc:r.rcmcNumber, type:r.applicationType_Value, status:r.status_Value, with:r.pendingWith, hist:(r.action.match(/viewFileHistory\([^)]*\)/)||[''])[0]})));
const out = [];
for (const r of rows) {
  if (!r.hist) continue;
  await page.evaluate(r.hist); await page.waitForTimeout(6000);
  const sel = page.locator('select[name$=_length]:visible'); for (let i=0;i<await sel.count();i++) await sel.nth(i).selectOption('100').catch(()=>{});
  await page.waitForTimeout(1500);
  r.history = await page.evaluate(()=>[...document.querySelectorAll('table')].filter(t=>t.offsetParent && /Remarks/.test(t.innerText)).flatMap(t=>[...t.querySelectorAll('tbody tr')].map(tr=>[...tr.cells].slice(1,6).map(c=>c.innerText.replace(/\s+/g,' ').trim()).join(' | '))));
  out.push(r);
  await page.click('text=Back >> visible=true').catch(()=>{}); await page.waitForTimeout(4000);
}
return rows.map(r=>out.find(o=>o.file===r.file)||r);
```

## 5. Download the application PDF and all attachments
```js
const FILE='<<FILE_NO>>'; const DIR = WORK+'/'+FILE; fs.mkdirSync(DIR+'/att', {recursive:true});
await page.evaluate(()=>menuAct('web?requestType=ApplicationRH&actionVal=RCMCProcessingPage&screenId=9000012381&menuCode=306000052&auditUSFlag=true&menuCode=306000059&auditUSFlag=true'));
await page.waitForTimeout(7000);
await page.evaluate(f=>fileDataRCMC(f), FILE); await page.waitForTimeout(9000);
const grab = async (clickFn, to) => {
  const dlp = new Promise(res => { page.once('download', res); ctx.once('page', p => p.once('download', res)); });
  await clickFn();
  const d = await Promise.race([dlp, new Promise(r=>setTimeout(()=>r(null),25000))]);
  if (d) await d.saveAs(to);
  for (const p of ctx.pages().slice(1)) await p.close().catch(()=>{});
  return !!d; };
const log = [];
log.push('application: '+await grab(()=>page.click('#printBtn'), DIR+'/Application_'+FILE+'.pdf'));
for (let t=0;t<3 && !(await page.locator('a.editor_edit:visible').count());t++){ await page.locator('button.editDesc:visible',{hasText:'Attachments'}).first().click(); await page.waitForTimeout(4000); }
const n = await page.locator('a.editor_edit:visible').count();
for (let i=0;i<n;i++) {
  for (let t=0;t<3 && (await page.locator('a.editor_edit:visible').count())<=i;t++){ await page.locator('button.editDesc:visible',{hasText:'Attachments'}).first().click(); await page.waitForTimeout(4000); }
  await page.locator('a.editor_edit:visible').nth(i).click(); await page.waitForTimeout(2500);
  const type = await page.evaluate(()=>{ const s=document.querySelector('#attachmentType'); return s ? s.options[s.selectedIndex].text : '?'; });
  const links = page.locator('a[onclick*="viewAttachment_"]:visible'); const k = await links.count();
  for (let j=0;j<k;j++) {
    const name=(await links.nth(j).innerText()).trim(); const base=DIR+'/att/'+i+'_'+j+'_'+name.replace(/[^\w.]+/g,'_');
    if (/\.pdf$/i.test(name)) { log.push(type+' => '+name+' '+await grab(()=>links.nth(j).click(), base)); continue; }
    const popP = ctx.waitForEvent('page', {timeout:20000}); await links.nth(j).click(); const pop = await popP;
    await pop.waitForLoadState('load').catch(()=>{}); await pop.waitForTimeout(4000);
    const im = pop.locator('img').first(); if (await im.count()) await im.screenshot({path: base.replace(/\.\w+$/,'')+'.png'}); else await pop.screenshot({path: base+'.png', fullPage:true});
    await pop.close(); log.push(type+' => '+name+' (image screenshot)');
  }
}
return log;
```
Then read PDFs with `pdftotext -layout`; scanned ones (little text) with `pdftoppm -r 80 -png` and view the images.

## 6. Mark deficient (only after the user approves the remark)
```js
await page.evaluate(f=>fileDataRCMC(f), '<<FILE_NO>>'); await page.waitForTimeout(9000);
await page.click('button:has-text("Mark Deficient"):visible'); await page.waitForTimeout(4000);
await page.fill('#markdeffRemarks', '<<REMARK, max 200 chars>>');
await page.check('#rcmcDefiAmountPayNo');            // additional fee? No
await page.locator('#btnNext:visible').first().click(); await page.waitForTimeout(6000);
return await page.evaluate(()=>[...document.querySelectorAll('.modal')].filter(e=>getComputedStyle(e).display=='block').map(e=>e.innerText.trim().slice(0,200)));
```
Expect "File has been marked deficient". Verify in file history.

## 7. Upload the inspection report (type "EPC Officer Added")
```js
// file already open (snippet 5 opening lines)
for (let t=0;t<3 && !(await page.locator('#attachmentType:visible').count());t++){ await page.locator('button.editDesc:visible',{hasText:'Attachments'}).first().click(); await page.waitForTimeout(4000); }
const v = await page.evaluate(()=>[...document.querySelector('#attachmentType').options].find(o=>/EPC Officer Added/.test(o.text)).value);
await page.selectOption('#attachmentType', v); await page.waitForTimeout(3000);
await page.fill('#remark','INSPECTION REPORT WITH ENCLOSURES');   // max 40 chars
await page.setInputFiles('#importFile'+v, '<<ABS_PATH_TO_PDF (<5 MB)>>'); await page.waitForTimeout(8000);
await page.click('button:has-text("Upload Attachments"):visible'); await page.waitForTimeout(10000);
const msgs = await page.evaluate(()=>[...document.querySelectorAll('.modal')].filter(e=>getComputedStyle(e).display=='block').map(e=>e.innerText.trim().slice(0,200)));
await page.locator('.modal button:visible',{hasText:'OK'}).first().click().catch(()=>{});
return msgs;   // expect "Attachment has been uploaded successfully."
```

## 8. Read "Details to be printed in RCMC Certificate"
```js
await page.locator('button.custom-collapse-btn:visible',{hasText:'Details to be printed in RCMC Certificate'}).first().click(); await page.waitForTimeout(5000);
return await page.evaluate(()=>({reg: document.getElementById('registeredAs').selectedOptions[0].text,
  regOptions: [...document.getElementById('registeredAs').options].map(o=>o.text),
  cat: document.getElementById('membCatgY').selectedOptions[0].text,
  catOptions: [...document.getElementById('membCatgY').options].map(o=>o.text),
  issue: document.getElementById('certIssueDate').value, valid: document.getElementById('certValidUpto').value,
  years: [...document.getElementById('numberOfYearSelect').selectedOptions].map(o=>o.text),
  goods: document.getElementById('certGoodsDesc').value, remark: document.getElementById('certAdditionalRemark').value}));
```
Also read Basic Details → "RCMC Details" table for an existing RCMC's issue/expiry dates.

## 9. Set and save certificate details (only after the user approves every value)
```js
await page.evaluate(([cat, issue, valid])=>{
  const c=document.getElementById('membCatgY'); c.value=[...c.options].find(o=>o.text.trim()===cat).value;
  if (window.jQuery) jQuery(c).trigger('chosen:updated').trigger('change');
  for (const [id,v] of [['certIssueDate',issue],['certValidUpto',valid]]) { const e=document.getElementById(id);
    try { jQuery(e).datepicker('setDate', v); } catch(x){} e.value=v; jQuery(e).trigger('change'); }
}, ['<<New Member|Renewal|Amendment>>', '<<DD/MM/YYYY>>', '<<DD/MM/YYYY>>']);
await page.keyboard.press('Escape').catch(()=>{});
const cb = page.locator('#declaration'); if (!(await cb.isChecked())) await cb.check({force:true});
await page.locator('#btnSaveCertifciateAddDetails:visible').click(); await page.waitForTimeout(6000);
const msgs = await page.evaluate(()=>[...document.querySelectorAll('.modal')].filter(e=>getComputedStyle(e).display=='block').map(e=>e.innerText.trim()));
await page.locator('.modal button:visible',{hasText:'OK'}).first().click().catch(()=>{});
return msgs;   // expect "Details has been saved successfully."
```

## 10. Send the file to another officer (only after the user approves)
```js
await page.locator('button:visible',{hasText:/^Send$/}).first().click(); await page.waitForTimeout(4000);
const modal = page.locator('.modal:visible',{hasText:'Send to User'});
await modal.locator('#sendRemarks').fill('<<REMARK, max 200 chars>>');
await page.evaluate(name=>{ const s=[...document.querySelectorAll('#epcOfficer')].find(x=>x.offsetParent); s.value=[...s.options].find(o=>o.text.trim()===name).value; jQuery(s).trigger('chosen:updated').trigger('change'); }, '<<reji k,Administrator>>');
await modal.locator('#btnNext').click(); await page.waitForTimeout(4000);
await page.locator('.modal:visible',{hasText:'Do you wish to proceed'}).locator('button:visible',{hasText:/^Yes$/}).first().click();
await page.waitForTimeout(7000);
return await page.evaluate(()=>[...document.querySelectorAll('.modal')].filter(e=>getComputedStyle(e).display=='block').map(e=>e.innerText.trim()));
// expect "File has been sent successfully" – then confirm via file history (snippet 4)
```

## 11. Logout and clean up
```js
await page.evaluate(()=>fnLogout()); await page.waitForTimeout(3000);
const b = page.locator('button:visible',{hasText:/yes|ok|confirm|logout/i}); if (await b.count()) { await b.first().click(); await page.waitForTimeout(4000); }
await ctx.clearCookies();
return {url: page.url(), loggedOut: !/Dashboard/.test(await page.innerText('body'))};
```
Then `pkill -f browser_server.js` and delete downloaded exporter documents from the work dir.
