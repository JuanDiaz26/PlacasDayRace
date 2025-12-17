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

# --- VARIABLES GLOBALES ---
carreras_cargadas = []
carrera_actual_data = None 
dividendos_memoria = {} 
reloj_corriendo = False 
# Estados de visibilidad
visibilidad_placa = True
visibilidad_reloj = True
visibilidad_marcador = True # NUEVA VARIABLE GLOBAL

# =============================================================================
# 1. FUNCIONES DE LIMPIEZA Y COMUNICACIÓN
# =============================================================================

def inicializar_sistema():
    """Limpia todo al arrancar el programa"""
    print("--- INICIALIZANDO SISTEMA DE TV ---")
    # Inicializamos marcador visible pero vacío
    guardar_json(ARCHIVO_MARCADOR, []) 
    enviar_comando_reloj("RESET")
    # Datos vacíos pero visibles por defecto
    datos_vacios = {"num_carrera": "", "distancia": "", "premio": "", "condicion": "", "estado_pista": "", "visible": False}
    guardar_json(ARCHIVO_DATOS, datos_vacios)

def guardar_json(archivo, data):
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error guardando {archivo}: {e}")

def enviar_comando_reloj(accion):
    comando = { "id": time.time(), "accion": accion }
    guardar_json(ARCHIVO_COMANDO, comando)
    print(f"📡 COMANDO RELOJ: {accion}")

# =============================================================================
# 2. LÓGICA DE EXCEL (CORREGIDA PARA PUNTOS EN METROS)
# =============================================================================
def analizar_excel(ruta_archivo):
    print(f"--- ANALIZANDO: {ruta_archivo} ---")
    try:
        if ruta_archivo.endswith('.csv'): df = pd.read_csv(ruta_archivo, header=None, sep=None, engine='python')
        else: df = pd.read_excel(ruta_archivo, header=None)
        
        carreras = []
        carrera_act = None
        buscando_dist = False; cond_cerrada = False
        buscando_cab = False; col_num = -1; col_nom = -1

        for i in range(len(df)):
            fila_vals = [str(val).strip() for val in df.iloc[i].values]
            texto = " ".join([v for v in fila_vals if v not in ['nan', 'None', '']])
            texto_upper = texto.upper()
            
            # Detectar Carrera
            match_tit = re.search(r'^(\d+)[º°aª]\s*CARRERA', texto_upper)
            if match_tit:
                if carrera_act: carreras.append(carrera_act)
                carrera_act = { "id": "", "distancia": "---", "premio": "", "condicion": "", "pista": "NORMAL", "caballos": [] }
                cond_cerrada = False
                
                regex_premio = r'(GRAN PREMIO|PREMIO|CLÁSICO|CLASICO|ESPECIAL|HANDICAP)'
                match_corte = re.search(regex_premio, texto_upper)
                if match_corte:
                    carrera_act["id"] = texto[:match_corte.start()].strip()
                    tipo = match_corte.group(1).upper()
                    resto = texto[match_corte.end():].split("1")[0].split(":")[0].strip().replace('"', '')
                    carrera_act["premio"] = f'{tipo} "{resto}"'
                else:
                    carrera_act["id"] = texto
                
                buscando_dist = True; buscando_cab = True; col_num = -1; continue

            # Detectar Distancia (CORREGIDO: ACEPTA PUNTOS Y COMAS)
            if carrera_act and buscando_dist:
                match_mts = re.search(r'(\d{1,2}[.,]?\d{3}|\d{3})\s*(METROS|MTS)', texto_upper)
                if match_mts:
                    raw_num = match_mts.group(1)
                    num_limpio = raw_num.replace(".", "").replace(",", "")
                    carrera_act["distancia"] = num_limpio + " METROS"
                    buscando_dist = False

            # Detectar Caballos
            if carrera_act and buscando_cab:
                if col_num == -1: 
                    for idx, val in enumerate(fila_vals):
                        vup = val.upper()
                        if vup in ["Nº", "N°", "NO.", "NRO"]: col_num = idx
                        elif "CABALLO" in vup: col_nom = idx
                else: 
                    try:
                        p_num = fila_vals[col_num]
                        p_nom = fila_vals[col_nom]
                        if re.match(r'^\d+[A-Za-z]?$', p_num) and p_nom not in ['', 'nan']:
                            carrera_act["caballos"].append({ "numero": p_num, "nombre": p_nom })
                    except: pass

            # Condición
            if carrera_act:
                if cond_cerrada: continue
                if any(texto_upper.startswith(k) for k in ["NO COMPUTABLE", "PREMIOS", "APUESTA", "INCREMENTO"]) or (col_num != -1):
                    cond_cerrada = True; continue
                
                es_inicio = re.match(r'^(PARA|TODO|YEGUAS|PRODUCTOS|CABALLOS)', texto_upper)
                if (es_inicio or (carrera_act["condicion"] and "CARRERA" not in texto_upper)) and "CARRERA" not in texto_upper[:15]:
                    carrera_act["condicion"] += " " + texto
                    carrera_act["condicion"] = re.sub(' +', ' ', carrera_act["condicion"]).strip().capitalize()

        if carrera_act: carreras.append(carrera_act)
        return carreras
    except Exception as e: print(e); return []

# =============================================================================
# 3. INTERFAZ GRÁFICA (GUI)
# =============================================================================

def cargar_excel():
    global carreras_cargadas
    archivo = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls *.csv")])
    if archivo:
        datos = analizar_excel(archivo)
        if datos:
            carreras_cargadas = datos
            combo_selector['values'] = [c['id'] for c in carreras_cargadas]
            combo_selector.current(0)
            seleccionar_carrera(None)
            lbl_status.config(text=f"✅ LISTO: {len(datos)} Carreras", fg="#2ecc71")
        else: messagebox.showwarning("Error", "No se encontraron carreras.")

def seleccionar_carrera(event):
    global carrera_actual_data, dividendos_memoria
    idx = combo_selector.current()
    if idx >= 0:
        carrera_actual_data = carreras_cargadas[idx]
        dividendos_memoria = {} # Reset pagos
        
        entry_num.delete(0, tk.END); entry_num.insert(0, carrera_actual_data['id'])
        entry_dist.delete(0, tk.END); entry_dist.insert(0, carrera_actual_data['distancia'])
        entry_premio.delete(0, tk.END); entry_premio.insert(0, carrera_actual_data.get('premio',''))
        txt_cond.delete("1.0", tk.END); txt_cond.insert("1.0", carrera_actual_data.get('condicion',''))
        lbl_vivo_carrera.config(text=carrera_actual_data['id'])

# --- CONTROL PLACA INFO ---
def enviar_placa_info():
    global visibilidad_placa
    visibilidad_placa = True # Al enviar, forzamos que se vea
    guardar_placa_json()
    btn_placa_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
    
    btn_placa.config(bg="#27ae60", text="✅ PLACA ENVIADA")
    root.after(2000, lambda: btn_placa.config(bg="#d35400", text="📡 ACTUALIZAR DATOS"))

def toggle_placa():
    global visibilidad_placa
    visibilidad_placa = not visibilidad_placa
    guardar_placa_json()
    if visibilidad_placa:
        btn_placa_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
    else:
        btn_placa_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")

def guardar_placa_json():
    data = {
        "num_carrera": entry_num.get(),
        "distancia": entry_dist.get(),
        "premio": entry_premio.get(),
        "condicion": txt_cond.get("1.0", "end-1c").replace("\n", " ").strip(),
        "estado_pista": combo_pista.get(),
        "visible": visibilidad_placa # CAMPO NUEVO PARA HTML
    }
    guardar_json(ARCHIVO_DATOS, data)

# --- VENTANA DE PAGOS (FIX UI) ---
def abrir_pagos():
    if not carrera_actual_data: messagebox.showwarning("!","Selecciona carrera"); return
    
    win = tk.Toplevel(root); win.title("Cargar Dividendos"); win.geometry("450x600")
    
    # Header
    tk.Label(win, text="TABLA DE PAGOS", font=("bold", 12), pady=10).pack()

    # Frame Scrollable (Para los caballos)
    frame_main = tk.Frame(win)
    frame_main.pack(fill="both", expand=True, padx=10)
    
    canvas = tk.Canvas(frame_main); scroll = tk.Scrollbar(frame_main, command=canvas.yview)
    frm_list = tk.Frame(canvas); canvas.create_window((0,0), window=frm_list, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set); canvas.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
    frm_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    entries = []
    caballos = carrera_actual_data.get("caballos", [{"numero":str(i),"nombre":"--"} for i in range(1,17)])
    
    for c in caballos:
        row = tk.Frame(frm_list); row.pack(fill="x", pady=2)
        tk.Label(row, text=f"{c['numero']}", width=4, font=("bold",11)).pack(side="left")
        tk.Label(row, text=f"{c['nombre'][:22]}", width=25, anchor="w").pack(side="left")
        e = tk.Entry(row, width=10); e.pack(side="left")
        if c['numero'] in dividendos_memoria: e.insert(0, dividendos_memoria[c['numero']])
        entries.append((c['numero'], e))
    
    # BOTÓN FIJO AL FINAL (Fuera del scroll para que siempre se vea)
    frame_btn = tk.Frame(win, pady=10, bg="#ecf0f1")
    frame_btn.pack(fill="x", side="bottom")
    
    def guardar():
        global dividendos_memoria
        dividendos_memoria = {n: e.get().strip() for n, e in entries if e.get().strip()}
        win.destroy(); messagebox.showinfo("OK", "Pagos guardados en memoria")
    
    tk.Button(frame_btn, text="💾 GUARDAR Y CERRAR", command=guardar, bg="#27ae60", fg="white", font=("bold",12), height=2).pack(fill="x", padx=20)

# =============================================================================
# 4. CONTROLES DE VIVO
# =============================================================================

# --- CONTROL RELOJ ---
def btn_start():
    global reloj_corriendo
    if not reloj_corriendo:
        enviar_comando_reloj("START")
        reloj_corriendo = True
        actualizar_estado_reloj()
    else:
        enviar_comando_reloj("STOP") # Pausa
        reloj_corriendo = False
        actualizar_estado_reloj()

def btn_parcial(): enviar_comando_reloj("PARCIAL")

def btn_final():
    global reloj_corriendo
    enviar_comando_reloj("FINALIZAR")
    reloj_corriendo = False
    actualizar_estado_reloj()

def btn_reset():
    global reloj_corriendo
    enviar_comando_reloj("RESET")
    reloj_corriendo = False
    actualizar_estado_reloj()

def toggle_reloj_visible():
    global visibilidad_reloj
    visibilidad_reloj = not visibilidad_reloj
    if visibilidad_reloj:
        enviar_comando_reloj("MOSTRAR")
        btn_reloj_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
    else:
        enviar_comando_reloj("OCULTAR")
        btn_reloj_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")

def actualizar_estado_reloj():
    if reloj_corriendo:
        lbl_reloj_status.config(text="⏱ CARRERA EN CURSO", bg="#27ae60", fg="white")
        btn_larga.config(text="⏸ PAUSAR (F1)", bg="#f1c40f", fg="black")
    else:
        lbl_reloj_status.config(text="⏹ RELOJ DETENIDO", bg="#34495e", fg="#bbb")
        btn_larga.config(text="▶ LARGARON (F1)", bg="#27ae60", fg="white")

# --- CONTROL MARCADOR ---
# Esta funcion construye los datos a guardar en el JSON
def construir_datos_marcador(visible):
    datos = []
    caballos_obj = carrera_actual_data.get("caballos", []) if carrera_actual_data else []

    # Si NO es visible, guardamos una lista VACIA para que el HTML la detecte y se oculte
    if not visible:
        return []

    # Si ES visible, construimos la lista con los datos actuales
    for i in range(4):
        entry = entradas_marcador[i]
        num_str = entry.get().strip()
        if num_str:
            nombre = "COMPETIDOR"
            for c in caballos_obj:
                if str(c["numero"]) == num_str: nombre = c["nombre"]; break
            precio = dividendos_memoria.get(num_str, "")
            datos.append({ "posicion": i+1, "numero": num_str, "nombre": nombre, "dividendo": precio })
    return datos

def actualizar_marcador_vivo():
    global visibilidad_marcador
    visibilidad_marcador = True # Al actualizar forzamos mostrar
    
    datos = construir_datos_marcador(True)
    guardar_json(ARCHIVO_MARCADOR, datos)
    
    btn_act_marcador.config(bg="#2ecc71", text="✅ EN AIRE")
    btn_mar_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")

def toggle_marcador_tv():
    global visibilidad_marcador
    visibilidad_marcador = not visibilidad_marcador
    
    datos = construir_datos_marcador(visibilidad_marcador)
    guardar_json(ARCHIVO_MARCADOR, datos)
    
    if visibilidad_marcador:
        btn_mar_toggle.config(text="👁️ OCULTAR", bg="#7f8c8d")
        btn_act_marcador.config(bg="#2ecc71", text="✅ EN AIRE")
    else:
        btn_mar_toggle.config(text="👁️ MOSTRAR", bg="#2ecc71")
        btn_act_marcador.config(bg="#8e44ad", text="🚀 ENVIAR A TV (Oculto)")

# --- ATAJOS ---
def key_handler(event):
    if event.keysym == 'F1': btn_start()
    if event.keysym == 'F2': btn_parcial()
    if event.keysym == 'F3': btn_final()
    if event.keysym == 'F4': btn_reset()


# =============================================================================
# 5. VENTANA PRINCIPAL
# =============================================================================
root = tk.Tk()
root.title("CONSOLA DE MANDO V13 - HIPÓDROMO")
root.geometry("1100x700") 
root.configure(bg="#2c3e50") 

# --- PANEL IZQUIERDO ---
p_izq = tk.Frame(root, bg="#ecf0f1", padx=10, pady=10)
p_izq.place(relx=0, rely=0, relwidth=0.4, relheight=1)

tk.Label(p_izq, text="1. CONFIGURACIÓN", font=("Segoe UI", 14, "bold"), bg="#ecf0f1", fg="#7f8c8d").pack(anchor="w")

# Carga
fr_carga = tk.LabelFrame(p_izq, text="Archivo", bg="#ecf0f1"); fr_carga.pack(fill="x", pady=5)
tk.Button(fr_carga, text="📂 ABRIR EXCEL", command=cargar_excel, bg="#bdc3c7").pack(side="left", padx=5, pady=5)
combo_selector = ttk.Combobox(fr_carga, state="readonly"); combo_selector.pack(side="left", fill="x", expand=True, padx=5)
combo_selector.bind("<<ComboboxSelected>>", seleccionar_carrera)

# Datos
fr_datos = tk.Frame(p_izq, bg="#ecf0f1"); fr_datos.pack(fill="x", pady=10)
tk.Label(fr_datos, text="Carrera:", bg="#ecf0f1").grid(row=0, column=0, sticky="w"); entry_num = tk.Entry(fr_datos, width=30); entry_num.grid(row=0, column=1, pady=2)
tk.Label(fr_datos, text="Distancia:", bg="#ecf0f1").grid(row=1, column=0, sticky="w"); entry_dist = tk.Entry(fr_datos, width=30); entry_dist.grid(row=1, column=1, pady=2)
tk.Label(fr_datos, text="Premio:", bg="#ecf0f1").grid(row=2, column=0, sticky="w"); entry_premio = tk.Entry(fr_datos, width=30); entry_premio.grid(row=2, column=1, pady=2)
tk.Label(fr_datos, text="Condición:", bg="#ecf0f1").grid(row=3, column=0, sticky="nw"); txt_cond = tk.Text(fr_datos, width=30, height=4); txt_cond.grid(row=3, column=1, pady=2)
tk.Label(fr_datos, text="Pista:", bg="#ecf0f1").grid(row=4, column=0, sticky="w"); combo_pista = ttk.Combobox(fr_datos, values=["NORMAL", "HÚMEDA", "PESADA", "FANGOSA"], width=27); combo_pista.current(0); combo_pista.grid(row=4, column=1, pady=2)

# Control Placa
fr_placa_ctrl = tk.Frame(p_izq, bg="#ecf0f1"); fr_placa_ctrl.pack(fill="x", pady=5)
btn_placa = tk.Button(fr_placa_ctrl, text="📡 ACTUALIZAR DATOS", command=enviar_placa_info, bg="#d35400", fg="white", font=("bold", 11), height=2)
btn_placa.pack(side="left", fill="x", expand=True)
btn_placa_toggle = tk.Button(fr_placa_ctrl, text="👁️ OCULTAR", command=toggle_placa, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2)
btn_placa_toggle.pack(side="right", padx=5)

tk.Button(p_izq, text="💰 CARGAR PAGOS", command=abrir_pagos, bg="#2980b9", fg="white", font=("bold", 10)).pack(fill="x", pady=5)
lbl_status = tk.Label(p_izq, text="Esperando archivo...", bg="#ecf0f1", fg="#95a5a6"); lbl_status.pack(side="bottom")


# --- PANEL DERECHO ---
p_der = tk.Frame(root, bg="#34495e", padx=20, pady=20)
p_der.place(relx=0.4, rely=0, relwidth=0.6, relheight=1)

tk.Label(p_der, text="2. CONSOLA DE VIVO", font=("Segoe UI", 16, "bold"), bg="#34495e", fg="#f1c40f").pack()
lbl_vivo_carrera = tk.Label(p_der, text="---", font=("Segoe UI", 12), bg="#34495e", fg="#ecf0f1"); lbl_vivo_carrera.pack()

# RELOJ
fr_reloj = tk.LabelFrame(p_der, text="CONTROL RELOJ", font=("bold", 10), bg="#34495e", fg="white", padx=10, pady=10)
fr_reloj.pack(fill="x", pady=15)

# Fila status + toggle
fr_sts_reloj = tk.Frame(fr_reloj, bg="#34495e"); fr_sts_reloj.pack(fill="x")
lbl_reloj_status = tk.Label(fr_sts_reloj, text="⏹ RELOJ DETENIDO", font=("Arial", 18, "bold"), bg="#2c3e50", fg="#bbb", pady=5)
lbl_reloj_status.pack(side="left", fill="x", expand=True)
btn_reloj_toggle = tk.Button(fr_sts_reloj, text="👁️ OCULTAR", command=toggle_reloj_visible, bg="#7f8c8d", fg="white", font=("bold", 9))
btn_reloj_toggle.pack(side="right", padx=5)

fr_btns_reloj = tk.Frame(fr_reloj, bg="#34495e"); fr_btns_reloj.pack(pady=5)
btn_larga = tk.Button(fr_btns_reloj, text="▶ LARGARON (F1)", command=btn_start, bg="#27ae60", fg="white", font=("bold", 12), width=20, height=2)
btn_larga.grid(row=0, column=0, padx=5, pady=5)
tk.Button(fr_btns_reloj, text="📷 PARCIAL (F2)", command=btn_parcial, bg="#e67e22", fg="white", font=("bold", 10), width=15, height=2).grid(row=0, column=1, padx=5)

fr_btns_reloj2 = tk.Frame(fr_reloj, bg="#34495e"); fr_btns_reloj2.pack(pady=5)
tk.Button(fr_btns_reloj2, text="🏁 FINALIZAR (F3)", command=btn_final, bg="#c0392b", fg="white", font=("bold", 10), width=18).pack(side="left", padx=5)
tk.Button(fr_btns_reloj2, text="🔄 RESET (F4)", command=btn_reset, bg="#7f8c8d", fg="white", font=("bold", 10), width=18).pack(side="left", padx=5)


# MARCADOR
fr_mar = tk.LabelFrame(p_der, text="MARCADOR VIVO (Mandiles)", font=("bold", 10), bg="#34495e", fg="white", padx=10, pady=10)
fr_mar.pack(fill="x", pady=10)

entradas_marcador = []
fr_grid_mar = tk.Frame(fr_mar, bg="#34495e"); fr_grid_mar.pack()

for i in range(4):
    tk.Label(fr_grid_mar, text=f"{i+1}°", font=("bold", 14), bg="#34495e", fg="white").grid(row=0, column=i, padx=10)
    e = tk.Entry(fr_grid_mar, width=4, font=("bold", 24), justify="center"); e.grid(row=1, column=i, padx=10, pady=5)
    entradas_marcador.append(e)

fr_btn_mar = tk.Frame(fr_mar, bg="#34495e"); fr_btn_mar.pack(fill="x", pady=10)
btn_act_marcador = tk.Button(fr_btn_mar, text="🚀 ENVIAR A TV", command=actualizar_marcador_vivo, bg="#8e44ad", fg="white", font=("bold", 14), height=2)
btn_act_marcador.pack(side="left", fill="x", expand=True)
btn_mar_toggle = tk.Button(fr_btn_mar, text="👁️ OCULTAR", command=toggle_marcador_tv, bg="#7f8c8d", fg="white", font=("bold", 10), width=12, height=2)
btn_mar_toggle.pack(side="right", padx=5)

root.bind('<Key>', key_handler)
inicializar_sistema()
root.mainloop()