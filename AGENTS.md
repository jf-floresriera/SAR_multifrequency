# Contexto para asistentes de IA / Context for AI assistants

Lea primero / Read first: **[`docs/HANDOFF.md`](docs/HANDOFF.md) (estado real y qué NO repetir)** · [`docs/PROYECTO.md`](docs/PROYECTO.md) (objetivo, datos, método, reglas SRL, estado) ·
[`docs/notas_procesamiento.md`](docs/notas_procesamiento.md) (decisiones) · [`manuscrito/`](manuscrito/) (borradores, checklist, requisitos de envío y **guía de estilo SRL**: `manuscrito/GUIA_ESTILO_SRL.md`).

Reglas / Rules:
- Toda salida (figuras, tablas, pies, mensajes) en **español e inglés** vía `src/comun.py`.
- Lógica en `src/*.py`; notebooks solo `correr("script.py")`. El usuario ejecuta en Google Colab; datos en Google Drive.
- Figuras con formato SRL: sin título interno, etiquetas (a)(b) fuera arriba-izquierda, fuentes ≥ 6 pt tras reducción, legibles en gris.
- Registrar cada decisión nueva en `docs/notas_procesamiento.md`.
- **No reenviar a HyP3 ni redescargar**: usar `src/registro_datos.py` (clave = par de escenas + resolución). Ver `docs/HANDOFF.md` §1.
- Figuras: `src/estilo_figuras.py` + `docs/ESTILO_FIGURAS.md` (paletas Crameri; divergentes necesitan contornos con signo para gris). Capas de referencia de mapas: `docs/REFERENCIAS_MAPA.md`.
- No subir imágenes Planet (CC BY-NC) ni Esri, ni credenciales, ni datos pesados. No modificar el entorno global de Python.
