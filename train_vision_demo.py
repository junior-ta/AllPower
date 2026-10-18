"""Train a compact binary vision model on licensed, manually staged image splits.

Expected layout: data/vision/{train,val,test}/{normal,defect}/*.{jpg,png}
Keep crops from the same source image in a single split before running.
"""
import argparse, json, random, pickle
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',default='artifacts/vision');a=p.parse_args()
    try:
        import numpy as np
        from PIL import Image
        import torch
        from torch import nn
        from sklearn.metrics import balanced_accuracy_score,recall_score,confusion_matrix
        from sklearn.linear_model import LogisticRegression
        from skimage.feature import hog
    except ImportError as exc:
        raise SystemExit(f'Missing vision dependency: {exc}. See README; do not claim vision training.')
    torch.set_num_threads(2)
    torch.manual_seed(19);np.random.seed(19);random.seed(19)
    root=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    provenance=json.loads((root/'provenance.json').read_text())
    print('Training HOG baseline first...', flush=True)
    splits={}
    for split in ('train','val','test'):
        items=[]
        for label,name in ((0,'normal'),(1,'defect')):
            items.extend((p,label) for p in (root/split/name).glob('*') if p.suffix.lower() in ('.jpg','.jpeg','.png'))
        if not items or set(y for _,y in items)!={0,1}: raise ValueError(f'{split} needs both classes')
        splits[split]=items
    paths=[str(p.resolve()) for items in splits.values() for p,_ in items]
    if len(paths)!=len(set(paths)): raise ValueError('exact duplicate path across splits')
    def pixels(path):return np.asarray(Image.open(path).convert('RGB').resize((96,96)),dtype=np.float32)/255
    def hog_features(items):
        return np.stack([hog(np.asarray(Image.open(p).convert('L').resize((96,96))),
                             pixels_per_cell=(12,12),cells_per_block=(2,2)) for p,_ in items])
    labels=lambda items:np.array([y for _,y in items])
    baseline=LogisticRegression(max_iter=300,class_weight='balanced',random_state=19)
    baseline.fit(hog_features(splits['train']),labels(splits['train']))
    with open(out/'hog_logistic.pkl','wb') as f:pickle.dump(baseline,f)
    base_pred=baseline.predict(hog_features(splits['test']))
    early={'dataset':provenance,'hog_logistic':{'balanced_accuracy':float(balanced_accuracy_score(labels(splits['test']),base_pred)), 'defect_recall':float(recall_score(labels(splits['test']),base_pred)), 'confusion_matrix':confusion_matrix(labels(splits['test']),base_pred,labels=[0,1]).tolist()}}
    (out/'hog_evaluation.json').write_text(json.dumps(early,indent=2))
    print('HOG model saved. Training CNN for at most 5 epochs...', flush=True)
    class Net(nn.Module):
        def __init__(self):
            super().__init__();self.layers=nn.Sequential(
                nn.Conv2d(3,16,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
                nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
                nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),nn.Linear(64,2))
        def forward(self,x):return self.layers(x)
    def batch(items):
        x=torch.tensor(np.stack([pixels(p).transpose(2,0,1) for p,_ in items]))
        y=torch.tensor(labels(items),dtype=torch.long)
        return x,y
    xtrain,ytrain=batch(splits['train']);xval,yval=batch(splits['val']);xtest,ytest=batch(splits['test'])
    model=Net();opt=torch.optim.Adam(model.parameters(),lr=.001);loss_fn=nn.CrossEntropyLoss(weight=len(ytrain)/(2*torch.bincount(ytrain).float()))
    best=-1;best_state=None;stale=0
    for epoch in range(5):
        model.train();order=torch.randperm(len(ytrain))
        for ids in order.split(32):
            # Simple training-only horizontal flip.
            x=xtrain[ids].clone();mask=torch.rand(len(x))<.5;x[mask]=torch.flip(x[mask],dims=[3])
            opt.zero_grad();loss=loss_fn(model(x),ytrain[ids]);loss.backward();opt.step()
        model.eval()
        with torch.no_grad():pred=model(xval).argmax(1).numpy()
        score=balanced_accuracy_score(yval.numpy(),pred)
        print(f'Epoch {epoch+1}/5: validation balanced accuracy {score:.3f}',flush=True)
        if score>best+1e-4:
            best=score;best_state={k:v.clone() for k,v in model.state_dict().items()};stale=0
        else:stale+=1
        if stale>=2:break
    model.load_state_dict(best_state);model.eval()
    with torch.no_grad():cnn_pred=model(xtest).argmax(1).numpy()
    def metrics(y,p):return {'balanced_accuracy':round(float(balanced_accuracy_score(y,p)),3),
                             'defect_recall':round(float(recall_score(y,p,pos_label=1)),3),
                             'confusion_matrix':confusion_matrix(y,p,labels=[0,1]).tolist()}
    report={'dataset':provenance,'counts':{k:len(v) for k,v in splits.items()},
            'hog_logistic':metrics(ytest.numpy(),base_pred),
            'compact_cnn':metrics(ytest.numpy(),cnn_pred),
            'validation_balanced_accuracy':round(float(best),3),
            'source_photo_grouping_checked_during_packaging':True,
            'note':'Small grouped demo subset; no verified flight-session or physical-asset independence. HOG model is used by the existing website; CNN weights are comparison evidence only.'}
    torch.save(model.state_dict(),out/'compact_cnn_state.pt')
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
