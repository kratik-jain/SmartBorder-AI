import hashlib, json, mimetypes, os, uuid, shutil
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import Base, engine, get_db, SessionLocal
from .models import User, ScreeningCase, AuditEvent, WatchlistEntry
from .security import hash_password, verify_password, issue_token, current_user
from .services.document_classifier import detect_document_type
from .services.ocr import extract_fields
from .services.validator import validate_document
from .services.forensics import analyze as forensic_analyze
from .services.face import verify as face_verify
from .services.risk import score as risk_score
from .services.audit import event_hash

ROOT=Path(__file__).resolve().parent.parent
UPLOADS=ROOT/'uploads'; EVIDENCE=UPLOADS/'evidence'; MODELS=ROOT/'models'; FRONTEND=ROOT/'frontend'/'index.html'
UPLOADS.mkdir(exist_ok=True); EVIDENCE.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)
Base.metadata.create_all(engine)

app=FastAPI(title='SMARTBORDER AI API',version='4.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])

class LoginIn(BaseModel): officer_id:str; password:str
class ActionIn(BaseModel): action:str; reason:str|None=None
class WatchlistIn(BaseModel): identifier_type:str; identifier_value:str; subject_name:str; category:str='REVIEW'; status:str='REVIEW'; notes:str=''

ALLOWED_EXT={'.jpg','.jpeg','.png','.webp'}
DOC_LABELS={'passport':'Passport','visa':'Visa','national_id':'National ID','driving_licence':'Driving Licence','permit':'Permit'}

def seed():
    db=SessionLocal()
    try:
        if not db.query(User).filter_by(officer_id='OB-021').first():
            db.add(User(officer_id='OB-021',password_hash=hash_password('Smart@1234'),name='Border Officer',role='Authorized Officer'))
        if not db.query(User).filter_by(officer_id='ADMIN-001').first():
            db.add(User(officer_id='ADMIN-001',password_hash=hash_password('Admin@1234'),name='System Administrator',role='Administrator'))
        if db.query(WatchlistEntry).count()==0:
            db.add_all([
                WatchlistEntry(identifier_type='PASSPORT',identifier_value='X9999999',subject_name='Demo Watchlist Subject',category='DOCUMENT FRAUD',status='HIGH_RISK',notes='Synthetic SIH demonstration record'),
                WatchlistEntry(identifier_type='PASSPORT',identifier_value='X8888888',subject_name='Demo Blacklisted Subject',category='WATCHLIST',status='BLACKLISTED',notes='Synthetic SIH demonstration record')
            ])
        db.commit()
    finally:db.close()
seed()

def log_event(db,case_id,actor,event_type,details):
    prev=db.query(AuditEvent).filter_by(case_id=case_id).order_by(AuditEvent.id.desc()).first()
    h=event_hash(case_id,actor,event_type,details,prev.event_hash if prev else '')
    ev=AuditEvent(case_id=case_id,actor=actor,event_type=event_type,details_json=json.dumps(details),event_hash=h)
    db.add(ev); db.flush(); return ev

def public_case(row,include_result=True):
    result=json.loads(row.result_json or '{}')
    base={'id':row.id,'case_id':row.case_id,'created_at':row.created_at.isoformat(),'officer_id':row.officer_id,'document_type':row.document_type,'original_filename':row.original_filename,'status':row.status,'risk_score':row.risk_score,'decision':row.decision,'action':row.action}
    if include_result: base['result']=result
    return base

@app.get('/api/health')
def health():
    return {'status':'ok','service':'SMARTBORDER AI','version':'4.0.0','ocr':'ready' if (shutil.which('tesseract') or os.getenv('TESSERACT_CMD')) else 'not_configured','forensics':'OpenCV ELA','face_models_installed':(MODELS/'face_recognition_sface_2021dec.onnx').exists(),'database':os.getenv('DATABASE_URL','sqlite')}

@app.post('/api/auth/login')
@app.post('/api/login')
def login(body:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(officer_id=body.officer_id,active=True).first()
    if not u or not verify_password(body.password,u.password_hash): raise HTTPException(401,'Invalid Officer ID or password')
    return {'token':issue_token(u.officer_id,u.name,u.role),'user':{'officer_id':u.officer_id,'name':u.name,'role':u.role}}

@app.get('/api/auth/me')
@app.get('/api/me')
def me(user=Depends(current_user)): return user

@app.get('/api/dashboard/stats')
@app.get('/api/stats')
def stats(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(ScreeningCase).all(); today=datetime.utcnow().date(); todays=[x for x in rows if x.created_at.date()==today]
    return {'total':len(todays),'flagged':sum(x.decision in {'HIGH RISK','MANUAL REVIEW'} for x in todays),'review':sum(x.decision=='MANUAL REVIEW' for x in todays),'high_risk':sum(x.decision=='HIGH RISK' for x in todays),'screened':len(rows),'avg_risk':round(sum(x.risk_score for x in rows)/len(rows),1) if rows else 0}

@app.get('/api/screenings')
def screenings(user=Depends(current_user),db:Session=Depends(get_db)):
    return [public_case(x,False) for x in db.query(ScreeningCase).order_by(ScreeningCase.id.desc()).limit(100).all()]

@app.post('/api/screenings/create')
async def create_screening(document:UploadFile=File(...),selfie:UploadFile|None=File(None),document_type:str|None=Form(None),user=Depends(current_user),db:Session=Depends(get_db)):
    ext=Path(document.filename or '').suffix.lower()
    if ext not in ALLOWED_EXT: raise HTTPException(400,'Upload JPG, PNG or WEBP image files')
    raw=await document.read()
    if len(raw)>15*1024*1024: raise HTTPException(413,'Document exceeds 15 MB')
    sha=hashlib.sha256(raw).hexdigest(); safe_name=f'{sha}{ext}'; doc_path=UPLOADS/safe_name; doc_path.write_bytes(raw)
    selfie_path=''
    if selfie:
        sext=Path(selfie.filename or '').suffix.lower()
        if sext not in ALLOWED_EXT: raise HTTPException(400,'Selfie must be JPG, PNG or WEBP')
        sraw=await selfie.read()
        if len(sraw)>10*1024*1024: raise HTTPException(413,'Selfie exceeds 10 MB')
        selfie_path=str(UPLOADS/f'{uuid.uuid4().hex}{sext}'); Path(selfie_path).write_bytes(sraw)
    detected,det_conf,_=detect_document_type(doc_path,document_type)
    case_id='SB-'+datetime.utcnow().strftime('%Y')+'-'+uuid.uuid4().hex[:8].upper()
    row=ScreeningCase(case_id=case_id,officer_id=user['sub'],document_type=detected,original_filename=document.filename or '',document_path=str(doc_path),selfie_path=selfie_path,document_sha256=sha,status='PROCESSING')
    db.add(row); db.flush(); log_event(db,case_id,user['sub'],'DOCUMENT_UPLOADED',{'filename':document.filename,'sha256':sha}); log_event(db,case_id,user['sub'],'DOCUMENT_DETECTED',{'type':detected,'confidence':det_conf}); db.commit();
    try:
        ocr=extract_fields(doc_path); log_event(db,case_id,user['sub'],'OCR_COMPLETED',{'confidence':ocr['confidence'],'field_count':len(ocr['fields'])});
        validation=validate_document(detected,ocr['fields'],ocr['mrz']); log_event(db,case_id,user['sub'],'VALIDATION_COMPLETED',{'valid':validation['valid'],'issues':validation['issues']});
        evidence_path=EVIDENCE/f'{case_id}_evidence.jpg'; forensic=forensic_analyze(doc_path,evidence_path); log_event(db,case_id,user['sub'],'TAMPERING_ANALYSIS_COMPLETED',{'score':forensic['score'],'signals':forensic['signals']});
        face=face_verify(doc_path,Path(selfie_path) if selfie_path else None,MODELS); log_event(db,case_id,user['sub'],'FACE_VERIFICATION_COMPLETED',{'decision':face['decision'],'match':face.get('match'),'method':face.get('method')});
        number=ocr['fields'].get('passport_number',''); reg=db.query(WatchlistEntry).filter_by(identifier_value=number).first() if number else None; reg_status=reg.status if reg else 'CLEAR'
        risk,decision=risk_score(ocr['confidence'],validation,forensic['score'],face.get('match'),reg_status)
        reasons=[]; reasons += validation['issues']; reasons += [f"{s['name']}: {s['level']} ({s['confidence']}%)" for s in forensic['signals'] if s['level']!='LOW']
        if face['decision'] in {'REVIEW','NO FACE'}:reasons.append('Possible identity mismatch')
        if face['decision']=='MODEL UNAVAILABLE':reasons.append('Face model weights unavailable; secondary verification required')
        if reg_status!='CLEAR':reasons.append(f'Watchlist/registry status: {reg_status}')
        if not reasons: reasons=['No material anomaly detected by configured checks']
        log_event(db,case_id,user['sub'],'RISK_GENERATED',{'risk_score':risk,'decision':decision});
        result={'case_id':case_id,'document_type':detected,'document_type_confidence':det_conf,'document':{'name':ocr['fields'].get('name','UNKNOWN'),'passport_number':number,'nationality':ocr['fields'].get('nationality',''),'dob':ocr['fields'].get('date_of_birth',''),'expiry':ocr['fields'].get('date_of_expiry_human') or ocr['fields'].get('date_of_expiry',''),'gender':ocr['fields'].get('sex','')},'ocr':ocr,'validation':validation,'tampering':forensic,'face':face,'registry':{'status':reg_status,'subject_name':reg.subject_name if reg else None,'category':reg.category if reg else None},'risk_score':risk,'decision':decision,'reasons':reasons}
        row.status='COMPLETED';row.risk_score=risk;row.decision=decision;row.result_json=json.dumps(result);row.completed_at=datetime.utcnow();db.commit()
        return public_case(row,True) | {'evidence_url':f'/api/evidence/{case_id}'}
    except HTTPException: raise
    except Exception as e:
        row.status='FAILED';row.decision='ERROR';row.result_json=json.dumps({'error':str(e)});db.commit(); raise HTTPException(500,f'Screening failed: {e}')

@app.get('/api/screenings/{case_id}/pipeline')
def pipeline(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row: raise HTTPException(404,'Case not found')
    events=db.query(AuditEvent).filter_by(case_id=case_id).order_by(AuditEvent.id.asc()).all()
    completed={e.event_type for e in events}
    stages=[
        ('DOCUMENT_DETECTED','Document detected'),
        ('OCR_COMPLETED','OCR extraction completed'),
        ('VALIDATION_COMPLETED','Document validation completed'),
        ('TAMPERING_ANALYSIS_COMPLETED','Tampering / forgery analysis completed'),
        ('FACE_VERIFICATION_COMPLETED','Face verification completed'),
        ('RISK_GENERATED','Risk calculation completed'),
        ('OFFICER_ACTION','Officer action recorded'),
    ]
    ordered=[]
    for event_type,label in stages:
        ordered.append({'event_type':event_type,'label':label,'status':'DONE' if event_type in completed else ('ACTIVE' if row.status=='PROCESSING' and not ordered else 'WAITING')})
    # The classifier event is not separately persisted in old cases, so derive it from case creation.
    ordered[0]['status']='DONE' if row.document_type!='unknown' else 'WAITING'
    return {'case_id':case_id,'status':row.status,'decision':row.decision,'stages':ordered}

@app.get('/api/screenings/{case_id}/document')
def original_document(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row: raise HTTPException(404,'Case not found')
    p=Path(row.document_path)
    if not p.exists(): raise HTTPException(404,'Original document not available')
    return FileResponse(p,filename=row.original_filename or p.name)

@app.get('/api/screenings/{case_id}/selfie')
def screening_selfie(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row or not row.selfie_path: raise HTTPException(404,'Selfie not available')
    p=Path(row.selfie_path)
    if not p.exists(): raise HTTPException(404,'Selfie not available')
    return FileResponse(p,filename=p.name)

@app.get('/api/screenings/{case_id}')
def screening(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row: raise HTTPException(404,'Case not found')
    return public_case(row,True) | {'evidence_url':f'/api/evidence/{case_id}'}

@app.post('/api/screenings/{case_id}/action')
def case_action(case_id:str,body:ActionIn,user=Depends(current_user),db:Session=Depends(get_db)):
    allowed={'APPROVED','REFERRED_FOR_REVIEW','REFERRED_FOR_INVESTIGATION','REJECTED'}
    if body.action not in allowed: raise HTTPException(400,f'Action must be one of {sorted(allowed)}')
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row: raise HTTPException(404,'Case not found')
    row.action=body.action; log_event(db,case_id,user['sub'],'OFFICER_ACTION',{'action':body.action,'reason':body.reason or ''}); db.commit()
    return {'case_id':case_id,'action':body.action,'updated_at':datetime.utcnow().isoformat()}

@app.get('/api/screenings/{case_id}/audit')
def audit(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    if not db.query(ScreeningCase).filter_by(case_id=case_id).first(): raise HTTPException(404,'Case not found')
    events=db.query(AuditEvent).filter_by(case_id=case_id).order_by(AuditEvent.id.asc()).all()
    return [{'id':e.id,'time':e.created_at.isoformat(),'actor':e.actor,'event_type':e.event_type,'details':json.loads(e.details_json),'event_hash':e.event_hash} for e in events]

@app.get('/api/evidence/{case_id}')
def evidence(case_id:str,user=Depends(current_user),db:Session=Depends(get_db)):
    row=db.query(ScreeningCase).filter_by(case_id=case_id).first()
    if not row: raise HTTPException(404,'Case not found')
    p=EVIDENCE/f'{case_id}_evidence.jpg'
    if not p.exists(): raise HTTPException(404,'Evidence image not available')
    return FileResponse(p,media_type='image/jpeg',filename=p.name)

@app.get('/api/watchlist/search')
def watchlist_search(q:str='',user=Depends(current_user),db:Session=Depends(get_db)):
    q=q.strip()
    rows=db.query(WatchlistEntry).filter(WatchlistEntry.identifier_value.contains(q) if q else True).limit(50).all()
    return [{'id':r.id,'identifier_type':r.identifier_type,'identifier_value':r.identifier_value,'subject_name':r.subject_name,'category':r.category,'status':r.status,'notes':r.notes} for r in rows]

@app.post('/api/watchlist')
def add_watchlist(body:WatchlistIn,user=Depends(current_user),db:Session=Depends(get_db)):
    if user.get('role')!='Administrator': raise HTTPException(403,'Administrator role required')
    row=WatchlistEntry(**body.model_dump());db.add(row);db.commit();db.refresh(row);return {'id':row.id,'status':'created'}

@app.get('/api/reports/summary')
def report_summary(user=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(ScreeningCase).all(); return {'total':len(rows),'verified':sum(r.decision=='VERIFIED' for r in rows),'manual_review':sum(r.decision=='MANUAL REVIEW' for r in rows),'high_risk':sum(r.decision=='HIGH RISK' for r in rows),'actions':{a:sum(r.action==a for r in rows) for a in ['APPROVED','REFERRED_FOR_REVIEW','REFERRED_FOR_INVESTIGATION','REJECTED','PENDING']}}

@app.get('/')
def index(): return FileResponse(FRONTEND)
@app.get('/{path:path}')
def assets(path:str):
    p=ROOT/'frontend'/path
    return FileResponse(p if p.exists() and p.is_file() else FRONTEND)
