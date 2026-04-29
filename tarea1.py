from tabulate import tabulate
import sys
import re
import time
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

#  TOKENIZADOR
TOKEN_SPEC = [
    ("opsuma", r"[+\-]"),
    ("opmul",  r"[*/]"),
    ("asig",   r"="),
    ("relop",  r"[<>]"),
    ("pari",   r"\("),
    ("pard",   r"\)"),
    ("pyc",    r";"),
    ("coma",   r","),
    ("num",    r"[0-9]+"),
    ("if",     r"\bif\b"),
    ("then",   r"\bthen\b"),
    ("else",   r"\belse\b"),
    ("id",     r"[a-zA-Z][0-9a-zA-Z]*"),
    ("WS",     r"[ \t]+"),
]
TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC))

def tokenizar(texto):
    tokens = []
    for m in TOKEN_RE.finditer(texto):
        tipo = m.lastgroup
        valor = m.group()
        if tipo != "WS":
            tokens.append((tipo, valor))
    tokens.append(("$", "$"))
    return tokens

#  GRAMÁTICA
class Gramatica:
    def __init__(self, nombre, terminales, no_terminales, simbolo_inicial, producciones):
        self.nombre          = nombre
        self.terminales      = terminales
        self.no_terminales   = no_terminales
        self.simbolo_inicial = simbolo_inicial
        self.producciones    = producciones

    def __str__(self):
        filas = [
            [f"{nt} -> {' '.join(prod)}"]
            for nt, prods in self.producciones.items()
            for prod in prods
        ]
        return (
            f"Gramática:       {self.nombre}\n"
            f"Símbolo inicial: {self.simbolo_inicial}\n"
            f"No terminales:   {{ {', '.join(self.no_terminales)} }}\n"
            f"Terminales:      {{ {', '.join(self.terminales)} }}\n"
            f"Producciones:\n{tabulate(filas, tablefmt='simple')}"
        )

#  PSP  (PRIMEROS / SIGUIENTES / PREDICCIÓN)
class PSP:
    def __init__(self, gramatica):
        self.gramatica  = gramatica
        self.PRIMEROS   = {}
        self.SIGUIENTES = {}
        self.PREDICCION = {}

    # ---------- PRIMEROS ----------
    def calcular_PRIMEROS(self):
        for nt in self.gramatica.no_terminales:
            self.PRIMEROS[nt] = set()
        for nt, prods in self.gramatica.producciones.items():
            for prod in prods:
                if prod == ['_']:
                    self.PRIMEROS[nt].add('_')
        for t in self.gramatica.terminales:
            self.PRIMEROS[t] = {t}

        cambios = True
        while cambios:
            cambios = False
            for nt, prods in self.gramatica.producciones.items():
                for prod in prods:
                    if prod == ['_']:
                        continue
                    for simbolo in prod:
                        if simbolo == '_':
                            if '_' not in self.PRIMEROS[nt]:
                                self.PRIMEROS[nt].add('_'); cambios = True
                            break
                        elif simbolo in self.gramatica.terminales:
                            if simbolo not in self.PRIMEROS[nt]:
                                self.PRIMEROS[nt].add(simbolo); cambios = True
                            break
                        else:
                            antes = len(self.PRIMEROS[nt])
                            self.PRIMEROS[nt].update(self.PRIMEROS[simbolo] - {'_'})
                            if len(self.PRIMEROS[nt]) != antes:
                                cambios = True
                            if '_' not in self.PRIMEROS[simbolo]:
                                break
                    else:
                        if '_' not in self.PRIMEROS[nt]:
                            self.PRIMEROS[nt].add('_'); cambios = True

    # ---------- SIGUIENTES ----------
    def calcular_SIGUIENTES(self):
        for nt in self.gramatica.no_terminales:
            self.SIGUIENTES[nt] = set()
        self.SIGUIENTES[self.gramatica.simbolo_inicial] = {'$'}

        cambios = True
        while cambios:
            cambios = False
            for nt, prods in self.gramatica.producciones.items():
                for prod in prods:
                    for i, simbolo in enumerate(prod):
                        if simbolo in self.gramatica.no_terminales:
                            beta = prod[i+1:]
                            prim_beta = set()
                            for b in beta:
                                if b in self.gramatica.terminales:
                                    prim_beta.add(b); break
                                else:
                                    prim_beta.update(self.PRIMEROS[b] - {'_'})
                                    if '_' not in self.PRIMEROS[b]:
                                        break
                            antes = len(self.SIGUIENTES[simbolo])
                            self.SIGUIENTES[simbolo].update(prim_beta)
                            if len(self.SIGUIENTES[simbolo]) != antes:
                                cambios = True
                            beta_vacio = all(
                                '_' in self.PRIMEROS.get(b, set()) for b in beta
                            ) if beta else True
                            if beta_vacio:
                                antes = len(self.SIGUIENTES[simbolo])
                                self.SIGUIENTES[simbolo].update(self.SIGUIENTES[nt])
                                if len(self.SIGUIENTES[simbolo]) != antes:
                                    cambios = True

    # ---------- PREDICCIÓN ----------
    def calcular_PREDICCION(self):
        for nt, prods in self.gramatica.producciones.items():
            for prod in prods:
                conj = set()
                if prod == ['_']:
                    conj.update(self.SIGUIENTES[nt])
                else:
                    for simbolo in prod:
                        if simbolo in self.gramatica.terminales:
                            conj.add(simbolo); break
                        else:
                            conj.update(self.PRIMEROS[simbolo] - {'_'})
                            if '_' not in self.PRIMEROS[simbolo]:
                                break
                    else:
                        conj.update(self.SIGUIENTES[nt])
                self.PREDICCION[(nt, tuple(prod))] = conj

    # ---------- DETECCIÓN DE K ----------
    def detectar_k(self, k_max=5):
        """
        Determina el mínimo k de lookahead necesario para que la gramática
        sea LL(k), analizando los conjuntos de predicción de cada no terminal.

        Para k=1: la gramática es LL(1) si los conjuntos de predicción de
        todas las alternativas de cada NT son disjuntos entre sí.

        Para k>1: se simulan tuplas de k tokens y se verifica si los conflictos
        del nivel anterior se resuelven con el token adicional.

        Retorna (k, conflictos) donde conflictos es un dict con los NT
        que aún presentan ambigüedad si k > k_max.
        """
        # Agrupar producciones por NT
        por_nt = {}
        for (nt, prod), conj in self.PREDICCION.items():
            por_nt.setdefault(nt, []).append((prod, conj))

        # Verificar k=1
        conflictos_k1 = {}
        for nt, alternativas in por_nt.items():
            vistos = {}
            for prod, conj in alternativas:
                for tok in conj:
                    if tok in vistos:
                        conflictos_k1.setdefault(nt, set()).add(tok)
                    vistos[tok] = prod
        if not conflictos_k1:
            return 1, {}

        # Para k>1: construir tabla extendida con tuplas de tokens
        # Usamos las producciones reales de la gramática para generar
        # prefijos de longitud k y ver si se pueden distinguir
        for k in range(2, k_max + 1):
            if self._conflictos_resueltos_con_k(k, por_nt):
                return k, {}

        # No se pudo resolver en k_max
        return k_max + 1, conflictos_k1

    def _primeros_k(self, secuencia, k):
        """
        Calcula el conjunto de tuplas de hasta k terminales que pueden
        comenzar la secuencia dada (lista de símbolos de gramática).
        Equivalente a FIRST_k de la literatura.
        """
        if k == 0 or not secuencia:
            return {()}

        simbolo = secuencia[0]
        resto   = secuencia[1:]

        if simbolo in self.gramatica.terminales:
            sufijos = self._primeros_k(resto, k - 1)
            return {(simbolo,) + s for s in sufijos}
        elif simbolo == '_':
            return self._primeros_k(resto, k)
        else:  # no terminal
            resultado = set()
            for prod in self.gramatica.producciones.get(simbolo, []):
                expansion = (prod if prod != ['_'] else []) + list(resto)
                resultado.update(self._primeros_k(expansion, k))
            return resultado

    def _conflictos_resueltos_con_k(self, k, por_nt):
        """
        Retorna True si mirando k tokens se pueden distinguir todas
        las alternativas de cada NT (sin intersecciones en FIRST_k).
        """
        for nt, alternativas in por_nt.items():
            if len(alternativas) < 2:
                continue
            conjuntos_k = []
            for prod, _ in alternativas:
                prod_lista = list(prod)
                secuencia = prod_lista if prod_lista != ['_'] else []
                ck = self._primeros_k(secuencia + ['$'], k)
                conjuntos_k.append(ck)
            # Verificar que sean disjuntos par a par
            for i in range(len(conjuntos_k)):
                for j in range(i + 1, len(conjuntos_k)):
                    if conjuntos_k[i] & conjuntos_k[j]:
                        return False
        return True

    # ---------- TABLA M ----------
    def tabla_M(self):
        """
        Tabla de parsing M[NT][token] -> produccion para k=1.
        Ante conflicto guarda TODAS las alternativas para que el parser
        con k>1 pueda elegir la correcta mirando más tokens.
        """
        M = {nt: {} for nt in self.gramatica.no_terminales}
        for (nt, prod), conj in self.PREDICCION.items():
            for t in conj:
                M[nt].setdefault(t, [])
                if list(prod) not in M[nt][t]:
                    M[nt][t].append(list(prod))
        return M

#  NODO DE ÁRBOL
class Nodo:
    def __init__(self, etiqueta):
        self.etiqueta = etiqueta
        self.hijos    = []

    def agregar(self, hijo):
        self.hijos.append(hijo)
        return hijo

#  PARSER LL(k)
def parsear(tokens, gramatica, tabla_M, psp_obj, k):
    """
    Parser predictivo dirigido por tabla, generalizado para LL(k).

    Con k=1 opera exactamente como un parser LL(1) clásico con pila.
    Con k>1, al encontrar un conflicto en la tabla (varias producciones
    para el mismo token de entrada), examina los siguientes k tokens
    para desambiguar usando FIRST_k de cada alternativa.

    Retorna (aceptada: bool, raiz: Nodo).
    """
    no_terminales = gramatica.no_terminales

    raiz = Nodo(gramatica.simbolo_inicial)
    pila = [("$", None), (gramatica.simbolo_inicial, raiz)]
    pos  = 0

    def lookahead(n=1):
        """Devuelve una tupla con los tipos de los próximos n tokens."""
        return tuple(
            tokens[pos + i][0] if pos + i < len(tokens) else "$"
            for i in range(n)
        )

    while pila:
        tope_sim, tope_nodo = pila[-1]
        tok_tipo = lookahead(1)[0]

        #  Fin de pila 
        if tope_sim == "$":
            return tok_tipo == "$", raiz

        #  Símbolo vacío 
        elif tope_sim == "_":
            pila.pop()
            if tope_nodo is not None:
                tope_nodo.agregar(Nodo("ε"))

        #  No terminal: consultar tabla M 
        elif tope_sim in no_terminales:
            alternativas = tabla_M.get(tope_sim, {}).get(tok_tipo)

            if alternativas is None:
                return False, raiz

            # Sin conflicto (k=1 resuelve)
            if len(alternativas) == 1:
                prod = alternativas[0]
            else:
                # Conflicto: usar lookahead de k tokens para desambiguar
                ventana = lookahead(k)
                prod = None
                for alt in alternativas:
                    secuencia = (alt if alt != ['_'] else []) + ['$']
                    primeros  = psp_obj._primeros_k(secuencia, k)
                    # Verificar si algún prefijo de la ventana está en primeros_k
                    for largo in range(k, 0, -1):
                        if ventana[:largo] in primeros:
                            prod = alt
                            break
                    if prod is not None:
                        break
                if prod is None:
                    # Última alternativa como fallback
                    prod = alternativas[-1]

            pila.pop()
            hijos = [Nodo(sim) for sim in prod]
            for hijo in hijos:
                tope_nodo.agregar(hijo)
            for sim, hijo in reversed(list(zip(prod, hijos))):
                pila.append((sim, hijo))

        #  Terminal: debe coincidir 
        else:
            tok_val = tokens[pos][1] if pos < len(tokens) else "$"
            if tope_sim == tok_tipo or tope_sim == tok_val:
                if tope_nodo is not None:
                    tope_nodo.etiqueta = f"{tok_tipo}({tok_val})"
                pos += 1
                pila.pop()
            else:
                return False, raiz

    return lookahead(1)[0] == "$", raiz

#  DIBUJO DEL ÁRBOL
def calcular_posiciones(nodo, profundidad=0, contador=[0]):
    if not nodo.hijos:
        nodo._x = contador[0]; contador[0] += 1
        nodo._y = -profundidad
        return
    for hijo in nodo.hijos:
        calcular_posiciones(hijo, profundidad + 1, contador)
    nodo._x = sum(h._x for h in nodo.hijos) / len(nodo.hijos)
    nodo._y = -profundidad

def dibujar_nodos(nodo, ax, no_terminales):
    es_eps = nodo.etiqueta == "ε"
    es_nt  = nodo.etiqueta in no_terminales
    color  = "#E499DD" if es_eps else ("#AC4AD9" if es_nt else "#7EC5C8")
    for hijo in nodo.hijos:
        ax.plot([nodo._x, hijo._x], [nodo._y, hijo._y],
                color="#888888", linewidth=1, zorder=1)
        dibujar_nodos(hijo, ax, no_terminales)
    circulo = plt.Circle((nodo._x, nodo._y), 0.35,
                          color=color, zorder=2, ec="white", linewidth=1.5)
    ax.add_patch(circulo)
    fs = 7 if len(nodo.etiqueta) > 6 else 8
    ax.text(nodo._x, nodo._y, nodo.etiqueta,
            ha="center", va="center", fontsize=fs,
            color="white", fontweight="bold", zorder=3)

def mostrar_arbol(raiz, expresion, aceptada, no_terminales, k):
    calcular_posiciones(raiz, contador=[0])
    todos = []
    def recoger(n):
        todos.append(n)
        for h in n.hijos: recoger(h)
    recoger(raiz)

    xs = [n._x for n in todos]; ys = [n._y for n in todos]
    fig, ax = plt.subplots(figsize=(
        max(10, (max(xs)-min(xs)+2)*0.6),
        max(6,  (max(ys)-min(ys)+2)*1.1)
    ))
    ax.set_aspect("equal"); ax.axis("off")
    dibujar_nodos(raiz, ax, no_terminales)

    estado = "ACEPTADA" if aceptada else "RECHAZADA"
    color_t = "#2ecc50" if aceptada else "#e74c3c"
    ax.set_title(f'[LL({k})]  "{expresion}"  →  {estado}',
                 fontsize=12, fontweight="bold", color=color_t, pad=14)
    leyenda = [
        mpatches.Patch(color="#AC4AD9", label="No terminal"),
        mpatches.Patch(color="#7EC5C8", label="Terminal"),
        mpatches.Patch(color="#E499DD", label="epsilon (vacío)"),
    ]
    ax.legend(handles=leyenda, loc="upper right", fontsize=8, framealpha=0.8)
    ax.set_xlim(min(xs)-1, max(xs)+1); ax.set_ylim(min(ys)-1, 1.5)
    plt.tight_layout()
    nombre  = re.sub(r'[^a-zA-Z0-9]', '_', expresion)[:40]
    archivo = f"arbol_{nombre}{str(time.time())[-4:]}.png"
    plt.savefig(archivo, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  → Árbol guardado en: {archivo}")

#  LECTURA DE ARCHIVOS
def leer_gramatica(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        lineas = [l.strip() for l in f if l.strip()]

    nombre          = lineas[0]
    n               = int(lineas[1])
    terminales      = []
    no_terminales   = []
    simbolo_inicial = ""
    producciones    = {}

    for i in range(2, 2 + n):
        nt, prod_s = lineas[i].split("->")
        nt         = nt.strip()
        produccion = prod_s.strip().split()
        if i == 2:
            simbolo_inicial = nt
        if nt not in no_terminales:
            no_terminales.append(nt)
            producciones[nt] = []
        producciones[nt].append(produccion)
        for simbolo in produccion:
            if simbolo == '_':
                continue
            # Terminal = cualquier símbolo que no sea no-terminal
            if simbolo not in no_terminales and not simbolo[0].isupper():
                if simbolo not in terminales:
                    terminales.append(simbolo)

    return Gramatica(nombre, terminales, no_terminales, simbolo_inicial, producciones)

def leer_entradas(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return [l.rstrip('\n') for l in f if l.strip()]

#  MAIN
def main():
    if len(sys.argv) < 3:
        print("Uso: python parser.py gramatica.txt entrada.txt")
        sys.exit(1)

    gram = leer_gramatica(sys.argv[1])

    psp = PSP(gram)
    psp.calcular_PRIMEROS()
    psp.calcular_SIGUIENTES()
    psp.calcular_PREDICCION()

    #  Detectar k mínimo 
    k, conflictos = psp.detectar_k()
    if conflictos:
        print(f" La gramática no es LL(k) con k ≤ 5. "
              f"Conflictos no resueltos en: {list(conflictos.keys())}")
        print("  Se usará k=5 como mejor esfuerzo.\n")
        k = 5
    else:
        print(f" Gramática LL({k}) detectada.\n")

    #  Mostrar gramática y tablas 
    print(gram)
    filas_ps = [
        [nt,
         "{ " + ", ".join(sorted(psp.PRIMEROS[nt]))   + " }",
         "{ " + ", ".join(sorted(psp.SIGUIENTES[nt])) + " }"]
        for nt in gram.no_terminales
    ]
    filas_pred = [
        [f"{nt} -> {' '.join(prod)}",
         "{ " + ", ".join(sorted(conj)) + " }"]
        for (nt, prod), conj in psp.PREDICCION.items()
    ]
    print()
    print(tabulate(filas_ps,   headers=["No Terminal", "PRIMEROS", "SIGUIENTES"],
                  tablefmt="fancy_grid"))
    print()
    print(tabulate(filas_pred, headers=["Regla", "Conjunto de Predicción"],
                  tablefmt="fancy_grid"))
    print()

    tabla = psp.tabla_M()

    #  Parsear entradas 
    entradas = leer_entradas(sys.argv[2])
    print("=" * 60)
    for linea in entradas:
        toks     = tokenizar(linea)
        aceptada, arbol = parsear(toks, gram, tabla, psp, k)
        estado   = "ACEPTADA" if aceptada else "RECHAZADA"
        print(f'{estado:10}  "{linea}"')
        mostrar_arbol(arbol, linea, aceptada, gram.no_terminales, k)
    print("=" * 60)

if __name__ == "__main__":
    main()