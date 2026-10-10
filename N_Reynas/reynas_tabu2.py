import argparse
import random
import time
from itertools import combinations
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Resultado:
    estado_inicial: list
    mejor_estado: list
    mejor_f: int
    movimientos: int
    evaluaciones: int
    tiempo: float
    exito: bool
    historial: list = field(default_factory=list)


def estado_aleatorio(n=8, rgn=None):
    """Devuelve una permutacion aleatoria de 1..n"""
    
    rgn = rgn or random.Random()
    estado = list(range(1, n+1))
    rgn.shuffle(estado)
    return estado

def funcion_objetivo(estado):
    """Cuenta los pares de reinas que estan en la misma diagonal"""
    n= len(estado)
    colisiones = 0
    for i in range(n-1):
        for j in range(i+1,n):
            if abs(i-j) == abs(estado[i]-estado[j]):
                colisiones += 1
    return colisiones

def movimientos_posibles(n):
    """Devuelve todos los swaps (i,j) con i<j: es el tamaño de la vecindad = n(n-1)/2"""
    return list(combinations(range(n), 2))

def evaluar_vecino(estado,i,j):
    estado[i], estado[j] = estado[j], estado[i] # aqui se aplica el swap}
    f = funcion_objetivo(estado)
    estado[i], estado[j] = estado[j], estado[i] # aqui se deshace el swap
    return f

def escalada_simple(estado_inicial= None, n=8, max_iteraciones=1000, semilla=None):
    """ Se mueve siempre al mejor vecino mientras este mejore al estado actual"""
    rgn = random.Random(semilla)
    actual = estado_aleatorio(n,rgn) if estado_inicial is None else list(estado_inicial)
    n = len(actual)
    swaps = movimientos_posibles(n)
    inicio = time.perf_counter()
    estado_inicial = actual[:]
    f_actual = funcion_objetivo(actual)
    evaluaciones = 1
    movimientos =0
    historial = [f_actual]
    
    while f_actual > 0 and movimientos < max_iteraciones:
        #buscamos el mejor valor entre los vecinos y guardamos todos los que lo logran
        mejor_f = float('inf')
        mejores_vecinos = []
        for(i, j) in swaps:
            f = evaluar_vecino(actual, i, j)
            if f < mejor_f:
                mejor_f = f
                mejores_vecinos = [(i, j)]
            elif f == mejor_f:
                mejores_vecinos.append((i, j))
        
        # si ningun vecino mejora estariamos en un opsimo local y se terminaria
        if mejor_f >= f_actual:
            break
        # avanzamos elegir al aazar de forma uniforme entre los mejores empatesa
        i,j =rgn.choice(mejores_vecinos)
        actual[i], actual[j] = actual[j], actual[i]
        f_actual = mejor_f
        movimientos +=1
        historial.append(f_actual)
    return Resultado(
        estado_inicial=estado_inicial,
        mejor_estado=actual[:],
        mejor_f= f_actual,
        movimientos = movimientos,
        evaluaciones = evaluaciones,
        tiempo = time.perf_counter() - inicio,
        exito=(f_actual == 0),
        historial = historial
    )

def busqueda_tabu(estado_inicial =None,n=8,tenencia=5,max_iteraciones=1000, semilla=None):
    #La busqueda tabu con memoria a corto plazo que es l alista de los ultimos swaps
    rgn = random.Random(semilla)
    tabu_list = deque(maxlen=tenencia)
    actual = estado_aleatorio(n,rgn) if estado_inicial is None else list(estado_inicial)
    n = len(actual)
    swaps = movimientos_posibles(n)
    if not 1 <= tenencia < len(swaps):
        raise ValueError(f"tenencia debe estar entre 1 y {len(swaps)-1}") 
    inicio = time.perf_counter()
    estado_ini = actual[:]
    f_actual = funcion_objetivo(actual)
    evaluaciones = 1
    movimientos = 0
    mejor, mejor_f = actual[:], f_actual
    lista_tabu = deque(maxlen=tenencia)
    historial = [f_actual] 
    
    while mejor_f > 0 and movimientos < max_iteraciones:
        mejor_vecinof = float('inf')
        candidatos = []
        for(i,j) in swaps:
            f = evaluar_vecino(actual,i,j)
            evaluaciones +=1
            #aqui es el mov tabu pq solo se permite si va a superar la mejor solucion
            if(i,j)in lista_tabu and f >= mejor_f:
                continue
            if f < mejor_vecinof:
                mejor_vecinof = f
                candidatos = [(i,j)]
            elif f == mejor_vecinof:
                candidatos.append((i,j))
        if not candidatos:
            break
        
        i,j = rgn.choice(candidatos) #aqui va a ser el desempate parejo
        actual[i], actual[j] = actual[j], actual[i] #aun q empeore sigue y abajo en el append ese swap queda prohibido
        f_actual = mejor_vecinof
        lista_tabu.append((i,j))
        movimientos +=1
        historial.append(f_actual)
        if f_actual < mejor_f:
            mejor, mejor_f = actual[:], f_actual
    return Resultado(
        estado_inicial=estado_ini,
        mejor_estado=mejor,
        mejor_f=mejor_f,
        movimientos=movimientos,
        evaluaciones=evaluaciones,
        tiempo=time.perf_counter() - inicio,
        exito=(mejor_f == 0),
        historial=historial,
    )


def _main():
    parser = argparse.ArgumentParser(description="N reinas con Búsqueda Tabú")
    parser.add_argument("--n", type=int, default=8, help="Número de reinas")
    parser.add_argument("--tenencia", type=int, default=5, help="Tamaño de la lista tabú")
    parser.add_argument("--max_iteraciones", type=int, default=1000, help="Número máximo de iteraciones")
    parser.add_argument("--semilla", type=int, default=None, help="Semilla para generación de números aleatorios")
    args = parser.parse_args()
    r = busqueda_tabu(n=args.n, tenencia=args.tenencia, max_iteraciones=args.max_iteraciones, semilla=args.semilla)
    print("estado inicial:", r.estado_inicial, f"-> f={funcion_objetivo(r.estado_inicial)}")
    print("mejor estado:", r.mejor_estado, f"-> f={r.mejor_f}")
    print("movimientos:", r.movimientos)
    print("evaluaciones:", r.evaluaciones)
    print("tiempo:", r.tiempo)
    print("éxito:", r.exito)

if __name__ == "__main__":
    _main()