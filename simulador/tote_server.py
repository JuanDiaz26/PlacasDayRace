import threading
import time
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permite que tu interfaz se conecte sin problemas

# --- MEMORIA DEL SISTEMA ---
estado_carrera = {
    "activa": False,
    "numero_carrera": 0,
    "caballos": [],         # Lista de números de caballos [1, 2, 3...]
    "retirados": [],        # Lista de retirados
    "apuestas": {},         # { "GAN": {1: 5000, 2: 1000}, "EXA": {...} }
    "pozos_base": {},       # { "CUA": 500000 } (Incrementos iniciales)
    "total_jugado": {},     # { "GAN": 6000, "CUA": 505000 }
    "dividendos": {}        # { "1": 2.40, "2": 15.30 }
}

COMISION = 0.25 # El hipódromo se queda con el 25%

# --- FUNCIONES DE LOGICA DE NEGOCIO ---

def calcular_dividendos():
    """Recalcula los sports basados en la plata jugada."""
    if not estado_carrera["activa"]: return

    # 1. Calcular Totales por Tipo de Apuesta
    for tipo, bolsas in estado_carrera["apuestas"].items():
        total_tipo = sum(bolsas.values())
        
        # Sumar el incremento base si existe (Ej: Cuaterna arranca en 500k)
        if tipo in estado_carrera["pozos_base"]:
            total_tipo += estado_carrera["pozos_base"][tipo]
        
        estado_carrera["total_jugado"][tipo] = total_tipo

    # 2. Calcular Sport a GANADOR
    pozo_ganador = estado_carrera["total_jugado"].get("GAN", 0)
    pozo_neto = pozo_ganador * (1 - COMISION) # Sacamos la comisión
    
    nuevos_dividendos = {}
    bolsas_gan = estado_carrera["apuestas"].get("GAN", {})
    
    # Encontrar favorito para lógica de retirados (el que más plata tiene)
    caballo_fav = None
    max_plata = -1
    
    for cab_num in estado_carrera["caballos"]:
        if cab_num in estado_carrera["retirados"]: continue
        plata = bolsas_gan.get(cab_num, 0)
        if plata > max_plata:
            max_plata = plata
            caballo_fav = cab_num

    for cab_num in estado_carrera["caballos"]:
        if cab_num in estado_carrera["retirados"]:
            nuevos_dividendos[cab_num] = "RET"
            continue
            
        plata_al_caballo = bolsas_gan.get(cab_num, 0)
        
        # Si nadie le jugó, paga un fijo alto (simulado)
        if plata_al_caballo == 0:
            sport = 99.90
        else:
            sport = pozo_neto / plata_al_caballo
            if sport < 1.10: sport = 1.10 # Mínimo legal
            
        nuevos_dividendos[cab_num] = round(sport, 2)
        
    estado_carrera["dividendos"] = nuevos_dividendos

def mover_plata_retirado_al_favorito(caballo_retirado):
    """Mueve las apuestas del retirado al favorito actual."""
    print(f"--- ⚠️ RETIRO: Moviendo plata del {caballo_retirado} al Favorito ---")
    
    # Identificar favorito actual (el que tiene más plata en GANADOR)
    bolsas_gan = estado_carrera["apuestas"].get("GAN", {})
    favorito = None
    max_plata = -1
    
    for cab, plata in bolsas_gan.items():
        if cab != caballo_retirado and cab not in estado_carrera["retirados"]:
            if plata > max_plata:
                max_plata = plata
                favorito = cab
    
    if favorito:
        print(f"--- EL FAVORITO ES EL {favorito} ---")
        # Mover en todas las categorías (simplificado para GAN, se podría expandir)
        for tipo in estado_carrera["apuestas"]:
            plata_muerta = estado_carrera["apuestas"][tipo].get(caballo_retirado, 0)
            if plata_muerta > 0:
                estado_carrera["apuestas"][tipo][caballo_retirado] = 0
                estado_carrera["apuestas"][tipo][favorito] = estado_carrera["apuestas"][tipo].get(favorito, 0) + plata_muerta
                print(f"Movidos ${plata_muerta} de {caballo_retirado} a {favorito} en {tipo}")
    else:
        print("No se encontró favorito (¿Todos retirados?)")

def simulador_bucle():
    """Genera apuestas automáticas cada 5 segundos."""
    while True:
        time.sleep(5) 
        if estado_carrera["activa"]:
            # Simular gente apostando
            cant_apuestas = random.randint(5, 20) # 5 a 20 personas apuestan
            
            for _ in range(cant_apuestas):
                # Elige un caballo al azar que NO esté retirado
                candidatos = [c for c in estado_carrera["caballos"] if c not in estado_carrera["retirados"]]
                if not candidatos: break
                
                # Simular tendencia: Es más probable que apuesten a los que ya tienen plata
                cab_elegido = random.choice(candidatos) 
                
                monto = random.choice([100, 200, 500, 1000, 5000])
                
                # Cargar a Ganador
                if "GAN" not in estado_carrera["apuestas"]: estado_carrera["apuestas"]["GAN"] = {}
                estado_carrera["apuestas"]["GAN"][cab_elegido] = estado_carrera["apuestas"]["GAN"].get(cab_elegido, 0) + monto
                
                # Cargar a Pozos Extra (Aleatorio)
                for tipo in ["EXA", "TRI", "CUA", "CAD"]:
                    if tipo in estado_carrera["apuestas"] and random.random() > 0.7: # 30% chance
                         estado_carrera["apuestas"][tipo]["POZO"] = estado_carrera["apuestas"][tipo].get("POZO", 0) + monto

            calcular_dividendos()
            print(f"💰 TOTE ACTUALIZADO | Pozo GAN: ${estado_carrera['total_jugado'].get('GAN',0)}")

# Arrancar el hilo del simulador en segundo plano
t = threading.Thread(target=simulador_bucle)
t.daemon = True
t.start()

# --- ENDPOINTS (LA API PARA TU CONTROLADOR) ---

@app.route('/configurar', methods=['POST'])
def configurar():
    data = request.json
    estado_carrera["activa"] = True
    estado_carrera["numero_carrera"] = data.get("carrera")
    estado_carrera["caballos"] = data.get("caballos", [])
    estado_carrera["retirados"] = []
    
    # Inicializar bolsas vacias
    estado_carrera["apuestas"] = { "GAN": {}, "EXA": {}, "TRI": {}, "CUA": {}, "CAD": {} }
    
    # Cargar Incrementos Iniciales (Si vienen del Excel)
    estado_carrera["pozos_base"] = data.get("incrementos", {}) 
    
    # Poner un piso de plata inicial para que no den error de división por cero
    for c in estado_carrera["caballos"]:
        estado_carrera["apuestas"]["GAN"][c] = 1000 # Semilla inicial invisible
        
    calcular_dividendos()
    print(f"\n=== CARRERA {estado_carrera['numero_carrera']} CONFIGURADA ===")
    print(f"Incrementos base: {estado_carrera['pozos_base']}")
    return jsonify({"status": "ok", "msg": "Sistema de apuestas iniciado"})

@app.route('/retirar', methods=['POST'])
def retirar():
    data = request.json
    cab_num = data.get("numero") # Puede venir como string "1" o int 1
    
    # Normalizar a string o int según uses en tu lista
    # Asumimos que la lista 'caballos' tiene ints o strings consistentes.
    # Vamos a forzar string para evitar líos.
    cab_num = str(cab_num)
    estado_carrera["caballos"] = [str(x) for x in estado_carrera["caballos"]]
    
    if cab_num not in estado_carrera["retirados"]:
        estado_carrera["retirados"].append(cab_num)
        mover_plata_retirado_al_favorito(cab_num)
        calcular_dividendos()
        return jsonify({"status": "ok", "msg": f"Caballo {cab_num} retirado. Apuestas movidas al favorito."})
    
    return jsonify({"status": "error", "msg": "Ya estaba retirado"})

@app.route('/dividendos', methods=['GET'])
def obtener_dividendos():
    # Esta es la funcion que tu controlador consultará cada 2 segs
    return jsonify({
        "carrera": estado_carrera["numero_carrera"],
        "dividendos": estado_carrera["dividendos"],
        "pozos": estado_carrera["total_jugado"]
    })

if __name__ == '__main__':
    print("🏇 SERVIDOR TOTE (SIMULADOR) INICIADO EN PUERTO 5000")
    app.run(host='0.0.0.0', port=5000)