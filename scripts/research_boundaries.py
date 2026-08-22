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

report={'big':{'service':None,'layers':[],'errors':[]},'gfw':{'errors':[],'files':[]}}

# BIG Kebijakan Satu Peta: inspect every public polygon layer and search all text fields.
big='https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer'
try:
    root,final,status,ctype=get_json(big,{'f':'pjson'})
    report['big']['service']={'url':final,'status':status,'currentVersion':root.get('currentVersion'),'layers':root.get('layers',[])}
    all_features=[]
    for layer in root.get('layers',[]):
        lid=layer['id']; lname=layer.get('name',''); lurl=f'{big}/{lid}'
        try:
            meta,mfinal,mstatus,_=get_json(lurl,{'f':'pjson'})
            fields=[f for f in meta.get('fields',[]) if f.get('type')=='esriFieldTypeString']
            li={'id':lid,'name':lname,'url':mfinal,'geometryType':meta.get('geometryType'),'fields':[f['name'] for f in fields],'matches':{}}
            report['big']['layers'].append(li)
            if meta.get('geometryType')!='esriGeometryPolygon': continue
            for did,aliases in targets.items():
                seen=set(); matched=[]
                for field in fields:
                    fname=field['name']
                    for alias in aliases:
                        where=f"UPPER({fname}) LIKE '%{alias.replace(chr(39),chr(39)*2).upper()}%'"
                        try:
                            gj,qfinal,qstatus,_=get_json(lurl+'/query',{'where':where,'outFields':'*','returnGeometry':'true','outSR':'4326','f':'geojson'})
                        except Exception:
                            continue
                        for feat in gj.get('features',[]):
                            props=feat.get('properties') or {}
                            vals=' | '.join(str(v) for v in props.values() if v is not None)
                            if not any(norm(a) in norm(vals) for a in aliases): continue
                            key=json.dumps([props,feat.get('geometry')],sort_keys=True,ensure_ascii=False)
                            if key in seen: continue
                            seen.add(key)
                            feat['_research']={'dossierId':did,'layerId':lid,'layerName':lname,'queryField':fname,'queryUrl':qfinal}
                            matched.append(feat); all_features.append(feat)
                if matched: li['matches'][did]=len(matched)
        except Exception as e:
            report['big']['errors'].append({'layer':lid,'name':lname,'error':repr(e)})
    with open(os.path.join(OUT,'big_matches.geojson'),'w',encoding='utf-8') as f:
        json.dump({'type':'FeatureCollection','features':all_features},f,ensure_ascii=False)
except Exception as e:
    report['big']['errors'].append({'service':big,'error':repr(e)})

# GFW/WRI legacy oil-palm concession archive.
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
            dids=[did for did,aliases in targets.items() if did in {'bsg','thm1','thm2','lar','sum'} and any(norm(a) in nv for a in aliases)]
            if not dids: continue
            gi=sr.shape.__geo_interface__
            for did in dids:
                gfw_features.append({'type':'Feature','properties':{**props,'_researchDossierId':did,'_researchSourceFile':os.path.relpath(shp,ex)},'geometry':gi})
    with open(os.path.join(OUT,'gfw_matches.geojson'),'w',encoding='utf-8') as f:
        json.dump({'type':'FeatureCollection','features':gfw_features},f,ensure_ascii=False)
except Exception as e:
    report['gfw']['errors'].append({'url':gfw,'error':repr(e)})

with open(os.path.join(OUT,'research_report.json'),'w',encoding='utf-8') as f:
    json.dump(report,f,indent=2,ensure_ascii=False)
print(json.dumps(report,indent=2,ensure_ascii=False))
