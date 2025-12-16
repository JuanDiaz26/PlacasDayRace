import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import pandas as pd
import re
import os

# Archivos JSON
ARCHIVO_DATOS = "datos.json"
ARCHIVO_MARCADOR = "marcador.json"

carreras_cargadas = []
carrera_actual_data = None 
dividendos_memoria = {} 

# --- 1. LÓGICA DE LECTURA INTELIGENTE ---
def analizar_excel(ruta_archivo):
    print(f"--- ANALIZANDO: {ruta_archivo} ---")
    try:
        if ruta_archivo.endswith('.csv'):
             df = pd.read_csv(ruta_archivo, header=None, sep=None, engine='python')
        else:
             df = pd.read_excel(ruta_archivo, header=None)
        
        carreras_detectadas = []
        carrera_actual = None
        buscando_distancia = False 
        condicion_cerrada = False
        buscando_caballos = False
        col_idx_numero = -1
        col_idx_nombre = -1

        n_filas = len(df)
        for i in range(n_filas):
            fila_vals_raw = [str(val).strip() for val in df.iloc[i].values]
            fila_texto = " ".join([v for v in fila_vals_raw if v != 'nan' and v != 'None' and v != ''])
            texto_mayus = fila_texto.upper()
            
            match_titulo = re.search(r'^(\d+)[º°aª]\s*CARRERA', texto_mayus)
            if match_titulo:
                if carrera_actual is not None: carreras_detectadas.append(carrera_actual)
                carrera_actual = { "id": "", "distancia": "DISTANCIA NO HALLADA", "premio": "", "condicion": "", "pista": "NORMAL", "caballos": [] }
                condicion_cerrada = False 
                palabras_clave = ["GRAN PREMIO", "PREMIO", "CLÁSICO", "CLASICO", "ESPECIAL", "HANDICAP"]
                regex_corte = r'(' + '|'.join(palabras_clave) + r')'
                match_corte = re.search(regex_corte, texto_mayus)
                if match_corte:
                    idx = match_corte.start()
                    carrera_actual["id"] = fila_texto[:idx].strip()
                    tipo = match_corte.group(1).upper()
                    resto = fila_texto[match_corte.end():].strip()
                    resto = re.split(r'\d{1,2}:\d{2}', resto)[0].strip()
                    resto = resto.replace(":", "").replace('"', '').replace("'", "").strip()
                    carrera_actual["premio"] = f'{tipo} "{resto}"'
                else:
                    carrera_actual["id"] = fila_texto
                buscando_distancia = True; buscando_caballos = True; col_idx_numero = -1; continue

            if carrera_actual is not None and buscando_distancia:
                match_mts = re.search(r'(\d{1,2}\.?\d{3}|\d{3})\s*(METROS|MTS)', texto_mayus)
                if match_mts:
                    num = match_mts.group(1).replace(".", "")
                    carrera_actual["distancia"] = num + " METROS"
                    buscando_distancia = False 
            
            if carrera_actual is not None and buscando_caballos:
                if col_idx_numero == -1:
                    for idx, val in enumerate(fila_vals_raw):
                        val_upper = val.upper()
                        if val_upper in ["Nº", "N°", "NO.", "NRO", "NRO."]: col_idx_numero = idx
                        elif "CABALLO" in val_upper: col_idx_nombre = idx
                    if col_idx_numero != -1 and col_idx_nombre != -1: continue 
                else:
                    try:
                        posible_numero = fila_vals_raw[col_idx_numero]
                        posible_nombre = fila_vals_raw[col_idx_nombre]
                        if re.match(r'^\d+[A-Za-z]?$', posible_numero) and posible_nombre != '' and posible_nombre != 'nan':
                            carrera_actual["caballos"].append({ "numero": posible_numero, "nombre": posible_nombre })
                    except: pass

            if carrera_actual is not None:
                if condicion_cerrada: continue
                palabras_freno = ["NO COMPUTABLE", "PREMIOS", "APUESTA", "INCREMENTO", "RECORD", "CAT.", "AP.", "4 ULT.", "Nº"]
                activar_freno = False
                for palabra in palabras_freno:
                    if texto_mayus.startswith(palabra): activar_freno = True; break
                if col_idx_numero != -1: activar_freno = True
                if activar_freno: condicion_cerrada = True; continue
                es_inicio = re.match(r'^(PARA|TODO|YEGUAS|PRODUCTOS|CABALLOS)', texto_mayus.strip())
                es_continuacion = (carrera_actual["condicion"] != "" and "CARRERA" not in texto_mayus)
                if (es_inicio or es_continuacion) and "CARRERA" not in texto_mayus[:15]:
                     if carrera_actual["condicion"] == "": carrera_actual["condicion"] = fila_texto
                     else: carrera_actual["condicion"] += " " + fila_texto; carrera_actual["condicion"] = re.sub(' +', ' ', carrera_actual["condicion"])
                     carrera_actual["condicion"] = carrera_actual["condicion"].capitalize()

        if carrera_actual is not None: carreras_detectadas.append(carrera_actual)
        return carreras_detectadas
    except Exception as e: return []

# --- 2. VENTANA DE PRECIOS ---
def abrir_ventana_dividendos():
    global dividendos_memoria
    if not carrera_actual_data: messagebox.showwarning("Error", "Selecciona una carrera."); return
    caballos = carrera_actual_data.get("caballos", [])
    if not caballos: caballos = [{"numero": str(i), "nombre": "Competidor"} for i in range(1, 17)]

    ventana_div = tk.Toplevel(root); ventana_div.title(f"Cargar Pagos - {carrera_actual_data['id']}"); ventana_div.geometry("450x500"); ventana_div.configure(bg="#f0f0f0")
    tk.Label(ventana_div, text="CARGAR PAGOS A GANADOR", font=("bold", 12), bg="#f0f0f0", fg="#257E77").pack(pady=10)
    
    frame_scroll = tk.Frame(ventana_div); frame_scroll.pack(fill="both", expand=True, padx=10, pady=5)
    canvas = tk.Canvas(frame_scroll, bg="#f0f0f0"); scrollbar = tk.Scrollbar(frame_scroll, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#f0f0f0")
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")

    entradas_div = []
    for cab in caballos:
        num = cab["numero"]; nom = cab["nombre"]
        f = tk.Frame(scrollable_frame, bg="#f0f0f0"); f.pack(fill="x", pady=2)
        tk.Label(f, text=f"{num}", width=4, font=("bold", 11), bg="#ddd").pack(side="left")
        tk.Label(f, text=f"{nom[:20]}", width=20, font=("Segoe UI", 9), anchor="w").pack(side="left", padx=5)
        entry = tk.Entry(f, width=8, font=("bold", 10)); entry.pack(side="left")
        if num in dividendos_memoria: entry.insert(0, dividendos_memoria[num])
        entradas_div.append((num, entry))

    def guardar_en_memoria():
        global dividendos_memoria; dividendos_memoria = {}
        for num, entry in entradas_div:
            val = entry.get().strip()
            if val: dividendos_memoria[num] = val
        messagebox.showinfo("Guardado", f"Datos guardados en memoria."); ventana_div.destroy()

    tk.Button(ventana_div, text="💾 GUARDAR EN MEMORIA", command=guardar_en_memoria, bg="#27ae60", fg="white", font=("bold", 11), height=2).pack(fill="x", pady=10, padx=10)

# --- 3. VENTANA MARCADOR VIVO (CON NOMBRES AUTOMÁTICOS) ---
def abrir_ventana_marcador():
    ventana_mar = tk.Toplevel(root); ventana_mar.title("Marcador EN VIVO"); ventana_mar.geometry("300x350"); ventana_mar.configure(bg="#2c3e50")
    
    max_caballos = 16 
    lista_caballos_obj = [] # Aquí guardamos la info completa de los caballos
    
    if carrera_actual_data and carrera_actual_data.get("caballos"):
        lista_caballos_obj = carrera_actual_data["caballos"]
        max_caballos = len(lista_caballos_obj)

    tk.Label(ventana_mar, text="MARCADOR VIVO", font=("Segoe UI", 14, "bold"), bg="#2c3e50", fg="#f1c40f").pack(pady=5)
    tk.Label(ventana_mar, text=f"Carrera con {max_caballos} caballos", font=("Segoe UI", 10, "bold"), bg="#2c3e50", fg="#00ffcc").pack(pady=0)

    entradas_pos = []
    frame_grid = tk.Frame(ventana_mar, bg="#2c3e50"); frame_grid.pack(pady=10)

    for i in range(4):
        tk.Label(frame_grid, text=f"{i+1}°", font=("bold", 14), fg="white", bg="#2c3e50").grid(row=i, column=0, padx=10, pady=5)
        entry = tk.Entry(frame_grid, width=5, font=("bold", 16), justify="center"); entry.grid(row=i, column=1, padx=10, pady=5)
        entradas_pos.append(entry)

    def enviar_al_aire():
        datos_json = []
        errores = []

        for i, entry in enumerate(entradas_pos):
            num_mandil = entry.get().strip()
            if num_mandil:
                # 1. Validación de Rango
                solo_num_str = "".join(filter(str.isdigit, num_mandil))
                es_valido = False
                if solo_num_str:
                    # Usamos un rango seguro (hasta 25) por si las dudas con yuntas, pero validamos que sea numero
                    if 1 <= int(solo_num_str) <= 30: 
                        es_valido = True
                
                if not es_valido:
                    errores.append(f"Posición {i+1}: Número '{num_mandil}' inválido")
                    continue

                # 2. BÚSQUEDA DEL NOMBRE (La magia nueva)
                nombre_caballo = "COMPETIDOR" # Valor por defecto
                
                # Buscamos en la lista de la carrera actual
                for cab in lista_caballos_obj:
                    # Comparamos strings para que "1" sea igual a "1"
                    if str(cab["numero"]) == str(num_mandil):
                        nombre_caballo = cab["nombre"]
                        break
                
                # 3. Precio
                precio = dividendos_memoria.get(num_mandil, "")
                
                # 4. Empaquetamos todo
                datos_json.append({ 
                    "posicion": i+1, 
                    "numero": num_mandil, 
                    "nombre": nombre_caballo, # Campo nuevo
                    "dividendo": precio 
                })
        
        if errores:
            msg = "\n".join(errores)
            messagebox.showwarning("Error de Validación", f"No se envió nada:\n\n{msg}")
            return 

        with open(ARCHIVO_MARCADOR, "w", encoding="utf-8") as f: json.dump(datos_json, f)
        lbl_feed.config(text="✅ EN AIRE (Con Nombres)", fg="#2ecc71")

    def limpiar_pantalla():
        with open(ARCHIVO_MARCADOR, "w", encoding="utf-8") as f: json.dump([], f)
        for entry in entradas_pos: entry.delete(0, tk.END)
        lbl_feed.config(text="🗑️ OFF", fg="#e74c3c")

    tk.Button(ventana_mar, text="🚀 ACTUALIZAR TV", command=enviar_al_aire, bg="#f39c12", fg="white", font=("bold", 12), height=2).pack(fill="x", padx=20, pady=5)
    tk.Button(ventana_mar, text="APAGAR / LIMPIAR", command=limpiar_pantalla, bg="#7f8c8d", fg="white", font=("bold", 9)).pack(fill="x", padx=20, pady=5)
    lbl_feed = tk.Label(ventana_mar, text="...", bg="#2c3e50", fg="white", font=("bold", 10)); lbl_feed.pack(pady=5)

# --- 4. FUNCIONES PRINCIPALES ---
def cargar_excel():
    global carreras_cargadas
    archivo = filedialog.askopenfilename(filetypes=[("Archivos Excel", "*.xlsx *.xls *.csv")])
    if archivo:
        datos = analizar_excel(archivo)
        if datos:
            carreras_cargadas = datos
            lista_nombres = [c['id'] for c in carreras_cargadas]
            combo_selector['values'] = lista_nombres
            combo_selector.current(0)
            seleccionar_carrera_de_lista(None)
            lbl_status.config(text=f"✅ {len(datos)} carreras cargadas", fg="blue")
        else: messagebox.showwarning("Atención", "No se detectaron carreras.")

def seleccionar_carrera_de_lista(event):
    global carrera_actual_data, dividendos_memoria
    indice = combo_selector.current()
    if indice >= 0:
        carrera_actual_data = carreras_cargadas[indice]
        dividendos_memoria = {} 
        entry_num.delete(0, tk.END); entry_num.insert(0, carrera_actual_data['id'])
        entry_dist.delete(0, tk.END); entry_dist.insert(0, carrera_actual_data['distancia'])
        entry_premio.delete(0, tk.END); entry_premio.insert(0, carrera_actual_data.get('premio', ''))
        txt_condicion.delete("1.0", tk.END); txt_condicion.insert("1.0", carrera_actual_data.get('condicion', ''))

def guardar_datos():
    condicion_texto = txt_condicion.get("1.0", "end-1c").replace("\n", " ").strip()
    datos = { "num_carrera": entry_num.get(), "distancia": entry_dist.get(), "premio": entry_premio.get(), "condicion": condicion_texto, "estado_pista": combo_pista.get() }
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f: json.dump(datos, f, ensure_ascii=False, indent=4)
    lbl_status.config(text="✅ PLACA CARRERA ACTUALIZADA", fg="green")

# --- 5. INTERFAZ GRÁFICA ---
root = tk.Tk(); root.title("Controlador TV - Hipódromo Tucumán"); root.geometry("650x650"); root.configure(bg="#f0f0f0")
tk.Label(root, text="PANEL DE CONTROL VIVO", font=("Segoe UI", 16, "bold"), bg="#257E77", fg="white", pady=10).pack(fill="x")
frame_auto = tk.LabelFrame(root, text="Carga Automática", bg="#e8f6f3", padx=10, pady=10, font=("Segoe UI", 9, "bold")); frame_auto.pack(fill="x", padx=20, pady=10)
tk.Button(frame_auto, text="📂 CARGAR EXCEL", command=cargar_excel, bg="#2ecc71", fg="white").pack(side="left", padx=5)
combo_selector = ttk.Combobox(frame_auto, state="readonly", width=30); combo_selector.pack(side="left", padx=5); combo_selector.bind("<<ComboboxSelected>>", seleccionar_carrera_de_lista)
frame = tk.Frame(root, bg="#f0f0f0", padx=20, pady=5); frame.pack(fill="both", expand=True)
tk.Label(frame, text="N° Carrera:", bg="#f0f0f0").grid(row=0, column=0, sticky="w", pady=5); entry_num = tk.Entry(frame, font=("Segoe UI", 11), width=40); entry_num.grid(row=0, column=1, pady=5)
tk.Label(frame, text="Distancia:", bg="#f0f0f0").grid(row=1, column=0, sticky="w", pady=5); entry_dist = tk.Entry(frame, font=("Segoe UI", 11), width=40); entry_dist.grid(row=1, column=1, pady=5)
tk.Label(frame, text="Premio:", bg="#f0f0f0").grid(row=2, column=0, sticky="w", pady=5); entry_premio = tk.Entry(frame, font=("Segoe UI", 11), width=40); entry_premio.grid(row=2, column=1, pady=5)
tk.Label(frame, text="Condición:", bg="#f0f0f0").grid(row=3, column=0, sticky="nw", pady=5); frame_cond = tk.Frame(frame); frame_cond.grid(row=3, column=1, pady=5, sticky="w")
txt_condicion = tk.Text(frame_cond, font=("Segoe UI", 10), width=40, height=5, wrap="word"); txt_condicion.pack(side="left", fill="both"); scrollbar = tk.Scrollbar(frame_cond, command=txt_condicion.yview); scrollbar.pack(side="right", fill="y"); txt_condicion.config(yscrollcommand=scrollbar.set)
tk.Label(frame, text="Pista (VIVO):", bg="#f0f0f0", fg="#d35400", font=("bold")).grid(row=4, column=0, sticky="w", pady=5); combo_pista = ttk.Combobox(frame, values=["NORMAL", "HÚMEDA", "PESADA", "FANGOSA", "BARROSA"], state="readonly", font=("Segoe UI", 11), width=38); combo_pista.current(0); combo_pista.grid(row=4, column=1, pady=5)
btn_frame = tk.Frame(root, bg="#f0f0f0"); btn_frame.pack(fill="x", padx=20, pady=10)
btn_update = tk.Button(btn_frame, text="🔴 ENVIAR PLACA", command=guardar_datos, bg="#EF5B2B", fg="white", font=("Segoe UI", 12, "bold"), width=18); btn_update.pack(side="left", padx=5)
btn_div = tk.Button(btn_frame, text="1. CARGAR PAGOS", command=abrir_ventana_dividendos, bg="#3498db", fg="white", font=("bold", 10), width=15); btn_div.pack(side="left", padx=5)
btn_vivo = tk.Button(btn_frame, text="2. MARCADOR VIVO", command=abrir_ventana_marcador, bg="#8e44ad", fg="white", font=("bold", 10), width=15); btn_vivo.pack(side="left", padx=5)
lbl_status = tk.Label(root, text="Esperando...", bd=1, relief=tk.SUNKEN, anchor=tk.W); lbl_status.pack(side=tk.BOTTOM, fill=tk.X)
root.mainloop()