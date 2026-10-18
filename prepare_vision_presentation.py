"""Run from the AllPower root on LinuxONE: %run prepare_vision_presentation.py
Creates pitch PNGs using the saved model and a website page using /api/inspection.
Does not train, alter model files or change the main dashboard.
"""
import json
import shutil
import textwrap
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from allpower.vision import classify


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AllPower Image Inspection Demo</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0d202e;color:#edf5f7;font:17px/1.5 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:40px 26px}a{color:#69dfc7}h1{font-size:40px;line-height:1.1;margin:12px 0}h2{font-size:27px}p{color:#b8cbd6}.eyebrow{color:#69dfc7;font-weight:700;letter-spacing:2px;font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:28px}.panel{background:#183342;border:1px solid #355260;border-radius:12px;padding:24px}label{display:block;margin:14px 0 7px}input{max-width:100%}input[type=password]{width:100%;padding:10px;border-radius:5px;border:1px solid #56717e;background:#102632;color:white}button{padding:13px 20px;background:#69dfc7;color:#0d202e;border:0;border-radius:6px;font-weight:bold;font-size:16px;cursor:pointer;margin-top:16px}button:disabled{opacity:.5}#preview{display:none;width:100%;height:290px;object-fit:contain;background:#0d202e;margin-top:20px;image-rendering:auto}.metric{font-size:32px;color:white}small{color:#b8cbd6}#result{color:#69dfc7}footer{margin-top:25px;font-size:13px;color:#b8cbd6}@media(max-width:720px){.grid{grid-template-columns:1fr}}
</style></head><body><main>
<div class="eyebrow">ALLPOWER / EXPERIMENTAL IMAGE INSPECTION</div>
<h1>Inspect a glass insulator</h1>
<p>Upload a cropped equipment image. The trained HOG classifier checks for a missing-cap defect.</p>
<div class="grid"><section class="panel"><h2>Image input</h2>
<label for="token">Private demo access token</label><input id="token" type="password" autocomplete="off" placeholder="Enter the existing AllPower token">
<small>Held only in this page while it is open. Do not include the token in recordings.</small>
<label for="file">PNG or JPEG under 2 MB</label><input id="file" type="file" accept="image/png,image/jpeg">
<img id="preview" alt="Selected glass insulator image"><br><button id="run">Classify image</button>
</section><section class="panel" aria-live="polite"><div class="eyebrow">LIVE MODEL RESPONSE</div>
<h2 id="result">Waiting for an image</h2><div id="score" class="metric"></div>
<p id="action">This result comes from the LinuxONE API, not a scripted scenario.</p><small id="model"></small>
<hr><p>A model score is not a calibrated probability of failure or an outage forecast. Human inspection is required before operational decisions.</p>
<p id="metrics">Loading evaluation summary...</p></section></div>
<footer>InsPLAD glass-insulator subset · Vieira-e-Silva et al. (2023) · CC BY-NC 3.0.<br>
Source photos are separated across splits; independence of adjacent flight frames and physical assets is unverified. This is a small research demo.<br>
<a href="/">Return to the main dashboard</a></footer></main>
<script>
const el=id=>document.getElementById(id);let previewURL;
el('file').onchange=()=>{el('result').textContent='Ready to classify';el('score').textContent='';el('model').textContent='';const f=el('file').files[0];if(previewURL)URL.revokeObjectURL(previewURL);if(f){previewURL=URL.createObjectURL(f);el('preview').src=previewURL;el('preview').style.display='block'}else{el('preview').style.display='none'}};
el('run').onclick=async()=>{const f=el('file').files[0];if(!f){el('result').textContent='Choose an image first';return}if(!['image/png','image/jpeg'].includes(f.type)||f.size>2000000){el('result').textContent='Use a PNG or JPEG under 2 MB';return}el('run').disabled=true;el('result').textContent='Running on LinuxONE...';el('score').textContent='';el('model').textContent='';try{const r=await fetch('/api/inspection',{method:'POST',headers:{'X-AllPower-Token':el('token').value.trim(),'Content-Type':f.type},body:f});const d=await r.json();if(!r.ok)throw Error(d.error||'API request failed');el('result').textContent=d.result;el('score').textContent='Defect score: '+Number(d.defect_score).toFixed(3);el('model').textContent=d.model_version+' | '+d.provenance;el('action').textContent=d.result==='defect concern'?'Suggested next step: request human inspection.':d.result==='inspection required'?'Uncertain model output: request human inspection.':'No defect concern flagged by this model. A missed defect remains possible.'}catch(e){el('result').textContent='Could not classify';el('action').textContent=e.message}finally{el('run').disabled=false}};
fetch('/vision-demo-metrics.json').then(r=>{if(!r.ok)throw Error();return r.json()}).then(d=>{el('metrics').textContent='Held-out demo set: '+d.test_count+' images. Balanced accuracy '+(100*d.balanced_accuracy).toFixed(1)+'%; defect recall '+(100*d.defect_recall).toFixed(1)+'%. These are model test results, not a guarantee for this image.'}).catch(()=>el('metrics').textContent='Evaluation summary unavailable. Do not infer performance from this example.');
</script></body></html>'''


def font(size):
    for f in ['/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/usr/share/fonts/dejavu/DejaVuSans.ttf']:
        if Path(f).exists(): return ImageFont.truetype(f,size)
    return ImageFont.load_default(size=size)


def main():
    root=Path.cwd()
    if not (root/'web').is_dir(): raise RuntimeError('Run from the AllPower repository root.')
    report=json.loads(Path('artifacts/vision/evaluation.json').read_text())
    metrics=report['hog_logistic']
    out=Path('artifacts/vision_demo');out.mkdir(parents=True,exist_ok=True)
    examples=out/'upload_examples';examples.mkdir(exist_ok=True)
    records=[]
    for label in ('normal','defect'):
        source=sorted(Path(f'data/vision_demo/test/{label}').glob('*.png'))[0]
        data=source.read_bytes();result=classify(data)
        shutil.copyfile(source,examples/f'{label}_example.png')
        card=Image.new('RGB',(1600,900),'#0d202e');draw=ImageDraw.Draw(card)
        draw.text((60,40),'ALLPOWER  /  IMAGE INSPECTION DEMO',font=font(25),fill='#69dfc7')
        draw.text((60,93),'Glass insulator defect classification',font=font(43),fill='white')
        photo=Image.open(source).convert('RGB');photo.thumbnail((530,480))
        # Enlarge only for presentation. No extra image detail is created.
        photo=photo.resize((480,480),Image.Resampling.NEAREST)
        card.paste(photo,(60,195))
        draw.text((60,700),'Model input: 96 x 96 pixel crop',font=font(23),fill='#b8cbd6')
        x=620
        expected='Missing-cap defect' if label=='defect' else 'Normal'
        draw.text((x,200),'DATASET LABEL',font=font(23),fill='#b8cbd6')
        draw.text((x,240),expected,font=font(37),fill='white')
        draw.text((x,320),'ACTUAL MODEL RESPONSE',font=font(23),fill='#b8cbd6')
        draw.text((x,363),result['result'],font=font(39),fill='#69dfc7')
        draw.text((x,430),f'Defect score: {result["defect_score"]:.3f}',font=font(32),fill='white')
        draw.text((x,482),'HOG + logistic regression | LinuxONE run',font=font(25),fill='#b8cbd6')
        lines=[f'Test balanced accuracy: {metrics["balanced_accuracy"]*100:.1f}%',
               f'Defect recall: {metrics["defect_recall"]*100:.1f}% | {report["counts"]["test"]} test images',
               'Illustrative example; not an outage prediction.',
               'Score is not a calibrated failure probability.']
        for i,line in enumerate(lines):draw.text((x,552+38*i),line,font=font(24),fill='#b8cbd6')
        draw.text((60,795),'Source: InsPLAD | Vieira-e-Silva et al. (2023) | CC BY-NC 3.0',font=font(23),fill='#b8cbd6')
        draw.text((60,835),'First test example by filename. No selection based on whether the prediction was correct.',font=font(22),fill='#b8cbd6')
        card.save(out/f'pitch_{label}.png')
        records.append({'source':str(source),'dataset_label':label,'api_prediction':result})
        print(label,result)
    (out/'example_predictions.json').write_text(json.dumps(records,indent=2))
    # These are new, dedicated demo assets; existing dashboard files stay untouched.
    # Keep the current supplier portal entry point; this script only refreshes evidence.
    if not Path('web/vision-demo.html').exists():
        Path('web/vision-demo.html').write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="0;url=/supplier.html#inspection">'
            '<title>AllPower inspection</title><a href="/supplier.html#inspection">'
            'Open supplier inspection</a></html>')
    Path('web/vision-demo-metrics.json').write_text(json.dumps({'test_count':report['counts']['test'],**metrics},indent=2))
    with zipfile.ZipFile(out/'pitch_and_upload_images.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ('pitch_normal.png','pitch_defect.png','example_predictions.json'):
            z.write(out/name,name)
        for path in sorted(examples.glob('*.png')):z.write(path,'upload_examples/'+path.name)
    print('\nREADY: download artifacts/vision_demo/pitch_and_upload_images.zip')
    print('Supplier inspection page preserved: web/vision-demo.html')
    print('Rebuild and recreate the web container to serve the new page. No retraining needed.')


if __name__=='__main__': main()
