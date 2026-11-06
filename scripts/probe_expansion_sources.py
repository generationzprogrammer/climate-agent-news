"""Verify advertised public publisher APIs, respecting existing robots/circuit rules."""
import concurrent.futures as cf
import json
import argparse
import urllib.parse as u
from bs4 import BeautifulSoup
import fulltext_pilot as p
import bulk_fulltext as b

SOURCES = [
 ('CLEANTECHNICA','CleanTechnica','https://cleantechnica.com/'),
 ('PVMAG','pv magazine','https://www.pv-magazine.com/'),
 ('RENEWECONOMY','RenewEconomy','https://reneweconomy.com.au/'),
 ('PVTECH','PV Tech','https://www.pv-tech.org/'),
 ('STORAGE','Energy Storage News','https://www.energy-storage.news/'),
 ('CARBONHERALD','Carbon Herald','https://carbonherald.com/'),
 ('CLIMATEHOME','Climate Home News','https://www.climatechangenews.com/'),
 ('MONGABAY_ES','Mongabay Latam','https://es.mongabay.com/'),
 ('MONGABAY_ID','Mongabay Indonesia','https://www.mongabay.co.id/'),
 ('MONGABAY_IN','Mongabay India','https://india.mongabay.com/'),
 ('ENB','Earth Negotiations Bulletin','https://enb.iisd.org/'),
]

EXTRA = [
 ('PVMAG_US','pv magazine USA','https://pv-magazine-usa.com/'),
 ('PVMAG_AU','pv magazine Australia','https://www.pv-magazine-australia.com/'),
 ('PVMAG_IN','pv magazine India','https://www.pv-magazine-india.com/'),
 ('SOLARQUARTER','SolarQuarter','https://solarquarter.com/'),
 ('THEDRIVEN','The Driven','https://thedriven.io/'),
 ('SOLLARPOWER','Solar Power World','https://www.solarpowerworldonline.com/'),
 ('WINDFARM','Windpower Engineering','https://www.windpowerengineering.com/'),
 ('ENERGYPOST','Energy Post','https://energypost.eu/'),
 ('CARBONCREDITS','Carbon Credits','https://carboncredits.com/'),
 ('ENVIROAFRICA','EnviroNews Nigeria','https://www.environewsnigeria.com/'),
 ('CLIMATECHANGENEWS','Climate Home News canonical','https://www.climatechangenews.com/'),
]
ROUND3=[
 ('ECOWATCH','EcoWatch','https://www.ecowatch.com/'),
 ('EARTHORG','Earth.org','https://earth.org/'),
 ('EARTHCOM','Earth.com','https://www.earth.com/'),
 ('SCITECH','SciTechDaily','https://scitechdaily.com/'),
 ('IPS','Inter Press Service','https://www.ipsnews.net/'),
 ('SCIDEV','SciDev.Net','https://www.scidev.net/global/'),
 ('SUSTIMES','Sustainability Times','https://www.sustainability-times.com/'),
 ('ELECTREK','Electrek','https://electrek.co/'),
 ('CARBONBRIEF_CN','Dialogue Earth Chinese','https://dialogue.earth/zh/'),
 ('CLIMATEANALYTICS','Climate Analytics','https://climateanalytics.org/'),
]
ROUND4=[
 ('ENERGYMIX','The Energy Mix','https://www.theenergymix.com/'),
 ('OFFSHORE','Offshore Energy','https://www.offshore-energy.biz/'),
 ('RENEWABLEWORLD','Renewable Energy World','https://www.renewableenergyworld.com/'),
 ('RECHARGE','Recharge','https://www.rechargenews.com/'),
 ('CLIMATENEWSNET','Climate News Network','https://climatenewsnetwork.net/'),
 ('REVE','REVE Wind Energy and Electric Vehicles Review','https://www.evwind.es/'),
 ('CLEANENERGYWIRE','Clean Energy Wire','https://www.cleanenergywire.org/'),
 ('CLIMATECHANGENEWS2','Climate Home','https://climatechangenews.com/'),
]

def main(round_number=1):
 p.ACCEPT_ENCODING='gzip'; f=p.Fetcher()
 def check(s):
  ident,name,home=s; d=dict(source_id=ident,name=name,homepage=home,checked_at=p.stamp())
  try:
   _,body,_,heads=f.get(home,b.timing()); soup=BeautifulSoup(body,'lxml')
   link=soup.find('link',rel='https://api.w.org/')
   if not link: raise p.StopFetch('no_advertised_API')
   api=u.urljoin(home,link.get('href',''))
   if not api.endswith('/wp-json/'): raise p.StopFetch('unsupported_advertised_API')
   endpoint=api+'wp/v2/posts'
   _,body,_,heads=f.get(endpoint+'?per_page=1&_fields=id,link,title,date,date_gmt,content',b.timing())
   posts=json.loads(body); post=posts[0]
   row=dict(url=post['link'],title=BeautifulSoup(post['title']['rendered'],'lxml').get_text(),date=post.get('date_gmt') or post.get('date'),source=name)
   text,checks=b.accept_post(row,post)
   _,page,_,_=f.get(row['url'],b.timing()); htmltext,htmlchecks=p.extract(page,row['title'],row['url'])
   if len(htmltext)/max(1,len(text))<.75: raise p.StopFetch('HTML_does_not_confirm_API_body')
   d.update(verified=True,endpoint=endpoint,allowed_hosts=sorted({p.host(home),p.host(row['url'])}),api_total_posts={k.lower():v for k,v in heads.items()}.get('x-wp-total'),sample_url=row['url'],api_characters=len(text),html_characters=len(htmltext),sample_checks=checks)
  except Exception as e: d.update(verified=False,error=getattr(e,'reason',type(e).__name__))
  p.dump(p.ROOT/('analysis/global_expansion_20261106/probe_'+ident+'.json'),d)
  print(json.dumps(d,ensure_ascii=True),flush=True); return d
 with cf.ThreadPoolExecutor(max_workers=6) as pool: result=list(pool.map(check,{1:SOURCES,2:EXTRA,3:ROUND3,4:ROUND4}[round_number]))
 suffix='' if round_number==1 else '_round'+str(round_number)
 p.dump(p.ROOT/('analysis/global_expansion_20261106/source_probes'+suffix+'.json'),result)
 p.dump(p.ROOT/('analysis/global_expansion_20261106/probe_requests'+suffix+'.json'),f.requests)
if __name__=='__main__':
 a=argparse.ArgumentParser(); a.add_argument('--round',type=int,default=1); main(a.parse_args().round)
