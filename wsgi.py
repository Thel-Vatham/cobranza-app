# WSGI para PythonAnywhere
# 1. Sustituye "tu_usuario" por tu nombre de usuario real de PythonAnywhere.
# 2. Copia el contenido de este archivo en el WSGI que te da PythonAnywhere
#    (pestaña "Web" > enlace al archivo WSGI), o apunta ese WSGI a importar este.
import sys
import os

project_home = "/home/tu_usuario/cartera"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Variables de entorno (ajústalas según necesites).
# Descomenta para EXIGIR inicio de sesión (admin / admin123):
# os.environ["AUTH_DISABLED"] = "false"

from run import app as application
