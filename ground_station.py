import socket
import datetime

# 1) CONFIGURAZIONE DI RETE

IP_ASCOLTO = "0.0.0.0" # 0.0.0.0 dice al PC di ascoltare su tutte le reti
PORTA_ASCOLTO = 5000 # stessa porta della classe TrasmettitoreWiFi


# 2) SETUP DEL SOCKET

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((IP_ASCOLTO, PORTA_ASCOLTO))

print("\n--- 🛰️  GROUND STATION ATTIVA 🛰️ ---\n")
print(f"In attesa di telemetria sulla porta {PORTA_ASCOLTO}...\n")


# 3) CICLO DI RICEZIONE (LIVE TELEMETRY)

try:
    while True:
        dati_grezzi, indirizzo_mittente = sock.recvfrom(1024)

        # decodifica byte in stringa leggibile
        messaggio = dati_grezzi.decode('utf-8')

        # feedback visivo di ricezione
        orario_ricezione = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # stampa dati a schermo
        ip_sonda = indirizzo_mittente[0]
        print(f"[{orario_ricezione}] da {ip_sonda} -> {messaggio}")

except KeyboardInterrupt:
    # blocco manuale del programma tramite VSCode (Ctrl + C)
    print("\n[AVVISO] Chiusura manuale della Ground Station.")

finally:
    # chiusura socket
    sock.close()
    print("\n--- Socket chiuso. Ricezione terminata ---")