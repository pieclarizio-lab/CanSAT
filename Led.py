#region import
from machine import Pin
import time
#endregion

class Led:

    #region 1) Costruttore
    def __init__(
            self,
            id: str | int,
            mode = Pin.OUT,
            value: int = 0
            ) -> None:

        # inizializzazione variabili
        self._id: str | int = id
        self._mode = Pin.OUT

        # inizializzazione led
        self._led = Pin(self._id, self._mode, value=value)

    #endregion

    #region 2) Metodi Principali
    def accensione_led(self):
        self._led(1)

    def spegnimento_led(self):
        self._led(0)

    def inverti_stato(self):
        self._led.toggle()

    def lampeggio_bloccante(self, n_lampeggi: int, t_lampeggio_ms: int):

        for _ in range(n_lampeggi * 2): # *2 per fare un ciclo On/Off completo
            self._led.toggle()
            time.sleep_ms(t_lampeggio_ms)

        self.spegnimento_led()

    #endregion

    #region 3) Getter
    def get_stato_led(self):
        return self._led.value()