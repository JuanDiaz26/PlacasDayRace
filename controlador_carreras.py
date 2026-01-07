import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import pandas as pd
import re
import os
import time

# --- ARCHIVOS ---
ARCHIVO_DATOS = "datos.json"
ARCHIVO_MARCADOR = "marcador.json"
ARCHIVO_COMANDO = "comando_reloj.json"
ARCHIVO_PASEO = "paseo.json"
ARCHIVO_PANTALLA = "pantalla_completa.json"

# --- GLOBALES ---
carreras_cargadas = []
carrera_actual_data = None 
dividendos_memoria = {} 
memoria_paseo = {} 
memoria_retirados = {} 
reloj_corriendo = False 
visibilidad_placa = True
visibilidad_reloj = True
visibilidad_marcador = True
visibilidad_paseo = False
visibilidad_pantalla = False 

# =============================================================================
# FUNCIONES SISTEMA
# =============================================================================
def inicializar_sistema():
    print("--- INICIANDO SISTEMA V11 ---")
    guardar_json(ARCHIVO_MARCADOR, []) 
    guardar_json(ARCHIVO_PASEO, {"visible": False})
    guardar_json(ARCHIVO_PANTALLA, {"visible": False})
    enviar_comando_reloj("RESET")
    datos_vacios = {"num_carrera": "", "distancia": "", "premio": "", "condicion": "", "estado_pista": "", "visible": False}
    guardar_json(ARCHIVO_DATOS, datos_vacios)
    root.after(2000, ciclo_automatico_paseo)

def guardar_json(archivo, data):
    try:
        with open(archivo, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Error {archivo}: {e}")

def enviar_comando_reloj(accion):
    comando = { "id": time.time(), "accion": accion }
    guardar_json(ARCHIVO_COMANDO, comando)

# =============================================================================
# LÓGICA EXCEL
# =============================================================================
def analizar_excel(ruta_archivo):
    try:
        if ruta_archivo.endswith('.csv'): df = pd.read_csv(ruta_archivo, header=None, sep=None, engine='python')
        else: df = pd.read_excel(ruta_archivo, header=None)
        carreras = []; carrera_act = None; buscando_dist = False; cond_cerrada = False; buscando_cab = False; col_num = -1; col_cab = -1; col_joc = -1; col_stud = -1; col_cuid = -1; temp_inc_label = ""; temp_inc_monto = ""
        for i in range(len(df)):
            fila_vals = [str(val).strip() for val in df.iloc[i].values]
            texto = " ".join([v for v in fila_vals if v not in ['nan', 'None', '']]); texto_upper = texto.upper()
            
            if "INCREMENTO" in texto_upper or "$" in texto:
                match_apuesta = re.search(r'(CADENA|CUATERNA|TRIPLO|QUINTUPLO|DOBLE|EXACTA)', texto_upper)
                match_plata = re.search(r'\$\s?([\d\.,]+)', texto)
                if match_apuesta: temp_inc_label = match_apuesta.group(1)
                if match_plata: temp_inc_monto = match_plata.group(1)

            match_tit = re.search(r'^(\d+)[º°aª]\s*CARRERA', texto_upper)
            if match_tit:
                if carrera_act: carreras.append(carrera_act)
                carrera_act = { "id": "", "distancia": "---", "premio": "", "condicion": "", "pista": "NORMAL", "hora": "00:00", "caballos": [], "incremento_tipo": temp_inc_label, "incremento_monto": temp_inc_monto }
                temp_inc_label = ""; temp_inc_monto = ""; cond_cerrada = False
                match_hora = re.search(r'(\d{1,2}:\d{2})', texto); 
                if match_hora: carrera_act["hora"] = match_hora.group(1)
                regex_premio = r'(GRAN PREMIO|PREMIO|CLÁSICO|CLASICO|ESPECIAL|HANDICAP)'; match_corte = re.search(regex_premio, texto_upper)
                if match_corte:
                    carrera_act["id"] = texto[:match_corte.start()].strip(); tipo = match_corte.group(1).upper(); match_comillas = re.search(r'["“](.*?)["”]', texto)
                    if match_comillas: nombre_premio = match_comillas.group(1).strip()
                    else: resto_linea = texto[match_corte.end():]; nombre_premio = re.split(r'\s-\s|METROS', resto_linea, flags=re.IGNORECASE)[0].strip().replace('"', '')
                    carrera_act["premio"] = f'{tipo} "{nombre_premio}"'
                else: carrera_act["id"] = texto
                buscando_dist = True; buscando_cab = True; col_num = -1; continue

            if carrera_act and buscando_dist:
                match_mts = re.search(r'(\d{1,2}[.,]?\d{3}|\d{3})\s*(METROS|MTS)', texto_upper)
                if match_mts: raw_num = match_mts.group(1).replace(".", "").replace(",", ""); carrera_act["distancia"] = raw_num + " METROS"; buscando_dist = False

            if carrera_act and buscando_cab:
                if col_num == -1: 
                    for idx, val in enumerate(fila_vals):
                        vup = val.upper(); 
                        if vup in ["Nº", "N°", "NO.", "NRO"]: col_num = idx
                        elif "CABALLO" in vup: col_cab = idx
                        elif "JOCKEY" in vup: col_joc = idx
                        elif "CABALLERIZA" in vup or "STUD" in vup: col_stud = idx
                        elif "CUIDADOR" in vup or "ENTRENADOR" in vup: col_cuid = idx
                else: 
                    try:
                        p_num = fila_vals[col_num]
                        if re.match(r'^\d+[A-Za-z]?$', p_num):
                            p_nom = fila_vals[col_cab] if col_cab != -1 else "---"; p_joc = fila_vals[col_joc] if col_joc != -1 and fila_vals[col_joc] not in ['nan', 'None', ''] else ""; p_stud = fila_vals[col_stud] if col_stud != -1 and fila_vals[col_stud] not in ['nan', 'None', ''] else ""; p_cuid = fila_vals[col_cuid] if col_cuid != -1 and fila_vals[col_cuid] not in ['nan', 'None', ''] else ""
                            if p_joc:
                                match_ap = re.search(r'^(.*?)(\s\d+|\d+)$', p_joc)
                                if match_ap: p_joc = f"{match_ap.group(1).strip()} - Ap. ({match_ap.group(2).strip()}kg)"
                            if p_nom not in ['', 'nan']: carrera_act["caballos"].append({ "numero": p_num, "nombre": p_nom, "jockey": p_joc, "stud": p_stud, "cuidador": p_cuid })
                    except: pass
            if carrera_act:
                if cond_cerrada: continue
                if any(texto_upper.startswith(k) for k in ["NO COMPUTABLE", "PREMIOS", "APUESTA", "INCREMENTO"]) or (col_num != -1): cond_cerrada = True; continue
                es_inicio = re.match(r'^(PARA|TODO|YEGUAS|PRODUCTOS|CABALLOS)', texto_upper)
                if (es_inicio or (carrera_act["condicion"] and "CARRERA" not in texto_upper)) and "CARRERA" not in texto_upper[:15]: carrera_act["condicion"] += " " + texto; carrera_act["condicion"] = re.sub(' +', ' ', carrera_act["condicion"]).strip().capitalize()
        if carrera_act: carreras.append(carrera_act)
        return carreras
    except Exception as e: print(e); return []

# =============================================================================
# INTERFAZ
# =============================================================================
def cargar_excel():
    global carreras_cargadas, memoria_retirados
    archivo = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls *.csv")])
    if archivo:
        datos = analizar_excel(archivo)
        if datos:
            carreras_cargadas = datos; combo_selector['values'] = [c['id'] for c in carreras_cargadas]; combo_selector.current(0)
            memoria_retirados = {}
            for i, c in enumerate(carreras_cargadas):
                num_real = str(i + 1)
                memoria_retirados[num_real] = "CORREN TODOS"
            seleccionar_carrera(None)
            lbl_status.config(text=f"✅ LISTO: {len(datos)} Carreras", fg="#2ecc71")
        else: messagebox.showwarning("Error", "No se encontraron carreras.")

def seleccionar_carrera(event):
    global carrera_actual_data, dividendos_memoria, memoria_paseo
    idx = combo_selector.current()
    if idx >= 0:
        carrera_actual_data = carreras_cargadas[idx]
        dividendos_memoria = {}; memoria_paseo = {} 
        entry_num.delete(0, tk.END); entry_num.insert(0, carrera_actual_data['id'])
        entry_dist.delete(0, tk.END); entry_dist.insert(0, carrera_actual_data['distancia'])
        entry_premio.delete(0, tk.END); entry_premio.insert(0, carrera_actual_data.get('premio',''))
        txt_cond.delete("1.0", tk.END); txt_cond.insert("1.0", carrera_actual_data.get('condicion',''))
        lbl_vivo_carrera.config(text=carrera_actual_data['id'])
        entry_inc_label.delete(0, tk.END); entry_inc_label.insert(0, carrera_actual_data.get("incremento_tipo", "INC."))
        entry_inc_monto.delete(0, tk.END); entry_inc_monto.insert(0, carrera_actual_data.get("incremento_monto", ""))
        lista_caballos = [f"{c['numero']} - {c['nombre']}" for c in carrera_actual_data['caballos']]
        combo_paseo['values'] = lista_caballos
        if lista_caballos: combo_paseo.current(0); seleccionar_caballo_paseo(None)
        actualizar_grilla_pantalla()
        cargar_checklist_retirados()

def enviar_placa_info():
    global visibilidad_placa; visibilidad_placa = True; guardar_placa_json()
    btn_placa_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d"); btn_placa.config(bg="#27ae60", text="✅ ENVIADA"); root.after(2000, lambda: btn_placa.config(bg="#d35400", text="📡 ACTUALIZAR DATOS"))
def toggle_placa():
    global visibilidad_placa; visibilidad_placa = not visibilidad_placa; guardar_placa_json()
    if visibilidad_placa: btn_placa_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
    else: btn_placa_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")
def guardar_placa_json():
    data = { "num_carrera": entry_num.get(), "distancia": entry_dist.get(), "premio": entry_premio.get(), "condicion": txt_cond.get("1.0", "end-1c").replace("\n", " ").strip(), "estado_pista": combo_pista.get(), "visible": visibilidad_placa }
    guardar_json(ARCHIVO_DATOS, data)
def abrir_pagos():
    if not carrera_actual_data: 
        messagebox.showwarning("Atención", "Primero seleccioná una carrera.")
        return
    
    # Crear ventana emergente
    win = tk.Toplevel(root)
    win.title(f"Cargar Dividendos - {carrera_actual_data['id']}")
    win.geometry("400x600")
    win.configure(bg="#ecf0f1")
    
    # Títulos
    tk.Label(win, text="N° - CABALLO", font=("bold", 10), bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    tk.Label(win, text="PAGO ($)", font=("bold", 10), bg="#ecf0f1").grid(row=0, column=1, padx=10, pady=10)

    entradas_pagos = {} # Para guardar referencia a los Entry

    # Frame con scroll para que entren todos los caballos
    canvas = tk.Canvas(win, bg="#ecf0f1", highlightthickness=0)
    scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#ecf0f1")

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.grid(row=1, column=0, columnspan=2, sticky="nsew")
    scrollbar.grid(row=1, column=2, sticky="ns")
    
    # Configurar peso del grid para que expanda
    win.grid_rowconfigure(1, weight=1)
    win.grid_columnconfigure(0, weight=1)

    # Generar campos
    caballos = carrera_actual_data.get('caballos', [])
    for idx, cab in enumerate(caballos):
        num_str = str(cab['numero'])
        
        # Etiqueta Nombre
        lbl = tk.Label(scrollable_frame, text=f"{num_str} - {cab['nombre']}", bg="#ecf0f1", anchor="w")
        lbl.grid(row=idx, column=0, padx=10, pady=2, sticky="w")
        
        # Input Pago
        entry = tk.Entry(scrollable_frame, width=10, justify="center")
        # Si ya existe en memoria, cargarlo
        valor_actual = dividendos_memoria.get(num_str, "")
        entry.insert(0, valor_actual)
        entry.grid(row=idx, column=1, padx=10, pady=2)
        
        entradas_pagos[num_str] = entry

    # Función interna para guardar
    def guardar_y_cerrar():
        global dividendos_memoria
        cambios = False
        for n, ent in entradas_pagos.items():
            val = ent.get().strip()
            if val:
                dividendos_memoria[n] = val
                cambios = True
            elif n in dividendos_memoria:
                # Si borraron el dato, lo sacamos de memoria
                del dividendos_memoria[n]
                cambios = True
        
        if cambios:
            print("Dividendos actualizados en memoria.")
            # Si el marcador está visible, forzar actualización en vivo
            if visibilidad_marcador:
                actualizar_marcador_vivo()
        
        win.destroy()

    # Botón Guardar
    btn_save = tk.Button(win, text="💾 GUARDAR Y CERRAR", command=guardar_y_cerrar, bg="#27ae60", fg="white", font=("bold", 12), height=2)
    btn_save.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

# =============================================================================
# CONTROLES VIVO
# =============================================================================
def btn_start(): global reloj_corriendo; reloj_corriendo = True; enviar_comando_reloj("START"); actualizar_estado_reloj()
def btn_parcial(): enviar_comando_reloj("PARCIAL")
def btn_final(): global reloj_corriendo; reloj_corriendo = False; enviar_comando_reloj("FINALIZAR"); actualizar_estado_reloj()
def btn_reset(): global reloj_corriendo; reloj_corriendo = False; enviar_comando_reloj("RESET"); actualizar_estado_reloj()
def toggle_reloj_visible():
    global visibilidad_reloj; visibilidad_reloj = not visibilidad_reloj
    if visibilidad_reloj: enviar_comando_reloj("MOSTRAR"); btn_reloj_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
    else: enviar_comando_reloj("OCULTAR"); btn_reloj_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")
def actualizar_estado_reloj():
    if reloj_corriendo: lbl_reloj_status.config(text="⏱ CARRERA EN CURSO", bg="#27ae60", fg="white"); btn_larga.config(text="⏸ PAUSAR (F1)", bg="#f1c40f", fg="black")
    else: lbl_reloj_status.config(text="⏹ RELOJ DETENIDO", bg="#34495e", fg="#bbb"); btn_larga.config(text="▶ LARGARON (F1)", bg="#27ae60", fg="#white")
def construir_datos_marcador(visible):
    datos = []; caballos_obj = carrera_actual_data.get("caballos", []) if carrera_actual_data else []
    if not visible: return []
    for i in range(4):
        entry = entradas_marcador[i]; num_str = entry.get().strip()
        if num_str:
            nombre = "COMPETIDOR"; 
            for c in caballos_obj:
                if str(c["numero"]) == num_str: nombre = c["nombre"]; break
            datos.append({ "posicion": i+1, "numero": num_str, "nombre": nombre, "dividendo": dividendos_memoria.get(num_str, "") })
    return datos
def actualizar_marcador_vivo(): global visibilidad_marcador; visibilidad_marcador = True; guardar_json(ARCHIVO_MARCADOR, construir_datos_marcador(True)); btn_act_marcador.config(bg="#2ecc71", text="✅ EN AIRE"); btn_mar_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
def toggle_marcador_tv():
    global visibilidad_marcador; visibilidad_marcador = not visibilidad_marcador; guardar_json(ARCHIVO_MARCADOR, construir_datos_marcador(visibilidad_marcador))
    if visibilidad_marcador: btn_mar_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d"); btn_act_marcador.config(bg="#2ecc71", text="✅ EN AIRE")
    else: btn_mar_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71"); btn_act_marcador.config(bg="#8e44ad", text="🚀 ENVIAR A TV (Oculto)")

# =============================================================================
# CONTROL PASEO
# =============================================================================
def guardar_cambios_paseo_actual():
    idx = combo_paseo.current(); 
    if idx < 0 or not carrera_actual_data: return
    caballo = carrera_actual_data['caballos'][idx]; num_cab = caballo['numero']
    memoria_paseo[num_cab] = { "jockey": entry_jockey.get(), "stud": entry_stud.get(), "cuidador": entry_cuid.get(), "cambio_monta": chk_cambio_var.get(), "retirado": chk_retirado_var.get() }
def seleccionar_caballo_paseo(event):
    if not carrera_actual_data: return
    idx = combo_paseo.current()
    if idx >= 0:
        caballo = carrera_actual_data['caballos'][idx]; num_cab = caballo['numero']; datos_memo = memoria_paseo.get(num_cab, {})
        entry_jockey.delete(0, tk.END); entry_jockey.insert(0, datos_memo.get("jockey", caballo.get('jockey', '')))
        entry_stud.delete(0, tk.END); entry_stud.insert(0, datos_memo.get("stud", caballo.get('stud', '')))
        entry_cuid.delete(0, tk.END); entry_cuid.insert(0, datos_memo.get("cuidador", caballo.get('cuidador', '')))
        chk_cambio_var.set(datos_memo.get("cambio_monta", False)); chk_retirado_var.set(datos_memo.get("retirado", False))
def enviar_placa_paseo():
    global visibilidad_paseo; visibilidad_paseo = True; idx = combo_paseo.current(); 
    if idx < 0: return
    guardar_cambios_paseo_actual(); caballo_data = carrera_actual_data['caballos'][idx]
    data = { "visible": True, "numero": caballo_data['numero'], "nombre": caballo_data['nombre'], "jockey": entry_jockey.get(), "stud": entry_stud.get(), "cuidador": entry_cuid.get(), "cambio_monta": chk_cambio_var.get(), "retirado": chk_retirado_var.get() }
    guardar_json(ARCHIVO_PASEO, data); btn_paseo_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
def toggle_paseo():
    global visibilidad_paseo; visibilidad_paseo = not visibilidad_paseo
    if visibilidad_paseo: enviar_placa_paseo()
    else: guardar_json(ARCHIVO_PASEO, {"visible": False}); btn_paseo_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")
def siguiente_caballo():
    guardar_cambios_paseo_actual(); current = combo_paseo.current(); total = len(combo_paseo['values'])
    if total > 0: combo_paseo.current((current + 1) % total); seleccionar_caballo_paseo(True); 
    if visibilidad_paseo: enviar_placa_paseo()
def anterior_caballo():
    guardar_cambios_paseo_actual(); current = combo_paseo.current(); total = len(combo_paseo['values'])
    if total > 0: combo_paseo.current((current - 1) % total); seleccionar_caballo_paseo(True); 
    if visibilidad_paseo: enviar_placa_paseo()
def ciclo_automatico_paseo():
    if chk_auto_var.get() and visibilidad_paseo and carrera_actual_data: siguiente_caballo()
    root.after(20000, ciclo_automatico_paseo)

# =============================================================================
# PANTALLA COMPLETA
# =============================================================================
entradas_pantalla = []; checklist_vars = []

def actualizar_grilla_pantalla():
    for widget in fr_grilla_scroll.winfo_children(): widget.destroy()
    global entradas_pantalla; entradas_pantalla = []
    if not carrera_actual_data: return
    headers = ["Nº", "GAN ($)", "EXACTA ($)", "TRIFECTA ($)"]
    for col, h in enumerate(headers): tk.Label(fr_grilla_scroll, text=h, font=("Arial", 9, "bold"), bg="#bdc3c7", relief="ridge").grid(row=0, column=col, sticky="nsew", ipadx=5)
    caballos = carrera_actual_data.get('caballos', [])
    for i, cab in enumerate(caballos):
        row = i + 1; tk.Label(fr_grilla_scroll, text=cab['numero'], bg="white", relief="sunken", width=6).grid(row=row, column=0, sticky="nsew")
        e_gan = tk.Entry(fr_grilla_scroll, width=10, justify="center"); e_gan.grid(row=row, column=1, padx=1)
        e_exa = tk.Entry(fr_grilla_scroll, width=10, justify="center"); e_exa.grid(row=row, column=2, padx=1)
        e_tri = tk.Entry(fr_grilla_scroll, width=10, justify="center"); e_tri.grid(row=row, column=3, padx=1)
        entradas_pantalla.append({ "num": cab['numero'], "gan": e_gan, "exa": e_exa, "tri": e_tri })

def cargar_checklist_retirados():
    for widget in fr_check_ret.winfo_children(): widget.destroy()
    global checklist_vars; checklist_vars = []
    if not carrera_actual_data: return
    caballos = carrera_actual_data.get('caballos', [])
    for cab in caballos:
        var = tk.BooleanVar(); c = tk.Checkbutton(fr_check_ret, text=f"{cab['numero']} - {cab['nombre']}", var=var, bg="#ecf0f1", anchor="w")
        c.pack(fill="x"); checklist_vars.append({"num": cab['numero'], "nom": cab['nombre'], "var": var})

def cerrar_carrera_retirados():
    carrera_id = carrera_actual_data.get('id', '??'); num_car = "".join(filter(str.isdigit, carrera_id))
    if not num_car: num_car = "1"
    lista_ret = []
    for item in checklist_vars:
        if item["var"].get(): lista_ret.append(f"{item['num']},{item['nom']}")
    if not lista_ret: memoria_retirados[num_car] = "CORREN TODOS"
    else: memoria_retirados[num_car] = "|".join(lista_ret)
    messagebox.showinfo("OK", f"Retirados guardados para Carrera {num_car}")

def calcular_favoritos_interno():
    try:
        lista_ganadores = []
        for item in entradas_pantalla:
            val_str = item["gan"].get().replace("$","").replace(",",".")
            is_ret = False
            for check in checklist_vars:
                if check["num"] == item["num"] and check["var"].get(): is_ret = True; break
            if val_str and not is_ret:
                try: val = float(val_str); lista_ganadores.append( (val, item["num"]) )
                except: pass
        lista_ganadores.sort(key=lambda x: x[0]); favs = [x[1] for x in lista_ganadores[:3]]; return "-".join(favs)
    except: return ""

def enviar_pantalla_completa():
    global visibilidad_pantalla; visibilidad_pantalla = True
    fav_auto = calcular_favoritos_interno()
    if fav_auto: entry_favoritos.delete(0, tk.END); entry_favoritos.insert(0, fav_auto)
    dividendos = []
    for item in entradas_pantalla:
        is_ret = False
        for check in checklist_vars:
            if check["num"] == item["num"] and check["var"].get(): is_ret = True; break
        val_gan = "RET" if is_ret else item["gan"].get()
        val_exa = "RET" if is_ret else item["exa"].get()
        val_tri = "RET" if is_ret else item["tri"].get()
        dividendos.append({ "numero": item["num"], "ganador": val_gan, "exacta": val_exa, "trifecta": val_tri })
    lista_final_retirados = []
    for k in sorted(memoria_retirados.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        val = memoria_retirados[k]; lista_final_retirados.append(f"{k}ª:{val}")
    data = { "visible": True, "favoritos": entry_favoritos.get(), "carrera_info": { "numero": entry_num.get(), "distancia": entry_dist.get(), "hora": carrera_actual_data.get("hora", "00:00") if carrera_actual_data else "00:00", "pista": combo_pista.get() }, "pozos": { "gan": entry_pozo_gan.get(), "exa": entry_pozo_exa.get(), "tri": entry_pozo_tri.get(), "extra": entry_pozo_extra.get(), "label_extra": combo_pozo_extra.get() }, "incremento": { "label": entry_inc_label.get(), "monto": entry_inc_monto.get() }, "retirados_global": lista_final_retirados, "tabla_apuestas": dividendos }
    guardar_json(ARCHIVO_PANTALLA, data); btn_pantalla_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")

def toggle_pantalla():
    global visibilidad_pantalla; visibilidad_pantalla = not visibilidad_pantalla
    if visibilidad_pantalla: enviar_pantalla_completa()
    else: guardar_json(ARCHIVO_PANTALLA, {"visible": False}); btn_pantalla_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")

def key_handler(event):
    if event.keysym == 'F1': btn_start()
    if event.keysym == 'F2': btn_parcial()
    if event.keysym == 'F3': btn_final()
    if event.keysym == 'F4': btn_reset()

# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================
root = tk.Tk(); root.title("CONSOLA DE MANDO V21 - HIPÓDROMO OFICIAL"); root.geometry("1250x780"); root.configure(bg="#2c3e50") 
p_izq = tk.Frame(root, bg="#ecf0f1", padx=10, pady=10); p_izq.place(relx=0, rely=0, relwidth=0.30, relheight=1)
tk.Label(p_izq, text="1. CONFIGURACIÓN", font=("Segoe UI", 14, "bold"), bg="#ecf0f1", fg="#7f8c8d").pack(anchor="w")
fr_carga = tk.LabelFrame(p_izq, text="Archivo", bg="#ecf0f1"); fr_carga.pack(fill="x", pady=5); tk.Button(fr_carga, text="📂 EXCEL", command=cargar_excel, bg="#bdc3c7").pack(side="left", padx=5, pady=5); combo_selector = ttk.Combobox(fr_carga, state="readonly"); combo_selector.pack(side="left", fill="x", expand=True, padx=5); combo_selector.bind("<<ComboboxSelected>>", seleccionar_carrera)
fr_datos = tk.Frame(p_izq, bg="#ecf0f1"); fr_datos.pack(fill="x", pady=10); tk.Label(fr_datos, text="Carrera:", bg="#ecf0f1").grid(row=0, column=0, sticky="w"); entry_num = tk.Entry(fr_datos, width=28); entry_num.grid(row=0, column=1, pady=2); tk.Label(fr_datos, text="Distancia:", bg="#ecf0f1").grid(row=1, column=0, sticky="w"); entry_dist = tk.Entry(fr_datos, width=28); entry_dist.grid(row=1, column=1, pady=2); tk.Label(fr_datos, text="Premio:", bg="#ecf0f1").grid(row=2, column=0, sticky="w"); entry_premio = tk.Entry(fr_datos, width=28); entry_premio.grid(row=2, column=1, pady=2); tk.Label(fr_datos, text="Condición:", bg="#ecf0f1").grid(row=3, column=0, sticky="nw"); txt_cond = tk.Text(fr_datos, width=28, height=4); txt_cond.grid(row=3, column=1, pady=2); tk.Label(fr_datos, text="Pista:", bg="#ecf0f1").grid(row=4, column=0, sticky="w"); combo_pista = ttk.Combobox(fr_datos, values=["NORMAL", "HÚMEDA", "PESADA", "FANGOSA", "BARROSA"], width=25); combo_pista.current(0); combo_pista.grid(row=4, column=1, pady=2)
fr_placa_ctrl = tk.Frame(p_izq, bg="#ecf0f1"); fr_placa_ctrl.pack(fill="x", pady=5); btn_placa = tk.Button(fr_placa_ctrl, text="📡 ACTUALIZAR DATOS", command=enviar_placa_info, bg="#d35400", fg="white", font=("bold", 11), height=2); btn_placa.pack(side="left", fill="x", expand=True); btn_placa_toggle = tk.Button(fr_placa_ctrl, text="👁️ OCULTAR", command=toggle_placa, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2); btn_placa_toggle.pack(side="right", padx=5)
tk.Button(p_izq, text="💰 CARGAR PAGOS", command=abrir_pagos, bg="#2980b9", fg="white", font=("bold", 10)).pack(fill="x", pady=5); lbl_status = tk.Label(p_izq, text="Esperando archivo...", bg="#ecf0f1", fg="#95a5a6"); lbl_status.pack(side="bottom")
p_der = tk.Frame(root, bg="#34495e", padx=10, pady=10); p_der.place(relx=0.30, rely=0, relwidth=0.70, relheight=1); style = ttk.Style(); style.configure("TNotebook", background="#34495e", borderwidth=0); style.configure("TNotebook.Tab", padding=[10, 5], font=('Segoe UI', 10, 'bold')); notebook = ttk.Notebook(p_der, style="TNotebook"); notebook.pack(fill="both", expand=True)
tab_paseo = tk.Frame(notebook, bg="#34495e", padx=20, pady=20); notebook.add(tab_paseo, text=" PREVIA / PASEO "); tk.Label(tab_paseo, text="CONTROL PLACA PASEO", font=("Segoe UI", 16, "bold"), bg="#34495e", fg="#f1c40f").pack(pady=10); fr_nav = tk.Frame(tab_paseo, bg="#34495e"); fr_nav.pack(fill="x", pady=5); tk.Button(fr_nav, text="◀ ANT", command=anterior_caballo, bg="#95a5a6").pack(side="left"); combo_paseo = ttk.Combobox(fr_nav, state="readonly", font=("Arial", 12)); combo_paseo.pack(side="left", fill="x", expand=True, padx=5); combo_paseo.bind("<<ComboboxSelected>>", seleccionar_caballo_paseo); tk.Button(fr_nav, text="SIG ▶", command=siguiente_caballo, bg="#95a5a6").pack(side="left"); fr_edit_paseo = tk.LabelFrame(tab_paseo, text="Datos Editables", bg="#34495e", fg="white", padx=10, pady=10); fr_edit_paseo.pack(fill="x", pady=10); tk.Label(fr_edit_paseo, text="Jockey:", bg="#34495e", fg="white").grid(row=0, column=0, sticky="e"); entry_jockey = tk.Entry(fr_edit_paseo, width=30); entry_jockey.grid(row=0, column=1, pady=5, padx=5); fr_checks = tk.Frame(fr_edit_paseo, bg="#34495e"); fr_checks.grid(row=0, column=2, rowspan=3, padx=10); chk_cambio_var = tk.BooleanVar(); tk.Checkbutton(fr_checks, text="Cambio de Monta", var=chk_cambio_var, bg="#34495e", fg="#f1c40f", selectcolor="#2c3e50").pack(anchor="w"); chk_retirado_var = tk.BooleanVar(); tk.Checkbutton(fr_checks, text="🚫 RETIRADO", var=chk_retirado_var, bg="#34495e", fg="#e74c3c", font=("bold",10), selectcolor="#2c3e50").pack(anchor="w", pady=5); tk.Label(fr_edit_paseo, text="Stud:", bg="#34495e", fg="white").grid(row=1, column=0, sticky="e"); entry_stud = tk.Entry(fr_edit_paseo, width=30); entry_stud.grid(row=1, column=1, pady=5, padx=5); tk.Label(fr_edit_paseo, text="Entrenador:", bg="#34495e", fg="white").grid(row=2, column=0, sticky="e"); entry_cuid = tk.Entry(fr_edit_paseo, width=30); entry_cuid.grid(row=2, column=1, pady=5, padx=5); chk_auto_var = tk.BooleanVar(); tk.Checkbutton(tab_paseo, text="🔄 PASEO AUTOMÁTICO (20 seg)", var=chk_auto_var, bg="#34495e", fg="#f1c40f", font=("bold", 11), selectcolor="#2c3e50").pack(pady=5); fr_btn_paseo = tk.Frame(tab_paseo, bg="#34495e"); fr_btn_paseo.pack(pady=20); tk.Button(fr_btn_paseo, text="🚀 MOSTRAR PLACA", command=enviar_placa_paseo, bg="#e67e22", fg="white", font=("bold", 12), width=20, height=2).pack(side="left", padx=5); btn_paseo_toggle = tk.Button(fr_btn_paseo, text="👁️ OCULTAR", command=toggle_paseo, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2); btn_paseo_toggle.pack(side="left", padx=5)
tab_vivo = tk.Frame(notebook, bg="#34495e", padx=20, pady=20); notebook.add(tab_vivo, text=" EN VIVO "); lbl_vivo_carrera = tk.Label(tab_vivo, text="---", font=("Segoe UI", 12), bg="#34495e", fg="#ecf0f1"); lbl_vivo_carrera.pack(); fr_reloj = tk.LabelFrame(tab_vivo, text="CONTROL RELOJ", font=("bold", 10), bg="#34495e", fg="white", padx=10, pady=10); fr_reloj.pack(fill="x", pady=15); fr_sts_reloj = tk.Frame(fr_reloj, bg="#34495e"); fr_sts_reloj.pack(fill="x"); lbl_reloj_status = tk.Label(fr_sts_reloj, text="⏹ RELOJ DETENIDO", font=("Arial", 18, "bold"), bg="#2c3e50", fg="#bbb", pady=5); lbl_reloj_status.pack(side="left", fill="x", expand=True); btn_reloj_toggle = tk.Button(fr_sts_reloj, text="👁️ OCULTAR", command=toggle_reloj_visible, bg="#7f8c8d", fg="white", font=("bold", 9)); btn_reloj_toggle.pack(side="right", padx=5); fr_btns_reloj = tk.Frame(fr_reloj, bg="#34495e"); fr_btns_reloj.pack(pady=5); btn_larga = tk.Button(fr_btns_reloj, text="▶ LARGARON (F1)", command=btn_start, bg="#27ae60", fg="white", font=("bold", 12), width=20, height=2); btn_larga.grid(row=0, column=0, padx=5, pady=5); tk.Button(fr_btns_reloj, text="📷 PARCIAL (F2)", command=btn_parcial, bg="#e67e22", fg="white", font=("bold", 10), width=15, height=2).grid(row=0, column=1, padx=5); fr_btns_reloj2 = tk.Frame(fr_reloj, bg="#34495e"); fr_btns_reloj2.pack(pady=5); tk.Button(fr_btns_reloj2, text="🏁 FINALIZAR (F3)", command=btn_final, bg="#c0392b", fg="white", font=("bold", 10), width=18).pack(side="left", padx=5); tk.Button(fr_btns_reloj2, text="🔄 RESET (F4)", command=btn_reset, bg="#7f8c8d", fg="white", font=("bold", 10), width=18).pack(side="left", padx=5); fr_mar = tk.LabelFrame(tab_vivo, text="MARCADOR VIVO", font=("bold", 10), bg="#34495e", fg="white", padx=10, pady=10); fr_mar.pack(fill="x", pady=10); entradas_marcador = []; fr_grid_mar = tk.Frame(fr_mar, bg="#34495e"); fr_grid_mar.pack(); 
for i in range(4): tk.Label(fr_grid_mar, text=f"{i+1}°", font=("bold", 14), bg="#34495e", fg="white").grid(row=0, column=i, padx=10); e = tk.Entry(fr_grid_mar, width=4, font=("bold", 24), justify="center"); e.grid(row=1, column=i, padx=10, pady=5); entradas_marcador.append(e)
fr_btn_mar = tk.Frame(fr_mar, bg="#34495e"); fr_btn_mar.pack(fill="x", pady=10); btn_act_marcador = tk.Button(fr_btn_mar, text="🚀 ENVIAR A TV", command=actualizar_marcador_vivo, bg="#8e44ad", fg="white", font=("bold", 14), height=2); btn_act_marcador.pack(side="left", fill="x", expand=True); btn_mar_toggle = tk.Button(fr_btn_mar, text="👁️ OCULTAR", command=toggle_marcador_tv, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2); btn_mar_toggle.pack(side="right", padx=5)
tab_pantalla = tk.Frame(notebook, bg="#34495e", padx=10, pady=10); notebook.add(tab_pantalla, text=" PANTALLA COMPLETA "); fr_top_pc = tk.Frame(tab_pantalla, bg="#34495e"); fr_top_pc.pack(fill="x"); fr_inc = tk.LabelFrame(fr_top_pc, text="Incremento", bg="#34495e", fg="white"); fr_inc.pack(side="left", padx=5); entry_inc_label = tk.Entry(fr_inc, width=10); entry_inc_label.insert(0, "INC."); entry_inc_label.pack(side="left"); entry_inc_monto = tk.Entry(fr_inc, width=10); entry_inc_monto.pack(side="left"); fr_fav = tk.LabelFrame(fr_top_pc, text="Favoritos (Calc Auto)", bg="#34495e", fg="white"); fr_fav.pack(side="left", padx=5); entry_favoritos = tk.Entry(fr_fav, width=15, font=("bold", 11)); entry_favoritos.pack(side="left"); fr_pozos = tk.LabelFrame(tab_pantalla, text="Pozos Acumulados ($)", bg="#34495e", fg="white"); fr_pozos.pack(fill="x", pady=5); tk.Label(fr_pozos, text="GAN:", bg="#34495e", fg="white").grid(row=0, column=0); entry_pozo_gan = tk.Entry(fr_pozos, width=10); entry_pozo_gan.grid(row=0, column=1); tk.Label(fr_pozos, text="EXA:", bg="#34495e", fg="white").grid(row=0, column=2); entry_pozo_exa = tk.Entry(fr_pozos, width=10); entry_pozo_exa.grid(row=0, column=3); tk.Label(fr_pozos, text="TRI:", bg="#34495e", fg="white").grid(row=0, column=4); entry_pozo_tri = tk.Entry(fr_pozos, width=10); entry_pozo_tri.grid(row=0, column=5); combo_pozo_extra = ttk.Combobox(fr_pozos, values=["CADENA:", "QUINTUPLO:", "CUATERNA:", "TRIPLO:", "DOBLE:"], width=10); combo_pozo_extra.current(0); combo_pozo_extra.grid(row=0, column=6, padx=5); entry_pozo_extra = tk.Entry(fr_pozos, width=10); entry_pozo_extra.grid(row=0, column=7)
fr_split = tk.Frame(tab_pantalla, bg="#34495e"); fr_split.pack(fill="both", expand=True); fr_grilla_wrapper = tk.LabelFrame(fr_split, text="Carga de Dividendos", bg="#34495e", fg="white"); fr_grilla_wrapper.pack(side="left", fill="both", expand=True, padx=5); canvas_grilla = tk.Canvas(fr_grilla_wrapper, bg="#ecf0f1"); scroll_grilla = tk.Scrollbar(fr_grilla_wrapper, command=canvas_grilla.yview); fr_grilla_scroll = tk.Frame(canvas_grilla, bg="#ecf0f1"); canvas_grilla.create_window((0,0), window=fr_grilla_scroll, anchor="nw"); canvas_grilla.configure(yscrollcommand=scroll_grilla.set); canvas_grilla.pack(side="left", fill="both", expand=True); scroll_grilla.pack(side="right", fill="y"); fr_grilla_scroll.bind("<Configure>", lambda e: canvas_grilla.configure(scrollregion=canvas_grilla.bbox("all")))
fr_gestor_ret = tk.LabelFrame(fr_split, text="Marcar Retirados", bg="#34495e", fg="white", width=250); fr_gestor_ret.pack(side="right", fill="y", padx=5); fr_check_ret = tk.Frame(fr_gestor_ret, bg="#ecf0f1"); fr_check_ret.pack(fill="both", expand=True, padx=2, pady=2); tk.Button(fr_gestor_ret, text="🔒 CERRAR CARRERA", command=cerrar_carrera_retirados, bg="#c0392b", fg="white", font=("bold", 10)).pack(fill="x", pady=5)
fr_btn_pc = tk.Frame(tab_pantalla, bg="#34495e"); fr_btn_pc.pack(fill="x", pady=10); tk.Button(fr_btn_pc, text="🖥️ ENVIAR PANTALLA", command=enviar_pantalla_completa, bg="#9b59b6", fg="white", font=("bold", 12), height=2).pack(side="left", fill="x", expand=True); btn_pantalla_toggle = tk.Button(fr_btn_pc, text="👁️ OCULTAR", command=toggle_pantalla, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2); btn_pantalla_toggle.pack(side="right", padx=5)

root.bind('<Key>', key_handler)
inicializar_sistema(); root.mainloop()