"""Deterministic, source-stratified model and regional comparisons.

No synthetic country-performance scores. Each exclusive macro count uses a
project coordinator country or the explicitly reviewed single-country focus.
"""
from collections import Counter
import copy

REGIONS = {
 "europe": ("欧洲", "Europe", "NO NL RO RU RS PL PT ME LT LU LV MT UA SK SI SE CH DK EE DE CZ AT AL BA BE BG IS IT HU IE FR GB ES FI HR GR"),
 "asia": ("亚洲", "Asia", "PK TR SG CN CY JO IN IL JP KR"),
 "africa": ("非洲", "Africa", "MA ZA TN CD KE EG ET GH"),
 "north_america": ("北美洲", "Northern America", "US CA"),
 "south_america": ("南美洲", "South America", "BR"),
 "oceania": ("大洋洲", "Oceania", "NZ AU MH"),
}
COUNTRY_REGION = {code:key for key,(_,_,codes) in REGIONS.items() for code in codes.split()}
DEVELOPED_ASIA_OCEANIA = {"IL", "JP", "KR", "AU", "NZ"}
PROVINCES = {"CN-GD": {"zh":"广东省","en":"Guangdong"}, "CN-ZJ":{"zh":"浙江省","en":"Zhejiang"},
             "CN-AH":{"zh":"安徽省","en":"Anhui"},"CN-SC":{"zh":"四川省","en":"Sichuan"}}

def economy_group(country):
    # The full UNCTAD list is access-blocked; do not guess individual exceptions.
    if country in {"CY","TR"}: return "unclassified"
    region = COUNTRY_REGION.get(country)
    if not region: return "unclassified"
    return "developed" if region in {"europe","north_america"} or country in DEVELOPED_ASIA_OCEANIA else "developing"

def annotate_cases(cases, config):
    ids={row["id"] for row in config["archetypes"]}
    for c in cases:
        a=c.setdefault("research_annotation",{})
        p=c.get("project") or {}
        if p.get("source_type")=="ARPAE":
            model,country,cohort="mission","US","ARPAE"
        elif p.get("funding_basis")=="maximum_EU_contribution_not_actual_expenditure":
            model,country,cohort="consortium",p.get("coordinator_country"),"CORDIS"
        else:
            model=a.get("primary_model") or config["legacy_assignments"].get(c["id"])
            country=a.get("country") or (c["countries"][0] if len(c["countries"])==1 else None)
            cohort="regional_review" if c.get("id","").removeprefix("oi_") in {
              "ssl_factory","giri","siat","scici","gdut_cnc","icost","tsinghua_sz_storage","songshan_medeng",
              "zju_shaoxing","zhejiang_tsinghua","zhejiang_lab","sjtu_shaoxing","tju_idim","tju_shangyu","zjut_shengzhou",
              "buaa_hangzhou","nimte_daishan","graphene_centre","nimte_poc","ustc_iat","tsinghua_eiri",
              "stanford_otl","startx","aist_solutions"} else "legacy_review"
        if model not in ids: raise ValueError("unclassified_innovation_model:"+c["id"])
        if country and country not in c["countries"]: raise ValueError("focus_not_in_country_tags:"+c["id"])
        a.update(primary_model=model,country=country,cohort=cohort,
                 continent=COUNTRY_REGION.get(country,"cross_region"),economy=economy_group(country),
                 grain="project" if p else "platform",basis=a.get("basis","editorial_mechanism_coding"),reviewed_at=config["reviewed_at"])
    return cases

def build_analysis(cases, config):
    models=copy.deepcopy(config)
    byid={c["id"]:c for c in cases}
    for profile in models["profiles"]:
        # A cohort representative is a deterministic real project, never a guessed ID.
        if profile.get("cohort"):
            valid=[cid for cid in profile["case_ids"] if cid in byid]
            if not valid:
                valid=[c["id"] for c in cases if c["research_annotation"]["cohort"]==profile["cohort"]][:3]
            profile["case_ids"]=valid
        if not profile["case_ids"] or any(cid not in byid for cid in profile["case_ids"]):
            raise ValueError("unresolved_model_evidence:"+profile["id"])
        profile["source_ids"]=list(dict.fromkeys(ref["source_id"] for cid in profile["case_ids"] for ref in byid[cid]["evidence"]))
        profile["source_ids"].extend(profile.get("additional_source_ids", []))
    rows=[]
    for grain in ("platform","project"):
        subset=[c for c in cases if c["research_annotation"]["grain"]==grain]
        for dimension,groups in (("continent",list(REGIONS)+["cross_region"]), ("economy",["developed","developing","unclassified"])):
            for group in groups:
                cohort=[c for c in subset if c["research_annotation"][dimension]==group]
                counts=Counter(c["research_annotation"]["primary_model"] for c in cohort)
                for model in config["archetypes"]:
                    count=counts[model["id"]]
                    rows.append({"grain":grain,"dimension":dimension,"group":group,"model":model["id"],
                        "count":count,"denominator":len(cohort),"share":count/len(cohort) if cohort else None,
                        "source_cohorts":dict(Counter(c["research_annotation"]["cohort"] for c in cohort))})
    province_rows=[]
    for code,name in PROVINCES.items():
        subset=[c for c in cases if c["research_annotation"].get("province")==code]
        province_rows.append({"id":code,"name":name,"count":len(subset),
          "cities":sorted({c["research_annotation"]["city"] for c in subset}),
          "models":dict(Counter(c["research_annotation"]["primary_model"] for c in subset)),
          "case_ids":[c["id"] for c in subset]})
    models.update(macro=rows,provinces=province_rows,
      group_labels={**{k:{"zh":v[0],"en":v[1]} for k,v in REGIONS.items()},
        "cross_region":{"zh":"跨区域与国际机制","en":"Cross-regional / international"},
        "developed":{"zh":"发达经济体","en":"Developed economies"},
        "developing":{"zh":"发展中经济体","en":"Developing economies"},
        "unclassified":{"zh":"跨分组或未归类","en":"Cross-group / unclassified"}},
      macro_note={"zh":"每个项目按协调国计一次；平台按明确的单国主体计一次，多国与国际机制单列。项目与平台分开统计。来源渠道不均，数量与模式占比均不代表地区创新绩效。发展分组依UNCTAD地区定义，不等于收入等级；塞浦路斯与土耳其待完整名单核验，暂列未归类。",
       "en":"Projects count once by coordinator country; platforms use explicit single-country focus, with international mechanisms separate. Projects and platforms are not pooled. Uneven source coverage means counts/shares are not performance. UNCTAD development groups are not income classes; Cyprus and Türkiye await list verification and remain unclassified."})
    return models
