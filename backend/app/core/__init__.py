"""Infraestructura transversal.

    database.py    conexion y sesion
    base_model.py  Base declarativa y sellos de tiempo
    tiempo.py      UTC <-> America/Tijuana (el unico reloj)
    security.py    hash, JWT y dependencias de rol
    migraciones.py columnas e indices que create_all no aplica
"""
