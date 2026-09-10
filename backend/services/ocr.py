import os, re, shutil
from pathlib import Path
import cv2
import pytesseract

MRZ_WEIGHTS = [7, 3, 1]

def _configure_tesseract():
    cmd = os.getenv('TESSERACT_CMD')
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    elif shutil.which('tesseract'):
        return
    candidates = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
    ]
    for c in candidates:
        if Path(c).exists():
            pytesseract.pytesseract.tesseract_cmd = c
            return

_configure_tesseract()

def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.7, fy=1.7, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

def clean_lines(text):
    out=[]
    for line in text.splitlines():
        s=re.sub(r'[^A-Z0-9<:/.,\- ]','',line.upper()).strip()
        if s: out.append(s)
    return out

def char_value(ch):
    if ch == '<': return 0
    if ch.isdigit(): return int(ch)
    if 'A' <= ch <= 'Z': return ord(ch)-55
    return None

def check_digit(data, expected):
    if len(expected)!=1 or not expected.isdigit(): return False
    total=0
    for i,ch in enumerate(data):
        v=char_value(ch)
        if v is None: return False
        total += v * MRZ_WEIGHTS[i % 3]
    return total % 10 == int(expected)

def parse_mrz(lines):
    c=[re.sub(r'\s','',x) for x in lines if '<' in x and len(re.sub(r'\s','',x)) >= 30]
    for i in range(len(c)-1):
        a=c[i][:44].ljust(44,'<'); b=c[i+1][:44].ljust(44,'<')
        if not a.startswith('P<') or len(b)<28: continue
        passport_no=b[0:9]; nationality=b[10:13]; dob=b[13:19]; sex=b[20]; expiry=b[21:27]
        name_parts=a[5:44].split('<<',1)
        surname=name_parts[0].replace('<',' ').strip()
        given=name_parts[1].replace('<',' ').strip() if len(name_parts)>1 else ''
        valid_num=check_digit(passport_no,b[9]); valid_dob=check_digit(dob,b[19]); valid_expiry=check_digit(expiry,b[27])
        return {
            'detected':True,
            'valid':bool(valid_num and valid_dob and valid_expiry),
            'checks':{'passport_number':valid_num,'date_of_birth':valid_dob,'date_of_expiry':valid_expiry},
            'raw':[a,b],
            'fields':{'passport_number':passport_no.replace('<',''),'nationality':nationality,'date_of_birth':dob,'sex':sex,'date_of_expiry':expiry,'surname':surname,'given_names':given,'name':' '.join([x for x in [given,surname] if x])}
        }
    return {'detected':False,'valid':False,'checks':{},'raw':[],'fields':{}}

def extract_fields(path: Path):
    img=cv2.imread(str(path))
    if img is None: raise ValueError('Unable to decode document image')
    try:
        runs=[]
        for view in (img, preprocess(img)):
            runs.append(pytesseract.image_to_string(view, config='--psm 6'))
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError('Tesseract OCR is not installed or not on PATH. Install Tesseract and restart SMARTBORDER AI.') from exc
    text='\n'.join(runs)
    lines=clean_lines(text)
    mrz=parse_mrz(lines)
    fields=dict(mrz['fields'])
    joined='\n'.join(lines)
    patterns={
        'passport_number':r'(?:PASSPORT\s*(?:NO|NUMBER)?|DOCUMENT\s*(?:NO|NUMBER)?)\s*[: ]\s*([A-Z0-9]{6,12})',
        'nationality':r'NATIONALITY\s*[: ]\s*([A-Z]{3,15})',
        'sex':r'(?:SEX|GENDER)\s*[: ]\s*([MF])',
        'dob':r'(?:DATE OF BIRTH|DOB)\s*[: ]\s*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})',
        'expiry_human':r'(?:DATE OF EXPIRY|EXPIRY)\s*[: ]\s*(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})',
        'name':r'(?:FULL NAME|NAME)\s*[: ]\s*([A-Z][A-Z .<\-]{4,80})'
    }
    for k,p in patterns.items():
        if k in fields: continue
        m=re.search(p,joined)
        if m: fields[k]=m.group(1).replace('<',' ').strip()
    if 'dob' in fields and 'date_of_birth' not in fields: fields['date_of_birth']=fields['dob']
    if 'expiry_human' in fields and 'date_of_expiry_human' not in fields: fields['date_of_expiry_human']=fields['expiry_human']
    # Tesseract confidence if available; use TSV word confidences.
    conf=50.0
    try:
        d=pytesseract.image_to_data(preprocess(img),config='--psm 6',output_type=pytesseract.Output.DICT)
        vals=[float(x) for x in d['conf'] if float(x)>=0]
        if vals: conf=sum(vals)/len(vals)
    except Exception: pass
    return {'confidence':round(max(0,min(99.5,conf)),1),'raw_text':text[:12000],'lines':lines[:150],'fields':fields,'mrz':mrz}
