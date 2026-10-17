"""Optional licensed image inference. Never substitute the scenario finding."""
from io import BytesIO
import os, pickle
from pathlib import Path

def classify(data):
    model_path=Path(os.getenv('ALLPOWER_VISION_MODEL','artifacts/vision/hog_logistic.pkl'))
    if not model_path.exists():
        raise FileNotFoundError('No trained vision model is installed')
    from PIL import Image, UnidentifiedImageError
    import numpy as np
    from skimage.feature import hog
    try:
        img=Image.open(BytesIO(data)); img.verify()
        img=Image.open(BytesIO(data)).convert('L').resize((96,96))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Invalid image') from exc
    vector=hog(np.asarray(img),pixels_per_cell=(12,12),cells_per_block=(2,2))
    with open(model_path,'rb') as f:model=pickle.load(f)
    probability=float(model.predict_proba([vector])[0][1])
    result='inspection required' if .35 <= probability <= .65 else ('defect concern' if probability>.65 else 'no defect concern')
    return {'result':result,'defect_score':round(probability,3),
            'model_version':'hog-logistic-v1','provenance':'trained licensed image model',
            'note':'Score is a classifier output, not a calibrated asset-failure probability.'}
