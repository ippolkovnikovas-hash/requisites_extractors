import os
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from app.schemas.validation import PipelineResult
from app.services.pipeline_service import run_pipeline

web_bp = Blueprint('web', __name__)
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.jpg', '.jpeg', '.png', '.tiff'}


def _allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


@web_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html', result=None)


@web_bp.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('Файл не был отправлен', 'error')
        return redirect(url_for('web.index'))

    file = request.files['file']

    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('web.index'))

    if not _allowed_file(file.filename):
        flash('Неподдерживаемый формат файла', 'error')
        return redirect(url_for('web.index'))

    original_name = file.filename
    filename = secure_filename(original_name)
    short_id = uuid.uuid4().hex[:8]
    name, ext = os.path.splitext(filename)
    stored_name = f"{name}_{short_id}{ext}"

    upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
    file_path = upload_folder / stored_name
    file.save(str(file_path))

    try:
        result: PipelineResult = run_pipeline(file_path, original_name)
    except Exception as exc:
        current_app.logger.exception('Ошибка при обработке файла')
        flash(f'Ошибка при обработке файла: {exc}', 'error')
        return redirect(url_for('web.index'))

    flash('Файл успешно обработан', 'success')
    return render_template('index.html', result=result)


@web_bp.route('/downloads/<path:filename>', methods=['GET'])
def downloads(filename: str):
    return send_from_directory(current_app.config['EXPORT_FOLDER'], filename, as_attachment=True)
