"""Trusted media processing helper. Never evaluates user Python, R, MATLAB or formulas."""
import argparse,json,os,subprocess,tempfile,wave
from pathlib import Path

def ocr_image(image):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS=16000000
    if image.width*image.height>16000000:raise ValueError('Image too large')
    from rapidocr_onnxruntime import RapidOCR
    global engine
    if engine is None:engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
    result,_=engine(image)
    return [{'text':str(row[1]),'confidence':float(row[2]),'box':[[float(x),float(y)] for x,y in row[0]]} for row in (result or [])]

def process(file,mode,language,models,ffmpeg):
    suffix=file.suffix.lower();segments=[];warning='';status='ready'
    if mode=='ocr' or suffix in ['.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp']:
        from PIL import Image
        if suffix=='.pdf':
            import pypdfium2 as pdfium
            pdf=pdfium.PdfDocument(str(file))
            try:
                pages=len(pdf)
                for i in range(min(pages,20)):
                    page=pdf[i];scale=min(2.0,2200/max(page.get_width(),page.get_height()));bitmap=page.render(scale=scale)
                    try:words=ocr_image(bitmap.to_pil().convert('RGB'))
                    finally:bitmap.close();page.close()
                    segments.extend({**word,'page':i+1} for word in words)
                if pages>20:status='partial';warning='OCR仅处理前20页，原始PDF完整保留。'
            finally:pdf.close()
        else:
            with Image.open(file) as image:segments=[{**word,'page':1} for word in ocr_image(image.convert('RGB'))]
        text='\n'.join(x['text'] for x in segments)
        if not text.strip():return {'text':'','status':'saved_only','warning':'未识别到文字，请核对清晰度、语言及版式；原件保留。','segments':[]}
        return {'text':text,'status':status,'warning':warning,'segments':segments,'engine':'RapidOCR/ONNX Runtime'}
    if mode=='transcribe':
        from vosk import Model,KaldiRecognizer,SetLogLevel
        SetLogLevel(-1)
        model_path=models/('vosk-model-small-cn-0.22' if language=='zh' else 'vosk-model-small-en-us-0.15')
        if not model_path.is_dir():return {'text':'','status':'awaiting_model','warning':'本地语音模型未安装，未产生转写结果。','segments':[]}
        formats={'.wav':'wav','.mp3':'mp3','.mp4':'mov','.m4a':'mov','.webm':'matroska','.mkv':'matroska','.ogg':'ogg','.flac':'flac'}
        if suffix not in formats:raise ValueError('Unsupported media format')
        with tempfile.TemporaryDirectory() as folder:
            wav=Path(folder)/'audio.wav'
            subprocess.run([ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe','-f',formats[suffix],'-i',str(file),'-vn','-ac','1','-ar','16000','-t','600','-f','wav',str(wav)],check=True,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            # Vosk's Windows native library opens UTF-8 paths through narrow C APIs.
            # A relative ASCII path avoids failing when this existing workspace has a Chinese name.
            previous=Path.cwd()
            try:
                os.chdir(model_path);model=Model('.')
            finally:os.chdir(previous)
            recognizer=KaldiRecognizer(model,16000);recognizer.SetWords(True);texts=[]
            with wave.open(str(wav),'rb') as stream:
                duration=stream.getnframes()/stream.getframerate()
                while True:
                    data=stream.readframes(4000)
                    if not data:break
                    if recognizer.AcceptWaveform(data):
                        result=json.loads(recognizer.Result());texts.append(result.get('text',''));segments.extend(result.get('result',[]))
            result=json.loads(recognizer.FinalResult());texts.append(result.get('text',''));segments.extend(result.get('result',[]));text=' '.join(t for t in texts if t)
            if not text.strip():return {'text':'','status':'saved_only','warning':'没有识别到可读语音；不能把静音或无结果视为成功。','segments':[]}
            if duration>=599.9:status='partial';warning='转写最多处理前10分钟，完整音视频原件保留。'
            return {'text':text,'status':status,'warning':warning,'segments':segments,'engine':'Vosk small '+language,'durationSeconds':duration}
    raise ValueError('Unsupported mode')

engine=None
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--mode',choices=['ocr','transcribe'],required=True);parser.add_argument('--language',choices=['zh','en'],default='zh');parser.add_argument('--models',required=True);parser.add_argument('--ffmpeg',default='ffmpeg');parser.add_argument('--start-gate');args=parser.parse_args()
    if args.start_gate:
        import time
        deadline=time.monotonic()+10
        while not Path(args.start_gate).is_file():
            if time.monotonic()>deadline:raise SystemExit('Media supervisor did not establish containment')
            time.sleep(.02)
    try:result=process(Path(args.input).resolve(),args.mode,args.language,Path(args.models),args.ffmpeg)
    except Exception:result={'text':'','status':'failed','warning':'媒体处理未完成，请检查格式、工具及资源限制；原件仍保留。','segments':[]}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False),'utf-8')
