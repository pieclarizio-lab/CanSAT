#region import
from machine import Pin, I2C
import time
from MPU6050 import MPU6050
import math
#endregion

class SensoreMPU6050:

    #region 1) Costruttore
    def __init__(
            self,
            id_i2c: int = 0,
            pin_scl: int = 17,
            pin_sda: int = 16,
            indirizzo: int = 0x68,
            alpha: float = 0.7,
            offset: dict[str, float] | None = None
            ) -> None:

        # inizializzazione variabili protette
        self._indirizzo: int = indirizzo
        self._mpu: MPU6050| None = None
        self._connesso: bool = False

        # inizializzazione variabili media EMA
        self._alpha: float = alpha

        self._acc_filtrate: dict[str, float | None] = {
            "x": None,
            "y": None,
            "z": None
        }

        # inizializzazione offset
        if offset is None:
            self._offset = {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0
            }

        else:
            self._offset = offset

        # inizializzazione parametri trigger caduta libera
        self._caduta_libera: bool = False
        self._soglia_caduta: float = 2.0 # 2 m/s^2 (circa 0.2 g)
        self._cicli_consecutivi_target: int = 5
        self._contatore_caduta_libera: int = 0

        # inizializzazione I2C
        try:
            self._i2c = I2C(id_i2c, scl=Pin(pin_scl), sda=Pin(pin_sda), freq=400000)

            self._mpu = MPU6050(i2c=self._i2c, addr=self._indirizzo)

            # azzeramento offset
            self._mpu.offset_x = self._offset["x"]
            self._mpu.offset_y = self._offset["y"]
            self._mpu.offset_z = self._offset["z"]

            self._connesso = True
            print("[OK] Sensore MPU6050 inizializzato correttamente")

        except Exception as e:
            self._connesso = False
            print(f"[ERRORE] Impossibile comunicare con MPU6050 via i2c: {e}")

        #endregion


    #region 2) Metodi Principali
    def calibra_offset(self, campioni: int = 50) -> bool:

        """
        Calibra offset iniziale del sensore
        """

        # controllo di sicurezza
        if not self._connesso or self._mpu is None:
            print(f"[ERRORE] Impossibile connettersi al sensore MPU6050 {self}")
            return False


        somma_offset: dict[str, float] = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }

        try:
            print(f"... Calibrazione offset in corso: {campioni} campioni")

            for _ in range(campioni):
                dati = self._mpu.read_accel_data(g=False)

                somma_offset["x"] += dati["x"]
                somma_offset["y"] += dati["y"]
                somma_offset["z"] += dati["z"]

                time.sleep_ms(20)

            self._offset["x"] = somma_offset["x"] / campioni
            self._offset["y"] = somma_offset["y"] / campioni
            self._offset["z"] = somma_offset["z"] / campioni - 9.80665

            self._mpu.offset_x = self._offset["x"]
            self._mpu.offset_y = self._offset["y"]
            self._mpu.offset_z = self._offset["z"]

            print(f"-> Calibrazione completata")
            return True

        except Exception as e:
            print(f"[ERRORE] Impossibile calibrare offset: {e}")
            return False


    def lettura_dati(self) -> dict[str, float]:

        """
        Lettura dati tramite filtro EMA
        """

        # dizionario fallback
        dati_fallback: dict[str, float] = {
            "x": -999.0,
            "y": -999.0,
            "z": -999.0,
            "magnitudo": -999.0
        }

        # controllo di sicurezza
        if not self._connesso or self._mpu is None:
            print(f"[ERRORE] Impossibile connettersi al sensore MPU6050 {self}")
            return dati_fallback

        # lettura dati
        try:
            dati_grezzi = self._mpu.read_accel_data(g=False)

            for asse in ("x", "y", "z"):
                self._acc_filtrate[asse] = self._calcola_ema(
                    dati_grezzi[asse],
                    self._acc_filtrate[asse],
                    self._alpha
                )

            # variabili da restituire
            ax = self._acc_filtrate["x"] or 0.0
            ay = self._acc_filtrate["y"] or 0.0
            az = self._acc_filtrate["z"] or 0.0

            magnitudo = math.sqrt(ax**2 + ay**2 + az**2)

            return {
                "x": ax,
                "y": ay,
                "z": az,
                "magnitudo": magnitudo
            }

        except Exception as e:
            print(f"[ERRORE] Impossibile leggere il sensore: {e}")
            return dati_fallback


    def check_caduta_libera(self, magnitudo: float) -> bool:

        """
        Verifica caduta libera quando g = 0
        """

        # controllo di sicurezza
        if not self._connesso or self._mpu is None:
            print(f"[ERRORE] Impossibile connettersi al sensore MPU6050 {self}")
            return False

        # failsafe magnitudo anomala failback
        if magnitudo < 0.0:
            print(f"[ERRORE] anomalia failback con magnitudo < 0")
            return False

        if magnitudo < self._soglia_caduta:
            self._contatore_caduta_libera += 1

            if self._contatore_caduta_libera >= self._cicli_consecutivi_target:
                self._caduta_libera = True
                print("< sonda in caduta libera >")
                return True

        else:
            self._contatore_caduta_libera = 0

        return False


    def rileva_impatto(self, magnitudo: float) -> bool:

        # controllo di sicurezza
        if not self._connesso or self._mpu is None:
            print(f"[ERRORE] Impossibile connettersi al sensore MPU6050 {self}")
            return False

        # failsafe magnitudo anomala failback
        if magnitudo < 0.0:
            return False

        return magnitudo >= 20.0

    #endregion


    #region 3) Getter / Properties
    def is_connesso(self) -> bool:
        return self._connesso

    def is_caduta_libera(self) -> bool:
        return self._caduta_libera

    def get_offset(self) -> dict[str, float]:
         return self._offset

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