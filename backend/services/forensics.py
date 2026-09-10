from pathlib import Path
import cv2, numpy as np
from PIL import Image, ExifTags

def metadata(path):
    try:
        ex=Image.open(path).getexif(); return {ExifTags.TAGS.get(k,str(k)):str(v)[:300] for k,v in ex.items()}
    except:return {}

def analyze(path: Path, evidence_path: Path):
    img=cv2.imread(str(path))
    if img is None: raise ValueError('Image decode failed during forensic analysis')
    rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
    pil=Image.fromarray(rgb)
    tmp=evidence_path.with_suffix('.ela.jpg')
    pil.save(tmp,'JPEG',quality=88)
    recom=np.asarray(Image.open(tmp)).astype(np.int16)
    orig=np.asarray(pil).astype(np.int16)
    diff=np.abs(orig-recom).mean(axis=2)
    tmp.unlink(missing_ok=True)
    p95=float(np.percentile(diff,95)); mean=float(diff.mean())
    score=float(min(100,max(0,(p95/25)*65+(mean/10)*35)))
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY); blur=float(cv2.Laplacian(gray,cv2.CV_64F).var())
    metadata_flags=[]; meta=metadata(path)
    if 'Software' in meta or 'ProcessingSoftware' in meta: metadata_flags.append('Editing software metadata present')
    heat=np.uint8(np.clip(diff*7,0,255)); heat=cv2.applyColorMap(heat,cv2.COLORMAP_JET)
    # Highlight strongest anomalies over document at 50% alpha.
    overlay=cv2.addWeighted(img,0.55,heat,0.45,0)
    evidence_path.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(evidence_path),overlay)
    signals=[]
    if score>=70: signals.append(('Text / region manipulation','HIGH',round(min(99,score+5),1)))
    elif score>=40: signals.append(('Text / region manipulation','MEDIUM',round(score,1)))
    else: signals.append(('Text / region manipulation','LOW',round(100-score,1)))
    if blur < 40: signals.append(('Image quality anomaly','MEDIUM',78.0))
    else: signals.append(('Image quality anomaly','LOW',18.0))
    signals.append(('Metadata anomaly','LOW' if not metadata_flags else 'MEDIUM',20.0 if not metadata_flags else 68.0))
    return {'score':round(score,1),'signals':[{'name':a,'level':b,'confidence':c} for a,b,c in signals],'metadata':meta,'metadata_flags':metadata_flags,'evidence_image':str(evidence_path.relative_to(path.parents[1])).replace('\\','/'),'heatmap_path':str(evidence_path)}
