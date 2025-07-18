from encodings.utf_8 import getregentry
from functools import reduce
from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj
import json, sys
from datetime import datetime, timedelta, time as time_obj # Import time_obj for comparison
from catalogador import catag
from tabulate import tabulate
from colorama import init, Fore, Back, Style
from threading import Thread
from iqoptionapi.constants  import ACTIVES
import numpy as np
import pandas as pd # Import pandas for ATR and ADX calculation

# Função para calcular MACD
def calcular_macd(velas, fast_period=12, slow_period=26, signal_period=9):
    df = pd.DataFrame(velas)
    df["close"] = df["close"].astype(float)

    ema_fast = df["close"].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow_period, adjust=False).mean()

    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    histogram = macd - signal

    return macd.iloc[-1], signal.iloc[-1], histogram.iloc[-1]

# Função para calcular Bandas de Bollinger
def calcular_bollinger_bands(velas, periodo=20, desvios=2):
    df = pd.DataFrame(velas)
    df["close"] = df["close"].astype(float)

    sma = df["close"].rolling(window=periodo).mean()
    std = df["close"].rolling(window=periodo).std()

    upper_band = sma + (std * desvios)
    lower_band = sma - (std * desvios)

    return upper_band.iloc[-1], sma.iloc[-1], lower_band.iloc[-1]

init(autoreset=True)
green  = Fore.GREEN
yellow = Fore.YELLOW
blue = Fore.BLUE
red = Fore.RED
white = Fore.WHITE

# Substituindo a arte ASCII "LUCAS CODE" por "_WALISON"
print(green +'''
    __    _       __    ____  _       ____  _____   _____
   / /   | |     / /   / __ \| |     / __ \/ ___/  / ___/
  / /    | | /| / /   / / / /| | /| / / / /\__ \  / __ \ 
 / /___  | |/ |/ /   / /_/ / | |/ |/ / /_/ /__/ / / /_/ /
/_____/  |__/|__/   /_____/  |__/|__/\____/____/  \____/ 
                                                          
''' + yellow+'''

                           WALISON M
                           DEUS NOS ABENÇOE

''')

print(green + '*****************************************************************************************')

config = ConfigObj()


### CRIANDO ARQUIVO DE CONFIGURAÇÃO ####
config = ConfigObj('config.txt')
email = config['LOGIN']['email']
senha = config['LOGIN']['senha']
tipo = config['AJUSTES']['tipo']
valor_entrada = float(config['AJUSTES']['valor_entrada'])
stop_win = float(config['AJUSTES']['stop_win'])
stop_loss = float(config['AJUSTES']['stop_loss'])
pay_minimo = float(config['AJUSTES']['pay_minimo'])

# Parâmetros ATR
try:
    usar_filtro_atr = config['AJUSTES']['usar_filtro_atr'].upper() == 'S'
    periodo_atr = int(config['AJUSTES']['periodo_atr'])
    multiplicador_atr_min = float(config['AJUSTES']['multiplicador_atr_min'])
    multiplicador_atr_max = float(config['AJUSTES']['multiplicador_atr_max'])
except:
    print(yellow + "Aviso: Parâmetros ATR não encontrados em config.txt. Usando valores padrão.")
    usar_filtro_atr = True 
    periodo_atr = 14
    multiplicador_atr_min = 0.8 
    multiplicador_atr_max = 2.0 

# Parâmetros Filtro de Horário
try:
    usar_filtro_horario = config['AJUSTES']['usar_filtro_horario'].upper() == 'S'
    horarios_bloqueados_str = config['AJUSTES']['horarios_bloqueados']
    # Processar os horários bloqueados
    horarios_bloqueados = []
    if usar_filtro_horario and horarios_bloqueados_str:
        intervalos = horarios_bloqueados_str.split(',')
        for intervalo in intervalos:
            try:
                inicio_str, fim_str = intervalo.strip().split('-')
                inicio_h, inicio_m = map(int, inicio_str.split(':'))
                fim_h, fim_m = map(int, fim_str.split(':'))
                horarios_bloqueados.append((time_obj(inicio_h, inicio_m), time_obj(fim_h, fim_m)))
            except ValueError:
                print(red + f"Erro ao processar intervalo de horário bloqueado: '{intervalo}'. Verifique o formato HH:MM-HH:MM em config.txt.")
                usar_filtro_horario = False # Desativa o filtro se houver erro
                break
except Exception as e:
    print(yellow + f"Aviso: Parâmetros de Filtro de Horário não encontrados ou inválidos em config.txt ({e}). Usando valores padrão (desativado).")
    usar_filtro_horario = False
    horarios_bloqueados = []

# Parâmetros Filtro ADX
try:
    usar_filtro_adx = config['AJUSTES']['usar_filtro_adx'].upper() == 'S'
    periodo_adx = int(config['AJUSTES']['periodo_adx'])
    nivel_adx_min = float(config['AJUSTES']['nivel_adx_min'])
except Exception as e:
    print(yellow + f"Aviso: Parâmetros de Filtro ADX não encontrados ou inválidos em config.txt ({e}). Usando valores padrão (desativado).")
    usar_filtro_adx = False
    periodo_adx = 14
    nivel_adx_min = 25.0

# Parâmetros MACD
try:
    usar_filtro_macd = config["MACD"]["usar_filtro_macd"].upper() == "S"
    fast_period_macd = int(config["MACD"]["fast_period_macd"])
    slow_period_macd = int(config["MACD"]["slow_period_macd"])
    signal_period_macd = int(config["MACD"]["signal_period_macd"])
except Exception as e:
    print(yellow + f"Aviso: Parâmetros MACD não encontrados ou inválidos em config.txt ({e}). Usando valores padrão (desativado).")
    usar_filtro_macd = False
    fast_period_macd = 12
    slow_period_macd = 26
    signal_period_macd = 9

# Parâmetros Bandas de Bollinger
try:
    usar_filtro_bollinger = config["BOLLINGER_BANDS"]["usar_filtro_bollinger"].upper() == "S"
    periodo_bollinger = int(config["BOLLINGER_BANDS"]["periodo_bollinger"])
    desvios_bollinger = float(config["BOLLINGER_BANDS"]["desvios_bollinger"])
except Exception as e:
    print(yellow + f"Aviso: Parâmetros Bandas de Bollinger não encontrados ou inválidos em config.txt ({e}). Usando valores padrão (desativado).")
    usar_filtro_bollinger = False
    periodo_bollinger = 20
    desvios_bollinger = 2.0

lucro_total = 0
stop = True

if config['MARTINGALE']['usar_martingale'].upper() == 'S':
    martingale = int(config['MARTINGALE']['niveis_martingale'])
    gales = True
else:
    martingale = 0
    gales = False
fator_mg = float(config['MARTINGALE']['fator_martingale'])

proximo_sinal = config['MARTINGALE']['proximo_sinal']
valor_proximo_sinal = 0
nivel_proximo_sinal = 0  

if config['SOROS']['usar_soros'].upper() == 'S':
    soros = True
    niveis_soros = int(config['SOROS']['niveis_soros'])
    nivel_soros = 0

else:
    soros = False
    niveis_soros = 0
    nivel_soros = 0

valor_soros = 0
lucro_op_atual = 0

# Análise de médias sempre ativa
analise_medias = 'S'
velas_medias = int(config['AJUSTES']['velas_medias'])

print('Iniciando Conexão com a IQOption')
API = IQ_Option(email,senha)

### Função para conectar na IQOPTION ###
check, reason = API.connect()
if check:
    print('\nConectado com sucesso')
else:
    if reason == '{"code":"invalid_credentials","message":"You entered the wrong credentials. Please ensure that your login/password is correct."}':
        print('\nEmail ou senha incorreta')
        sys.exit()
        
    else:
        print('\nHouve um problema na conexão')

        print(reason)
        sys.exit()


while True:
    escolha = input(Fore.GREEN +'\n>>'+Fore.WHITE+' Qual conta deseja conectar?\n'+ Fore.GREEN+' 1 - '+ Fore.WHITE+'DEMO \n'+ Fore.GREEN+' 2 - '+ Fore.WHITE+'REAL \n'+ Fore.GREEN+'--> ')
    try:
        escolha = int(escolha)
        if escolha == 1:
            conta = 'PRACTICE'
            escolha_txt = 'Demo'
            print(Fore.GREEN + '\n>> Conta demo selecionada')
            break
        elif escolha== 2:
            conta = 'REAL'
            escolha_txt = 'Real'
            print(Fore.GREEN+ '\n>> Conta real selecionada')
            break

        else:
            print(Fore.RED +'>> Opção inválida - Digite 1 ou 2')
            continue
    except:
        print(Fore.RED +'>> Opção inválida - Digite 1 ou 2')
        
API.change_balance(conta)

# Restaurar exibição da banca e valor de entrada
cifrao = API.get_currency()
saldo_inicial = API.get_balance()
print(yellow + '\n------------------------------------')
print(yellow + f">> Saldo Atual ({escolha_txt}): {white}{cifrao} {saldo_inicial:.2f}")
print(yellow + f">> Valor de Entrada Configurado: {white}{cifrao} {valor_entrada:.2f}")
print(yellow + '------------------------------------\n')


### Função para checar stop win e loss
def check_stop():
    global stop,lucro_total
    if lucro_total <= float('-'+str(abs(stop_loss))):
        stop = False
        print(Fore.WHITE + Back.RED+'\n ########################### ')
        print(red+'  STOP LOSS BATIDO ',str(cifrao),str(lucro_total))
        print(Fore.WHITE + Back.RED+' ########################### ')
        sys.exit()
        

    if lucro_total >= float(abs(stop_win)):
        stop = False
        print(Fore.WHITE + Back.RED+'\n ########################### ')
        print(green+'  STOP WIN BATIDO ',str(cifrao),str(lucro_total))
        print(Fore.WHITE + Back.RED+' ########################### ')
        sys.exit()

def payout(par):
    global all_asset

    try:
        if all_asset["digital"][par]["open"]:
            digital = API.get_digital_payout(par)
            if digital is not None and digital > 0:
                return True, "digital"
    except KeyError:
        pass

    try:
        if all_asset["turbo"][par]["open"]:
            turbo = API.get_all_profit()[par]["turbo"]
            if turbo is not None and turbo > 0:
                return True, "turbo"
    except KeyError:
        pass

    try:
        if all_asset["binary"][par]["open"]:
            binary = API.get_all_profit()[par]["binary"]
            if binary is not None and binary > 0:
                return True, "binary"
    except KeyError:
        pass

    # Verifica se o par está fechado em todas as modalidades
    digital_open = all_asset.get("digital", {}).get(par, {}).get("open", False)
    turbo_open = all_asset.get("turbo", {}).get(par, {}).get("open", False)
    binary_open = all_asset.get("binary", {}).get(par, {}).get("open", False)

    if not digital_open and not turbo_open and not binary_open:
        return False, "FECHADO"
    else:
        return False, "abaixo"

### Função abrir ordem e checar resultado ###
def compra(ativo,valor_entrada,direcao,exp,tipo):
    global stop,lucro_total, nivel_soros, niveis_soros, valor_soros, lucro_op_atual, valor_proximo_sinal, nivel_proximo_sinal, usar_filtro_macd, fast_period_macd, slow_period_macd, signal_period_macd, usar_filtro_bollinger, periodo_bollinger, desvios_bollinger

    if soros:
        if nivel_soros == 0:
            if gales == True and proximo_sinal == 'S':
                if nivel_proximo_sinal == 0:
                
                    entrada = valor_entrada
                else:
                    entrada = valor_proximo_sinal
                
            else:
                entrada = valor_entrada

        if nivel_soros >=1 and valor_soros > 0 and nivel_soros <= niveis_soros:
            entrada = valor_entrada + valor_soros

        if nivel_soros > niveis_soros:
            lucro_op_atual = 0
            valor_soros = 0
            entrada = valor_entrada
            nivel_soros = 0
    else:
        if gales == True and proximo_sinal == 'S':
            if nivel_proximo_sinal == 0:

                entrada = valor_entrada
                #print('entrou no if do gale e proximo sinal valor entrada = '+ str(entrada))
            else:
                entrada = valor_proximo_sinal
                #print('entrou no else do gale e proximo sinal valor entrada = '+ str(entrada))
            
        else:
            entrada = valor_entrada
            #print('não entrou no if do gale e proximo sinal valor entrada = '+ str(entrada))


    for i in range(martingale + 1):

        if stop == True:
        
            if tipo == 'digital':
                check, id = API.buy_digital_spot_v2(ativo,entrada,direcao,exp)
            else:
                check, id = API.buy(entrada,ativo,direcao,exp)


            if check:
                if i == 0 and proximo_sinal == 'N' or (proximo_sinal =='S' and nivel_proximo_sinal == 0 and i == 0):
                    print('\n >> Ordem aberta \n', 
                          yellow+'>> Par:',white,ativo,'\n', 
                          yellow+'>> Direção:',white,direcao,'\n', 
                          yellow+'>> Entrada de:',white,cifrao,entrada)
                if i >= 1:
                    print('\n >> Ordem aberta para GALE',str(i),'\n', 
                          '>> Par:',ativo,'\n', 
                          '>> Direção:',direcao,'\n', 
                          '>> Entrada de:',cifrao,entrada)
                if i == 0 and proximo_sinal == 'S' and nivel_proximo_sinal >= 1:
                    print('\n >> Ordem aberta para GALE',str(nivel_proximo_sinal),'\n', 
                          '>> Par:',ativo,'\n', 
                          '>> Direção:',direcao,'\n', 
                          '>> Entrada de:',cifrao,entrada)

                while True:
                    time.sleep(0.1)
                    status , resultado = API.check_win_digital_v2(id) if tipo == 'digital' else API.check_win_v4(id)

                    if status:

                        lucro_total += round(resultado,2)
                        valor_soros += round(resultado,2)
                        lucro_op_atual += round(resultado,2)
                        printar_lucro = lucro_tot(lucro_total)

                        if resultado > 0:
                            if i == 0 and proximo_sinal == 'N' or (proximo_sinal =='S' and nivel_proximo_sinal == 0 and i == 0):
                                print(green+'\n >> Resultado: WIN \n'+
                                        yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                        yellow+'\n >> Par: '+white+ ativo+
                                        yellow+'\n >> Lucro total: '+ printar_lucro)
                            if i >= 1:
                                print(green+'\n >> Resultado: WIN no gale ' + str(i)+' '+
                                    yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                    yellow+'\n >> Par: '+white+ ativo+
                                    yellow+'\n >> Lucro total: '+ printar_lucro)
                            if i == 0 and proximo_sinal == 'S' and nivel_proximo_sinal >= 1:
                                print(green+'\n >> Resultado: WIN no gale ' + str(nivel_proximo_sinal)+' '+
                                    yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                    yellow+'\n >> Par: '+white+ ativo+
                                    yellow+'\n >> Lucro total: '+ printar_lucro)
                                
                            if gales == True and proximo_sinal =='S':
                                valor_proximo_sinal = 0
                                nivel_proximo_sinal = 0


                        elif resultado == 0:
                            if  i == 0 and proximo_sinal == 'N' or (proximo_sinal =='S' and nivel_proximo_sinal == 0 and i == 0):
                                print(yellow+'\n >> Resultado: EMPATE \n' +
                                        yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                        yellow+'\n >> Par: '+white+ ativo+
                                        yellow+'\n >> Lucro total: '+ printar_lucro)
                                
                            if i >= 1:

                                print(yellow+'\n>> Resultado: EMPATE no gale' + str(i) +' '+
                                        yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                        yellow+'\n >> Par: '+white+ ativo+
                                        yellow+'\n >> Lucro total: '+ printar_lucro)
                                
                            if i == 0 and proximo_sinal == 'S' and nivel_proximo_sinal >= 1:
                                print(yellow+'\n >> Resultado: EMPATE no gale ' + str(nivel_proximo_sinal)+' '+
                                    yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                    yellow+'\n >> Par: '+white+ ativo+
                                    yellow+'\n >> Lucro total: '+ printar_lucro)

                            if proximo_sinal =='S':
                                if nivel_proximo_sinal + 1 <= martingale:
                                    #print('multiplicando gale')
                                    gale = float(entrada)                   
                                    valor_proximo_sinal = round(abs(gale), 2)
                                    nivel_proximo_sinal += 1
                                    break
                            else:
                                if i+1 <= martingale:
                                    gale = float(entrada)                   
                                    entrada = round(abs(gale), 2)


                        else:
                            if i == 0 and proximo_sinal == 'N' or (proximo_sinal =='S' and nivel_proximo_sinal == 0 and i == 0):
                                print(red+'\n>> Resultado: LOSS ' +
                                        yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                        yellow+'\n >> Par: '+white+ ativo+
                                        yellow+'\n >> Lucro total: '+ printar_lucro)
                            if i >= 1:
                                print(red+'\n>> Resultado: LOSS no gale' + str(i) +' '+
                                        yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                        yellow+'\n >> Par: '+white+ ativo+
                                        yellow+'\n >> Lucro total: '+ printar_lucro)
                            if i == 0 and proximo_sinal == 'S' and nivel_proximo_sinal >= 1:
                                print(red+'\n >> Resultado: LOSS no gale ' + str(nivel_proximo_sinal)+' '+
                                    yellow+'\n >> Lucro: '+white+ str(round(resultado,2))+
                                    yellow+'\n >> Par: '+white+ ativo+
                                    yellow+'\n >> Lucro total: '+ printar_lucro)


                            if proximo_sinal =='S':
                                
                                if nivel_proximo_sinal + 1 <= martingale:
                                    #print('multiplicando gale')
                                    gale = float(entrada) * float(fator_mg)                    
                                    valor_proximo_sinal = round(abs(gale), 2)
                                    nivel_proximo_sinal += 1
                                    break
                            else:
                                if i+1 <= martingale:
                                    gale = float(entrada) * float(fator_mg)                    
                                    entrada = round(abs(gale), 2)


                        check_stop()

                        break


                if resultado > 0:
                    break

                if proximo_sinal == 'S':
                    if nivel_proximo_sinal > martingale:
                        #print('zerando gale')
                        nivel_proximo_sinal = 0
                        valor_proximo_sinal = 0
                        valor_soros = 0
                        nivel_soros = 0
                        lucro_op_atual = 0
                        break     
                    else:
                        break   
            else:
                print('>> Erro na abertura da ordem,', id,ativo)

    if soros:
        if lucro_op_atual > 0:
            nivel_soros += 1
            lucro_op_atual = 0
     
        else:
            if proximo_sinal == 'N':
                valor_soros = 0
                nivel_soros = 0
                lucro_op_atual = 0

def lucro_tot(lucro_total):
    if lucro_total == 0:
        return white + cifrao + ' '+str(round(lucro_total,2))
    if lucro_total > 0:
        return green + cifrao + ' '+str(round(lucro_total,2))
    if lucro_total < 0:
        return red + cifrao + ' '+str(round(lucro_total,2))
    

### Fução que busca hora da corretora ###
def horario():
    # x = API.get_server_timestamp() # Não usado
    now = datetime.fromtimestamp(API.get_server_timestamp())
    return now

# Função para verificar se o horário atual está bloqueado
def verificar_horario_bloqueado():
    if not usar_filtro_horario:
        return False # Retorna False (não bloqueado) se o filtro estiver desativado

    hora_atual = horario().time() # Pega apenas a parte de hora/minuto/segundo

    for inicio, fim in horarios_bloqueados:
        # Verifica se o horário atual está dentro do intervalo bloqueado
        # Lógica para intervalo que atravessa a meia-noite (ex: 23:00-01:00)
        if inicio > fim: 
            if hora_atual >= inicio or hora_atual < fim:
                print(yellow + f"Operação abortada - Horário bloqueado ({inicio.strftime('%H:%M')} - {fim.strftime('%H:%M')}). Aguardando...")
                return True # Bloqueado
        # Lógica para intervalo normal (ex: 10:00-11:00)
        else:
            if inicio <= hora_atual < fim:
                print(yellow + f"Operação abortada - Horário bloqueado ({inicio.strftime('%H:%M')} - {fim.strftime('%H:%M')}). Aguardando...")
                return True # Bloqueado
                
    return False # Não bloqueado

def medias(velas):
    soma = 0
    for i in velas:
        soma += i['close']
    media = soma / velas_medias

    if media > velas[-1]['close']:
        tendencia = 'put'
    else:
        tendencia = 'call'

    return tendencia

# Função para calcular RSI (Relative Strength Index)
def calcular_rsi(velas, periodo=14):
    fechamentos = [vela['close'] for vela in velas]
    
    if len(fechamentos) < periodo + 1:
        return 50  # Valor neutro se não houver dados suficientes
    
    # Calcular mudanças
    mudancas = [fechamentos[i] - fechamentos[i-1] for i in range(1, len(fechamentos))]
    
    # Separar ganhos e perdas
    ganhos = [max(0, mudanca) for mudanca in mudancas]
    perdas = [max(0, -mudanca) for mudanca in mudancas]
    
    # Calcular médias de ganhos e perdas
    media_ganhos = sum(ganhos[-periodo:]) / periodo
    media_perdas = sum(perdas[-periodo:]) / periodo
    
    if media_perdas == 0:
        return 100 # Evita divisão por zero
        
    rs = media_ganhos / media_perdas
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

# Função para calcular ATR (Average True Range)
def calcular_atr(velas, periodo=14):
    if len(velas) < periodo + 1:
        return 0, 0 # Retorna 0 se não houver dados suficientes

    df = pd.DataFrame(velas)
    df['high'] = df['max'].astype(float)
    df['low'] = df['min'].astype(float)
    df['close'] = df['close'].astype(float)

    # Calcular True Range (TR)
    df['tr1'] = abs(df['high'] - df['low'])
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

    # Calcular Average True Range (ATR) usando Média Móvel Simples (SMA)
    df['atr'] = df['tr'].rolling(window=periodo).mean()
    
    atr_atual = df['atr'].iloc[-1]
    atr_medio = df['atr'].iloc[-(periodo*2):-1].mean() # Média do ATR dos últimos 'periodo' períodos (excluindo o atual)

    return atr_atual, atr_medio

# Função para calcular ADX (Average Directional Index)
def calcular_adx(velas, periodo=14):
    if len(velas) < periodo * 2: # ADX precisa de mais dados
        return 0 # Retorna 0 se não houver dados suficientes

    df = pd.DataFrame(velas)
    df['high'] = df['max'].astype(float)
    df['low'] = df['min'].astype(float)
    df['close'] = df['close'].astype(float)

    # Calcular +DM, -DM e TR
    df['move_up'] = df['high'].diff()
    df['move_down'] = -df['low'].diff()
    df['plus_dm'] = np.where((df['move_up'] > df['move_down']) & (df['move_up'] > 0), df['move_up'], 0.0)
    df['minus_dm'] = np.where((df['move_down'] > df['move_up']) & (df['move_down'] > 0), df['move_down'], 0.0)
    
    df['tr1'] = abs(df['high'] - df['low'])
    df['tr2'] = abs(df['high'] - df['close'].shift(1))
    df['tr3'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

    # Calcular ATR, +DI, -DI (usando Wilder's Smoothing)
    df['atr_adx'] = df['tr'].ewm(alpha=1/periodo, adjust=False).mean()
    df['plus_di'] = 100 * (df['plus_dm'].ewm(alpha=1/periodo, adjust=False).mean() / df['atr_adx'])
    df['minus_di'] = 100 * (df['minus_dm'].ewm(alpha=1/periodo, adjust=False).mean() / df['atr_adx'])

    # Calcular DX e ADX
    df['dx'] = 100 * (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di']))
    df['adx'] = df['dx'].ewm(alpha=1/periodo, adjust=False).mean()

    return df['adx'].iloc[-1]

# Função para verificar tendência (Médias + RSI)
def verificar_tendencia(par):
    # Aumentar a quantidade de velas para RSI e Médias
    velas_tendencia = API.get_candles(par, 60, max(velas_medias, 15) + 1, time.time())
    if not velas_tendencia or len(velas_tendencia) < max(velas_medias, 15) + 1:
        print(f"Dados insuficientes para análise de tendência em {par}.")
        return None, False # Retorna None se não houver dados suficientes

    tendencia_media = medias(velas_tendencia[-velas_medias:])
    rsi_atual = calcular_rsi(velas_tendencia)

    # Ajuste dos níveis de RSI para confirmação mais forte
    rsi_confirma_call = rsi_atual > 55 # Anteriormente 50
    rsi_confirma_put = rsi_atual < 45 # Anteriormente 50

    confirmada = (tendencia_media == 'call' and rsi_confirma_call) or \
                 (tendencia_media == 'put' and rsi_confirma_put)
    
    # Adiciona print para debug
    # print(f"Tendência {par}: Média={tendencia_media.upper()}, RSI={rsi_atual:.2f}, Confirmada={confirmada}")

    return tendencia_media, confirmada

# Função para verificar volatilidade (ATR)
def verificar_volatilidade(par):
    if not usar_filtro_atr:
        return True # Retorna True se o filtro estiver desativado

    # Pega mais velas para o cálculo do ATR
    velas_atr = API.get_candles(par, 60, periodo_atr * 3, time.time()) # Pega 3x o período para ter uma média mais estável
    if not velas_atr or len(velas_atr) < periodo_atr + 1:
        print(f"Dados insuficientes para análise de volatilidade (ATR) em {par}.")
        return False # Não opera se não puder calcular ATR

    atr_atual, atr_medio = calcular_atr(velas_atr, periodo_atr)

    if atr_medio == 0: # Evita divisão por zero ou ATR médio inválido
        print(f"ATR Médio inválido para {par}. Volatilidade não verificada.")
        return True # Permite operação se não conseguir calcular ATR médio

    volatilidade_ok = (atr_atual >= atr_medio * multiplicador_atr_min) and \
                      (atr_atual <= atr_medio * multiplicador_atr_max)

    if not volatilidade_ok:
        if atr_atual < atr_medio * multiplicador_atr_min:
            print(yellow + f"Entrada abortada ({par}) - Volatilidade BAIXA (ATR Atual: {atr_atual:.5f}, Limite Mín: {(atr_medio * multiplicador_atr_min):.5f})")
        else:
            print(yellow + f"Entrada abortada ({par}) - Volatilidade ALTA (ATR Atual: {atr_atual:.5f}, Limite Máx: {(atr_medio * multiplicador_atr_max):.5f})")
    # else:
    #     print(f"Volatilidade OK ({par}) - ATR Atual: {atr_atual:.5f}, Média: {atr_medio:.5f}")

    return volatilidade_ok

# Função para verificar força da tendência (ADX)
def verificar_forca_tendencia(par):
    if not usar_filtro_adx:
        return True # Retorna True se o filtro estiver desativado

    # Pega velas suficientes para o cálculo do ADX (pelo menos 2x o período)
    velas_adx = API.get_candles(par, 60, periodo_adx * 3, time.time()) # Pega 3x o período para cálculo mais estável
    if not velas_adx or len(velas_adx) < periodo_adx * 2:
        print(f"Dados insuficientes para análise de força da tendência (ADX) em {par}.")
        return False # Não opera se não puder calcular ADX

    adx_atual = calcular_adx(velas_adx, periodo_adx)

    tendencia_forte = adx_atual >= nivel_adx_min

    if not tendencia_forte:
        print(yellow + f"Entrada abortada ({par}) - Tendência FRACA (ADX Atual: {adx_atual:.2f}, Nível Mín: {nivel_adx_min:.2f})")
    # else:
    #     print(f"Força da Tendência OK ({par}) - ADX Atual: {adx_atual:.2f}")

    return tendencia_forte

### Função para verificar payouts ###
def verifica_payouts(par):
    global profit, all_asset

    try:
        if all_asset['digital'][par]['open']:
            digital = API.get_digital_payout(par)
            if digital >= pay_minimo:
                return True, 'digital'
    except:
        pass

    try:
        if all_asset['turbo'][par]['open']:
            if profit[par]['turbo'] > 0:
                turbo = round(profit[par]['turbo'],2) * 100
                if turbo >= pay_minimo:
                    return True, 'turbo'
    except:
        pass

    try:
        if all_asset['binary'][par]['open']:
            if profit[par]['binary']> 0:
                binary = round(profit[par]['binary'],2) * 100
                if binary >= pay_minimo:
                    return True, 'binary'
    except:
        pass

    # Verifica se o par está fechado em todas as modalidades
    try:
        digital_open = all_asset['digital'][par]['open']
    except: digital_open = False
    try:
        turbo_open = all_asset['turbo'][par]['open']
    except: turbo_open = False
    try:
        binary_open = all_asset['binary'][par]['open']
    except: binary_open = False

    if not digital_open and not turbo_open and not binary_open:
        return False, 'FECHADO'
    else:
        return False, 'abaixo'


### Função para catalogar ###
def catalogacao():
    global analise_result, linha, all_asset, profit

    print(yellow+'\n>> Recatalogando...\n')

    all_asset = API.get_all_open_time()
    profit = API.get_all_profit()

    analise_result, linha = catag(all_asset,API)

    if analise_result:
        tabela = []
        for i in analise_result:
            # Ajusta a formatação da assertividade para exibir corretamente
            tabela.append([i[0],i[1],str(round(i[linha],2))+'%'])

        print(tabulate(tabela[:15], headers=["ESTRATÉGIA", "PAR", "ASSERTIVIDADE"], tablefmt="grid", stralign="center"))
    else:
        print(red + "Nenhuma estratégia encontrada na catalogação.")


### Função para operar automaticamente ###
def automatico():
    global analise_result, linha, par, cifrao

    while True: # Loop principal para recatalogação e operação
        catalogacao()

        if not analise_result:
            print(red + "Catalogação vazia. Aguardando 60 segundos para tentar novamente...")
            time.sleep(60)
            continue # Volta para o início do loop para recatalogar

        melhor_estrategia = analise_result[0][0]
        par = analise_result[0][1]
        assertividade = analise_result[0][linha]

        print(yellow + '\n>> Melhor par atualizado:', white + par, yellow + '| Melhor estratégia:', white + melhor_estrategia, yellow + '| Assertividade:', white + str(round(assertividade, 2)) + '%')

        # Obtém o símbolo da moeda para exibição (já definido globalmente após seleção da conta)
        # cifrao = API.get_currency() # Removido daqui

        # Chama a estratégia correspondente
        if melhor_estrategia == 'MHI':
            estrategia_mhi('um', 'Minoria')
        elif melhor_estrategia == 'MHI MAIORIA':
            estrategia_mhi('um', 'Maioria')
        elif melhor_estrategia == 'MHI2':
            estrategia_mhi('dois', 'Minoria')
        elif melhor_estrategia == 'MHI2 MAIORIA':
            estrategia_mhi('dois', 'Maioria')
        elif melhor_estrategia == 'MHI3':
            estrategia_mhi('tres', 'Minoria')
        elif melhor_estrategia == 'MHI3 MAIORIA':
            estrategia_mhi('tres', 'Maioria')
        elif melhor_estrategia == 'MILHAO':
            estrategia_milhao('Minoria')
        elif melhor_estrategia == 'MILHAO MAIORIA':
            estrategia_milhao('Maioria')
        elif melhor_estrategia == 'PADRAO_3_VELAS':
            estrategia_padrao_3_velas('Minoria')
        elif melhor_estrategia == 'PADRAO_3_VELAS_MAIORIA':
            estrategia_padrao_3_velas('Maioria')
        else:
            print(red + f"Estratégia '{melhor_estrategia}' não reconhecida no modo automático.")
            time.sleep(5) # Espera antes de recatalogar

        # A recatalogação agora acontece no início do próximo loop
        # Não é mais necessário o time.sleep(60) aqui
        # time.sleep(60) 

def estrategia_milhao(maior_menor):
    global usar_filtro_macd, fast_period_macd, slow_period_macd, signal_period_macd, usar_filtro_bollinger, periodo_bollinger, desvios_bollinger, par

    if maior_menor == 'Minoria':
        print(yellow+'\n>> '+white+'Iniciando MILHÃO - Minoria\n')
    else:
        print(yellow+'\n>> '+white+'Iniciando MILHÃO - Maioria\n')

    while True:
        time.sleep(0.1)

        ### horario da iqoption ###
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S')[1:])

        entrar = True if minutos >= 9.59 else False

        print('Aguardando Horário de entrada (Milhão)' ,minutos, end='\r')
        

        if entrar:
            # Verifica filtro de horário ANTES de iniciar análise
            if verificar_horario_bloqueado():
                time.sleep(30) # Espera 30s antes de verificar novamente
                continue # Volta para o início do loop de espera

            print('>> Iniciando análise (Milhão)...\n')

            direcao = False

            timeframe = 60

            qnt_velas = 3

            # Verificação de tendência obrigatória
            tendencia, confirmada = verificar_tendencia(par)
            if tendencia is None: # Se não conseguiu verificar tendência, aborta
                print(red + f"Não foi possível verificar a tendência para {par}. Abortando entrada.")
                break # Sai do loop da estratégia
            
            # Verificação de volatilidade (ATR)
            if not verificar_volatilidade(par):
                break # Sai do loop da estratégia se a volatilidade não for adequada

            # Verificação de força da tendência (ADX)
            if not verificar_forca_tendencia(par):
                break # Sai do loop da estratégia se a tendência for fraca

            # Verificação de MACD
            if usar_filtro_macd:
                velas_macd = API.get_candles(par, 60, max(fast_period_macd, slow_period_macd, signal_period_macd) * 2, time.time())
                if not velas_macd or len(velas_macd) < max(fast_period_macd, slow_period_macd, signal_period_macd) + 1:
                    print(f"Dados insuficientes para análise MACD em {par}. Abortando entrada.")
                    break
                macd_val, signal_val, hist_val = calcular_macd(velas_macd, fast_period_macd, slow_period_macd, signal_period_macd)
                if direcao == 'call' and not (macd_val > signal_val and hist_val > 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma CALL (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break
                elif direcao == 'put' and not (macd_val < signal_val and hist_val < 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma PUT (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break

            # Verificação de Bandas de Bollinger
            if usar_filtro_bollinger:
                velas_bollinger = API.get_candles(par, 60, periodo_bollinger * 2, time.time())
                if not velas_bollinger or len(velas_bollinger) < periodo_bollinger + 1:
                    print(f"Dados insuficientes para análise Bandas de Bollinger em {par}. Abortando entrada.")
                    break
                upper_band, sma, lower_band = calcular_bollinger_bands(velas_bollinger, periodo_bollinger, desvios_bollinger)
                if direcao == 'call' and not (velas_bollinger[-1]['close'] < lower_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está abaixo da Banda Inferior para CALL (Close: {velas_bollinger[-1]['close']:.2f}, Lower: {lower_band:.2f})")
                    break
                elif direcao == 'put' and not (velas_bollinger[-1]['close'] > upper_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está acima da Banda Superior para PUT (Close: {velas_bollinger[-1]['close']:.2f}, Upper: {upper_band:.2f})")
                    break

            velas = API.get_candles(par, timeframe, qnt_velas, time.time())
            if not velas or len(velas) < qnt_velas:
                print(f"Dados insuficientes para análise Milhão em {par}.")
                time.sleep(5)
                continue

            velas[-1] = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'
            velas[-2] = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
            velas[-3] = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'

            if velas[-1] == velas[-2] and velas[-2] == velas[-3] and velas[-1] != 'Doji': # Verifica se não há Dojis
                if velas[-1] == 'Verde': direcao = 'put'
                if velas[-1] == 'Vermelha': direcao = 'call'

            if maior_menor == 'Maioria':
                if direcao == 'call':
                    direcao = 'put'
                elif direcao == 'put':
                    direcao = 'call'

            # Verificação de tendência obrigatória
            if direcao == 'put' or direcao == 'call':
                if direcao == tendencia and confirmada:
                    print(f"Confirmação de Tendência OK: Sinal={direcao.upper()}, Tendência={tendencia.upper()}, RSI Confirmado={confirmada}")
                    pass  # Direção está de acordo com a tendência e confirmada por múltiplos indicadores
                else:
                    if direcao != tendencia:
                        print(f'>> Entrada abortada - Contra Tendência. Sinal: {direcao.upper()}, Tendência: {tendencia.upper()}')
                    else:
                        print(f'>> Entrada abortada - Tendência não confirmada por RSI (Média:{tendencia.upper()}, RSI Confirmado:{confirmada}).')
                    direcao = 'abortar'

            if direcao == 'put' or direcao == 'call':

                stat, tipo_op = verifica_payouts(par)

                if stat:
                    compra(par,valor_entrada,direcao,1,tipo_op)

                else:
                    if tipo_op =='FECHADO':
                        print('\n>> Par Fechado, iniciarei uma nova análise')

                    if tipo_op =='abaixo':
                        print('\n>> Par abaixo do payout mínimo configurado, iniciarei uma nova análise')    

            else:
                if direcao == 'abortar':
                    # Mensagem já impressa na verificação de tendência
                    pass 
                elif 'Doji' in [velas[-1], velas[-2], velas[-3]]:
                    print('>> Entrada abortada (Milhão) - Foi encontrado um doji na análise.')
                else:
                    print('>> Entrada abortada (Milhão) - Padrão não identificado.')

                time.sleep(2)

            print(green + '\n*****************************************************************************************\n\n')
            # A recatalogação agora acontece no início do próximo loop da função automatico()
            break # Sai do loop da estratégia para permitir a recatalogação


def estrategia_mhi(tipo_mhi,maior_menor):
    global usar_filtro_macd, fast_period_macd, slow_period_macd, signal_period_macd, usar_filtro_bollinger, periodo_bollinger, desvios_bollinger, par

    if tipo_mhi == 'um':
        print(yellow+'\n>> '+white+'Iniciando MHI 1 - '+ maior_menor+'\n')
    if tipo_mhi == 'dois':
        print(yellow+'\n>> '+white+'Iniciando MHI 2 - '+ maior_menor+'\n')
    if tipo_mhi == 'tres':
        print(yellow+'\n>> '+white+'Iniciando MHI 3 - '+ maior_menor+'\n')

    while True:
        time.sleep(0.1)

        ### horario da iqoption ###
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S')[1:])

        if tipo_mhi == 'um':
            entrar = True if (minutos >= 4.59 and minutos <= 5.00) or minutos >= 9.59 else False
            qnt_velas_analise = 3 # Velas -1, -2, -3
            offset_velas = 1 # Começa da vela i+1
            nome_log = "MHI1"

        if tipo_mhi == 'dois':
            entrar = True if (minutos >= 5.59 and minutos <= 6.00) or (minutos >= 0.59 and minutos <= 1.00) else False
            qnt_velas_analise = 3 # Velas -2, -3, -4
            offset_velas = 2 # Começa da vela i+2
            nome_log = "MHI2"

        if tipo_mhi == 'tres':
            entrar = True if (minutos >= 6.59 and minutos <= 7.00) or (minutos >= 1.59 and minutos <= 2.00) else False
            qnt_velas_analise = 3 # Velas -3, -4, -5
            offset_velas = 3 # Começa da vela i+3
            nome_log = "MHI3"

        print(f'Aguardando Horário de entrada ({nome_log} {maior_menor}) ' ,minutos, end='\r')
        

        if entrar:
            # Verifica filtro de horário ANTES de iniciar análise
            if verificar_horario_bloqueado():
                time.sleep(30) # Espera 30s antes de verificar novamente
                continue # Volta para o início do loop de espera

            print(f'>> Iniciando análise ({nome_log} {maior_menor})...\n')

            direcao = False

            timeframe = 60

            qnt_velas_total = 5 # Suficiente para MHI3

            # Verificação de tendência obrigatória
            tendencia, confirmada = verificar_tendencia(par)
            if tendencia is None: # Se não conseguiu verificar tendência, aborta
                print(red + f"Não foi possível verificar a tendência para {par}. Abortando entrada.")
                break # Sai do loop da estratégia

            # Verificação de volatilidade (ATR)
            if not verificar_volatilidade(par):
                break # Sai do loop da estratégia se a volatilidade não for adequada

            # Verificação de força da tendência (ADX)
            if not verificar_forca_tendencia(par):
                break # Sai do loop da estratégia se a tendência for fraca

            # Verificação de MACD
            if usar_filtro_macd:
                velas_macd = API.get_candles(par, 60, max(fast_period_macd, slow_period_macd, signal_period_macd) * 2, time.time())
                if not velas_macd or len(velas_macd) < max(fast_period_macd, slow_period_macd, signal_period_macd) + 1:
                    print(f"Dados insuficientes para análise MACD em {par}. Abortando entrada.")
                    break
                macd_val, signal_val, hist_val = calcular_macd(velas_macd, fast_period_macd, slow_period_macd, signal_period_macd)
                if direcao == 'call' and not (macd_val > signal_val and hist_val > 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma CALL (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break
                elif direcao == 'put' and not (macd_val < signal_val and hist_val < 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma PUT (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break

            # Verificação de Bandas de Bollinger
            if usar_filtro_bollinger:
                velas_bollinger = API.get_candles(par, 60, periodo_bollinger * 2, time.time())
                if not velas_bollinger or len(velas_bollinger) < periodo_bollinger + 1:
                    print(f"Dados insuficientes para análise Bandas de Bollinger em {par}. Abortando entrada.")
                    break
                upper_band, sma, lower_band = calcular_bollinger_bands(velas_bollinger, periodo_bollinger, desvios_bollinger)
                if direcao == 'call' and not (velas_bollinger[-1]['close'] < lower_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está abaixo da Banda Inferior para CALL (Close: {velas_bollinger[-1]['close']:.2f}, Lower: {lower_band:.2f})")
                    break
                elif direcao == 'put' and not (velas_bollinger[-1]['close'] > upper_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está acima da Banda Superior para PUT (Close: {velas_bollinger[-1]['close']:.2f}, Upper: {upper_band:.2f})")
                    break

            velas_api = API.get_candles(par, timeframe, qnt_velas_total, time.time())
            if not velas_api or len(velas_api) < qnt_velas_total:
                print(f"Dados insuficientes para análise {nome_log} em {par}.")
                time.sleep(5)
                continue

            # Mapeia as velas relevantes para a estratégia específica
            velas_analise = []
            cores_analise = []
            velas_print = [] # Para exibir as velas
            doji_presente = False

            for i in range(offset_velas, offset_velas + qnt_velas_analise):
                idx = -i # Índice negativo para pegar as velas corretas
                vela = velas_api[idx]
                cor = 'Verde' if vela['open'] < vela['close'] else 'Vermelha' if vela['open'] > vela['close'] else 'Doji'
                velas_analise.append(cor)
                cores_analise.append(cor)
                if cor == 'Doji': doji_presente = True
                
                # Para printar as velas na ordem correta (da mais antiga para a mais nova)
                if cor == 'Verde': vela_print = Back.GREEN + '       '
                elif cor == 'Vermelha': vela_print = Back.RED + '       '
                else: vela_print = Back.WHITE + '       '
                velas_print.insert(0, vela_print) # Insere no início para manter a ordem

            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
            print('  ', '  '.join(velas_print))
                        
            if not doji_presente:
                if cores_analise.count('Verde') > cores_analise.count('Vermelha'): direcao = 'put' # Minoria
                if cores_analise.count('Vermelha') > cores_analise.count('Verde'): direcao = 'call' # Minoria

                if maior_menor == 'Maioria':
                    if direcao == 'call': direcao = 'put'
                    elif direcao == 'put': direcao = 'call'
            
            # Verificação de tendência obrigatória
            if direcao == 'put' or direcao == 'call':
                if direcao == tendencia and confirmada:
                    print(f"Confirmação de Tendência OK: Sinal={direcao.upper()}, Tendência={tendencia.upper()}, RSI Confirmado={confirmada}")
                    pass  # Direção está de acordo com a tendência e confirmada por múltiplos indicadores
                else:
                    if direcao != tendencia:
                        print(f'>> Entrada abortada - Contra Tendência. Sinal: {direcao.upper()}, Tendência: {tendencia.upper()}')
                    else:
                        print(f'>> Entrada abortada - Tendência não confirmada por RSI (Média:{tendencia.upper()}, RSI Confirmado:{confirmada}).')
                    direcao = 'abortar'

            if direcao == 'put' or direcao == 'call':
                stat, tipo_op = verifica_payouts(par)

                if stat:
                    compra(par,valor_entrada,direcao,1,tipo_op)
                    
                else:
                    if tipo_op =='FECHADO':
                        print('\n>> Par Fechado, iniciarei uma nova análise')

                    if tipo_op =='abaixo':
                        print('\n>> Par abaixo do payout mínimo configurado, iniciarei uma nova análise')  

            else:
                if direcao == 'abortar':
                    # Mensagem já impressa
                    pass
                elif doji_presente:
                    print(f'>> Entrada abortada ({nome_log}) - Foi encontrado um doji na análise.')
                else:
                    # Caso onde verde == vermelho (não deveria acontecer com 3 velas)
                    print(f'>> Entrada abortada ({nome_log}) - Padrão não identificado ou empate de cores.')

                time.sleep(2)

            print(green + '\n*****************************************************************************************\n\n')
            # A recatalogação agora acontece no início do próximo loop da função automatico()
            break # Sai do loop da estratégia para permitir a recatalogação

# Estratégia: Padrão 3 Velas (Refinada)
def estrategia_padrao_3_velas(maior_menor):
    global usar_filtro_macd, fast_period_macd, slow_period_macd, signal_period_macd, usar_filtro_bollinger, periodo_bollinger, desvios_bollinger, par
    if maior_menor == 'Minoria':
        print(yellow+'\n>> '+white+'Iniciando Padrão 3 Velas (Refinado) - Minoria\n')
    else:
        print(yellow+'\n>> '+white+'Iniciando Padrão 3 Velas (Refinado) - Maioria\n')

    while True:
        time.sleep(0.1)
        minutos = float(datetime.fromtimestamp(API.get_server_timestamp()).strftime('%M.%S')[1:])
        
        # Verifica no final de cada minuto
        entrar = True if minutos >= 59.00 else False 

        print('Aguardando Horário de entrada (Padrão 3 Velas Refinado)' ,minutos, end='\r')

        if entrar:
            # Verifica filtro de horário ANTES de iniciar análise
            if verificar_horario_bloqueado():
                time.sleep(30) # Espera 30s antes de verificar novamente
                continue # Volta para o início do loop de espera

            print('>> Iniciando análise (Padrão 3 Velas Refinado)...\n')
            direcao = False
            timeframe = 60
            qnt_velas = 4 # Precisa de 4 velas para analisar engolfo/harami na 3ª vela

            # Verificação de tendência obrigatória
            tendencia, confirmada = verificar_tendencia(par)
            if tendencia is None: # Se não conseguiu verificar tendência, aborta
                print(red + f"Não foi possível verificar a tendência para {par}. Abortando entrada.")
                break # Sai do loop da estratégia

            # Verificação de volatilidade (ATR)
            if not verificar_volatilidade(par):
                break # Sai do loop da estratégia se a volatilidade não for adequada

            # Verificação de força da tendência (ADX)
            if not verificar_forca_tendencia(par):
                break # Sai do loop da estratégia se a tendência for fraca

            # Verificação de MACD
            if usar_filtro_macd:
                velas_macd = API.get_candles(par, 60, max(fast_period_macd, slow_period_macd, signal_period_macd) * 2, time.time())
                if not velas_macd or len(velas_macd) < max(fast_period_macd, slow_period_macd, signal_period_macd) + 1:
                    print(f"Dados insuficientes para análise MACD em {par}. Abortando entrada.")
                    break
                macd_val, signal_val, hist_val = calcular_macd(velas_macd, fast_period_macd, slow_period_macd, signal_period_macd)
                if direcao == 'call' and not (macd_val > signal_val and hist_val > 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma CALL (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break
                elif direcao == 'put' and not (macd_val < signal_val and hist_val < 0):
                    print(yellow + f"Entrada abortada ({par}) - MACD não confirma PUT (MACD: {macd_val:.2f}, Signal: {signal_val:.2f}, Hist: {hist_val:.2f})")
                    break

            # Verificação de Bandas de Bollinger
            if usar_filtro_bollinger:
                velas_bollinger = API.get_candles(par, 60, periodo_bollinger * 2, time.time())
                if not velas_bollinger or len(velas_bollinger) < periodo_bollinger + 1:
                    print(f"Dados insuficientes para análise Bandas de Bollinger em {par}. Abortando entrada.")
                    break
                upper_band, sma, lower_band = calcular_bollinger_bands(velas_bollinger, periodo_bollinger, desvios_bollinger)
                if direcao == 'call' and not (velas_bollinger[-1]['close'] < lower_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está abaixo da Banda Inferior para CALL (Close: {velas_bollinger[-1]['close']:.2f}, Lower: {lower_band:.2f})")
                    break
                elif direcao == 'put' and not (velas_bollinger[-1]['close'] > upper_band):
                    print(yellow + f"Entrada abortada ({par}) - Preço não está acima da Banda Superior para PUT (Close: {velas_bollinger[-1]['close']:.2f}, Upper: {upper_band:.2f})")
                    break

            velas = API.get_candles(par, timeframe, qnt_velas, time.time())

            if not velas or len(velas) < qnt_velas: 
                print("Dados insuficientes para Padrão 3 Velas Refinado.")
                time.sleep(5)
                continue # Espera e tenta novamente

            # Define as velas (0 é a mais recente)
            v = [{'open': c['open'], 'close': c['close'], 'high': c['max'], 'low': c['min'], 
                  'cor': 'Verde' if c['open'] < c['close'] else 'Vermelha' if c['open'] > c['close'] else 'Doji'} 
                 for c in velas[-qnt_velas:]]
            
            v0, v1, v2, v3 = v[-1], v[-2], v[-3], v[-4] # v0=atual, v1=anterior, etc.

            # --- Lógica Refinada Padrão 3 Velas --- 
            # Analisa as 3 velas anteriores (v1, v2, v3)
            
            # Verifica Dojis nas 3 velas de análise
            if 'Doji' in [v1['cor'], v2['cor'], v3['cor']]:
                print(">> Padrão 3 Velas abortado - Doji encontrado nas velas de análise.")
                direcao = 'abortar_doji'
            else:
                # Padrão 1: Três Velas Iguais (v1, v2, v3)
                if v1['cor'] == v2['cor'] == v3['cor']:
                    if maior_menor == 'Minoria': # Reversão
                        direcao = 'put' if v1['cor'] == 'Verde' else 'call'
                        print(f">> Padrão 3 Velas: 3 Iguais ({v1['cor']}). Sinal: {direcao.upper()} (Minoria)")
                    else: # Maioria (Continuação)
                        direcao = 'call' if v1['cor'] == 'Verde' else 'put'
                        print(f">> Padrão 3 Velas: 3 Iguais ({v1['cor']}). Sinal: {direcao.upper()} (Maioria)")
                
                # Padrão 2: Duas Iguais + Reversão Forte (v2, v3 iguais, v1 diferente e forte)
                elif v2['cor'] == v3['cor'] and v1['cor'] != v2['cor']:
                    # Verifica se v1 é um Engolfo ou Harami de reversão
                    engolfo = (v1['cor'] == 'Verde' and v1['close'] > v2['open'] and v1['open'] < v2['close']) or \
                              (v1['cor'] == 'Vermelha' and v1['open'] > v2['close'] and v1['close'] < v2['open'])
                    harami = (v1['cor'] == 'Verde' and v1['open'] > v2['close'] and v1['close'] < v2['open']) or \
                             (v1['cor'] == 'Vermelha' and v1['close'] > v2['open'] and v1['open'] < v2['close'])
                    
                    if engolfo or harami: # Considera reversão forte
                        if maior_menor == 'Minoria': # Segue a vela de reversão (v1)
                            direcao = 'call' if v1['cor'] == 'Verde' else 'put'
                            print(f">> Padrão 3 Velas: Reversão Forte ({'Engolfo' if engolfo else 'Harami'} {v1['cor']}). Sinal: {direcao.upper()} (Minoria)")
                        else: # Maioria (Aposta contra a reversão forte)
                            direcao = 'put' if v1['cor'] == 'Verde' else 'call'
                            print(f">> Padrão 3 Velas: Reversão Forte ({'Engolfo' if engolfo else 'Harami'} {v1['cor']}). Sinal: {direcao.upper()} (Maioria)")
                    else: # Reversão fraca, não opera
                         print(f">> Padrão 3 Velas: Reversão Fraca (Vela {v1['cor']} não é Engolfo/Harami). Abortando.")
                         direcao = 'abortar_fraco'
                else:
                    # Outras combinações (ex: VVR, VRV) - Não opera por padrão
                    print(f">> Padrão 3 Velas: Combinação não identificada ({v3['cor'][0]}{v2['cor'][0]}{v1['cor'][0]}). Abortando.")
                    direcao = 'abortar_outro'

            # --- Fim da Lógica --- 

            # Verificação de tendência obrigatória
            if direcao == 'put' or direcao == 'call':
                if direcao == tendencia and confirmada:
                    print(f"Confirmação de Tendência OK: Sinal={direcao.upper()}, Tendência={tendencia.upper()}, RSI Confirmado={confirmada}")
                    pass
                else:
                    if direcao != tendencia:
                        print(f'>> Entrada abortada - Contra Tendência. Sinal: {direcao.upper()}, Tendência: {tendencia.upper()}')
                    else:
                        print(f'>> Entrada abortada - Tendência não confirmada por RSI (Média:{tendencia.upper()}, RSI Confirmado:{confirmada}).')
                    direcao = 'abortar_tendencia'

            if direcao == 'put' or direcao == 'call':
                stat, tipo_op = verifica_payouts(par)
                if stat:
                    compra(par, valor_entrada, direcao, 1, tipo_op)
                else:
                    if tipo_op == 'FECHADO':
                        print('\n>> Par Fechado, iniciarei uma nova análise')
                    if tipo_op == 'abaixo':
                        print('\n>> Par abaixo do payout mínimo configurado, iniciarei uma nova análise')
            else:
                # Mensagens de aborto já impressas na lógica ou na verificação de tendência
                time.sleep(2)

            print(green + '\n*****************************************************************************************\n\n')
            # A recatalogação agora acontece no início do próximo loop da função automatico()
            break # Sai do loop da estratégia para permitir a recatalogação


### Função para escolher par manualmente ###
def manual():
    global par, cifrao

    while True:
        par = input(Fore.GREEN+'\n>> Digite o par que deseja operar: '+ Fore.WHITE).upper()
        if par in ACTIVES:
            print(Fore.GREEN+'\n>> Par selecionado: '+ Fore.WHITE+ par)
            break
        else:
            print(Fore.RED+'>> Par inválido ou indisponível.')

    # cifrao já definido globalmente
    # cifrao = API.get_currency()

    while True:
        # Verifica filtro de horário ANTES de mostrar estratégias
        if verificar_horario_bloqueado():
            time.sleep(30) # Espera 30s antes de verificar novamente
            continue # Volta para o início do loop de espera do modo manual

        escolha_estrategia = input(Fore.GREEN+'\n>> Escolha a estratégia:\n'+
                                   Fore.WHITE+' 1 - MHI 1 Minoria\n'+
                                   Fore.WHITE+' 2 - MHI 1 Maioria\n'+
                                   Fore.WHITE+' 3 - MHI 2 Minoria\n'+
                                   Fore.WHITE+' 4 - MHI 2 Maioria\n'+
                                   Fore.WHITE+' 5 - MHI 3 Minoria\n'+
                                   Fore.WHITE+' 6 - MHI 3 Maioria\n'+
                                   Fore.WHITE+' 7 - Milhão Minoria\n'+
                                   Fore.WHITE+' 8 - Milhão Maioria\n'+
                                   Fore.WHITE+' 9 - Padrão 3 Velas Minoria (Refinado)\n'+
                                   Fore.WHITE+' 10 - Padrão 3 Velas Maioria (Refinado)\n'+
                                   Fore.GREEN+'--> '+ Fore.WHITE)
        try:
            escolha_estrategia = int(escolha_estrategia)
            if 1 <= escolha_estrategia <= 10:
                if escolha_estrategia == 1: estrategia_mhi('um', 'Minoria')
                elif escolha_estrategia == 2: estrategia_mhi('um', 'Maioria')
                elif escolha_estrategia == 3: estrategia_mhi('dois', 'Minoria')
                elif escolha_estrategia == 4: estrategia_mhi('dois', 'Maioria')
                elif escolha_estrategia == 5: estrategia_mhi('tres', 'Minoria')
                elif escolha_estrategia == 6: estrategia_mhi('tres', 'Maioria')
                elif escolha_estrategia == 7: estrategia_milhao('Minoria')
                elif escolha_estrategia == 8: estrategia_milhao('Maioria')
                elif escolha_estrategia == 9: estrategia_padrao_3_velas('Minoria')
                elif escolha_estrategia == 10: estrategia_padrao_3_velas('Maioria')
                # No modo manual, após executar uma vez, ele sai da função
                break 
            else:
                print(Fore.RED + '>> Opção inválida.')
        except ValueError:
            print(Fore.RED + '>> Entrada inválida. Digite um número.')


### Função principal ###
while True:
    modo = input(Fore.GREEN+'\n>> Escolha o modo de operação:\n'+
                   Fore.WHITE+' 1 - Manual (Escolher par e estratégia)\n'+
                   Fore.WHITE+' 2 - Automático (Catalogação)\n'+
                   Fore.GREEN+'--> '+ Fore.WHITE)
    try:
        modo = int(modo)
        if modo == 1:
            manual()
            # Após operação manual, pergunta se quer continuar
            cont = input(Fore.YELLOW + "\nDeseja realizar outra operação manual? (S/N): " + Fore.WHITE).upper()
            if cont != 'S':
                break # Sai do loop principal se não quiser continuar
        elif modo == 2:
            automatico()
            break # Sai do loop principal após modo automático (que tem seu próprio loop interno)
        else:
            print(Fore.RED + '>> Opção inválida.')
    except ValueError:
        print(Fore.RED + '>> Entrada inválida. Digite um número.')

print(yellow + "\nBot finalizado.")

