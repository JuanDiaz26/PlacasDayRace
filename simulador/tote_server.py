import threading
import time
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- MEMORIA DEL HIPODROMO ---
HIPODROMO = {}
COMISION = 0.25 

# --- HERRAMIENTAS DE LOGICA ---
def formatear_combinacion_exa(modo_juego, cab_fila, cab_fav):
    """
    Define el orden de los números:
    - IMPERFECTA: Menor - Mayor
    - EXACTA: Fila - Favorito
    """
    try:
        n1, n2 = int(cab_fila), int(cab_fav)
        if "IMPERFECTA" in modo_juego or "IMP" in modo_juego:
            return f"{min(n1,n2)}-{max(n1,n2)}"
        else:
            return f"{n1}-{n2}"
    except:
        return f"{cab_fila}-{cab_fav}"

def calcular_pago_simulado(base_ganador_1, base_ganador_2, pozo_total):
    """Genera un monto creíble basado en los sports individuales."""
    if base_ganador_1 == 0 or base_ganador_2 == 0: return 0.0
    factor_azar = random.uniform(0.9, 1.1)
    # Formula simple: Multiplicacion de sports ajustada
    pago = (base_ganador_1 * base_ganador_2 * 0.8) * factor_azar
    if pozo_total > 500000: pago = pago * 0.95 # Si hay mucha plata el pago se estabiliza
    return round(max(pago, 2.0), 1) # Minimo 2.0

# --- BUCLE PRINCIPAL ---
def simulador_bucle():
    while True:
        time.sleep(10) # 10 Segundos como pediste
        
        carreras_activas = [k for k, v in HIPODROMO.items() if v["activa"]]
        if not carreras_activas: continue

        print(f"\n--- 🎲 SIMULANDO APUESTAS ({len(carreras_activas)} Carreras) ---")

        for num_c in carreras_activas:
            c = HIPODROMO[num_c]
            
            # 1. INYECTAR DINERO (Solo a los que corren)
            corren = [h for h in c["caballos"] if h not in c["retirados"]]
            if not corren: continue

            # Simular flujo de apuestas
            volumen = random.randint(15, 60)
            for _ in range(volumen):
                cab = random.choice(corren)
                monto = random.choices([100, 500, 1000], weights=[60, 30, 10])[0]
                
                # Sumar a Ganador
                c["apuestas_gan"][cab] = c["apuestas_gan"].get(cab, 0) + monto
                c["pozos"]["GAN"] += monto
                
                # Sumar un poquito a los otros pozos para que crezcan
                for p in ["EXA", "TRI", "DOBLE", "CUA", "QUI", "CAD"]:
                    if p in c["pozos"]: c["pozos"][p] += (monto * 0.4)

            # 2. CALCULAR SPORT GANADOR
            neto_gan = c["pozos"]["GAN"] * (1 - COMISION)
            
            # Ranking de favoritos (Tupla: id, plata)
            ranking = sorted(c["apuestas_gan"].items(), key=lambda x: x[1], reverse=True)
            # Quitar retirados del ranking
            ranking = [r for r in ranking if r[0] not in c["retirados"]]
            
            # Identificar Top 3 Favoritos
            fav1 = ranking[0][0] if len(ranking) > 0 else None
            fav2 = ranking[1][0] if len(ranking) > 1 else None
            fav3 = ranking[2][0] if len(ranking) > 2 else None
            
            sports_gan = {}
            for cab in c["caballos"]:
                if cab in c["retirados"]:
                    sports_gan[cab] = "RET"
                    continue
                
                plata = c["apuestas_gan"].get(cab, 0)
                if plata == 0: val = 99.9
                else: val = max(neto_gan / plata, 1.10)
                sports_gan[cab] = round(val, 2)
            
            c["dividendos_gan"] = sports_gan

            # 3. GENERAR COMBINACIONES (EXA / TRI / DOBLE)
            # Aca generamos el texto "1-4 $500.0"
            
            grid_data = {} # { "1": {"EXA": "1-2 $50", "TRI":...} }
            
            # Detectar qué tipo de juego es (EXACTA o IMPERFECTA)
            # Buscamos en config_apuestas si hay alguna string que diga "IMP"
            es_imperfecta = any("IMP" in tipo for tipo in c["config_apuestas"])
            modo_exa = "IMPERFECTA" if es_imperfecta else "EXACTA"

            sport_fav1 = sports_gan.get(fav1, 2.0) if fav1 else 2.0
            
            for cab in corren:
                mi_sport = sports_gan.get(cab, 10.0)
                
                # --- EXACTA / IMPERFECTA ---
                # Si soy el favorito 1, combino con el 2. Si no, combino con el 1.
                pareja = fav2 if cab == fav1 else fav1
                if pareja:
                    sport_pareja = sports_gan.get(pareja, 2.0)
                    pago = calcular_pago_simulado(mi_sport, sport_pareja, c["pozos"]["EXA"])
                    txt_comb = formatear_combinacion_exa(modo_exa, cab, pareja)
                    str_exa = f"{txt_comb} ${pago}"
                else:
                    str_exa = "-"

                # --- TRIFECTA (Yo + Fav1 + Fav2) ---
                # Logica simple: 3 caballos
                p3 = fav3 if (cab == fav1 or cab == fav2) else fav2
                p2 = fav2 if cab == fav1 else fav1
                
                if p2 and p3:
                    pago_tri = round(pago * random.uniform(5, 10), 1)
                    str_tri = f"{cab}-{p2}-{p3} ${pago_tri}"
                else:
                    str_tri = "-"

                # --- DOBLE ---
                str_dob = "-"
                if not c["es_ultima"]:
                    # Simulamos un caballo X de la proxima carrera (ej: numero 1 al 14)
                    cab_next = random.randint(1, 14)
                    pago_dob = calcular_pago_simulado(mi_sport, 3.5, c["pozos"]["DOBLE"])
                    str_dob = f"{cab}-{cab_next} ${pago_dob}"

                grid_data[cab] = {
                    "EXA": str_exa,
                    "TRI": str_tri,
                    "DOBLE": str_dob
                }
            
            c["dividendos_extra"] = grid_data
            print(f"   > C{num_c}: Fav {fav1} (${sports_gan.get(fav1)}) | Pozo GAN: ${int(c['pozos']['GAN'])}")

# Arrancar
t = threading.Thread(target=simulador_bucle)
t.daemon = True
t.start()

# --- ENDPOINTS ---
@app.route('/configurar', methods=['POST'])
def configurar():
    data = request.json
    num = str(data.get("carrera"))
    caballos = [str(x) for x in data.get("caballos", [])]
    # Limpiamos duplicados y ordenamos
    caballos = sorted(list(set(caballos)), key=lambda x: int(x) if x.isdigit() else 0)
    
    incrementos = data.get("incrementos", {})
    tipos = data.get("tipos_apuesta", []) # ["EXACTA", "TRIFECTA"...]
    
    # Solo inicializamos si no existe o si queremos forzar reconexión
    if num not in HIPODROMO:
        print(f"🆕 CREANDO CARRERA {num}")
        HIPODROMO[num] = {
            "activa": True,
            "caballos": caballos,
            "retirados": [],
            "config_apuestas": tipos,
            "es_ultima": False, # Se podria detectar
            "apuestas_gan": {c: 500 for c in caballos}, # Base chica
            "pozos": {
                "GAN": incrementos.get("GAN", 5000),
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
        print(f"♻️ RECONECTANDO CARRERA {num} (Datos previos mantenidos)")
        HIPODROMO[num]["activa"] = True # Asegurar que siga corriendo
        # Actualizamos la config de apuestas por si cambiaste de Exacta a Imperfecta en la GUI
        HIPODROMO[num]["config_apuestas"] = tipos

    return jsonify({"status": "ok"})

@app.route('/retirar', methods=['POST'])
def retirar():
    data = request.json
    num_c = str(data.get("carrera"))
    cab = str(data.get("caballo"))
    
    if num_c in HIPODROMO:
        c = HIPODROMO[num_c]
        if cab not in c["retirados"]:
            c["retirados"].append(cab)
            # Transferencia de fondos al favorito
            rank = sorted(c["apuestas_gan"].items(), key=lambda x: x[1], reverse=True)
            rank = [r for r in rank if r[0] != cab and r[0] not in c["retirados"]]
            if rank:
                fav = rank[0][0]
                monto = c["apuestas_gan"].get(cab, 0)
                c["apuestas_gan"][cab] = 0
                c["apuestas_gan"][fav] += monto
                print(f"⚠️ RETIRO C{num_c}: {cab} -> ${monto} pasados al {fav}")
            return jsonify({"status": "ok"})
            
    return jsonify({"status": "error"})

@app.route('/dividendos', methods=['GET'])
def get_dividendos():
    num_c = str(request.args.get('carrera'))
    if num_c in HIPODROMO:
        return jsonify({
            "status": "ok",
            "ganador": HIPODROMO[num_c]["dividendos_gan"],
            "extras": HIPODROMO[num_c]["dividendos_extra"],
            "pozos": HIPODROMO[num_c]["pozos"]
        })
    return jsonify({"status": "error"})

if __name__ == '__main__':
    print("🏇 TOTE SERVER V3 (COMBINACIONES EXPLICITAS) LISTO...")
    app.run(host='0.0.0.0', port=5000)