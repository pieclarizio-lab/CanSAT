#region import
from machine import Pin, SPI
import os
import sdcard
#endregion

class DataloggerSD:

    #region 1) Costruttore
    def __init__(
            self,
            id_spi: int = 1,          # Il Pico ha SPI(0) e SPI(1)
            pin_sck: int = 10,
            pin_mosi: int = 11,
            pin_miso: int = 8,
            pin_cs: int = 9,
            prefisso_file: str = "volo"
            ) -> None:

        # inizializzazione variabili protette
        self._connesso: bool = False
        self._nome_file: str = ""
        self._file = None

        try:
            # 1. inizializzazione bus SPI (freq = 1 MHz)
            self._spi = SPI(
                id_spi,
                baudrate = 1000000,
                polarity = 0,
                phase = 0,
                sck = Pin(pin_sck),
                mosi = Pin(pin_mosi),
                miso = Pin(pin_miso)
            )

            # 2. inizializzazione Pin Chip Select (CS)
            self._cs = Pin(pin_cs, Pin.OUT)

            # 3. Mount del File System della MicroSD
            self._sd = sdcard.SDCard(self._spi, self._cs)

            os.mount(self._sd, '/sd')

            print("[OK] MicroSD montata con successo")
            self._connesso = True

            # 4. trova il nome file e inizializza
            self._nome_file = self._trova_nome_disponibile(prefisso_file)
            self._inizializza_file()

        except Exception as e:
            print(f"[ERRORE] Impossibile inizializzare MicroSD: {e}")
            self._connesso = False

        #endregion


    #region 2) Metodi Principali
    def _trova_nome_disponibile(self, prefisso: str) -> str:

        """
        Scansiona la SD e restituisce il primo nome file disponibile.
        Es. se esiste volo_01.csv, restituisce /sd/volo_02.csv
        """

        for i in range(1, 1000):
            nome_test = f"/sd/{prefisso}_{i:02d}.csv"

            try:
                os.stat(nome_test) # lancia errore se il file non esiste
            except OSError:
                return nome_test

        # fallback se ci sono 999 file
        return f"/sd/{prefisso}_999.csv"


    def _inizializza_file(self) -> None:
        """
        Crea il file se non esiste, o lo sovrascrive, inserendo
        l'intestazione (Header) delle colonne CSV.
        """

        if not self._connesso:
            return

        try:
            # apertura file in modalità 'w'
            self._file = open(self._nome_file, 'w')

            # intestazione colonne
            header = (
            "Tempo_ms,"
            "Stato,"
            "Altitudine_m,"
            "Temperatura_C,"
            "Pressione_hPa,"
            "Umidita_pct,"
            "AccX_ms2,"
            "AccY_ms2,"
            "AccZ_ms2,"
            "Magnitudo_ms2\n"
            )

            self._file.write(header)

            # forza la scrittura sulla memoria fisica
            self._file.flush()

            print(f"[OK] file {self._nome_file} creato con intestazione")

        except Exception as e:
            print(f"[ERRORE] Impossibile creare il file: {e}")
            self._connesso = False


    def scrivi_telemetria(
            self,
            tempo_ms: int,
            stato_volo: str,
            dati_bme: dict[str, float],
            dati_mpu: dict[str, float],
            ) -> bool:

        """
        Formatta i dati dei sensori in una stringa CSV e li salva
        """

        # controllo di sicurezza
        if not self._connesso or self._file is None:
            return False

        try:
            # costruzione riga CSV (formattazione a 2 decimali)
            riga = (
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

            # scrittura sul buffer
            self._file.write(riga)
            self._file.flush()

            return True

        except Exception as e:
            self._connesso = False
            print(f"[ERRORE] scrittura su SD fallita. Modulo disabilitato: {e}")
            return False


    def chiudi_file(self) -> None:

        """
        Chiusura file in sicurezza dopo l'atterragio
        """

        if self._connesso and self._file is not None:
            try:
                self._file.close()
                os.umount('/sd')
                self._connesso = False
                print("[OK] file chiuso e MicroSD smontata in sicurezza")
            except Exception as e:
                print(f"[ERRORE] smontaggio SD fallito: {e}")

    #endregion


    #region 3) Getter
    def is_connesso(self) -> bool:
        return self._connesso

    #endregion