#!/usr/bin/env python3
"""
Script para crear un usuario de prueba en el sistema Case Manager.

Este script crea un usuario detective con permisos de administrador
para realizar pruebas del sistema.
"""
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models.user import User, Role

def create_test_user():
    """Crea un usuario de prueba para el sistema."""
    app = create_app()

    with app.app_context():
        # Crear tablas si no existen
        db.create_all()

        # Verificar si el usuario ya existe
        existing_user = User.query.filter_by(email='admin@casemanager.com').first()
        if existing_user:
            print("❌ El usuario de prueba ya existe.")
            print(f"   Email: admin@casemanager.com")
            return

        # Crear roles si no existen
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrator')
            db.session.add(admin_role)

        detective_role = Role.query.filter_by(name='detective').first()
        if not detective_role:
            detective_role = Role(name='detective', description='Private Detective')
            db.session.add(detective_role)

        db.session.commit()

        # Crear usuario de prueba
        test_user = User(
            email='admin@casemanager.com',
            nombre='Detective',
            apellidos='Admin',
            tip_number='TIP-00001',
            despacho='Despacho de Pruebas',
            telefono='+34 600 000 000',
            is_active=True,
            email_verified=True,
            mfa_enabled=False  # MFA deshabilitado para facilitar pruebas
        )

        # Establecer contraseña
        test_user.set_password('admin123')

        # Asignar roles
        test_user.roles.append(admin_role)
        test_user.roles.append(detective_role)

        # Guardar en base de datos
        db.session.add(test_user)
        db.session.commit()

        print("✅ Usuario de prueba creado exitosamente!")
        print("\n" + "="*60)
        print("CREDENCIALES DE PRUEBA")
        print("="*60)
        print(f"Email:        admin@casemanager.com")
        print(f"Contraseña:   admin123")
        print(f"TIP Number:   TIP-00001")
        print(f"Nombre:       Detective Admin")
        print(f"Roles:        admin, detective")
        print(f"MFA:          Deshabilitado")
        print("="*60)
        print("\nAccede a http://localhost para iniciar sesión")
        print()

if __name__ == '__main__':
    create_test_user()
