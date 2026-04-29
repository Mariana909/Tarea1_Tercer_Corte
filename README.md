# Parser Sintáctico Predictivo LL(k)

Analizador sintáctico descendente sin retroceso (predictivo) basado en tabla,
implementado en Python. Soporta múltiples gramáticas y genera el árbol de
derivación de cada entrada como imagen.

---

## Requisitos

- Python 3.8+
- pip

---

## Entorno virtual e instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar (Linux / macOS)
source venv/bin/activate

# Activar (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -r requerimientos.txt
```

---

## Uso

```bash
python tarea1.py <gramatica.txt> <entrada.txt>
```

**Ejemplos:**

```bash
python tarea1.py gramatica.txt  entrada.txt   # aritmética simple
python tarea1.py gramatica2.txt entrada2.txt  # sentencias secuenciales
python tarea1.py gramatica3.txt entrada3.txt  # llamadas a funciones
python tarea1.py gramatica4.txt entrada4.txt  # condicionales if/then/else
```

El programa imprime en consola los conjuntos PRIMEROS, SIGUIENTES y PREDICCIÓN,
la tabla M, y el veredicto ACEPTADA / RECHAZADA para cada línea del archivo de
entrada. Además guarda un árbol de derivación `.png` por cada línea analizada.

---

## Formato de los archivos

### Gramática (`gramatica.txt`)

```
Nombre de la gramática          ← línea 1: título libre
N                               ← línea 2: número de producciones
NT -> símbolo1 símbolo2 ...     ← líneas 3..N+2: una producción por línea
```

- El primer no-terminal es el símbolo inicial.
- `_` representa la producción vacía (ε).
- Los no-terminales empiezan con mayúscula; los terminales, con minúscula.

### Entrada (`entrada.txt`)

Una expresión o sentencia por línea, usando los tokens definidos en el tokenizador:

| Token    | Representa           | Ejemplo  |
|----------|----------------------|----------|
| `id`     | identificador        | `x`, `resultado` |
| `num`    | número entero        | `10`, `42` |
| `asig`   | asignación           | `=` |
| `opsuma` | suma / resta         | `+`, `-` |
| `opmul`  | multiplicación / div | `*`, `/` |
| `relop`  | comparación          | `<`, `>` |
| `pari`   | paréntesis izquierdo | `(` |
| `pard`   | paréntesis derecho   | `)` |
| `pyc`    | punto y coma         | `;` |
| `coma`   | coma                 | `,` |
| `if`     | palabra reservada    | `if` |
| `then`   | palabra reservada    | `then` |
| `else`   | palabra reservada    | `else` |

---

## Gramáticas incluidas

| Archivo         | Acepta                                              |
|-----------------|-----------------------------------------------------|
| `gramatica.txt`  | Expresiones aritméticas y asignaciones simples      |
| `gramatica2.txt` | Lo anterior + sentencias separadas por `;`          |
| `gramatica3.txt` | Lo anterior + llamadas a funciones con argumentos   |
| `gramatica4.txt` | Lo anterior + condicionales `if / then / else`      |

---

## Fundamento teórico

> Referencia: Aho, Lam, Sethi, Ullman — *Compiladores: principios, técnicas y herramientas* (2.ª ed.)

### Analizador sintáctico descendente sin retroceso

Un parser **descendente** construye el árbol de derivación de arriba hacia abajo,
partiendo del símbolo inicial y expandiendo no-terminales hasta llegar a los
terminales del input. La variante **sin retroceso** (predictiva) elige en cada
paso exactamente una producción sin necesidad de explorar alternativas, lo que
garantiza tiempo lineal O(n).

Para lograrlo se necesitan tres conjuntos previos:

**PRIMEROS(α)** — conjunto de terminales que pueden aparecer al inicio de
cualquier cadena derivable desde α. Si α puede derivar ε, se incluye también `_`.

**SIGUIENTES(A)** — conjunto de terminales que pueden aparecer inmediatamente
después del no-terminal A en alguna forma sentencial. Incluye `$` para el
símbolo inicial.

**PREDICCIÓN(A → α)** — indica con qué tokens del input se debe aplicar la
producción `A → α`. Se calcula como PRIMEROS(α) si α no deriva ε, o como
PRIMEROS(α) ∪ SIGUIENTES(A) si α puede ser vacía.

### Tabla M y uso de la pila

Con los conjuntos anteriores se construye la **tabla M[A][a]**, donde A es un
no-terminal y a un terminal: la celda contiene la producción a aplicar cuando
el tope de la pila es A y el token actual del input es a.

El parser mantiene una **pila explícita** inicializada con `[$, S]` (siendo S
el símbolo inicial) y avanza así:

1. Si el tope es un **terminal** que coincide con el token actual → lo consume y avanza.
2. Si el tope es un **no-terminal** → consulta M[tope][token] y reemplaza el tope
   con los símbolos de la producción elegida (en orden inverso).
3. Si tope y token son ambos `$` → cadena **ACEPTADA**.
4. En cualquier desajuste → cadena **RECHAZADA**.

### LL(k) y lookahead

La gramática es **LL(1)** si la tabla M no tiene celdas con más de una
producción. Cuando existe ambigüedad con un solo token, el parser amplía
el lookahead a k tokens (tuplas de k terminales) hasta resolver el conflicto.
El programa detecta automáticamente el k mínimo necesario (hasta k=5).

### Lexer por expresiones regulares

Antes del parsing, el texto de entrada pasa por un **lexer** construido con
expresiones regulares (`re` de Python). Cada patrón nombrado corresponde a un
tipo de token; el lexer recorre el input de izquierda a derecha y emite la
secuencia de pares `(tipo, valor)` que consume el parser. Los espacios se
descartan; la secuencia termina siempre con el token especial `$`.

---

## Basado en entregas anteriores

Este proyecto retoma y extiende código de dos repositorios previos:

**[PRIMEROS\_SIGUIENTES\_PREDICCION](https://github.com/Mariana909/PRIMEROS_SIGUIENTES_PREDICCION.git)**
Aportó la lógica de cálculo de los conjuntos PRIMEROS, SIGUIENTES y PREDICCIÓN,
así como la forma de visualizar esas tablas por consola usando `tabulate`.

**[ARBOL\_SINTACTICO](https://github.com/Mariana909/ARBOL_SINTACTICO.git)**
Aportó la definición de tokens mediante expresiones regulares y la visualización
del árbol de derivación como imagen con `matplotlib`.

La diferencia principal respecto a esa entrega es el tipo de parser: el
repositorio anterior implementaba un **ASD recursivo** (cada regla de la
gramática tenía su propia función en Python). Este proyecto lo reemplaza por un
**ASD predictivo basado en tabla**, donde una única función `parsear()` maneja
toda la gramática consultando la tabla M con una pila explícita, sin necesidad
de una función por regla.