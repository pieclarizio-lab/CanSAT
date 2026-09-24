#region import
from machine import Pin, I2C
import time
from BME280 import BME280
#endregion

class SensoreBME280:

    #region 1) Costruttore
    def __init__(
            self,
            id_i2c: int = 0,
            pin_scl: int = 17,
            pin_sda: int = 16,
            indirizzo: int = 0x76,
            alpha: float = 0.2
            ) -> None:

        # inizializzazione variabili protette
        self._indirizzo: int = indirizzo
        self._bme: BME280| None = None
        self._pressione_base: float = 0.0
        self._connesso: bool = False

        # inizializzazione variabili media EMA
        self._alpha: float = alpha

        self._temp_filtrata: float | None = None
        self._pres_filtrata:  float | None = None
        self._umi_filtrata:  float | None = None

        # inizializzazione variabili stabilità altitudine
        self._altitudine_precedente: float | None = None
        self._variazione_altitudine: float = 0.0
        self._cicli_stabilita: int = 0

        # inizializzazione I2C
        try:
            self._i2c = I2C(id_i2c, scl=Pin(pin_scl), sda=Pin(pin_sda), freq=400000)

            self._bme = BME280(i2c=self._i2c, address=self._indirizzo)

            self._connesso = True
            print("[OK] Sensore BME280 inizializzato correttamente")

        except Exception as e:
            self._connesso = False
            print(f"[ERRORE] Impossibile comunicare con BME280 via i2c: {e}")

    #endregion


    #region 2) Metodi Principali
    def calibra_altitudine_zero(self, campioni: int = 50) -> bool:

        """
        Calibra la P_0 e se la calibrazione è avvenuta con successo restituisce True
        """

        # controllo di sicurezza
        if not self._connesso or self._bme is None:
            print(f"[ERRORE] Impossibile connettersi al sensore BME280 {self}")
            return False

        somma_pressioni: float = 0.0
        try:
            print(f"... Calibrazione P_0 in corso: {campioni} campioni")

            for _ in range(campioni):
                pressione = (self._bme.read_pressure() // 256) / 100.0
                somma_pressioni += pressione
                time.sleep_ms(20)

            self._pressione_base = somma_pressioni / campioni
            print(f"-> Calibrazione completata: P_0 = {self._pressione_base:.2f} hPa")
            return True

        except Exception as e:
            print(f"[ERRORE] Impossibile calibrare P_0: {e}")
            return False

    def calcola_altitudine(self, pressione_attuale: float) -> float:

        """
        Applica la formula ipsometrica.
        Accetta una pressinoe float e restituisce l'altitudine
        """

        # failsafe se non è stata indicizzata la pressione base
        if self._pressione_base == 0.0: return 0.0

        # fomula ipsometrica
        altitudine: float = 44330.0 * (1.0 - (pressione_attuale / self._pressione_base) ** (1.0 / 5.225))

        return altitudine

    def lettura_dati(self) -> dict[str, float]:

        """
        Lettura dati tramite filtro EMA
        """

        # dizionario fallback
        dati_fallback: dict[str, float] = {
            "temperatura": -999.0,
            "pressione": -999.0,
            "umidita": -999.0,
            "altitudine": -999.0,
        }

        # controllo di sicurezza
        if not self._connesso or self._bme is None:
            print(f"[ERRORE] Impossibile connettersi al sensore BME280 {self}")
            return dati_fallback

        # lettura dati
        try:
            temp_grezza = self._bme.read_temperature() / 100.0
            pres_grezza = (self._bme.read_pressure() // 256) / 100.0
            umi_grezza = self._bme.read_humidity() / 1024.0

            self._temp_filtrata = self._calcola_ema(temp_grezza, self._temp_filtrata, self._alpha)
            self._pres_filtrata = self._calcola_ema(pres_grezza, self._pres_filtrata, self._alpha)
            self._umi_filtrata = self._calcola_ema(umi_grezza, self._umi_filtrata, self._alpha)

            altitudine = self.calcola_altitudine(self._pres_filtrata)

            return {
                "temperatura": self._temp_filtrata,
                "pressione": self._pres_filtrata,
                "umidita": self._umi_filtrata,
                "altitudine": altitudine,
            }

        except Exception as e:
            print(f"[ERRORE] Impossibile leggere il sensore: {e}")
            return dati_fallback


    def rileva_stabilita_quota(self, altitudine_attuale) -> bool:

        """
        Restituisce True se l'altitudine non cambia da 2 secondi
        """

        # controllo di sicurezza
        if not self._connesso or self._bme is None:
            print(f"[ERRORE] Impossibile connettersi al sensore BME280 {self}")
            return False

        # prima iterazione del ciclo
        if not self._altitudine_precedente:
            self._altitudine_precedente = altitudine_attuale

        # logica
        variazione = abs(altitudine_attuale - self._altitudine_precedente)

        if variazione < 0.3:
            self._cicli_stabilita += 1
        else:
            self._cicli_stabilita = 0

        self._altitudine_precedente = altitudine_attuale

        return self._cicli_stabilita >= 40

    #endregion


    #region 3) Getter / Properties
    def is_connesso(self) -> bool:
        return self._connesso


    def get_pressione_base(self) -> float:
        return self._pressione_base

    #endregion


    #region 4) Static Methods / Helper Functions
    @staticmethod
    def _calcola_ema(
        dato_grezzo: float,
        valore_precedente: float | None,
        alpha: float
        ) -> float:

        if valore_precedente is None:
            y = dato_grezzo
        else:
            y = (alpha * dato_grezzo) + ((1 - alpha) * valore_precedente)

        return y

    #endregion