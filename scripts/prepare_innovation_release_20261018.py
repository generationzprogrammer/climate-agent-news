"""Set up the new snapshot without modifying either October 14 release."""
import csv,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/innovation_research_20261018'
OUT.mkdir(parents=True,exist_ok=True)
previous=ROOT/'analysis/innovation_research_20261014_r2'
entries=list(csv.DictReader((previous/'data_dictionary.csv').read_text(encoding='utf-8').splitlines()))
for entry in entries:
    if entry['field']=='observation_basis':
        entry['unit_or_allowed_values']='registered_project_objectives; official_registry_unit; official_institutional_account'
        entry['definition']='Evidence grain: registered objectives, a named official directory unit, or an institutional account; none alone verifies impact'
    if entry['field']=='source_cohort':
        entry['definition']='Acquisition cohort retained for provenance-stratified analysis, including original and official-registry cohorts'
for field,kind,meaning in [('retrieved_at','datetime','UTC retrieval timestamp of the official document'),('content_sha256','string','SHA256 of the retrieved response bytes'),('robots_status','integer','HTTP status of robots policy request; 404 is no published rule')]:
    entries.append(dict(table='sources',field=field,type=kind,unit_or_allowed_values='source metadata',definition=meaning,missing_meaning='not retained for earlier cohorts'))
for field,kind,meaning in [('case_id','string','Foreign key to cases'),('registry','category','Official acquisition programme'),('source_record_key','string','Stable programme and original-name hash'),('original_name','string','Unit or project name as listed by the official registry'),('record_json','JSON object','Whitelisted original organisational metadata including technical focus and registered objectives; no personal contact fields')]:
    entries.append(dict(table='registry_records',field=field,type=kind,unit_or_allowed_values='UTF-8 metadata',definition=meaning,missing_meaning='not disclosed in source'))
with (OUT/'data_dictionary.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(entries[0]));w.writeheader();w.writerows(entries)
print(OUT)
