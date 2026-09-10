from datetime import date, datetime
import re

def _date(s):
    for fmt in ('%d-%m-%Y','%d/%m/%Y','%Y-%m-%d','%d-%m-%y','%d/%m/%y'):
        try:return datetime.strptime(s,fmt).date()
        except:pass
    return None

def _mrz_date(s, expiry=False):
    if not s or len(s)!=6 or not s.isdigit(): return None
    yy,mm,dd=int(s[:2]),int(s[2:4]),int(s[4:6]); year=(2000+yy if yy<=49 else 1900+yy)
    try:return date(year,mm,dd)
    except:return None

def validate_document(document_type, fields, mrz):
    checks=[]; issues=[]
    num=fields.get('passport_number','')
    if document_type=='passport':
        ok=bool(re.fullmatch(r'[A-Z0-9]{7,9}',num)) if num else False
        checks.append({'name':'Passport number format','status':'PASS' if ok else 'REVIEW'})
        if not ok: issues.append('Passport number format could not be confidently validated')
    else:
        checks.append({'name':'Required document fields','status':'PASS' if fields else 'REVIEW'})
    mrz_ok=bool(mrz.get('detected') and mrz.get('valid'))
    if document_type=='passport':
        checks.append({'name':'MRZ check digits','status':'PASS' if mrz_ok else 'REVIEW'})
        if not mrz_ok: issues.append('MRZ was not detected or one or more check digits failed')
    exp_raw=fields.get('date_of_expiry_human') or fields.get('date_of_expiry')
    exp=_date(exp_raw) if exp_raw and len(exp_raw) >= 8 else _mrz_date(fields.get('date_of_expiry'))
    if exp:
        valid=exp>=date.today(); checks.append({'name':'Expiry check','status':'PASS' if valid else 'FAIL'})
        if not valid: issues.append('Document appears to be expired')
    else:
        checks.append({'name':'Expiry check','status':'REVIEW'}); issues.append('Expiry date not confidently parsed')
    required=['name','nationality'] if document_type=='passport' else []
    missing=[x for x in required if not fields.get(x)]
    checks.append({'name':'Required fields','status':'PASS' if not missing else 'REVIEW'})
    if missing: issues.append('Missing OCR fields: '+', '.join(missing))
    return {'checks':checks,'issues':issues,'valid':not any(c['status']=='FAIL' for c in checks),'expiry_valid':not any('expired' in i.lower() for i in issues)}
