from flask import Flask, request, jsonify
from pybit.unified_trading import HTTP
import time
import sys
import math

# Configuración de la sesión para demo trading
session = HTTP(
    api_key="86GxUJS1f3XuVhwsR2",
    api_secret="ELMT4U9gt9lXZwLlZA0IqIyHYkVGm1nd31yM",
    demo=True,
    recv_window=10000
)

app = Flask(__name__)

#-------------------------INICIO DE LAS VARIABLES-------------------------#

#-------------------------Parametros Ajustables al deseo del usuario-------------------------#

TickATrabajar = "BTCUSDT" #Valor por default es bitcoin 
take_profit_distancia = float("0.4")# 0.4 es mas el 0.4%
stop_loss_distancia = float("5")# 5 es menos el 5%


#-------------------------Variables de la posicion-------------------------#

PrecioDeEntradaEnLaPosicion = 0
MonedasEnLaPosicion = 0
DireccionDeLaPosicion = "None"

#-------------------------Variables de la cuenta-------------------------#

CapitalDeLaCuenta = 0
CapitalDispuestoAPerder = 0
ApalancamientoDeLaCuenta = 20
PorcentajePerdidaMaxima = 0

#-------------------------Variables globales-------------------------#

EstadoCompraRecompra = 0  # si se establece como 0 es primera compra y si se establece como 1 es recompra.
RecomprasDisponibles = 3 # El valor de 3 son 1 entrada y 2 recompras           esto se movera mas adelante a variables de la cuenta 
RecomprasEjecutadas = 0
MonedasMinimasDelTick = 0.001 #Valor por default para bitcoin 
PrecioDelActivoParaElCalculo = 0
direccion_longshort_señal = None

#-------------------------FIN DE LAS VARIABLES-------------------------#


#-------------------------FUNCIONES INICIALES--------------------------#


def PreguntarParametros():
    global TickATrabajar, take_profit_distancia, stop_loss_distancia
    # Preguntar al usuario si quiere ingresar sus propios parámetros
    respuesta = input("¿Quieres ingresar nuevos parámetros? Escribe '1' para sí, cualquier otro valor para usar los predeterminados (BTC): ")

    if respuesta == '1':
        # Solicitar los 3 parámetros al usuario
        tick_seleccionado = input("Ingresa el ticker (por ejemplo, BTCUSDT): ")
        
        # Solicitar y convertir a float el take profit y stop loss
        try:
            tp_distancia_seleccionada = float(input("Ingresa la distancia de take profit (por ejemplo, 0.4 para 0.4% más): "))
            sl_distancia_seleccionada = float(input("Ingresa la distancia de stop loss (por ejemplo, 5 para 5% menos): "))
        except ValueError:
            print("Error: Debes ingresar números válidos para take profit y stop loss.")
            return

        # Mostrar los parámetros ingresados
        print(f"Parámetros ingresados: {tick_seleccionado}, TP distancia: {tp_distancia_seleccionada}, SL distancia: {sl_distancia_seleccionada}")
        
        # Asignar los valores ingresados a las variables globales
        TickATrabajar = tick_seleccionado
        take_profit_distancia = tp_distancia_seleccionada
        stop_loss_distancia = sl_distancia_seleccionada
    else:
        # Usar los parámetros por defecto
        tick_default = "BTCUSDT"
        tp_distancia_default = 0.4
        sl_distancia_default = 5
        
        print(f"Usando parámetros por defecto: {tick_default}, TP distancia: {tp_distancia_default}, SL distancia: {sl_distancia_default}")
        TickATrabajar = tick_default
        take_profit_distancia = tp_distancia_default
        stop_loss_distancia = sl_distancia_default


def VerificarSiExistenPosicionesaliniciar():
    global MonedasEnLaPosicion, PrecioDeEntradaEnLaPosicion, RecomprasEjecutadas, TickATrabajar, PrecioDelActivoParaElCalculo, DireccionDeLaPosicion

    try:
        response = session.get_positions(
            category="linear",
            symbol=TickATrabajar
        )
        positions = response.get('result', {}).get('list', [])
        if positions:
            for position in positions:
                size = float(position.get('size', 0))  # Convertir size a float
                PrecioDelActivoParaElCalculo = float(position.get('markPrice'))
                PrecioDeEntradaEnLaPosicion = float(position.get('avgPrice'))
                DireccionDeLaPosicion = str(position.get('side'))
                if size > 0:
                    MonedasEnLaPosicion = size
                    ajustar_recompras_segun_monedas_en_posicion(size)
                    print(f"Hay una posicion abierta al iniciar...Por favor este atento a su posicion y establezca manualmente su TakeProffit y StopLoss o espere a una señal.")
                    print(f"Precio Entrada: {PrecioDeEntradaEnLaPosicion}")
                    print(f"posiciones Actuales: {RecomprasEjecutadas}")
                    print(f"Monedas en Posición: {MonedasEnLaPosicion}")
                    if DireccionDeLaPosicion == "Buy":
                        print("Direccion de la posicion: Long")
                    elif DireccionDeLaPosicion == "Sell":
                        print("Direccion de la posicion: Short")
                    else:
                        break

                    break
                else:
                    
                    PrecioDelActivoParaElCalculo = float(position.get('markPrice'))
                    print(f"NO HAY POSICION ABIERTA  en el tick {TickATrabajar} AL INICIAR EL BOT.")
    except Exception as e:
        print(f"Error al actualizar la posición: {e}")

def Calculo_riesgo_atomar():
    
    # Solicita al usuario el porcentaje de riesgo y el apalancamiento
    porcentajeaarriesgar = float(input("Ingrese el porcentaje de riesgo (ejemplo: 12 para 12%): "))
    global PorcentajePerdidaMaxima, PrecioDelActivoParaElCalculo, capita
    PorcentajePerdidaMaxima = porcentajeaarriesgar

    #ApalancamientoStatic = float(input("Ingrese el apalancamiento (ejemplo: 20): "))
    ApalancamientoDeLaCuenta = 20
    
    global MonedasMinimasDelTick
    MonedasMinimasDelTick = obtener_Cantidad_Minima_De_Compra(TickATrabajar)
    cantidad_minima = float(MonedasMinimasDelTick)

    CapitalDisponible = float(obtener_valor_cuenta())
    global CapitalDeLaCuenta
    CapitalDeLaCuenta = CapitalDisponible
    
    print(f"Capital de la cuenta conectada: {CapitalDeLaCuenta}$ USDT")

    PrecioDelActivo = PrecioDelActivoParaElCalculo

    MontoTotalArriesgado = float((CapitalDisponible * porcentajeaarriesgar) / 100)
    CapitalDispuestoAPerder = MontoTotalArriesgado
    print("Monto total dispuesto a perder: " + str(MontoTotalArriesgado) + "$ USDT")

    VolumenMonedasMaximas = float((ApalancamientoDeLaCuenta * MontoTotalArriesgado) / PrecioDelActivo)
    print("Volumen final previsto: " + str(VolumenMonedasMaximas) + " Del Capital Total disponible: " + str(CapitalDispuestoAPerder))
    

    cantidad_total = VolumenMonedasMaximas
    recompras = 0

    # Calcular el número de recompras posibles
    while cantidad_total >= cantidad_minima:
        recompras += 1
        cantidad_total -= cantidad_minima
        cantidad_minima *= 2  # La siguiente recompra duplica la cantidad
    
    global RecomprasDisponibles
    RecomprasDisponibles = recompras + 1
    print(f"Número máximo de recompras actualizado a: {RecomprasDisponibles}")

    # Preguntar si el usuario desea continuar con la siguiente aplicación
    continuar = input("¿Está seguro de que desea continuar con la siguiente aplicación? (Si (Presione cualquier tecla (que no sea 2) y enter) / no(2)): ")

    if continuar == '2':
       print("Proceso cancelado.")
       sys.exit()  # Esto terminará el script
    else:
       # Continuar con el resto del código si la respuesta no es '2'
       pass

#-------------------------FUNCIONES DE PRODUCCION--------------------------#
#------------------------INICIO DEL TRABAJO DEL WEBHOOK-----------------------#


# Webhook para recibir alertas de TradingView
@app.route('/webhook', methods=['POST'])
def webhook():
    print("Señal recibida")
    datos = request.data.decode('utf-8')  # Extraer el texto recibido en la solicitud

    if datos:
        # Dividir los datos recibidos para obtener el precio, ticker, y el valor adicional
        partes = datos.split()

        # Verificar que haya al menos 3 partes en los datos recibidos
        if len(partes) < 3:
            return jsonify({'mensaje': 'Faltan datos en la solicitud'}), 400

        # Extraer el precio (primera parte de la cadena)
        precio_str = partes[0]
        try:
            precio = float(precio_str) 
        except ValueError:
            return jsonify({'mensaje': 'El precio no es válido'}), 400

        # Extraer el símbolo (segunda parte de la cadena), eliminar "BYBIT:" y ".P"
        ticker = partes[1].replace('BYBIT:', '').replace('BINANCE:', '').replace('.P', '')

        # Extraer el valor adicional (tercera parte de la cadena), convertirlo en entero
        try:
            valor_direccion = int(partes[2])
            if valor_direccion not in [0, 1]:
                return jsonify({'mensaje': 'El valor adicional debe ser 0 o 1'}), 400 
        except ValueError:
            return jsonify({'mensaje': 'El valor adicional no es válido'}), 400

        # Procesar la señal con el precio, el ticker y el valor adicional
        procesar_senal(precio, ticker, valor_direccion)

        return jsonify({'mensaje': 'Alerta recibida', 'precio': precio, 'ticker': ticker, 'compra o venta': valor_direccion}), 200
    return jsonify({'mensaje': 'Sin datos'}), 400

# Procesar la señal recibida del webhook
def procesar_senal(precio_recibido, tick, direccion):
    print("procesando datos " + str(precio_recibido), str(tick), str(direccion))
    global DireccionDeLaPosicion, direccion_longshort_señal
    direccion_texto = None 
    if direccion == 1:
        direccion_texto = "Buy"
    elif direccion == 0:
        direccion_texto = "Sell"
    else:
        print("faltan datos para procesar la señal crack")
        return  # Salir de la función si la dirección no es válida
    if direccion == 1:
        direccion_longshort_señal = "Long"
    elif direccion == 0:
        direccion_longshort_señal = "Short"
    else:
        return
    print(f"Señal recibida: {precio_recibido} en el tick {tick} en la direccion {direccion_longshort_señal}" )
    MonedasMinimasDelTick = obtener_Cantidad_Minima_De_Compra(tick)
    TickATrabajar = tick
    if DireccionDeLaPosicion == direccion_texto:
        enviar_orden_al_exchange(precio_recibido, tick, direccion_texto)
    elif DireccionDeLaPosicion == "":
        enviar_orden_al_exchange(precio_recibido, tick, direccion_texto)
    else:
        print("No se puede ejecutar una posicion contraria a la posicion existente porque cerraria la posicion de inmediato mientras este el modo de una sola dirección")


#------------------------FIN DEL TRABAJO DEL WEBHOOK-----------------------#

#------------------------INICIO FUNCIONES CON EL EXCHANGE-------------------------#
 
def enviar_orden_al_exchange(PRECIOACOMPRAR, TICK, DIRECCION): #EJEMPLO 59000, BTCUSDT, Buy o Sell
    global RecomprasDisponibles, RecomprasEjecutadas, PrecioDeEntradaEnLaPosicion, MonedasEnLaPosicion, MonedasMinimasDelTick

    try:
        if DIRECCION == "Buy":
            direccion_long_short = "Long"
        elif DIRECCION == "Sell":
            direccion_long_short = "Short"
        
        
        print("Enviando orden de compra al precio: "+ str(PRECIOACOMPRAR) + " con direccion: " + direccion_long_short + " en la moneda " + TICK) 
        #COMPRA INICIAL
        if RecomprasEjecutadas <= 0 :
            response = session.place_order(
                category="linear",        # La categoría del mercado: linear, option, etc.
                symbol=TICK,         # El ticker del contrato
                side=DIRECCION,               # Lado de la orden: Buy o Sell
                orderType="Limit",        # Tipo de orden: Limit
                qty=MonedasMinimasDelTick,             # Cantidad de la orden
                price=PRECIOACOMPRAR,              # Precio recibido desde TradingView
                timeInForce="GTC",
            )
            order_id_compra = response['result']['orderId']
            verificar_estado_orden(order_id_compra, TICK)
        #RECOMPRA
        elif RecomprasEjecutadas > 0 and RecomprasEjecutadas < RecomprasDisponibles and PRECIOACOMPRAR < PrecioDeEntradaEnLaPosicion:
            response = session.place_order(
                category="linear",        # La categoría del mercado: linear, option, etc.
                symbol=TICK,         # El ticker del contrato
                side=DIRECCION,               # Lado de la orden: Buy o Sell
                orderType="Limit",        # Tipo de orden: Limit
                qty=str(MonedasEnLaPosicion),             # Cantidad de la orden
                price=PRECIOACOMPRAR,              # Precio recibido desde TradingView
                timeInForce="GTC",
            )
            order_id_recompra = response['result']['orderId']
            verificar_estado_orden(order_id_recompra, TICK)
        
        #Recompras agotadas
        elif RecomprasEjecutadas == RecomprasDisponibles:
            print("No se procesara la orden porque las recompras ya estan agotadas.")
        
        #Recompras excedidas
        elif RecomprasEjecutadas > RecomprasDisponibles:
            print("No se procesara la orden porque las recompras fueron agotadas y excedidas.")
    
        else:
            print("No se pudo colocar la orden de compra porque la nueva señal tiene un precio más alto que el precio de entrada que ya se tiene.")
    except Exception as e:
        print(f"Error al enviar la orden: {e}")
    
 
def verificar_estado_orden(id_de_la_orden, tick):
    global RecomprasEjecutadas
    tickrecibido = tick
    while True:
        try:
            response = session.get_open_orders(
                category="linear",
                symbol=tickrecibido,
                orderId=id_de_la_orden
            )

            orders = response['result']['list']
            order_found = False

            for order in orders:
                if order['orderId'] == id_de_la_orden:
                    order_status = order['orderStatus']
                    if order_status in ['Filled', 'Partially Filled']:
                        print(f"Orden completada o parcialmente completada. Estado: {order_status}")
                        #ajustar las variables con la funcion correspondiente despues de que entre una orden de manera completa
                        RecomprasEjecutadas += 1
                        time.sleep(2)
                        obtener_posicion_y_actualizar_datos()
                        return  # Salir de la función si la orden está completada

                    elif order_status == 'Cancelled':
                        print(f"Orden cancelada. Estado: {order_status}")
                        return

                    order_found = True

            if not order_found:
                print("Orden no encontrada en la respuesta.")

            time.sleep(10)

        except Exception as e:
            print(f"Error al consultar el estado de la orden: {e}")
 
def obtener_posicion_y_actualizar_datos():
    global MonedasEnLaPosicion, PrecioDeEntradaEnLaPosicion, RecomprasEjecutadas, TickATrabajar, DireccionDeLaPosicion

    try:
        response = session.get_positions(
            category="linear",
            symbol=TickATrabajar
        )
        positions = response.get('result', {}).get('list', [])
        if positions:
            for position in positions:
                size = float(position.get('size', 0))  # Convertir size a float
                if size > 0:
                    MonedasEnLaPosicion = size
                    PrecioDeEntradaEnLaPosicion = float(position.get('avgPrice'))  # Convertir avgPrice a float
                    DireccionDeLaPosicion = str(position.get('side'))
                    print(f"Compra/Recompra realizada.")
                    print(f"Precio Entrada: {PrecioDeEntradaEnLaPosicion}")
                    print(f"posiciones Actuales: {RecomprasEjecutadas}")
                    print(f"Monedas en Posición: {MonedasEnLaPosicion}")

                    cancelar_ordenes_existentes()
                    time.sleep(2)
                    establecer_take_profit_y_stop_loss()

                    break
                else:
                    print("NO HAY MONEDAS EN LA POSICION O DIRECTAMENTE NO HAY POSICION.")
    except Exception as e:
        print(f"Error al actualizar la posición: {e}")

 
def establecer_take_profit_y_stop_loss():
    global take_profit_distancia, stop_loss_distancia, PrecioDeEntradaEnLaPosicion, MonedasEnLaPosicion, TickATrabajar, DireccionDeLaPosicion

    #mensajes
    tp = take_profit_distancia
    sl = stop_loss_distancia
    (f"Estableciendo Take Profit en {tp}% y Stop Loss en {sl}%...")
    #calculo
    if DireccionDeLaPosicion == "Buy":
        take_profit_precio = PrecioDeEntradaEnLaPosicion + (take_profit_distancia / 100 * PrecioDeEntradaEnLaPosicion)
        stop_loss_precio = PrecioDeEntradaEnLaPosicion - (stop_loss_distancia / 100 * PrecioDeEntradaEnLaPosicion)
        direccioncontraria = "Sell"
    elif DireccionDeLaPosicion == "Sell":
        take_profit_precio = PrecioDeEntradaEnLaPosicion - (take_profit_distancia / 100 * PrecioDeEntradaEnLaPosicion)
        stop_loss_precio = PrecioDeEntradaEnLaPosicion + (stop_loss_distancia / 100 * PrecioDeEntradaEnLaPosicion)
        direccioncontraria = "Buy"
    else:
        print("Faltan datos para calcular el tp y el stoploss")
        return
    #ordenes

    # Colocar el Take Profit en la posición existente
    response_tp = session.place_order(
        category="linear",
        symbol=TickATrabajar,
        side=direccioncontraria,  # Cierra la posición (lado opuesto)
        orderType="Limit",
        qty=MonedasEnLaPosicion,
        price=str(take_profit_precio),
        timeInForce="GTC"
    )
    print(f"TP establecido en {take_profit_precio} para {TickATrabajar}.")

    # Establecer el SL para la posición completa
    response = session.set_trading_stop(
        category="linear",
        symbol=TickATrabajar,
        stopLoss=str(stop_loss_precio),
        slTriggerBy="LastPrice",
        tpslMode="Full",
        positionIdx=0
    )
    print(f"SL establecido en {stop_loss_precio} para {TickATrabajar}.")

    vigilar_posicion()
 
def vigilar_posicion():
    global TickATrabajar, MonedasEnLaPosicion, RecomprasEjecutadas, PrecioDeEntradaEnLaPosicion, DireccionDeLaPosicion, CapitalDeLaCuenta
    print(f"Vigilando la posición...")
    
    while True:
        try:
            # Obtener las posiciones actuales
            response = session.get_positions(
                category="linear",  # La categoría del mercado: linear, option, etc.
                symbol=TickATrabajar    # El ticker del contrato
            )
            
            positions = response.get('result', {}).get('list', [])
            
            if positions:
                position_found = False
                for position in positions:
                    size = float(position.get('size', 0))  # Convertir size a float
                    if size > 0:
                        position_found = True
                        break
                
                if position_found:
                    # Esperar 10 segundos y volver a revisar si la posición sigue abierta
                    if size != MonedasEnLaPosicion:
                        ajustar_recompras_segun_monedas_en_posicion(size)
                        obtener_posicion_y_actualizar_datos()
                        break
                    else:
                        time.sleep(10)
                else:
                    # Si no hay posiciones abiertas, TP o SL ha sido alcanzado
                    print("TP o SL tomado, reiniciando valores y cancelando ordenes para evitar conflictos con las posiciones futuras...") 
                    calcular_ganancia_perdida()
                    cancelar_ordenes_existentes()
                    MonedasEnLaPosicion = 0
                    RecomprasEjecutadas = 0
                    PrecioDeEntradaEnLaPosicion = 0
                    break  # Salir del bucle

            else:
                # No se encontraron posiciones
                print("No se encontraron posiciones, TP o SL tomado.")
                MonedasEnLaPosicion = 0
                RecomprasEjecutadas = 0
                PrecioDeEntradaEnLaPosicion = 0
                DireccionDeLaPosicion = "None"
                CapitalDeLaCuenta = obtener_valor_cuenta()
                recalcular_recompras()
                break  # Salir del bucle

        except Exception as e:
            print(f"Error al vigilar la posición: {e}")
            time.sleep(10)  # Espera antes de volver a intentar en caso de error





#-------------------------FUNCIONES AUXILIARES--------------------------#   AUN NO ESTAN EN FUNCIONAMIENTO CRACK, PURO VALOR A MANO, NO EL AUTODELICIOSO, MANUAL EL CAMBIO DE DATOS, ESTAMOS EN SEPTIEMPRE DE NOFAP COCHINO

def obtener_valor_cuenta():
    # Solicitar el balance de la billetera
    response = session.get_wallet_balance(accountType="UNIFIED")

    # sacar y mostrar el totalMarginBalance
    if response['retCode'] == 0:  # exito
       total_margin_balance = response['result']['list'][0]['totalWalletBalance']
       return total_margin_balance
    else:
       print("Error al obtener el balance:", response['retMsg'])

def obtener_Cantidad_Minima_De_Compra(tick_a_investigar):
    global PrecioDelActivoParaElCalculo, ApalancamientoDeLaCuenta
    # Solicitar la configuración del mercado para BTC derivados
    response = session.get_instruments_info(category="linear", symbol=tick_a_investigar)

    # Extraer y mostrar el tamaño mínimo de la orden
    if response['retCode'] == 0:  # Asegúrate de que la solicitud fue exitosa
        # Accede al valor mínimo de la orden
        min_order_size = float(response['result']['list'][0]['lotSizeFilter']['minOrderQty'])  # Convertir a float

        if PrecioDelActivoParaElCalculo < 5 and tick_a_investigar != "BTCUSDT":
            # Si el precio es menor que 5 y no es BTCUSDT
            return min_order_size
        elif PrecioDelActivoParaElCalculo >= 5 and tick_a_investigar != "BTCUSDT":
            # Multiplicar min_order_size por PrecioDelActivoParaElCalculo
            resultado = min_order_size * PrecioDelActivoParaElCalculo

            # Dividir 5 por el resultado anterior
            resultado_division = 5 / resultado

            # Redondear hacia arriba
            resultado_redondeado = math.ceil(resultado_division)
            # Multiplicar el resultado redondeado por min_order_size
            cantidad_final = resultado_redondeado * min_order_size

            # Redondear a 1 decimal para evitar el problema de precisión flotante
            cantidad_final = round(cantidad_final, 1)

            print(f"La cantidad mínima ajustada para el activo es: {cantidad_final}")
            return cantidad_final
        elif tick_a_investigar == "BTCUSDT":
            return min_order_size
    else:
        print("Error al obtener la configuración del mercado:", response['retMsg'])


def cancelar_ordenes_existentes():
    global TickATrabajar
    try:
        # Obtener las órdenes activas para el ticker
        response_orders = session.get_open_orders(
            category="linear",
            symbol = TickATrabajar
        )
        
        # Procesar la respuesta y cancelar cada orden
        orders = response_orders.get('result', {}).get('list', [])
        if orders:
            for order in orders:
                order_id = order.get('orderId')
                if order_id:
                    response_cancel = session.cancel_order(
                        category="linear",
                        symbol=TickATrabajar,
                        orderId=order_id
                    )
                    print(f"Orden con ID {order_id} cancelada.")
        else:
            print("No había órdenes existentes.")
    
    except Exception as e:
        print(f"Error al cancelar las órdenes existentes: {e}")

def calcular_ganancia_perdida():
    global CapitalDeLaCuenta
    nuevaCantidadDeLaCuenta = float(obtener_valor_cuenta())
    viejaCantidadDeLaCuenta = float(CapitalDeLaCuenta)
    Ganancia_Perdida = nuevaCantidadDeLaCuenta - viejaCantidadDeLaCuenta
    Ganancia_Perdida_Porcentaje = (Ganancia_Perdida / viejaCantidadDeLaCuenta) * 100
    if nuevaCantidadDeLaCuenta <= viejaCantidadDeLaCuenta:
        return print("Nuevo valor de la cuenta: " + str(nuevaCantidadDeLaCuenta) + "$ Anterior valor de la cuenta: " + str(viejaCantidadDeLaCuenta) + "$ Perdida de: " + str(Ganancia_Perdida) + "$ Porcentaje: " + str(Ganancia_Perdida_Porcentaje) + "%")
    elif nuevaCantidadDeLaCuenta >= viejaCantidadDeLaCuenta:
        return print("Nuevo valor de la cuenta: " + str(nuevaCantidadDeLaCuenta) + "$ Anterior valor de la cuenta: " + str(viejaCantidadDeLaCuenta) + "$ Ganancia de: " + str(Ganancia_Perdida) + "$ Porcentaje: " + str(Ganancia_Perdida_Porcentaje) + "%")
    else:
        return print("NO SE PUDO CALCULAR EL VALOR DE LA GANANCIA PERDIDA")


def recalcular_recompras():
    global MonedasMinimasDelTick, CapitalDeLaCuenta, PorcentajePerdidaMaxima, RecomprasDisponibles, ApalancamientoDeLaCuenta, PrecioDelActivoParaElCalculo

    MontoTotalArriesgado = float((CapitalDeLaCuenta * PorcentajePerdidaMaxima) / 100)

    VolumenMonedasMaximas = float((ApalancamientoDeLaCuenta * MontoTotalArriesgado) / PrecioDelActivoParaElCalculo)
    
    recompras = 0

    # Calcular el número de recompras posibles
    while VolumenMonedasMaximas >= MonedasMinimasDelTick:
        recompras += 1
        VolumenMonedasMaximas -= MonedasMinimasDelTick
        MonedasMinimasDelTick *= 2
    
    global RecomprasDisponibles
    RecomprasDisponibles = recompras + 1
    print(f"Numero máximo de recompras actualizado a: {RecomprasDisponibles}")
        
def ajustar_recompras_segun_monedas_en_posicion(cantidad):
    global RecomprasEjecutadas, MonedasMinimasDelTick
    if cantidad == float(MonedasMinimasDelTick):
        RecomprasEjecutadas = 1
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad == float(MonedasMinimasDelTick) * 2:
        RecomprasEjecutadas = 2
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 4:
        RecomprasEjecutadas = 3
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 8:
        RecomprasEjecutadas = 4
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 16:
        RecomprasEjecutadas = 5
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 32:
        RecomprasEjecutadas = 6
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 64:
        RecomprasEjecutadas = 7
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    elif cantidad >= float(MonedasMinimasDelTick) * 128:
        RecomprasEjecutadas = 8
        print("RECOMPRAS EJECUTADAS: " + str(RecomprasEjecutadas) + " RECOMPRAS MAXIMAS: " + str(RecomprasDisponibles) + " RECOMPRAS RESTANTES: " + str((RecomprasDisponibles - RecomprasEjecutadas)))
    else: 
        print("faltan datos para reajustar las recompras ejecutadas")



if __name__ == '__main__':
    PreguntarParametros()
    VerificarSiExistenPosicionesaliniciar()
    Calculo_riesgo_atomar()
    app.run(host='0.0.0.0', port=80)
