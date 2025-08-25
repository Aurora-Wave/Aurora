"""
interval_extractor.py
--------------------
Utilidad para extraer intervalos de eventos (coms y tilt) desde los comentarios de señales fisiológicas.
"""


def extract_event_intervals(signals, coms=None):
    """
    Extrae intervalos de eventos (coms y tilt) desde una lista de señales.
    Args:
        signals (list): Lista de objetos Signal, cada uno con MarkerData.
        coms (list): Palabras clave para eventos generales (ej: ['Tilt', 'Stand', ...])
    Returns:
        list[dict]: Lista de intervalos detectados, sin duplicados.
    """
    if coms is None:
        coms = ["Tilt", "Stand", "Hyperventilation", "Valsalva"]
    intervalos = []
    seen = set()
    # Estado para intervalos generales
    en_intervalo = False
    t_baseline = None
    evento = None
    t_evento = None
    t_recovery = None
    # Estado para tilt (independiente)
    en_tilt = False
    t_tilt_angle = None
    nombre_tilt = None

    for sig in signals:
        for marker in getattr(sig, "MarkerData", []):
            texto = getattr(marker, "text", "") or ""
            tiempo = getattr(marker, "time", None)
            # Detección de tilt: independiente de otros eventos
            if (not en_tilt) and ("tilt angle" in texto.lower()):
                en_tilt = True
                t_tilt_angle = tiempo
                nombre_tilt = texto
            elif en_tilt and texto.strip().lower() == "tilt down":
                key = (nombre_tilt, t_tilt_angle, tiempo, "tilt_angle")
                if key not in seen:
                    intervalos.append(
                        {
                            "evento": nombre_tilt,
                            "t_evento": t_tilt_angle,
                            "t_tilt_down": tiempo,
                            "tipo": "tilt_angle",
                        }
                    )
                    seen.add(key)
                en_tilt = False
                t_tilt_angle = None
                nombre_tilt = None
            # Intervalos generales Baseline -> evento coms -> Recovery
            if not en_intervalo and texto.strip().lower() == "baseline":
                en_intervalo = True
                t_baseline = tiempo
                evento = None
                t_evento = None
            elif en_intervalo:
                if any(c.lower() in texto.lower() for c in coms):
                    evento = texto
                    t_evento = tiempo
                if texto.strip().lower() == "recovery" and evento is not None:
                    t_recovery = tiempo
                    key = (evento, t_baseline, t_evento, t_recovery, "coms")
                    if key not in seen:
                        intervalos.append(
                            {
                                "t_baseline": t_baseline,
                                "evento": evento,
                                "t_evento": t_evento,
                                "t_recovery": t_recovery,
                                "tipo": "coms",
                            }
                        )
                        seen.add(key)
                    en_intervalo = False
                    t_baseline = None
                    evento = None
                    t_evento = None
                    t_recovery = None
    return intervalos