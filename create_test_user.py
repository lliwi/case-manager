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
        try:
            # Verificar si el usuario ya existe
            existing_user = User.query.filter_by(email='admin@casemanager.com').first()
            if existing_user:
                print("Usuario admin ya existe:")
                print("  Email:    admin@casemanager.com")
                print("  Password: admin123")
                return True

            # Crear roles si no existen
            admin_role = Role.query.filter_by(name='admin').first()
            if not admin_role:
                admin_role = Role(name='admin', description='Administrator')
                db.session.add(admin_role)
                print("Rol 'admin' creado")

            detective_role = Role.query.filter_by(name='detective').first()
            if not detective_role:
                detective_role = Role(name='detective', description='Private Detective')
                db.session.add(detective_role)
                print("Rol 'detective' creado")

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

            print("")
            print("=" * 60)
            print("  USUARIO ADMINISTRADOR CREADO")
            print("=" * 60)
            print("")
            print("  Email:      admin@casemanager.com")
            print("  Password:   admin123")
            print("  TIP:        TIP-00001")
            print("  Nombre:     Detective Admin")
            print("  Roles:      admin, detective")
            print("  MFA:        Deshabilitado")
            print("")
            print("=" * 60)
            return True

        except Exception as e:
            print(f"ERROR: {e}")
            db.session.rollback()
            return False


if __name__ == '__main__':
    success = create_test_user()
    sys.exit(0 if success else 1)
