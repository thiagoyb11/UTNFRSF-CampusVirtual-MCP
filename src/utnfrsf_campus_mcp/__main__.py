"""Permite ejecutar el servidor con python -m utnfrsf_campus_mcp."""

from utnfrsf_campus_mcp.server import main

# Punto de entrada de `python -m`: delega en el mismo main() que el script instalado.
if __name__ == "__main__":
    main()
