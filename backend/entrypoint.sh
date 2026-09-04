#!/bin/sh
# Primer arranque: si el volumen esta vacio, se copia la base que ya existe en
# el repo (montada de solo lectura en /semilla).
#
# Sin esto el contenedor arrancaria con una base recien creada: el seed siembra
# roles, usuarios y el plano, pero NO las 383 unidades reales -- esas las trajo
# importador.py desde los Excel y el arranque no lo ejecuta. El demo saldria
# vacio y pareceria que algo se rompio.
set -e

mkdir -p /datos

if [ ! -f /datos/bajagas.db ]; then
  if [ -f /semilla/bajagas.db ]; then
    echo "[bajagas] volumen vacio -> copiando la base del repo"
    cp /semilla/bajagas.db /datos/bajagas.db
  else
    echo "[bajagas] no hay /semilla/bajagas.db: se arranca con base nueva (solo seed)"
  fi
fi

exec "$@"
