import threading
import time
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- MEMORIA DEL HIPODROMO (Persistente entre cambios de pestaña) ---
# Estructura: { "1": { datos_carrera_1 }, "2": { datos_carrera_2 } }
HIPODROMO = {}

COMISION = 0.25  # 25% retención del hipódromo

# --- LOGICA DE COMBINACIONES ---
def calcular_pago_combinado(pozo_tipo, dividendo_gan_c1, dividendo_gan_c2):
    """
    Simula un pago de exacta/doble basándose en los sports de ganador.
    Formula aproximada: (Sport1 * Sport2) / Factor de corrección de pozo
    """
    if dividendo_gan_c1 == 0 or dividendo_gan_c2 == 0: return 0
    # Factor aleatorio para que varíe un poco
    factor = random.uniform(0.8, 1.2)
    base = (dividendo_gan_c1 * dividendo_gan_c2) * factor
    
    # Ajuste por tamaño de pozo (si hay mucha plata, paga un poco más estable)
    if pozo_tipo > 1000000: base = base * 0.9
    
    if base < 2.0: base = 2.0
    return round(base, 1)

def mover_plata_retirado_al_favorito(c, caballo_retirado):
    """Mueve las apuestas del retirado al favorito actual dentro de esa carrera."""
    print(f"--- ⚠️ RETIRO C{request.json.get('carrera')}: Moviendo plata del {caballo_retirado} al Favorito ---")
    
    bolsas_gan = c["apuestas_gan"]
    favorito = None
    max_plata = -1
    
    for cab, plata in bolsas_gan.items():
        if cab != caballo_retirado and cab not in c["retirados"]:
            if plata > max_plata:
                max_plata = plata
                favorito = cab
    
    if favorito:
        plata_muerta = bolsas_gan.get(caballo_retirado, 0)
        if plata_muerta > 0:
            c["apuestas_gan"][caballo_retirado] = 0
            c["apuestas_gan"][favorito] += plata_muerta
            print(f"   -> ${plata_muerta} transferidos al favorito {favorito}")

# --- BUCLE PRINCIPAL DE SIMULACION ---
def simulador_bucle():
    """Corre cada 10 segundos y actualiza TODAS las carreras activas."""
    while True:
        time.sleep(10) # RITMO PEDIDO (10 SEGUNDOS)
        
        carreras_activas = [k for k, v in HIPODROMO.items() if v["activa"]]
        
        if not carreras_activas:
            continue

        print(f"\n--- 🎲 SIMULANDO APUESTAS EN CARRERAS: {carreras_activas} ---")

        for num_carrera in carreras_activas:
            c = HIPODROMO[num_carrera]
            
            # 1. GENERAR APUESTAS ALEATORIAS (Inyectar plata)
            # Solo apostamos a caballos NO retirados
            corren = [h for h in c["caballos"] if h not in c["retirados"]]
            if not corren: continue

            # Simular volumen de apuestas
            volumen = random.randint(10, 50) 
            
            for _ in range(volumen):
                cab = random.choice(corren)
                # Montos variados
                monto = random.choices([100, 500, 1000, 5000], weights=[50, 30, 15, 5])[0]
                
                # Sumar a Ganador
                c["apuestas_gan"][cab] = c["apuestas_gan"].get(cab, 0) + monto
                c["pozos_totales"]["GAN"] += monto
                
                # Sumar a los otros pozos (Simulación de flujo de dinero)
                for tipo in ["EXA", "TRI", "DOBLE", "CUA", "QUI", "CAD"]:
                    if tipo in c["pozos_totales"]: 
                        c["pozos_totales"][tipo] += (monto * 0.5) 

            # 2. RECALCULAR SPORT GANADOR
            pozo_gan_neto = c["pozos_totales"]["GAN"] * (1 - COMISION)
            
            # Encontrar Favoritos
            ranking_favoritos = sorted(c["apuestas_gan"].items(), key=lambda item: item[1], reverse=True)
            ranking_favoritos = [x for x in ranking_favoritos if x[0] not in c["retirados"]]
            
            top_1 = ranking_favoritos[0][0] if len(ranking_favoritos) > 0 else None
            top_2 = ranking_favoritos[1][0] if len(ranking_favoritos) > 1 else None
            
            nuevos_sports = {}
            for cab in c["caballos"]:
                if cab in c["retirados"]:
                    nuevos_sports[cab] = "RET"
                    continue
                
                plata = c["apuestas_gan"].get(cab, 0)
                if plata == 0:
                    nuevos_sports[cab] = 99.90
                else:
                    val = pozo_gan_neto / plata
                    if val < 1.10: val = 1.10
                    nuevos_sports[cab] = round(val, 2)
            
            c["dividendos_gan"] = nuevos_sports

            # 3. RECALCULAR COMBINACIONES (EXA/TRI/DOBLE) PARA LA GRILLA
            data_grilla = {} 
            
            div_fav = novos_sports_val = nuevos_sports.get(top_1, 2.0) if top_1 else 2.0
            
            for cab in corren:
                mi_sport = nuevos_sports.get(cab, 10.0)
                if isinstance(mi_sport, str): mi_sport = 0 # Si es RET
                
                # --- EXACTA / IMPERFECTA ---
                # Si soy el favorito, cruzo con el 2do favorito. Si no, conmigo + favorito.
                pareja = top_2 if cab == top_1 else top_1
                div_pareja = nuevos_sports.get(pareja, 5.0) if pareja else 5.0
                if isinstance(div_pareja, str): div_pareja = 0

                # Simular pago combinada
                pago_exa = calcular_pago_combinado(c["pozos_totales"]["EXA"], mi_sport, div_pareja)
                
                # --- TRIFECTA / CUATRIFECTA ---
                pago_tri = round(pago_exa * random.uniform(4, 8), 1)
                
                # --- DOBLE ---
                pago_doble = 0
                # Simulamos que en la proxima carrera gana un caballo random (Factor 3.5)
                pago_doble = calcular_pago_combinado(c["pozos_totales"]["DOBLE"], mi_sport, 3.5)
                
                data_grilla[cab] = {
                    "EXA": pago_exa,
                    "TRI": pago_tri,
                    "DOBLE": pago_doble if pago_doble > 0 else "-"
                }
            
            c["dividendos_extra"] = data_grilla
            
            print(f"   > Carrera {num_carrera}: Pozo GAN ${c['pozos_totales']['GAN']} | Fav: {top_1} (${div_fav})")

# Iniciar hilo
t = threading.Thread(target=simulador_bucle)
t.daemon = True
t.start()

# --- ENDPOINTS ---

@app.route('/configurar', methods=['POST'])
def configurar():
    data = request.json
    num = str(data.get("carrera"))
    caballos = [str(x) for x in data.get("caballos", [])]
    incrementos = data.get("incrementos", {}) 
    
    # Si la carrera NO existe en memoria, la creamos
    if num not in HIPODROMO:
        print(f"🆕 INICIALIZANDO CARRERA {num}")
        HIPODROMO[num] = {
            "activa": True,
            "caballos": caballos,
            "retirados": [],
            "apuestas_gan": {c: 1000 for c in caballos}, # Semilla inicial
            "pozos_totales": {
                "GAN": incrementos.get("GAN", 10000), 
                "EXA": incrementos.get("EXACTA", incrementos.get("IMPERFECTA", 0)),
                "TRI": incrementos.get("TRIFECTA", incrementos.get("CUATRIFECTA", 0)),
                "DOBLE": incrementos.get("DOBLE", 0),
                "CUA": incrementos.get("CUATERNA", 0),
                "QUI": incrementos.get("QUINTUPLO", 0),
                "CAD": incrementos.get("CADENA", 0)
            },
            "dividendos_gan": {},
            "dividendos_extra": {}
        }
    else:
        print(f"🔄 RECONECTANDO A CARRERA {num} (Recuperando Pozos)")
        # Solo actualizamos status, no borramos la plata
        HIPODROMO[num]["activa"] = True 

    return jsonify({"status": "ok", "msg": f"Carrera {num} configurada."})

@app.route('/retirar', methods=['POST'])
def retirar():
    data = request.json
    num_c = str(data.get("carrera"))
    cab = str(data.get("caballo"))
    
    if num_c in HIPODROMO:
        c = HIPODROMO[num_c]
        if cab not in c["retirados"]:
            c["retirados"].append(cab)
            mover_plata_retirado_al_favorito(c, cab)
            return jsonify({"status": "ok"})
    
    return jsonify({"status": "error", "msg": "Carrera o caballo no valido"})

@app.route('/dividendos', methods=['GET'])
def get_dividendos():
    num_c = str(request.args.get('carrera'))
    
    if num_c in HIPODROMO:
        c = HIPODROMO[num_c]
        return jsonify({
            "status": "ok",
            "ganador": c["dividendos_gan"],
            "extras": c["dividendos_extra"],
            "pozos": c["pozos_totales"]
        })
    else:
        return jsonify({"status": "error", "msg": "Carrera no iniciada"})

if __name__ == '__main__':
    print("🏇 TOTE SERVER V2 (MULTI-CARRERA + LOGICA COMPLEJA) CORRIENDO...")
    app.run(host='0.0.0.0', port=5000)

import threading
import time
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- MEMORIA DEL HIPODROMO (Persistente entre cambios de pestaña) ---
# Estructura: { "1": { datos_carrera_1 }, "2": { datos_carrera_2 } }
HIPODROMO = {}

COMISION = 0.25  # 25% retención del hipódromo

# --- LOGICA DE COMBINACIONES ---
def calcular_pago_combinado(pozo_tipo, dividendo_gan_c1, dividendo_gan_c2):
    """
    Simula un pago de exacta/doble basándose en los sports de ganador.
    Formula aproximada: (Sport1 * Sport2) / Factor de corrección de pozo
    """
    if dividendo_gan_c1 == 0 or dividendo_gan_c2 == 0: return 0
    # Factor aleatorio para que varíe un poco
    factor = random.uniform(0.8, 1.2)
    base = (dividendo_gan_c1 * dividendo_gan_c2) * factor
    
    # Ajuste por tamaño de pozo (si hay mucha plata, paga un poco más estable)
    if pozo_tipo > 1000000: base = base * 0.9
    
    if base < 2.0: base = 2.0
    return round(base, 1)

def mover_plata_retirado_al_favorito(c, caballo_retirado):
    """Mueve las apuestas del retirado al favorito actual dentro de esa carrera."""
    print(f"--- ⚠️ RETIRO C{request.json.get('carrera')}: Moviendo plata del {caballo_retirado} al Favorito ---")
    
    bolsas_gan = c["apuestas_gan"]
    favorito = None
    max_plata = -1
    
    for cab, plata in bolsas_gan.items():
        if cab != caballo_retirado and cab not in c["retirados"]:
            if plata > max_plata:
                max_plata = plata
                favorito = cab
    
    if favorito:
        plata_muerta = bolsas_gan.get(caballo_retirado, 0)
        if plata_muerta > 0:
            c["apuestas_gan"][caballo_retirado] = 0
            c["apuestas_gan"][favorito] += plata_muerta
            print(f"   -> ${plata_muerta} transferidos al favorito {favorito}")

# --- BUCLE PRINCIPAL DE SIMULACION ---
def simulador_bucle():
    """Corre cada 10 segundos y actualiza TODAS las carreras activas."""
    while True:
        time.sleep(10) # RITMO PEDIDO (10 SEGUNDOS)
        
        carreras_activas = [k for k, v in HIPODROMO.items() if v["activa"]]
        
        if not carreras_activas:
            continue

        print(f"\n--- 🎲 SIMULANDO APUESTAS EN CARRERAS: {carreras_activas} ---")

        for num_carrera in carreras_activas:
            c = HIPODROMO[num_carrera]
            
            # 1. GENERAR APUESTAS ALEATORIAS (Inyectar plata)
            # Solo apostamos a caballos NO retirados
            corren = [h for h in c["caballos"] if h not in c["retirados"]]
            if not corren: continue

            # Simular volumen de apuestas
            volumen = random.randint(10, 50) 
            
            for _ in range(volumen):
                cab = random.choice(corren)
                # Montos variados
                monto = random.choices([100, 500, 1000, 5000], weights=[50, 30, 15, 5])[0]
                
                # Sumar a Ganador
                c["apuestas_gan"][cab] = c["apuestas_gan"].get(cab, 0) + monto
                c["pozos_totales"]["GAN"] += monto
                
                # Sumar a los otros pozos (Simulación de flujo de dinero)
                for tipo in ["EXA", "TRI", "DOBLE", "CUA", "QUI", "CAD"]:
                    if tipo in c["pozos_totales"]: 
                        c["pozos_totales"][tipo] += (monto * 0.5) 

            # 2. RECALCULAR SPORT GANADOR
            pozo_gan_neto = c["pozos_totales"]["GAN"] * (1 - COMISION)
            
            # Encontrar Favoritos
            ranking_favoritos = sorted(c["apuestas_gan"].items(), key=lambda item: item[1], reverse=True)
            ranking_favoritos = [x for x in ranking_favoritos if x[0] not in c["retirados"]]
            
            top_1 = ranking_favoritos[0][0] if len(ranking_favoritos) > 0 else None
            top_2 = ranking_favoritos[1][0] if len(ranking_favoritos) > 1 else None
            
            nuevos_sports = {}
            for cab in c["caballos"]:
                if cab in c["retirados"]:
                    nuevos_sports[cab] = "RET"
                    continue
                
                plata = c["apuestas_gan"].get(cab, 0)
                if plata == 0:
                    nuevos_sports[cab] = 99.90
                else:
                    val = pozo_gan_neto / plata
                    if val < 1.10: val = 1.10
                    nuevos_sports[cab] = round(val, 2)
            
            c["dividendos_gan"] = nuevos_sports

            # 3. RECALCULAR COMBINACIONES (EXA/TRI/DOBLE) PARA LA GRILLA
            data_grilla = {} 
            
            div_fav = novos_sports_val = nuevos_sports.get(top_1, 2.0) if top_1 else 2.0
            
            for cab in corren:
                mi_sport = nuevos_sports.get(cab, 10.0)
                if isinstance(mi_sport, str): mi_sport = 0 # Si es RET
                
                # --- EXACTA / IMPERFECTA ---
                # Si soy el favorito, cruzo con el 2do favorito. Si no, conmigo + favorito.
                pareja = top_2 if cab == top_1 else top_1
                div_pareja = nuevos_sports.get(pareja, 5.0) if pareja else 5.0
                if isinstance(div_pareja, str): div_pareja = 0

                # Simular pago combinada
                pago_exa = calcular_pago_combinado(c["pozos_totales"]["EXA"], mi_sport, div_pareja)
                
                # --- TRIFECTA / CUATRIFECTA ---
                pago_tri = round(pago_exa * random.uniform(4, 8), 1)
                
                # --- DOBLE ---
                pago_doble = 0
                # Simulamos que en la proxima carrera gana un caballo random (Factor 3.5)
                pago_doble = calcular_pago_combinado(c["pozos_totales"]["DOBLE"], mi_sport, 3.5)
                
                data_grilla[cab] = {
                    "EXA": pago_exa,
                    "TRI": pago_tri,
                    "DOBLE": pago_doble if pago_doble > 0 else "-"
                }
            
            c["dividendos_extra"] = data_grilla
            
            print(f"   > Carrera {num_carrera}: Pozo GAN ${c['pozos_totales']['GAN']} | Fav: {top_1} (${div_fav})")

# Iniciar hilo
t = threading.Thread(target=simulador_bucle)
t.daemon = True
t.start()

# --- ENDPOINTS ---

@app.route('/configurar', methods=['POST'])
def configurar():
    data = request.json
    num = str(data.get("carrera"))
    caballos = [str(x) for x in data.get("caballos", [])]
    incrementos = data.get("incrementos", {}) 
    
    # Si la carrera NO existe en memoria, la creamos
    if num not in HIPODROMO:
        print(f"🆕 INICIALIZANDO CARRERA {num}")
        HIPODROMO[num] = {
            "activa": True,
            "caballos": caballos,
            "retirados": [],
            "apuestas_gan": {c: 1000 for c in caballos}, # Semilla inicial
            "pozos_totales": {
                "GAN": incrementos.get("GAN", 10000), 
                "EXA": incrementos.get("EXACTA", incrementos.get("IMPERFECTA", 0)),
                "TRI": incrementos.get("TRIFECTA", incrementos.get("CUATRIFECTA", 0)),
                "DOBLE": incrementos.get("DOBLE", 0),
                "CUA": incrementos.get("CUATERNA", 0),
                "QUI": incrementos.get("QUINTUPLO", 0),
                "CAD": incrementos.get("CADENA", 0)
            },
            "dividendos_gan": {},
            "dividendos_extra": {}
        }
    else:
        print(f"🔄 RECONECTANDO A CARRERA {num} (Recuperando Pozos)")
        # Solo actualizamos status, no borramos la plata
        HIPODROMO[num]["activa"] = True 

    return jsonify({"status": "ok", "msg": f"Carrera {num} configurada."})

@app.route('/retirar', methods=['POST'])
def retirar():
    data = request.json
    num_c = str(data.get("carrera"))
    cab = str(data.get("caballo"))
    
    if num_c in HIPODROMO:
        c = HIPODROMO[num_c]
        if cab not in c["retirados"]:
            c["retirados"].append(cab)
            mover_plata_retirado_al_favorito(c, cab)
            return jsonify({"status": "ok"})
    
    return jsonify({"status": "error", "msg": "Carrera o caballo no valido"})

@app.route('/dividendos', methods=['GET'])
def get_dividendos():
    num_c = str(request.args.get('carrera'))
    
    if num_c in HIPODROMO:
        c = HIPODROMO[num_c]
        return jsonify({
            "status": "ok",
            "ganador": c["dividendos_gan"],
            "extras": c["dividendos_extra"],
            "pozos": c["pozos_totales"]
        })
    else:
        return jsonify({"status": "error", "msg": "Carrera no iniciada"})

if __name__ == '__main__':
    print("🏇 TOTE SERVER V2 (MULTI-CARRERA + LOGICA COMPLEJA) CORRIENDO...")
    app.run(host='0.0.0.0', port=5000)