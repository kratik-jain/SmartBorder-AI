from pathlib import Path
import cv2, numpy as np

def _models(model_dir):
    d=model_dir/'face_detection_yunet_2023mar.onnx'; r=model_dir/'face_recognition_sface_2021dec.onnx'
    if d.exists() and r.exists():
        return cv2.FaceDetectorYN.create(str(d),'',(320,320),0.9,0.3,5000), cv2.FaceRecognizerSF.create(str(r),'',0,0)
    return None,None

def verify(document_path: Path, selfie_path: Path | None, model_dir: Path):
    if not selfie_path:return {'available':False,'decision':'NOT RUN','match':None,'method':'—','reason':'No live/presented-person photo supplied'}
    doc=cv2.imread(str(document_path)); live=cv2.imread(str(selfie_path))
    if doc is None or live is None:return {'available':False,'decision':'ERROR','match':None,'method':'—','reason':'Could not decode face images'}
    detector,recognizer=_models(model_dir)
    if detector and recognizer:
        def emb(im):
            h,w=im.shape[:2];detector.setInputSize((w,h));_,faces=detector.detect(im)
            if faces is None or len(faces)==0:return None
            aligned=recognizer.alignCrop(im,faces[0]);return recognizer.feature(aligned)
        a,b=emb(doc),emb(live)
        if a is None or b is None:return {'available':True,'decision':'NO FACE','match':0.0,'method':'OpenCV SFace','reason':'A face was not detected in one or both images'}
        cosine=float(recognizer.match(a,b,cv2.FaceRecognizerSF_FR_COSINE)); score=max(0,min(100,cosine*100))
        return {'available':True,'decision':'MATCH' if cosine>=0.363 else 'REVIEW','match':round(score,1),'method':'OpenCV SFace','reason':'Cosine similarity from face embeddings'}
    return {'available':False,'decision':'MODEL UNAVAILABLE','match':None,'method':'OpenCV SFace','reason':'Install face model weights with scripts/download_models.py'}
