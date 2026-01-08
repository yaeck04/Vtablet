
import flet as ft
import json
import os
import random
import calendar
import io
import base64
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

# Constantes
ARCHIVO_JSON = "sorteos_unificados_con_fijos.json"
ARCHIVO_REGLAS = "reglas_color.json"
COLORES_PREDEFINIDOS = [
    "#FF5733", "#33FF57", "#3357FF", "#F333FF", "#FF33A1", 
    "#33FFF6", "#F6FF33", "#A833FF", "#FF8C33", "#33FF8C"
]

TURNOS_POR_STATE = {
    "FL": ["M", "E"],
    "GA": ["M", "E", "N"],
    "NY": ["M", "E"]
}

COL_DIA_WIDTH = 50
COL_TURNO_WIDTH = 60

class ReglaColor:
    def __init__(self, tipo, digito, color):
        self.tipo = tipo 
        self.digito = str(digito)
        self.color = color

class LoteriaApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Lotería App"
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.scroll = ft.ScrollMode.AUTO 
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 10
        
        self.datos = self.cargar_datos()
        
        self.reglas_colores = []
        self.datos_filtrados = []
        self.anio_seleccionado = None
        self.mes_seleccionado = None 
        self.state_seleccionado = None
        self.color_seleccionado_temp = None 
        
        # No necesitamos inicializar FilePicker aquí según el patrón de Flet 0.80.0
        self.dd_anio = None
        self.dd_mes = None
        self.dd_state = None
        self.dd_regla_tipo = None
        self.input_digito_container = None 
        self.lista_reglas_ui = None
        self.contenedor_vista_tabla = None
        
        # Cargar reglas persistentes al inicio
        self.cargar_reglas_persistentes()
        
        
        self.configurar_ui()
        self.actualizar_lista_reglas()
    
    def generar_datos_dummy(self):
        dummy_data = []
        estados = ["FL", "GA", "NY"]
        fecha_base = datetime(2026, 1, 1)
        fin_anio = datetime(2026, 12, 31)
        
        fecha_actual = fecha_base
        while fecha_actual <= fin_anio:
            for estado in estados:
                turnos = TURNOS_POR_STATE[estado]
                for turno in turnos:
                    nums = sorted([random.randint(0, 9) for _ in range(3)])
                    n1, n2, n3 = nums
                    fijo1 = f"{n1}{n2}"
                    fijo2 = f"{n2}{n3}" 
                    
                    dummy_data.append({
                        "date": fecha_actual.strftime("%d/%m/%y"),
                        "state": estado,
                        "draw": turno,
                        "numbers": f"{n1}-{n2}-{n3}",
                        "fijos": [fijo1, fijo2]
                    })
            fecha_actual += timedelta(days=1)
        
        with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f, indent=4)

    def cargar_datos(self):
        if not os.path.exists(ARCHIVO_JSON):
            self.generar_datos_dummy()
        with open(ARCHIVO_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # --- LÓGICA DE PERSISTENCIA ---
    def cargar_reglas_persistentes(self):
        if os.path.exists(ARCHIVO_REGLAS):
            try:
                with open(ARCHIVO_REGLAS, "r", encoding="utf-8") as f:
                    reglas_data = json.load(f)
                    for r in reglas_data:
                        self.reglas_colores.append(ReglaColor(r["tipo"], r["digito"], r["color"]))
                print(f"Reglas cargadas: {len(self.reglas_colores)}")
            except Exception as e:
                print(f"Error cargando reglas: {e}")

    def guardar_reglas_persistentes(self):
        try:
            reglas_data = []
            for r in self.reglas_colores:
                reglas_data.append({
                    "tipo": r.tipo,
                    "digito": r.digito,
                    "color": r.color
                })
            with open(ARCHIVO_REGLAS, "w", encoding="utf-8") as f:
                json.dump(reglas_data, f, indent=4)
            print(f"Reglas guardadas en {ARCHIVO_REGLAS}")
        except Exception as e:
            print(f"Error guardando reglas: {e}")

    def configurar_ui(self):
        self.page.appbar = ft.AppBar(
            title=ft.Text("Lotería Visualizador", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            center_title=True,
            bgcolor=ft.Colors.BLUE_800,
            actions=[ft.IconButton(ft.Icons.INFO, on_click=self.mostrar_ayuda, icon_color=ft.Colors.WHITE)]
        )
        
        # Filtros
        self.dd_anio = ft.Dropdown(label="Año", width=400, options=self.obtener_anios_opciones())
        opciones_mes = [ft.dropdown.Option("Todos", "Todos")] + [ft.dropdown.Option(str(i), calendar.month_name[i]) for i in range(1, 13)]
        self.dd_mes = ft.Dropdown(label="Mes", width=400, options=opciones_mes, value="Todos")
        self.dd_state = ft.Dropdown(
            label="Lotería",
            width=400,
            options=[
                ft.dropdown.Option("FL", "Florida"),
                ft.dropdown.Option("GA", "Georgia"),
                ft.dropdown.Option("NY", "New York")
            ]
        )
        
        # Reglas
        self.dd_regla_tipo = ft.Dropdown(
            label="Tipo Regla",
            width=400,
            options=[
                ft.dropdown.Option("decena", "Decena (1er dígito)"),
                ft.dropdown.Option("terminal", "Terminal (2º dígito)"),
                ft.dropdown.Option("completo", "Completo (Fijo exacto)")
            ],
            on_select=self.actualizar_input_regla
        )
        
        self.input_digito_container = ft.Container(
            width=400,
            content=ft.Dropdown(label="Dígito", options=[ft.dropdown.Option(str(i), str(i)) for i in range(10)])
        )

        self.lista_reglas_ui = ft.ListView(expand=True, spacing=5, item_extent=50)
        
        # Vista Tabla con Zoom
        self.contenedor_vista_tabla = ft.Column(
            scroll=ft.ScrollMode.AUTO, 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.START
        )

        # Layout General
        self.page.add(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # Sección Filtros (Columna para móviles)
                    ft.Container(
                        padding=10,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=10,
                        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.GREY_300),
                        width=600, 
                        content=ft.Column(controls=[
                            ft.Text("Filtros", size=16, weight=ft.FontWeight.BOLD),
                            ft.Column(
                                controls=[self.dd_anio, self.dd_mes, self.dd_state],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=10
                            ),
                            ft.Button("Generar Tabla", on_click=self.aplicar_filtros, expand=True, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE))
                        ])
                    ),
                    ft.Container(height=10),
                    
                    # Sección Reglas
                    ft.Container(
                        padding=10,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=10,
                        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.GREY_300),
                        width=600,
                        content=ft.Column(controls=[
                            ft.Text("Reglas de Color", size=16, weight=ft.FontWeight.BOLD),
                            self.dd_regla_tipo,
                            self.input_digito_container,
                            ft.Row(controls=[
                                ft.Button("Color Aleatorio", on_click=self.seleccionar_color, expand=True),
                                ft.Button("Agregar", on_click=self.agregar_regla, expand=True, bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE)
                            ]),
                            ft.Container(height=10),
                            ft.Text("Reglas Activas:", size=12, color=ft.Colors.GREY_600),
                            self.lista_reglas_ui
                        ])
                    ),
                    ft.Container(height=10),
                    
                    # Botones de Exportación
                    ft.Row(
                        wrap=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Button("Excel", icon=ft.Icons.TABLE_CHART, on_click=self.exportar_excel, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)),
                            ft.Container(width=10),
                            ft.Button("Imagen", icon=ft.Icons.IMAGE, on_click=self.exportar_imagen, style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE))
                        ]
                    ),
                    ft.Container(height=10),
                    
                    # Área de imagen
                    ft.Container(
                        padding=5,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=5,
                        content=self.contenedor_vista_tabla
                    )
                ]
            )
        )

    def actualizar_input_regla(self, e):
        tipo = e.control.value
        if tipo == "completo":
            self.input_digito_container.content = ft.TextField(
                label="Número (00-99)", 
                expand=True, 
                max_length=2, 
                keyboard_type=ft.KeyboardType.NUMBER
            )
        else:
            self.input_digito_container.content = ft.Dropdown(
                label="Dígito", 
                expand=True, 
                options=[ft.dropdown.Option(str(i), str(i)) for i in range(10)]
            )
        self.input_digito_container.update()

    def obtener_anios_opciones(self):
        anios = set()
        for sorteo in self.datos:
            try: fecha = datetime.strptime(sorteo["date"], "%d/%m/%y"); anios.add(fecha.year)
            except: continue
        return [ft.dropdown.Option(str(a), str(a)) for a in sorted(anios)]

    def aplicar_filtros(self, e):
        anio_val = self.dd_anio.value
        mes_val = self.dd_mes.value
        state_val = self.dd_state.value
        
        if not anio_val or not state_val:
            self.notificar("Selecciona Año y Lotería", ft.Colors.RED_500)
            return

        self.anio_seleccionado = int(anio_val)
        self.mes_seleccionado = None if mes_val == "Todos" else int(mes_val)
        self.state_seleccionado = state_val

        self.datos_filtrados = []
        for sorteo in self.datos:
            try:
                fecha = datetime.strptime(sorteo["date"], "%d/%m/%y")
                if fecha.year != self.anio_seleccionado: continue
                if self.mes_seleccionado is not None and fecha.month != self.mes_seleccionado: continue
                if sorteo["state"] == self.state_seleccionado: self.datos_filtrados.append(sorteo)
            except: continue
        
        self.renderizar_tabla_anual()
        self.notificar("Filtro aplicado correctamente", ft.Colors.GREEN_500)
    
    def renderizar_tabla_anual(self):
        self.contenedor_vista_tabla.controls.clear()
        pil_image = self._generar_imagen_tabla_logica()
        
        if not pil_image:
            return

        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)
        img_bytes = buffer.read()
        base64_string = base64.b64encode(img_bytes).decode("utf-8")
        
        data_uri = f"data:image/png;base64,{base64_string}"
        
        # ZOOM: InteractiveViewer
        viewer = ft.InteractiveViewer(
            min_scale=0.5,
            max_scale=5.0,
            content=ft.Image(
                src=data_uri,
                width=2000,
                fit="contain"
            )
        )
        
        titulo = ft.Text(f"Tabla {self.state_seleccionado} ({self.anio_seleccionado})", size=18, weight=ft.FontWeight.BOLD)
        
        self.contenedor_vista_tabla.controls.append(titulo)
        self.contenedor_vista_tabla.controls.append(ft.Container(height=10))
        self.contenedor_vista_tabla.controls.append(viewer)
        self.contenedor_vista_tabla.update()

    def _generar_imagen_tabla_logica(self):
        turnos_state = TURNOS_POR_STATE[self.state_seleccionado]
        meses = [self.mes_seleccionado] if self.mes_seleccionado else list(range(1, 13))
        
        datos_map = {}
        for d in range(1, 32):
            datos_map[d] = {}
            for m in meses:
                datos_map[d][m] = {}
                for t in turnos_state: datos_map[d][m][t] = None
        for s in self.datos_filtrados:
            f = datetime.strptime(s["date"], "%d/%m/%y")
            datos_map[f.day][f.month][s["draw"]] = s["fijos"][0]
            
        cell_w_turno = 45 
        cell_w_dia = 30
        cell_h = 35
        margin = 20
        
        total_width = margin + cell_w_dia + (len(meses) * len(turnos_state) * cell_w_turno) + margin
        total_height = margin + (2 * cell_h) + (32 * cell_h) + margin
        
        try:
            img = Image.new('RGB', (total_width, total_height), color='white')
            draw = ImageDraw.Draw(img)
            font_title = ImageFont.truetype("arial.ttf", 14)
            font_header = ImageFont.truetype("arial.ttf", 10)
            font_cell = ImageFont.truetype("arialbd.ttf", 16)
        except Exception as e:
            print(e)
            return None

        y = margin
        # Fila 1: Meses
        draw.rectangle([margin, y, margin+cell_w_dia, y+cell_h], fill='#4472C4', outline='black')
        draw.text((margin+cell_w_dia/2, y+cell_h/2), "Día", fill='white', font=font_header, anchor="mm")
        
        x = margin + cell_w_dia
        for mes in meses:
            w_mes = len(turnos_state) * cell_w_turno
            draw.rectangle([x, y, x+w_mes, y+cell_h], fill='#4472C4', outline='black')
            draw.text((x+w_mes/2, y+cell_h/2), calendar.month_name[mes].upper(), fill='white', font=font_header, anchor="mm")
            x += w_mes
        y += cell_h
        
        # Fila 2: Turnos
        draw.rectangle([margin, y, margin+cell_w_dia, y+cell_h], fill='#6085BF', outline='black')
        draw.text((margin+cell_w_dia/2, y+cell_h/2), "T", fill='white', font=font_header, anchor="mm")
        
        x = margin + cell_w_dia
        for mes in meses:
            for t in turnos_state:
                draw.rectangle([x, y, x+cell_w_turno, y+cell_h], fill='#6085BF', outline='black')
                draw.text((x+cell_w_turno/2, y+cell_h/2), t, fill='white', font=font_header, anchor="mm")
                x += cell_w_turno
        y += cell_h
        
        # Datos
        for dia in range(1, 32):
            x = margin
            draw.rectangle([x, y, x+cell_w_dia, y+cell_h], fill='#EEE', outline='black')
            draw.text((x+cell_w_dia/2, y+cell_h/2), str(dia), fill='black', font=font_title, anchor="mm")
            x += cell_w_dia
            
            for m in meses:
                for t in turnos_state:
                    fijo = datos_map[dia][m][t]
                    if fijo:
                        color = self.obtener_color_fijo(fijo) or 'white'
                        txt_col = 'black' if self.es_color_claro(color) else 'white'
                    else:
                        color = 'white'
                        txt_col = 'black'
                    
                    draw.rectangle([x, y, x+cell_w_turno, y+cell_h], fill=color, outline='black')
                    if fijo:
                        draw.text((x+cell_w_turno/2, y+cell_h/2), fijo, fill=txt_col, font=font_cell, anchor="mm")
                    x += cell_w_turno
            y += cell_h

        return img

    def obtener_color_fijo(self, fijo):
        if not fijo or len(fijo) < 2: return None
        regla_completa = next((r for r in self.reglas_colores if r.tipo == "completo" and r.digito == fijo), None)
        if regla_completa:
            return regla_completa.color
        
        decena, terminal = fijo[0], fijo[1]
        color_decena = next((r.color for r in self.reglas_colores if r.tipo == "decena" and r.digito == decena), None)
        color_terminal = next((r.color for r in self.reglas_colores if r.tipo == "terminal" and r.digito == terminal), None)
        
        if color_decena and color_terminal: return self.combinar_colores(color_decena, color_terminal)
        return color_decena or color_terminal
    
    def combinar_colores(self, color1, color2):
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        return f"#{(r1+r2)//2:02x}{(g1+g2)//2:02x}{(b1+b2)//2:02x}"
    
    def es_color_claro(self, color_str):
        if not color_str: return True
        cl = color_str.lower()
        if cl == 'white': return True
        if cl == 'black': return False
        if color_str.startswith("#"):
            try:
                r, g, b = int(color_str[1:3], 16), int(color_str[3:5], 16), int(color_str[5:7], 16)
                return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5
            except: return True
        return True

    def seleccionar_color(self, e):
        self.color_seleccionado_temp = random.choice(COLORES_PREDEFINIDOS)
        self.notificar(f"Color seleccionado: {self.color_seleccionado_temp}", self.color_seleccionado_temp)
    
    def agregar_regla(self, e):
        tipo = self.dd_regla_tipo.value
        input_control = self.input_digito_container.content
        digito_val = input_control.value if isinstance(input_control, ft.TextField) else input_control.value
            
        if not tipo or not digito_val or not hasattr(self, 'color_seleccionado_temp'):
            self.notificar("Completa Tipo, Dígito y Color", ft.Colors.RED_500); return
        
        if tipo == "completo" and len(digito_val) != 2:
             self.notificar("Fijo Completo debe ser 2 dígitos", ft.Colors.RED_500); return
             
        self.reglas_colores.append(ReglaColor(tipo, digito_val, self.color_seleccionado_temp))
        
        # PERSISTENCIA
        self.guardar_reglas_persistentes()
        
        self.actualizar_lista_reglas()
        self.renderizar_tabla_anual()
        self.notificar("Regla agregada correctamente", ft.Colors.GREEN_500)
    
    def actualizar_lista_reglas(self):
        self.lista_reglas_ui.controls.clear()
        for i, regla in enumerate(self.reglas_colores):
            tipo_txt = "Decena" if regla.tipo == "decena" else ("Terminal" if regla.tipo == "terminal" else "Completo")
            self.lista_reglas_ui.controls.append(
                ft.Container(
                    padding=5,
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=5,
                    content=ft.Row(controls=[
                        ft.Container(width=15, height=15, bgcolor=regla.color, border_radius=2),
                        ft.Text(f"{tipo_txt} {regla.digito}"),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED, on_click=lambda e, idx=i: self.eliminar_regla(idx))
                    ])
                )
            )
        self.lista_reglas_ui.update()
    
    def eliminar_regla(self, idx):
        if 0 <= idx < len(self.reglas_colores):
            del self.reglas_colores[idx]
            
            # PERSISTENCIA
            self.guardar_reglas_persistentes()
            
            self.actualizar_lista_reglas()
            self.renderizar_tabla_anual()

    # --- EXPORTACIONES CON ESTÁTICO FILE PICKER (FLET 0.80.0) ---

    async def exportar_excel(self, e):
        if not self.datos_filtrados: return
        
        # Uso estático de FilePicker según el ejemplo
        path = await ft.FilePicker().save_file(
            dialog_title="Guardar Excel",
            file_name=f"tabla_{self.state_seleccionado}_{self.anio_seleccionado}.xlsx"
        )
        
        if path:
            self._generar_y_guardar_excel(path)

    async def exportar_imagen(self, e):
        if not self.datos_filtrados: return
        
        # Uso estático de FilePicker según el ejemplo
        path = await ft.FilePicker().save_file(
            dialog_title="Guardar Imagen",
            file_name=f"tabla_{self.state_seleccionado}_{self.anio_seleccionado}.png"
        )
        
        if path:
            self._generar_y_guardar_imagen(path)

    def _generar_y_guardar_excel(self, path):
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Tabla Anual"
            
            turnos_state = TURNOS_POR_STATE[self.state_seleccionado]
            meses = [self.mes_seleccionado] if self.mes_seleccionado else list(range(1, 13))
            
            datos_map = {}
            for d in range(1, 32):
                datos_map[d] = {}
                for m in meses:
                    datos_map[d][m] = {}
                    for t in turnos_state: datos_map[d][m][t] = None
            for s in self.datos_filtrados:
                f = datetime.strptime(s["date"], "%d/%m/%y")
                datos_map[f.day][f.month][s["draw"]] = s["fijos"][0]
                
            col = 1
            ws.cell(row=1, column=col, value="Día").alignment = Alignment(horizontal="center", vertical="center")
            col += 1
            
            for mes in meses:
                start_col = col
                ws.cell(row=1, column=start_col, value=calendar.month_name[mes].upper()).alignment = Alignment(horizontal="center", vertical="center")
                end_col = col + len(turnos_state) - 1
                if start_col < end_col: ws.merge_cells(start_row=1, start_column=start_col, end_row=1, end_column=end_col)
                col = end_col + 1
                
            col = 1
            ws.cell(row=2, column=col, value="Turno").alignment = Alignment(horizontal="center")
            col += 1
            for mes in meses:
                for t in turnos_state:
                    ws.cell(row=2, column=col, value=t).alignment = Alignment(horizontal="center")
                    col += 1
                    
            fill_header = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            font_header = Font(bold=True, color="FFFFFF")
            for r in [1, 2]:
                for c in range(1, col):
                    ws.cell(row=r, column=c).fill = fill_header
                    ws.cell(row=r, column=c).font = font_header

            row_idx = 3
            for dia in range(1, 32):
                ws.cell(row=row_idx, column=1, value=str(dia)).alignment = Alignment(horizontal="center")
                col_idx = 2
                for m in meses:
                    for t in turnos_state:
                        fijo = datos_map[dia][m][t]
                        cell = ws.cell(row=row_idx, column=col_idx)
                        if fijo:
                            cell.value = fijo
                            color = self.obtener_color_fijo(fijo)
                            if color:
                                c_code = color[1:] if color.startswith("#") else color
                                try: cell.fill = PatternFill(start_color=c_code, end_color=c_code, fill_type="solid")
                                except: pass
                                if not self.es_color_claro(color): cell.font = Font(color="FFFFFF", bold=True)
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                        col_idx += 1
                row_idx += 1
            
            wb.save(path)
            self.notificar("Excel guardado exitosamente", ft.Colors.GREEN_500)
        except Exception as ex:
            print(f"Error: {ex}")
            self.notificar(f"Error al guardar Excel: {ex}", ft.Colors.RED_500)

    def _generar_y_guardar_imagen(self, path):
        try:
            pil_image = self._generar_imagen_tabla_logica()
            if pil_image:
                pil_image.save(path)
                self.notificar("Imagen guardada exitosamente", ft.Colors.GREEN_500)
            else:
                self.notificar("Error generando la imagen", ft.Colors.RED_500)
        except Exception as ex:
            print(f"Error: {ex}")
            self.notificar(f"Error al guardar Imagen: {ex}", ft.Colors.RED_500)

    def notificar(self, mensaje, color):
        self.page.show_dialog(ft.SnackBar(mensaje))
        #sb = ft.SnackBar(content=ft.Text(mensaje), bgcolor=color)
        #self.page.snack_bar = sb
        #self.page.snack_bar.open = True
        #self.page.update()
    
    def mostrar_ayuda(self, e):
        d = ft.AlertDialog(
            title=ft.Text("Ayuda"), 
            content=ft.Text("Usa dos dedos para hacer Zoom en la tabla.\nPara exportar, selecciona la carpeta Descargas en el diálogo."), 
            actions=[ft.TextButton("Cerrar", on_click=lambda _: self.close_dialog(d))]
        )
        #self.page.dialog = d
        self.page.show_dialog(d)
        #d.open = True
        #self.page.update()

    def close_dialog(self, d):
        d.open = False
        self.page.update()

def main(page: ft.Page):
    LoteriaApp(page)

ft.run(main)
