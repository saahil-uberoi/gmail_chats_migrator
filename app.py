import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
import time
from io import BytesIO


from flask import  Flask, request, render_template, send_file, abort, jsonify, Response

from src.pdf_module import jobs, worker

app = Flask(__name__)
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'zip_file' not in request.files:
        return abort(400, 'No file part')
    upload = request.files['zip_file']
    if upload.filename == '':
        return abort(400, 'No selected file')

    job_id = str(uuid.uuid4())
    tempdir = tempfile.mkdtemp()
    jobs[job_id] = {'tempdir': tempdir, 'total': 0, 'processed': 0, 'complete': False}

    zip_path = os.path.join(tempdir, 'upload.zip')
    upload.save(zip_path)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(tempdir)

    group_dirs = []
    for root, dirs, files in os.walk(tempdir):
        if 'group_info.json' in files and 'messages.json' in files:
            group_dirs.append(root)
    if not group_dirs:
        shutil.rmtree(tempdir)
        jobs.pop(job_id, None)
        return abort(400, 'No valid group folders found')

    out_dir = os.path.join(tempdir, 'pdfs')
    os.makedirs(out_dir, exist_ok=True)
    threading.Thread(target=worker, args=(job_id, group_dirs, out_dir), daemon=True).start()

    return jsonify({'job_id': job_id})


@app.route('/progress/<job_id>')
def progress(job_id):
    if job_id not in jobs:
        return abort(404)
    def generate():
        while True:
            job = jobs.get(job_id)
            data = {'total': job['total'], 'processed': job['processed'], 'complete': job['complete']}
            yield f"data: {json.dumps(data)}\n\n"
            if job['complete']:
                break
            time.sleep(0.5)
    return Response(generate(), mimetype='text/event-stream')


@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job or not job['complete']:
        return abort(404)
    out_dir = os.path.join(job['tempdir'], 'pdfs')
    mem = BytesIO()
    with zipfile.ZipFile(mem, 'w') as zout:
        for f in os.listdir(out_dir):
            if f.lower().endswith('.pdf'):
                zout.write(os.path.join(out_dir, f), arcname=f)
    mem.seek(0)
    shutil.rmtree(job['tempdir'])
    jobs.pop(job_id, None)
    return send_file(mem, download_name='all_pdfs.zip', as_attachment=True, mimetype='application/zip')


if __name__ == '__main__':
    app.run(debug=True)