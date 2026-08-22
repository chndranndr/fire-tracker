import json, os, re, ssl, urllib.parse, urllib.request, zipfile, glob, shutil
import shapefile

OUT='research-output'
os.makedirs(OUT, exist_ok=True)
ctx=ssl.create_default_context()
ua={'User-Agent':'MERATUS-boundary-research/1.0'}

targets={
  'kideco':['KIDECO JAYA AGUNG'], 'kpc':['KALTIM PRIMA COAL'],
  'agm':['ANTANG GUNUNG MERATUS'], 'bre':['BHUMI RANTAU ENERGI','BUMI RANTAU ENERGI'],
  'adaro':['ADARO INDONESIA'], 'dwima':['DWIMA INTIGA'], 'kiani':['KIANI LESTARI'],
  'bsg':['BAGUS SENTOSA GEMILANG'], 'thm1':['TRI H.M 1','TRI HM 1','TRI H M 1'],
  'thm2':['TRI H.M 2','TRI HM 2','TRI H M 2'], 'lar':['LESTARI ALAM RAYA'],
  'sum':['SUMATERA UNGGUL MAKMUR','SUMATRA UNGGUL MAKMUR']
}
mining_ids=['kideco','kpc','agm','bre','adaro']
pbph_ids=['dwima','kiani']
palm_ids=['bsg','thm1','thm2','lar','sum']

def get_bytes(url, params=None, timeout=120):
    if params: url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers=ua)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read(), r.geturl(), r.status, r.headers.get('content-type','')

def get_json(url, params=None, timeout=120):
    b, final, status, ctype=get_bytes(url,params,timeout)
    return json.loads(b.decode('utf-8')), final, status, ctype

def norm(s):
    s=str(s or '').upper().replace('&',' AND ')
    s=re.sub(r'\bPT\.?\b',' ',s)
    s=re.sub(r'[^A-Z0-9]+',' ',s)
    return ' '.join(s.split())

def query_big(layer_id, field, did):
    lurl=f'https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer/{layer_id}'
    out=[]
    for alias in targets[did]:
        needle=alias.replace("'", "''").upper()
        where=f"UPPER({field}) LIKE '%{needle}%'"
        gj,qfinal,qstatus,_=get_json(lurl+'/query',{
          'where':where,'outFields':'*','returnGeometry':'true','outSR':'4326','f':'geojson'
        })
        for feat in gj.get('features',[]):
            props=feat.get('properties') or {}
            val=str(props.get(field,'') or '')
            if norm(alias) not in norm(val): continue
            feat['_research']={'dossierId':did,'layerId':layer_id,'queryField':field,'queryUrl':qfinal}
            out.append(feat)
    # de-duplicate exact source features returned by alias variants
    uniq=[]; seen=set()
    for f in out:
        k=json.dumps([f.get('properties'),f.get('geometry')],sort_keys=True,ensure_ascii=False)
        if k not in seen: seen.add(k); uniq.append(f)
    return uniq

report={'big':{'errors':[],'matches':{}},'gfw':{'errors':[],'files':[],'matches':{}}}
all_big=[]
# BIG WIUP mining layer 4: operator field nmoprt.
for did in mining_ids:
    try:
        fs=query_big(4,'nmoprt',did); report['big']['matches'][did]=len(fs); all_big.extend(fs)
    except Exception as e: report['big']['errors'].append({'dossierId':did,'layer':4,'error':repr(e)})
# BIG forestry permit layers: display field namobj.
for did in pbph_ids:
    found=[]
    for lid in (1,2,3):
        try: found.extend(query_big(lid,'namobj',did))
        except Exception as e: report['big']['errors'].append({'dossierId':did,'layer':lid,'error':repr(e)})
    uniq=[]; seen=set()
    for f in found:
        k=json.dumps([f.get('properties'),f.get('geometry')],sort_keys=True,ensure_ascii=False)
        if k not in seen: seen.add(k); uniq.append(f)
    report['big']['matches'][did]=len(uniq); all_big.extend(uniq)
with open(os.path.join(OUT,'big_matches.geojson'),'w',encoding='utf-8') as f:
    json.dump({'type':'FeatureCollection','features':all_big},f,ensure_ascii=False)

# GFW/WRI Indonesia oil-palm concession archive from metadata Direct Download.
gfw='https://gfw2-data.s3.amazonaws.com/country/idn/zip/idn_oil_palm.zip'
try:
    b,final,status,ctype=get_bytes(gfw,timeout=180)
    zpath='/tmp/idn_oil_palm.zip'; open(zpath,'wb').write(b)
    report['gfw']['download']={'url':final,'status':status,'contentType':ctype,'bytes':len(b)}
    ex='/tmp/idn_oil_palm'; shutil.rmtree(ex,ignore_errors=True); os.makedirs(ex)
    with zipfile.ZipFile(zpath) as z: z.extractall(ex)
    gfw_features=[]
    for shp in glob.glob(ex+'/**/*.shp',recursive=True):
        r=shapefile.Reader(shp,encoding='latin1'); fnames=[x[0] for x in r.fields[1:]]
        report['gfw']['files'].append({'shp':os.path.relpath(shp,ex),'records':len(r),'fields':fnames})
        for sr in r.iterShapeRecords():
            props=dict(zip(fnames,sr.record)); vals=' | '.join(str(v) for v in props.values() if v not in (None,'')); nv=norm(vals)
            for did in palm_ids:
                if any(norm(a) in nv for a in targets[did]):
                    gfw_features.append({'type':'Feature','properties':{**props,'_researchDossierId':did,'_researchSourceFile':os.path.relpath(shp,ex)},'geometry':sr.shape.__geo_interface__})
    for did in palm_ids: report['gfw']['matches'][did]=sum(1 for f in gfw_features if f['properties']['_researchDossierId']==did)
    with open(os.path.join(OUT,'gfw_matches.geojson'),'w',encoding='utf-8') as f:
        json.dump({'type':'FeatureCollection','features':gfw_features},f,ensure_ascii=False)
except Exception as e:
    report['gfw']['errors'].append({'url':gfw,'error':repr(e)})

with open(os.path.join(OUT,'research_report.json'),'w',encoding='utf-8') as f:
    json.dump(report,f,indent=2,ensure_ascii=False)
print(json.dumps(report,indent=2,ensure_ascii=False))
