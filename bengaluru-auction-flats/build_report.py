import json,re,datetime as dt
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
NOW=dt.datetime(2026,10,7,5,50,tzinfo=dt.timezone.utc)
IST=dt.timezone(dt.timedelta(hours=5,minutes=30))
def p(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
def ist(s,fmt='%d %b %Y, %I:%M %p'): d=p(s); return d.astimezone(IST).strftime(fmt) if d else '-'
def lakh(v): v=float(v or 0); return f"{v/1e7:.2f} Cr" if v>=1e7 else f"{v/1e5:.2f} L"
def area(t):
    m=re.findall(r'(\d[\d,]*\.?\d*)\s*(?:sq\.?\s*ft|sqft|sft|square\s*feet|sq\.?\s*feet)',t,re.I)
    v=[float(x.replace(',','')) for x in m if 300<=float(x.replace(',',''))<=6000]
    return f"{max(v):,.0f} sq ft" if v else '-'
def bhk(t):
    m=re.search(r'(\d|one|two|three|four)\s*-?\s*(?:bhk|bed\s*room|bedroom)',t,re.I)
    if not m: return ''
    w={'one':'1','two':'2','three':'3','four':'4'}.get(m.group(1).lower(),m.group(1)); return w+' BHK'
rows=[]
for x in json.load(open('out/baanknet_raw.json')):
    if x['auctionTo']<'2026-10-07T05:50' or x['propertySubType']!='Flat': continue
    a=' '.join(x['address'].split())
    rows.append(dict(src='BAANKNET',id=str(x['auctionId']),pid=x['propertyUniqueId'],when=x['auctionFrom'],bank=x['propertyBankName'],branch=x['propertyBranchName'] or '',
      loc=(x.get('locality') or '').title(),pin=x.get('pincode') or '',addr=a,area=area(a),bhk=bhk(a),res=x['reservePrice'],emd=float(x['emd'] or 0),emdEnd=x['emdEnd'],
      poss=x.get('propertyPossessionType') or '-',contact=f"{x.get('inspectionName') or ''} {x.get('inspectionMobileNo') or ''}".strip(),
      insp=f"{ist(x['inspectionStart'],'%d %b')}" if x.get('inspectionStart') else '-',loan='Yes' if x.get('isLoanAvailable') else ''))
c1=[x for x in json.load(open('out/c1_karnataka.json')) if x[1]=='242543'][0]
a=' '.join(c1[3].split())
rows.append(dict(src='bankeauctions.com',id=c1[1],pid='-',when='2026-10-15T05:30:00Z',bank=c1[2],branch='',loc='Kadatamale, Hesaraghatta Hobli (Provident Welworth City)',pin='',addr=a[:600],area='1,075 sq ft',bhk='3 BHK',res=float(c1[6]),emd=float(c1[7]),emdEnd=None,poss='-',contact='See sale notice on bankeauctions.com',insp='-',loan=''))
rows.sort(key=lambda r:r['when'])
for r in rows: r['emdOpen']= (r['emdEnd'] is None) or p(r['emdEnd'])>NOW
json.dump(rows,open('out/bengaluru_flats.json','w'),indent=1,default=str)

ss=getSampleStyleSheet()
sm=ParagraphStyle('sm',parent=ss['Normal'],fontSize=7.2,leading=8.8)
smb=ParagraphStyle('smb',parent=sm,fontName='Helvetica-Bold')
h=ParagraphStyle('h',parent=ss['Normal'],fontSize=7.5,leading=9,textColor=colors.white,fontName='Helvetica-Bold')
doc=SimpleDocTemplate('out/Bengaluru_Bank_Auction_Flats_Oct2026.pdf',pagesize=landscape(A4),leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm,
    title='Bengaluru Bank-Auction Flats',author='Compiled with Browsing-agent')
E=[]
E.append(Paragraph('Bank-Auction Flats &amp; Apartments in Bengaluru',ss['Title']))
E.append(Paragraph(f'Upcoming e-auctions as of 07 Oct 2026 (11:20 AM IST) &mdash; {len(rows)} flats/apartments',ss['Heading3']))
vals=[r['res'] for r in rows]; open_n=sum(r['emdOpen'] for r in rows)
summ=f"""<b>Sources browsed:</b> BAANKNET (baanknet.com, the official PSB Alliance e-auction portal for all public-sector banks, the successor of IBAPI) and
bankeauctions.com (C1 India, used by private banks, NBFCs and ARCs). The browser was driven using the <i>Browsing-agent</i> repository's Playwright engine.
auctionbazaar.com was checked and had no Bengaluru listings. IBAPI, MSTC and foreclosureindia.com blocked access from the cloud server, so they were not covered.<br/><br/>
<b>Snapshot:</b> {len(rows)} flats, reserve prices ranging {lakh(min(vals))} to {lakh(max(vals))} (median {lakh(sorted(vals)[len(vals)//2])}).
EMD (deposit) still open for <b>{open_n}</b>; rows marked <font color='#b00020'><b>EMD CLOSED</b></font> can no longer be joined.
All times are IST. L = lakh, Cr = crore. Area is taken from the sale notice text (usually super built-up) and is blank when not stated.<br/><br/>
<b>How to act on a listing:</b> go to baanknet.com &rarr; Property &rarr; search the <b>Auction ID</b>. Register as a bidder (KYC), pay the EMD (usually 10% of the reserve price) before the EMD deadline,
inspect the flat on the inspection date, then bid online. <b>Before bidding, read the bank's sale notice PDF.</b> Check whether possession is <i>Physical</i>
(the bank already holds the flat) or <i>Symbolic</i> (an occupant may still be living there, so taking possession can be slow). Also check for dues and encumbrances, and get the title verified by a lawyer."""
E.append(Paragraph(summ,ParagraphStyle('s',parent=ss['Normal'],fontSize=8.5,leading=11)))
E.append(Spacer(1,5*mm))
hdr=['#','Auction date (IST)','Auction ID','Bank / Branch','Property &amp; location','Area / Type','Reserve price','EMD &amp; EMD deadline','Possession','Inspection contact']
data=[[Paragraph(x,h) for x in hdr]]
for i,r in enumerate(rows,1):
    short=r['addr'][:260]+('...' if len(r['addr'])>260 else '')
    emdtxt=f"Rs.{lakh(r['emd'])}<br/>"+(f"by {ist(r['emdEnd'],'%d %b %I:%M %p')}" if r['emdEnd'] else 'see notice')
    if not r['emdOpen']: emdtxt+="<br/><font color='#b00020'><b>EMD CLOSED</b></font>"
    data.append([Paragraph(str(i),sm),Paragraph(ist(r['when']),smb),Paragraph(f"{r['id']}<br/><font size=6>{r['pid']}<br/>{r['src']}</font>",sm),
        Paragraph(f"<b>{r['bank']}</b><br/>{r['branch'][:60]}",sm),Paragraph(f"<b>{r['loc']} {r['pin']}</b><br/>{short}",sm),
        Paragraph(f"{r['area']}<br/>{r['bhk']}",sm),Paragraph(f"<b>Rs.{lakh(r['res'])}</b>"+("<br/>Loan avail." if r['loan'] else ''),sm),Paragraph(emdtxt,sm),
        Paragraph(r['poss'],sm),Paragraph(f"{r['contact']}<br/>Insp: {r['insp']}",sm)])
t=Table(data,colWidths=[7*mm,23*mm,22*mm,33*mm,83*mm,20*mm,19*mm,26*mm,19*mm,25*mm],repeatRows=1)
st=[('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1f2a44')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#c8ccd4')),
    ('LEFTPADDING',(0,0),(-1,-1),2.5),('RIGHTPADDING',(0,0),(-1,-1),2.5)]
for i in range(1,len(data)):
    if i%2==0: st.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#f3f5f9')))
    if not rows[i-1]['emdOpen']: st.append(('TEXTCOLOR',(0,i),(-1,i),colors.HexColor('#777777')))
t.setStyle(TableStyle(st)); E.append(t)
E.append(Spacer(1,4*mm))
E.append(Paragraph("""<b>Also seen, auction today (7 Oct), EMD already closed:</b> Sri Guru Raghavendra Sahakara Bank, bankeauctions.com IDs 240979 (Flat 201, "Rayara Neralu", Halagevaderahalli, Kengeri, 2BHK 1,109 sq ft,
sold together with a 2,800 sq ft site, reserve Rs.59.34 L) and 241010 (Villament No 42, Varthur, 2,145 sq ft, reserve Rs.1.43 Cr).<br/>
<b>Disclaimer:</b> This list was compiled automatically from public listings on 07 Oct 2026. Auctions get postponed or withdrawn, so check every detail against the official sale notice before paying any EMD.""",
 ParagraphStyle('f',parent=ss['Normal'],fontSize=7.5,leading=9.5)))
doc.build(E)
print(len(rows), open_n)
