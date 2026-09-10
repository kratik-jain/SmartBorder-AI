from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parents[1]; M=ROOT/'models'; M.mkdir(exist_ok=True)
models={
 'face_detection_yunet_2023mar.onnx':'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
 'face_recognition_sface_2021dec.onnx':'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx'}
for n,u in models.items():
 p=M/n
 if p.exists() and p.stat().st_size>100000: print('OK',n); continue
 print('Downloading',n); urllib.request.urlretrieve(u,p); print('saved',p,p.stat().st_size)
