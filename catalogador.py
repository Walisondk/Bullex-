from iqoptionapi.stable_api import IQ_Option
import time
from configobj import ConfigObj
import sys
from datetime import datetime
from tabulate import tabulate
from iqoptionapi.constants import ACTIVES
import pandas as pd
import numpy as np

def catag(all_asset,API):
    global analise_result, pares_abertos

    quantidade_catalogacao = 21
    
    payout = 80
    payout = float((payout)/100)


    conf = ConfigObj("config.txt", encoding="UTF-8", list_values=False) 
    if conf['MARTINGALE']['usar_martingale'] == 'S':
        if int(conf['MARTINGALE']['niveis_martingale']) == 0:
            linha = 2
        if int(conf['MARTINGALE']['niveis_martingale']) == 1:
            linha = 3
        if int(conf['MARTINGALE']['niveis_martingale']) >= 2:
            linha = 4
        martingale = int(conf['MARTINGALE']['niveis_martingale'])
    else:
        linha =2
        martingale = 0


    ############# CAPTURA PARES ABERTOS ##############

    pares_abertos = []
    pares_abertos_turbo = []
    pares_abertos_digital = []


    if all_asset == '':
        all_asset = API.get_all_open_time()

    # Limpar as listas antes de preenchê-las
    pares_abertos.clear()
    pares_abertos_turbo.clear()
    pares_abertos_digital.clear()

    for par in all_asset['digital']:
        if all_asset['digital'][par]['open'] == True:
            if par in ACTIVES: 
                pares_abertos.append(par)
                pares_abertos_digital.append(par)

    for par in all_asset['turbo']:
        if all_asset['turbo'][par]['open'] == True:
            if par in ACTIVES: 
                if par not in pares_abertos:
                    pares_abertos.append(par)

    # Remover pares problemáticos ou indesejados
    pares_remover = ['USOUSD', 'USDCHF', 'XAUUSD']
    pares_abertos = [p for p in pares_abertos if p not in pares_remover]
    pares_abertos_digital = [p for p in pares_abertos_digital if p not in pares_remover]

    print(f"Total de pares abertos: {len(pares_abertos)}")

    def convert(x):
        x1 =  datetime.fromtimestamp(x)
        return x1.strftime('%H:%M')


    hora =  API.get_server_timestamp()
    vela = {}
    for par in pares_abertos:
        vela[par] = {}
        # Aumentar a quantidade de velas para garantir dados suficientes para todas as estratégias
        data = API.get_candles(par, 60, 1500, hora) # Aumentado para 1500 velas
        vela[par] = data


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

    def calcula_resultado(par,nome_estrategia,dicio):
        global  analise_result
        dici = dicio

        win = dici['win']
        gale1 = dici['g1']
        gale2 = dici['g2']
        loss =  dici['loss']
        

        todasentradas = win + gale1 + gale2 + loss
      
        win_perc = 0
        gale1_perc = 0
        gale2_perc = 0

        if todasentradas != 0:
            win_perc = round(win/(todasentradas)*100,2)
            gale1_perc = round((win + gale1)/(todasentradas)*100,2)
            gale2_perc = round((win + gale1 + gale2)/(todasentradas)*100,2)

        
        analise_result.append([nome_estrategia]+[par] +[win_perc]+[gale1_perc] +[gale2_perc])

    def contabiliza_resultado(dir,entrada, dici_result):
        global martingale
        numero = 0
        while True:
            # Verifica se a chave existe antes de acessá-la
            if str(numero+1) not in entrada:
                # Se a vela de entrada não existir (fim dos dados), conta como loss
                dici_result['loss'] += 1
                break

            if dir == entrada[str(numero+1)]:
                if numero == 0:
                    dici_result['win'] +=1
                    break
                elif numero == 1 :
                    dici_result['g1'] +=1
                    break
                elif numero == 2 :
                    dici_result['g2'] +=1
                    break
            else:
                # Se a direção for diferente e atingiu o limite de gales, é loss
                if numero == martingale:
                    dici_result['loss'] +=1
                    break
            
            numero +=1
            # Adiciona verificação para não exceder o número máximo de gales + 1 (entrada original)
            if numero > martingale:
                dici_result['loss'] += 1 # Considera loss se exceder os gales
                break

        return dici_result                       

    # --- Funções de Estratégia (MHI1, MHI2, MHI3, Milhão) --- 
    def MHI1(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue # Pula par sem dados
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 5 or minutos == 0:
                    try:
                        # Garante que há velas suficientes para análise e gales
                        if i < martingale + 2: continue 
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+1]['open'] < velas[i+1]['close'] else 'Vermelha' if velas[i+1]['open'] > velas[i+1]['close'] else 'Doji'

                        # Velas de entrada (até 3 para gales)
                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS' # Marca se não houver vela
                        
                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Vermelha'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Verde'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI1 para {par} no índice {i}")
                        continue # Pula para a próxima iteração se houver erro de índice
                    except Exception as e:
                        # print(f"Erro inesperado em MHI1 para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0: # Só calcula se houve entradas válidas
                calcula_resultado(par, 'MHI', dici_result)

    def MHI1_maioria(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 5 or minutos == 0:
                    try:
                        if i < martingale + 2: continue
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+1]['open'] < velas[i+1]['close'] else 'Vermelha' if velas[i+1]['open'] > velas[i+1]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Verde'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Vermelha'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI1_maioria para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em MHI1_maioria para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MHI MAIORIA', dici_result)

    def MHI2(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 6 or minutos == 1:
                    try:
                        if i < martingale + 3: continue # MHI2 usa vela i+4
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+4]['open'] < velas[i+4]['close'] else 'Vermelha' if velas[i+4]['open'] > velas[i+4]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Vermelha'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Verde'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI2 para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em MHI2 para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MHI2', dici_result)

    def MHI2_maioria(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 6 or minutos == 1:
                    try:
                        if i < martingale + 3: continue
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+4]['open'] < velas[i+4]['close'] else 'Vermelha' if velas[i+4]['open'] > velas[i+4]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Verde'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Vermelha'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI2_maioria para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em MHI2_maioria para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MHI2 MAIORIA', dici_result)

    def MHI3(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 7 or minutos == 2:
                    try:
                        if i < martingale + 4: continue # MHI3 usa vela i+5
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+5]['open'] < velas[i+5]['close'] else 'Vermelha' if velas[i+5]['open'] > velas[i+5]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+4]['open'] < velas[i+4]['close'] else 'Vermelha' if velas[i+4]['open'] > velas[i+4]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Vermelha'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Verde'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI3 para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em MHI3 para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MHI3', dici_result)

    def MHI3_maioria(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 7 or minutos == 2:
                    try:
                        if i < martingale + 4: continue
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+5]['open'] < velas[i+5]['close'] else 'Vermelha' if velas[i+5]['open'] > velas[i+5]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+4]['open'] < velas[i+4]['close'] else 'Vermelha' if velas[i+4]['open'] > velas[i+4]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        cores = vela1, vela2, vela3
                        dir = ''
                        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0 : dir = 'Verde'
                        if cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0 : dir = 'Vermelha'

                        if cores.count('Doji') > 0 or dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em MHI3_maioria para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em MHI3_maioria para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MHI3 MAIORIA', dici_result)

    def milhao(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 0:
                    try:
                        if i < martingale + 2: continue
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+1]['open'] < velas[i+1]['close'] else 'Vermelha' if velas[i+1]['open'] > velas[i+1]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        dir = ''
                        if vela1 == vela2 and vela2 == vela3 and vela1 != 'Doji':
                            if vela1 == 'Verde': dir = 'Vermelha'
                            if vela1 == 'Vermelha': dir = 'Verde'

                        if dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em milhao para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em milhao para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MILHAO', dici_result)

    def milhao_maioria(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada= 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 0:
                    try:
                        if i < martingale + 2: continue
                        
                        entrada= {}
                        vela3 = 'Verde' if velas[i+3]['open'] < velas[i+3]['close'] else 'Vermelha' if velas[i+3]['open'] > velas[i+3]['close'] else 'Doji'
                        vela2 = 'Verde' if velas[i+2]['open'] < velas[i+2]['close'] else 'Vermelha' if velas[i+2]['open'] > velas[i+2]['close'] else 'Doji'
                        vela1 = 'Verde' if velas[i+1]['open'] < velas[i+1]['close'] else 'Vermelha' if velas[i+1]['open'] > velas[i+1]['close'] else 'Doji'

                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        dir = ''
                        if vela1 == vela2 and vela2 == vela3 and vela1 != 'Doji':
                            if vela1 == 'Verde': dir = 'Verde'
                            if vela1 == 'Vermelha': dir = 'Vermelha'

                        if dir == '':
                            doji += 1
                        else:
                            qnt_entrada +=1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em milhao_maioria para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em milhao_maioria para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break 
            if qnt_entrada > 0:
                calcula_resultado(par, 'MILHAO MAIORIA', dici_result)

    # --- Novas Funções: Padrão 3 Velas (Refinado) --- 
    def padrao_3_velas(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada = 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                # Padrão 3 Velas pode ocorrer a qualquer momento, mas vamos verificar a cada 5 min para consistência
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 5 or minutos == 0: # Pode ajustar ou remover essa condição se necessário
                    try:
                        if i < martingale + 4: continue # Precisa de pelo menos 5 velas (i+1 a i+5)

                        entrada = {}
                        # Velas para análise do padrão
                        v = []
                        for j in range(5):
                            idx = i + j + 1
                            if idx < len(velas):
                                vela = velas[idx]
                                cor = 'Verde' if vela['open'] < vela['close'] else 'Vermelha' if vela['open'] > vela['close'] else 'Doji'
                                v.append({
                                    'open': vela['open'],
                                    'close': vela['close'],
                                    'high': vela['max'],
                                    'low': vela['min'],
                                    'cor': cor
                                })
                            else:
                                v.append(None)
                        
                        # Velas de entrada (até 3 para gales)
                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        dir = ''
                        # Verifica se temos velas suficientes para análise
                        if None in v[:3]:
                            continue
                            
                        # Verifica Dojis nas 3 velas de análise
                        if 'Doji' in [v[0]['cor'], v[1]['cor'], v[2]['cor']]:
                            doji += 1
                            continue
                            
                        # Padrão 1: Três Velas Iguais (v0, v1, v2)
                        if v[0]['cor'] == v[1]['cor'] == v[2]['cor']:
                            # Minoria (Reversão)
                            dir = 'Vermelha' if v[0]['cor'] == 'Verde' else 'Verde'
                        
                        # Padrão 2: Duas Iguais + Reversão Forte (v1, v2 iguais, v0 diferente e forte)
                        elif v[1]['cor'] == v[2]['cor'] and v[0]['cor'] != v[1]['cor']:
                            # Verifica se v0 é um Engolfo ou Harami de reversão
                            engolfo = (v[0]['cor'] == 'Verde' and v[0]['close'] > v[1]['open'] and v[0]['open'] < v[1]['close']) or \
                                    (v[0]['cor'] == 'Vermelha' and v[0]['open'] > v[1]['close'] and v[0]['close'] < v[1]['open'])
                            harami = (v[0]['cor'] == 'Verde' and v[0]['open'] > v[1]['close'] and v[0]['close'] < v[1]['open']) or \
                                    (v[0]['cor'] == 'Vermelha' and v[0]['close'] > v[1]['open'] and v[0]['open'] < v[1]['close'])
                            
                            if engolfo or harami: # Considera reversão forte
                                # Minoria (Segue a vela de reversão)
                                dir = v[0]['cor']

                        if dir == '':
                            doji += 1
                        else:
                            qnt_entrada += 1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em padrao_3_velas para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em padrao_3_velas para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break
            if qnt_entrada > 0:
                calcula_resultado(par, 'PADRAO_3_VELAS', dici_result)

    def padrao_3_velas_maioria(vela1):
        total = vela1
        for par in pares_abertos:
            velas = total[par]
            if not velas: continue
            velas.reverse()
            qnt_entrada = 0
            dici_result = {'win': 0, 'g1': 0, 'g2': 0, 'loss': 0}
            doji = 0

            for i in range(len(velas)):
                minutos = float(datetime.fromtimestamp(velas[i]['from']).strftime('%M')[1:])
                if minutos == 5 or minutos == 0: 
                    try:
                        if i < martingale + 4: continue

                        entrada = {}
                        # Velas para análise do padrão
                        v = []
                        for j in range(5):
                            idx = i + j + 1
                            if idx < len(velas):
                                vela = velas[idx]
                                cor = 'Verde' if vela['open'] < vela['close'] else 'Vermelha' if vela['open'] > vela['close'] else 'Doji'
                                v.append({
                                    'open': vela['open'],
                                    'close': vela['close'],
                                    'high': vela['max'],
                                    'low': vela['min'],
                                    'cor': cor
                                })
                            else:
                                v.append(None)
                        
                        # Velas de entrada (até 3 para gales)
                        for g in range(martingale + 1):
                            if i - g >= 0:
                                entrada[str(g+1)] = 'Verde' if velas[i-g]['open'] < velas[i-g]['close'] else 'Vermelha' if velas[i-g]['open'] > velas[i-g]['close'] else 'Doji'
                            else:
                                entrada[str(g+1)] = 'FIM_DADOS'

                        dir = ''
                        # Verifica se temos velas suficientes para análise
                        if None in v[:3]:
                            continue
                            
                        # Verifica Dojis nas 3 velas de análise
                        if 'Doji' in [v[0]['cor'], v[1]['cor'], v[2]['cor']]:
                            doji += 1
                            continue
                            
                        # Padrão 1: Três Velas Iguais (v0, v1, v2)
                        if v[0]['cor'] == v[1]['cor'] == v[2]['cor']:
                            # Maioria (Continuação)
                            dir = v[0]['cor']
                        
                        # Padrão 2: Duas Iguais + Reversão Forte (v1, v2 iguais, v0 diferente e forte)
                        elif v[1]['cor'] == v[2]['cor'] and v[0]['cor'] != v[1]['cor']:
                            # Verifica se v0 é um Engolfo ou Harami de reversão
                            engolfo = (v[0]['cor'] == 'Verde' and v[0]['close'] > v[1]['open'] and v[0]['open'] < v[1]['close']) or \
                                    (v[0]['cor'] == 'Vermelha' and v[0]['open'] > v[1]['close'] and v[0]['close'] < v[1]['open'])
                            harami = (v[0]['cor'] == 'Verde' and v[0]['open'] > v[1]['close'] and v[0]['close'] < v[1]['open']) or \
                                    (v[0]['cor'] == 'Vermelha' and v[0]['close'] > v[1]['open'] and v[0]['open'] < v[1]['close'])
                            
                            if engolfo or harami: # Considera reversão forte
                                # Maioria (Aposta contra a vela de reversão)
                                dir = 'Vermelha' if v[0]['cor'] == 'Verde' else 'Verde'

                        if dir == '':
                            doji += 1
                        else:
                            qnt_entrada += 1
                            dici_result = contabiliza_resultado(dir, entrada, dici_result)

                    except IndexError:
                        # print(f"IndexError em padrao_3_velas_maioria para {par} no índice {i}")
                        continue
                    except Exception as e:
                        # print(f"Erro inesperado em padrao_3_velas_maioria para {par}: {e}")
                        continue
                if qnt_entrada >= quantidade_catalogacao:
                    break
            if qnt_entrada > 0:
                calcula_resultado(par, 'PADRAO_3_VELAS_MAIORIA', dici_result)

    # --- Chamada das Funções de Catalogação --- 
    analise_result = []
    MHI1(vela)
    MHI1_maioria(vela)
    MHI2(vela)
    MHI2_maioria(vela)
    MHI3(vela)
    MHI3_maioria(vela)
    milhao(vela)
    milhao_maioria(vela)
    padrao_3_velas(vela)
    padrao_3_velas_maioria(vela)

    # --- Ordenação e Retorno --- 
    listaordenada = sorted(analise_result, key=lambda x: x[linha], reverse=True)

    return listaordenada, linha
