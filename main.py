# FSM - FINITE STATE MACHINE



#region FASE 1) Importazioni e Definizione Stati

#region import
import time
from machine import Pin

from Classi.SensoreBME280 import SensoreBME280
from Classi.SensoreMPU6050 import SensoreMPU6050
from Classi.DataloggerSD import DataloggerSD
from Classi.TrasmettitoreWiFi import TrasmettitoreWiFi
from Classi.Led import Led
#endregion

#region alfabeto macchina a stati
STATO_SETUP: str = "SETUP"
STATO_ATTESA: str = "ATTESA"
STATO_ASCESA: str = "ASCESA"
STATO_APOGEO: str = "APOGEO"
STATO_CADUTA_LIBERA: str = "CADUTA_LIBERA"
STATO_DISCESA: str = "DISCESA"
STATO_ATTERRATO: str = "ATTERRATO"
#endregion

# inizializzazione variabili flusso del programma e di supporto
stato_corrente: str = STATO_SETUP

altitudine_base: float = 0.0
altitudine_max:float = 0.0

#endregion



#region FASE 2) Inizializzazione Hardware
print("\n--- INIZIO SEQUENZA DI BOOT ---\n")

# 1. feedback visivo accensione led
led_pico = Led("LED")
led_pico.accensione_led()


#region 2. istanziazione degli oggetti
print("Inizializzazione MPU6050...")
mpu = SensoreMPU6050()

print("Inizializzazione BME280...")
bme = SensoreBME280()

print("Inizializzazione Datalogger SD...")
sd = DataloggerSD()

print("Inizializzazione Wi-Fi...")
wifi = TrasmettitoreWiFi("ssid", "password", "IP")
#endregion


# 3. calibrazione Pre-Volo e Sensor Fusion
mpu.calibra_offset()

# calibrazione quota zero
print("Acquisizione altitudine base per Sensor Fusion...")
try:
    # aggiorna P_0 del sensore
    bme.calibra_altitudine_zero()

    # calcolo altitudine
    dati_bme = bme.lettura_dati()

    altitudine_base = dati_bme["altitudine"]
    altitudine_max = altitudine_base

except Exception as e:
    print(f"[AVVISO] Impossibile leggere il  BME280 durante il boot: {e}")


# 4. conclusione del setup e cambio stato
stato_corrente = STATO_ATTESA

# feedback visivo cambio stato. Sonda armata pronta per il lancio
print(f"\n--- BOOT COMPLETATO. STATO ATTUALE: {stato_corrente} ---")
print(f"\n--- ALTITUDINE BASE REGISTRATA: {altitudine_base:.2f} m ---")

led_pico.lampeggio_bloccante(5, 500)
led_pico.accensione_led()

#endregion



#region FASE 3) Setup del Ciclo di Volo

# inizializzazione frequenza ciclo (20 Hz = 20 cicli al secondo)
frequenza_hz = 20
intervallo_ms = 1000 // frequenza_hz  # Risultato: 50 ms

ultimo_aggiornamento = time.ticks_ms()

print(f"\n--- INIZIO MISSIONE ({frequenza_hz} Hz) ---\n")

#endregion



#region FASE 4) Ciclo Infinito e Macchina a Stati

try:
    while True:
        tempo_attuale = time.ticks_ms()

        # 1. controllo del tempo (timing non bloccante)
        tempo_passato = time.ticks_diff(tempo_attuale, ultimo_aggiornamento)

        if tempo_passato >= intervallo_ms:
            ultimo_aggiornamento = tempo_attuale

            # 2. campionamento sensori
            dati_bme = bme.lettura_dati()
            dati_mpu = mpu.lettura_dati()

            # 3. registrazione e trasmissione (scatola nera)
            sd.scrivi_telemetria(
                tempo_ms = tempo_attuale,
                stato_volo = stato_corrente,
                dati_bme = dati_bme,
                dati_mpu = dati_mpu
                )
            wifi.invia_telemetria(
                tempo_ms = tempo_attuale,
                stato_volo = stato_corrente,
                dati_bme = dati_bme,
                dati_mpu = dati_mpu
            )

            # 4. macchina a stati (FSM)

            if stato_corrente == STATO_ATTESA:
                # condizione di lancio: rilevamento forte accelerazione o maggiore quota
                if dati_mpu["magnitudo"] > 15.0 or (dati_bme["altitudine"] > altitudine_base + 2):
                    stato_corrente = STATO_ASCESA
                    print("[EVENTO] Decollo rilevato! Inizio ascesa.")

            elif stato_corrente == STATO_ASCESA:
                # rilevamento altitudine massima
                alt_attuale = dati_bme["altitudine"]
                if alt_attuale > altitudine_max:
                    altitudine_max = alt_attuale

                # condizione di apogeo
                elif alt_attuale < (altitudine_max - 2.0):
                    stato_corrente = STATO_APOGEO
                    print(f"[EVENTO] Apogeo raggiunto a {altitudine_max:.2f}m. Inizio discesa.")

            elif stato_corrente == STATO_APOGEO:
                # conferma dell'accelerometro della caduta libera
                if mpu.check_caduta_libera(dati_mpu["magnitudo"]):
                    stato_corrente = STATO_CADUTA_LIBERA

            elif stato_corrente == STATO_CADUTA_LIBERA:
                print("[EVENTO] Caduta libera confermata. Paracadute dispiegato.")
                stato_corrente = STATO_DISCESA

            elif stato_corrente == STATO_DISCESA:

                # verifica dell'atterraggio

                if dati_bme["altitudine"] < (altitudine_max - 3):
                    impatto = mpu.rileva_impatto(dati_mpu["magnitudo"])
                else:
                    impatto = False

                quota_stabile = bme.rileva_stabilita_quota(dati_bme["altitudine"])

                if impatto or quota_stabile:
                    stato_corrente = STATO_ATTERRATO

            elif stato_corrente == STATO_ATTERRATO:
                print("[EVENTO] Touchdown! Missione conclusa.")
                break

except KeyboardInterrupt:
    # blocco manuale del programma tramite VSCode (Ctrl + C)
    print("\n[AVVISO] Interruzione manuale da terminale.")

except Exception as e:
    print(f"\n[ERRORE] Crash nel ciclo principale: {e}")

#endregion



#region FASE 5) Shutdown e Recupero (Safe Mode)
finally:
    print("\n--- INIZIO PROCEDURA DI SPEGNIMENTO ---\n")

    sd.chiudi_file()
    wifi.chiudi_connessione()

    print("--- SISTEMA SPENTO. DATI AL SICURO. ---")

#endregion