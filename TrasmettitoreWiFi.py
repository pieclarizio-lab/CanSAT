#region import
import network
import socket
import time
#endregion

class TrasmettitoreWiFi:

    #region 1) Costruttore
    def __init__(
            self,
            ssid: str,
            password: str,
            ip_ground_station: str,
            porta_udp: int = 5000
            ) -> None:

        # inizializzazione variabili protette
        self._connesso: bool = False
        self._ip_target: str = ip_ground_station
        self._porta: int = porta_udp
        self._socket = None

        print(f"... Tentativo di connessione alla rete: {ssid}")

        # 1. inizializzazione dell'interfaccia di Rete (Modalità Station)
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)
        self._wlan.connect(ssid, password)

        # 2. time-out di sicurezza (10 sec.)
        tentativi = 0
        while not self._wlan.isconnected() and tentativi < 20:
            time.sleep_ms(500)
            tentativi += 1
            print(".", end="")

        print()

        # 3. valutazione connessione e apertura Socket UDP
        if self._wlan.isconnected():
            self._connesso = True
            indirizzo_ip_pico = self._wlan.ifconfig()[0]
            print(f"[OK] Wi-Fi connesso. IP Sonda: {indirizzo_ip_pico}")

            try:
                # Creazione del Socket UDP (AF_INET = IPv4, SOCK_DGRAM = UDP)
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                print(f"[OK] Socket UDP aperto verso {self._ip_target}:{self._porta}")

            except Exception as e:
                self._connesso = False
                print(f"[ERRORE] Impossibile creare il socket UDP: {e}")

        else:
            # spegnimento antenna se non c'è connessione
            self._connesso = False
            self._wlan.active(False)
            print("[ERRORE] time-out connessione Wi-Fi. Antenna disattivata")

    #endregion


    #region 2) Metodi Principali
    def invia_telemetria(
            self,
            tempo_ms: int,
            stato_volo: str,
            dati_bme: dict[str, float],
            dati_mpu: dict[str, float]
            ) -> bool:

        """
        Formatta i dati in CSV e li spara via UDP alla Ground Station.
        Non è bloccante: se fallisce, esce in modo silenzioso.
        """

        # failsafe
        if not self._connesso or self._socket is None:
            return False

        try:
            # costruzione riga CSV (formattazione a 2 decimali)
            riga_csv = (
                f"{tempo_ms},"
                f"{stato_volo},"
                f"{dati_bme['altitudine']:.2f},"
                f"{dati_bme['temperatura']:.2f},"
                f"{dati_bme['pressione']:.2f},"
                f"{dati_bme['umidita']:.2f},"
                f"{dati_mpu['x']:.2f},"
                f"{dati_mpu['y']:.2f},"
                f"{dati_mpu['z']:.2f},"
                f"{dati_mpu['magnitudo']:.2f}\n"
            )

            # invio pacchetto UDP (codificato in byte)
            self._socket.sendto(riga_csv.encode('utf-8'), (self._ip_target, self._porta))
            return True

        except Exception as e:
            self._connesso = False
            self._wlan.active(False)
            print(f"\n[ALLARME] connessione UDP persa in volo: {e} \nTelemetria disabilitata")
            return False


    def chiudi_connessione(self) -> None:

        """
        Termina la connessione dopo la fine della missione
        """

        if self._socket:
            try:
                self._socket.close()

            except:
                pass
        if self._wlan.isconnected():
            self._wlan.disconnect()
            self._wlan.active(False)

        self._connesso = False
        print("[OK] Wi-Fi disattivato in sicurezza")

    #endregion

    #region 3) Getter
    def is_connesso(self) -> bool:
        return self._connesso

    #endregion