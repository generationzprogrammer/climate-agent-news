"""Extract factual directory fields, without copying personal contact details."""
from pathlib import Path
import json,re,hashlib
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collect_innovation_registries import CACHE,SOURCES

def clean(s):return re.sub(r'\s+',' ',s).strip()
def text(e):return clean(e.get_text(' ',strip=True)) if e else ''
def soup(key):return BeautifulSoup((CACHE/(key+'.html')).read_bytes(),'html.parser')
def identity(key,name):return key+'_'+hashlib.sha256(name.casefold().encode()).hexdigest()[:12]
def item(key,name,country,**kw):return dict(key=identity(key,name),registry=key,name=name,country=country,**kw)

def nsf():
    out=[]
    for row in soup('nsf_iucrc').select('div.row'):
        title=row.find(class_='title',recursive=False)
        if not title:continue
        a=title.find('a');name=text(a)
        if not name:continue
        def col(c):return row.find(class_=c,recursive=False)
        y=text(col('year'));focus=col('focus')
        out.append(item('nsf_iucrc',name,'US',url=urljoin(SOURCES['nsf_iucrc'],a['href']),
            focus=[text(x).replace(' (Primary Area)','') for x in focus.select('li')],
            institutions=[text(x) for x in col('universities').select('li')],
            members=[text(x) for x in col('members').select('li')] if col('members') else [],
            year=int(y) if re.fullmatch(r'(19|20)\d{2}',y) else None,
            status='completed' if name.startswith('Completed') else 'listed',location=text(col('location'))))
    return out

def embrapii():
    out=[]
    for row in soup('embrapii_export').select('tr')[1:]:
        t=[text(x) for x in row.select('td')]
        if len(t)!=5:raise ValueError('EMBRAPII column schema changed')
        if t[0] and t[1]:out.append(item('embrapii_export',t[0],'BR',focus=[t[1]],activities=t[2],institution_type=t[3],location=t[4]))
    return out

def australia():
    out=[]
    for table in soup('australia_crcp').select('table'):
        h=table.find_previous(['h2','h3']);round_name=text(h)
        for row in table.select('tr'):
            td=row.find_all('td',recursive=False)
            if not td:continue
            if len(td)!=6:raise ValueError('CRC-P column schema changed')
            t=[text(x) for x in td]
            # Names retain the explicitly listed order; no inferred roles or countries.
            partners=[clean(x) for x in td[1].get_text('\n',strip=True).splitlines() if clean(x)]
            out.append(item('australia_crcp',t[0],'AU',round=round_name,institutions=partners,description=t[2],period=t[3],grant=t[4],project_value=t[5]))
    return out

def africa():
    mapping={'Benin':'BJ','Burkina Faso':'BF',"Cote D’Ivoire":'CI',"Cote d’Ivoire":'CI',"Côte d’Ivoire":'CI','Djibouti':'DJ','Gambia':'GM','Ghana':'GH','Guinea':'GN','Niger':'NE','Nigeria':'NG','Senegal':'SN','Togo':'TG'}
    s=soup('africa_ace');out=[]
    for tab in s.select('.elementor-tab-content'):
        label=text(s.find(id=tab['id'].replace('content','title')))
        code=next((v for k,v in mapping.items() if k.casefold().replace('’',"'")==label.casefold().replace('’',"'")),None)
        if not code:raise ValueError('Unknown ACE country '+label)
        for li in tab.select('li'):
            a=li.find('a');name=text(a) if a else text(li).split(',')[0]
            full=text(li)
            if not name or len(name)<8:continue
            out.append(item('africa_ace',name,code,description=full,url=urljoin(SOURCES['africa_ace'],a.get('href','')) if a else None))
    last_host=''
    for row in soup('africa_ace2').select('table tr'):
        td=row.find_all('td',recursive=False)
        if len(td)==2:last_host=text(td[0]);cell=td[1]
        elif len(td)==1 and last_host:cell=td[0]
        else:continue
        code=next((v for k,v in {'Ethiopia':'ET','Mozambique':'MZ','Kenya':'KE','Rwanda':'RW','Tanzania':'TZ','Uganda':'UG','Zambia':'ZM'}.items() if k in last_host),None)
        if not code:continue
        name=text(cell)
        if name:out.append(item('africa_ace2',name,code,institutions=[last_host],description=name+'; '+last_host))
    return out

def japan():
    # Traverse sibling cells: the official markup omits several table rows.
    s=BeautifulSoup((CACHE/'jst_coinext.html').read_bytes(),'lxml');out=[]
    for a in s.select('table a[href]'):
        if not a['href'].endswith('.pdf') or '/overview/' not in a['href']:continue
        td=a.find_parent('td');cells=td.find_previous_siblings('td')
        if len(cells)<2:continue
        host=text(cells[0]);name=text(cells[1])
        if not name or not host:continue
        out.append(item('jst_coinext',name,'JP',institutions=[host],url=urljoin(SOURCES['jst_coinext'],a['href']),stage=text(a.find_parent('table').find_previous(['h2','h3']))))
    return out

def main():
    rows=nsf()+embrapii()+australia()+africa()+japan()
    if len({r['key'] for r in rows})!=len(rows):raise ValueError('Duplicate directory identity')
    (CACHE/'candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    from collections import Counter
    print(json.dumps(dict(Counter(r['registry'] for r in rows)),ensure_ascii=False))
if __name__=='__main__':main()
