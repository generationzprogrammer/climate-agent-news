"""Add evidence-addressable institutions to an existing local export."""
import collections,csv,gzip,itertools,json,shutil,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from climate_agent.governance_labels import governance_organization_evidence,GOVERNANCE_ORGANIZATIONS

def enrich(out):
    db=sqlite3.connect(out/'governance.sqlite')
    entities=collections.Counter();pairs=collections.Counter();links=collections.Counter();added=0
    for cohort in ('original_recovery','new_library'):
        path=out/(cohort+'_labeled_fulltexts.jsonl.gz');temp=path.with_suffix('.tmp.gz')
        with gzip.open(path,'rt',encoding='utf-8') as source,gzip.open(temp,'wt',encoding='utf-8') as dest:
            for line in source:
                r=json.loads(line);labels=r['labels'];key=r['document_key']
                extra=governance_organization_evidence(r['title'],r['source_text'])
                old={(e['label_type'],e['label_id'],e['field'],e['start'],e['end']) for e in labels['evidence']}
                for e in extra:
                    signature=(e['label_type'],e['label_id'],e['field'],e['start'],e['end'])
                    if signature in old:continue
                    assert r[e['field']][e['start']:e['end']]==e['quote']
                    labels['evidence'].append(e);old.add(signature);added+=1
                    db.execute('INSERT OR IGNORE INTO labels VALUES (?,?,?)',(key,'organization',e['label_id']))
                    db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?)',(key,'organization',e['label_id'],e['field'],e['start'],e['end'],e['quote']))
                labels['organization_mentions']=sorted(set(labels['organization_mentions'])|{e['label_id'] for e in extra})
                dest.write(json.dumps(r,ensure_ascii=False)+'\n')
                if r['research_eligible']:
                    es=sorted(set(['country:'+x for x in labels['country_mentions']]+['organization:'+x for x in labels['organization_mentions']]))
                    entities.update(es);pairs.update(itertools.combinations(es,2));links.update(itertools.product(es,labels['topics']))
        temp.replace(path);db.commit()
    def table(name,fields,rows):
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(fields);w.writerows(rows)
    table('article_labels.csv',['document_key','label_type','label_id'],db.execute('SELECT * FROM labels ORDER BY document_key,label_type,label_id'))
    table('entity_cooccurrence.csv',['entity_a','entity_b','cooccurring_articles','articles_a','articles_b','jaccard'],((a,b,n,entities[a],entities[b],n/(entities[a]+entities[b]-n)) for (a,b),n in pairs.most_common()))
    table('entity_topic.csv',['entity','topic_id','articles'],((a,b,n) for (a,b),n in links.most_common()))
    taxonomy=json.loads((out/'taxonomy.json').read_text('utf-8'));known={x['id'] for x in taxonomy['organizations']}
    taxonomy['organizations'] += [{'id':k,'name_zh':v[-1],'terms':list(v)} for k,v in GOVERNANCE_ORGANIZATIONS.items() if k not in known]
    (out/'taxonomy.json').write_text(json.dumps(taxonomy,ensure_ascii=False,indent=2),encoding='utf-8')
    for rel in ('src/climate_agent/governance_labels.py','tests/test_governance_labels.py','scripts/enrich_governance_organizations.py'):
        shutil.copy2(ROOT/rel,out/'reproducibility'/rel)
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
    print(json.dumps({'organization_evidence_added':added}),flush=True)

if __name__=='__main__':enrich(ROOT/'analysis/governance_handover_20261105_final')
