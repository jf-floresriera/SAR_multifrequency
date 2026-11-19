# Contexto para asistentes de IA / Context for AI assistants

Lea primero / Read first: [`docs/PROYECTO.md`](docs/PROYECTO.md) (objetivo, datos, método, reglas SRL, estado) ·
[`docs/notas_procesamiento.md`](docs/notas_procesamiento.md) (decisiones) · [`manuscrito/`](manuscrito/) (borradores y checklist SRL).

Reglas / Rules:
- Toda salida (figuras, tablas, pies, mensajes) en **español e inglés** vía `src/comun.py`.
- Lógica en `src/*.py`; notebooks solo `correr("script.py")`. El usuario ejecuta en Google Colab; datos en Google Drive.
- Figuras con formato SRL: sin título interno, etiquetas (a)(b) fuera arriba-izquierda, fuentes ≥ 6 pt tras reducción, legibles en gris.
- Registrar cada decisión nueva en `docs/notas_procesamiento.md`.
