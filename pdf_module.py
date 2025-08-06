import json
import os
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

jobs = {}

def sanitize_filename(name: str) -> str:
    """
    Generate a filesystem-safe filename from a name string.
    """
    return "".join(
        c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()


def process_folder(folder_path: str, output_dir: str) -> None:
    info_path = os.path.join(folder_path, 'group_info.json')
    with open(info_path, 'r', encoding='utf-8') as f:
        info = json.load(f)
    members = [m['name'] for m in info.get('members', [])]
    base_name = "_".join(sanitize_filename(n) for n in members)
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

    # Load & sort messages
    msg_path = os.path.join(folder_path, 'messages.json')
    with open(msg_path, 'r', encoding='utf-8') as f:
        msgs = json.load(f).get('messages', [])
    for m in msgs:
        m_dt = datetime.strptime(m['created_date'], '%A, %d %B %Y at %H:%M:%S UTC')
        m['_dt'] = m_dt
    msgs.sort(key=lambda x: x['_dt'])

    # Create PDF
    c = canvas.Canvas(pdf_path, pagesize=letter)
    w, h = letter
    margin = inch
    text = c.beginText(margin, h - margin)
    text.setFont('Helvetica', 11)

    title = f"Conversation between {', '.join(members)}"
    text.textLine(title)
    text.textLine('-' * len(title))
    text.textLine('')

    for m in msgs:
        ts = m['_dt'].strftime('%Y-%m-%d %H:%M:%S UTC')
        author = m['creator']['name']
        text.textLine(f"{ts} — {author}:")
        for line in m.get('text', '').splitlines():
            text.textLine(f"    {line}")
        text.textLine('')
        if text.getY() < margin:
            c.drawText(text)
            c.showPage()
            text = c.beginText(margin, h - margin)
            text.setFont('Helvetica', 11)
    c.drawText(text)

    # Attach images
    for fname in sorted(os.listdir(folder_path)):
        if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            img_reader = ImageReader(os.path.join(folder_path, fname))
            c.showPage()
            iw, ih = img_reader.getSize()
            max_w = w - 2 * margin
            scale = max_w / iw
            draw_h = ih * scale
            y_pos = (h - draw_h) / 2
            c.drawImage(img_reader, margin, y_pos, width=max_w, height=draw_h)

    c.save()


def worker(job_id, group_dirs, out_dir):
    total = len(group_dirs)
    jobs[job_id]['total'] = total
    jobs[job_id]['processed'] = 0
    for gd in group_dirs:
        try:
            process_folder(gd, out_dir)
        except Exception:
            pass
        jobs[job_id]['processed'] += 1
    jobs[job_id]['complete'] = True