#!/usr/bin/env python3
from app import create_app
from app.models.evidence import Evidence
from app.extensions import db

app = create_app('production')

with app.app_context():
    evidences = Evidence.query.filter_by(is_deleted=False).limit(5).all()
    print(f'Evidencias encontradas: {len(evidences)}')
    for e in evidences:
        print(f'  ID: {e.id}, Nombre: {e.original_filename}, MIME: {e.mime_type}')
