# Guía rápida del juguete Pokémon

Abre **[Guia-rapida-Pokemon-A4.pdf](Guia-rapida-Pokemon-A4.pdf)**.

- Papel A4, orientación vertical y escala 100 % (tamaño real).
- Son dos páginas: puedes imprimirlas a doble cara, girando por el borde largo.
- Los colores de carga también aparecen escritos para que se entiendan en blanco y negro.
- `vista-previa-1.png` y `vista-previa-2.png` permiten revisar las dos caras.

## Contenido e imágenes

La guía explica el encendido, los dos juegos, la lectura de descripciones, los cuidados,
el movimiento, la carga y el apagado. El botón izquierdo y derecho se identifican
como en las instrucciones del proyecto, con la pantalla en su orientación normal.

Las imágenes son recreaciones de escritorio con los gráficos originales de la SD
y los renderizadores del proyecto; **no son fotografías ni capturas tomadas de la placa**.
La tipografía de pantalla es aproximada. El menú, la descripción, los indicadores
de cuidado y el dibujo de apagado se generan a partir de sus funciones del firmware.
La carga usa valores de ejemplo. No se modifica el juguete para producir esta guía.

## Regenerar

Desde la raíz del repositorio, en macOS:

```sh
uv run --no-project --python 3.11 --with pillow --with numpy --with reportlab python docs/guia/crear_guia.py
```

El script usa las fuentes Arial del sistema y escribe el PDF y las imágenes en esta carpeta.
La guía se ha revisado visualmente como PDF A4 de dos páginas.
