# 03 · Motor financiero

El motor financiero está centralizado en `app/services/financial.py` y es
independiente de la interfaz. Toda regla que afecta capital, interés, saldo o
vencimiento debe mantenerse aquí para ser determinística y testeable.

## 1. Cálculo del plan de pagos

El sistema soporta dos modalidades de amortización, configuradas en `app/services/financial.py`:

### 1.1 Amortización francesa (cuota fija)
La cuota periódica total es constante a lo largo del crédito:

```
i = tasa_periodo  (por ejemplo 0.20 para 20% por cuota)
cuota = principal × i / (1 − (1 + i)^(−n))
```

Para cada cuota `k`:
```
interés_k   = saldo_{k−1} × i
capital_k   = cuota − interés_k
saldo_k     = saldo_{k−1} − capital_k
```

### 1.2 Amortización alemana (capital fijo)
La amortización a capital es constante y la cuota total es decreciente:

```
capital_fijo = principal / n
interés_k    = saldo_{k−1} × i
cuota_k      = capital_fijo + interés_k
saldo_k      = saldo_{k−1} − capital_fijo
```

En la última cuota de ambos sistemas se ajusta el capital exactamente al saldo remanente para cerrar la amortización sin residuos de centavos. Todos los cálculos se efectúan mediante tipos `Decimal` con redondeo `ROUND_HALF_UP` a 2 decimales (`money()`).

### 1.3 Tasa por período
La tasa de interés se gestiona como porcentaje por período de cuota (leída desde el parámetro `tasa_interes_periodo`, por defecto `20%`). De este modo, si la cuota es quincenal o mensual, se aplica directamente sobre el saldo sin conversiones anuales artificiales.

## 2. Aplicación de pagos (transaccional y dinámica)

Al registrar un pago sobre un crédito, el valor se distribuye transaccionalmente entre las obligaciones pendientes ordenadas por fecha de vencimiento y número (la más antigua primero).

### 2.1 Orden de imputación configurable
El orden en que se absorbe la deuda dentro de cada cuota depende del parámetro global `orden_aplicacion_pago`:

1. **`interes_primero` (Estándar recomendado)**:
   - Primero se cubre el interés pendiente de la obligación.
   - Con el remanente se amortiza el capital pendiente.
2. **`capital_primero`**:
   - Primero se abona al capital pendiente (reduciendo rápidamente el saldo insoluto).
   - Con el remanente se cubren los intereses pendientes.

Si tras saldar la cuota aún queda dinero disponible, el proceso continúa iterando con la siguiente obligación pendiente.

### 2.2 Actualización de estados del préstamo
- Si el saldo insoluto total del crédito llega a cero → `pagado`.
- Si existen cuotas vencidas no pagadas (`days_late > 0`) → `mora`.
- En caso contrario → `activo`.

### 2.3 Reversión transaccional (anulación)
La anulación de un pago revierte las aplicaciones registradas (`PaymentApplication`):
- Restaura `pending_capital` y `pending_interest` en cada obligación afectada.
- Restablece el estado de la cuota a `pendiente` (o `parcial` si hubo otros pagos).
- Limpia `paid_date` y recalcula el estado general del préstamo a `activo` o `mora`.
- Marca el pago como `anulado` y registra el evento en auditoría.

## 3. Reglas parametrizables del motor

Configurables en tiempo real desde **Administración → Parámetros**:

| Clave | Valor por defecto | Categoría | Descripción |
|---|---|---|---|
| `tasa_interes_periodo` | `20.0` | financieros | Tasa de interés (%) aplicada por período de cuota |
| `metodo_interes` | `frances` | financieros | Método de amortización (`frances` o `aleman`) |
| `periodicidad_interes` | `quincenal` | financieros | Periodicidad de cobro de interés |
| `orden_aplicacion_pago` | `interes_primero` | financieros | Prioridad de pago (`interes_primero` o `capital_primero`) |
| `tasa_mora_diaria` | `0.001` | financieros | Tasa de mora diaria referencial |
| `dias_proximos_vencer` | `15` | cobranza | Ventana de días para obligaciones por vencer |
| `dias_alerta_mora` | `5` | cobranza | Días de tolerancia antes de alerta visual de mora |

## 4. Score de comportamiento y análisis de riesgo

Definido en `app/services/scoring.py`. Calcula una calificación integral entre **0 y 100** basada en el historial de obligaciones:

```
score = 100 × (0.45 × puntualidad + 0.35 × cumplimiento + 0.20 × score_mora)
```

- **Puntualidad (45%)**: Proporción de cuotas pagadas en o antes de su fecha límite (`paid_date <= due_date`).
- **Cumplimiento (35%)**: Proporción de cuotas pagadas respecto al total programado.
- **Score de mora (20%)**: Penalización progresiva calculada como:
  ```
  mora_score = max(0, 1 - (max_dias_mora / 90)) - (cuotas_vencidas * 0.05)
  ```

### 4.1 Segmentación y panel de riesgo
El panel de análisis de riesgo precalcula las siguientes bandas para segmentación ejecutiva:

| Banda | Rango de Score | Nivel de Riesgo |
|---|---|---|
| **Bajo riesgo** | ≥ 80 puntos | Excelente comportamiento crediticio |
| **Medio riesgo** | 50 a 79 puntos | Comportamiento aceptable con atrasos menores |
| **Alto riesgo** | < 50 puntos | Alta morosidad o incumplimiento reiterado |
| **Sin historial** | `None` | Cliente nuevo sin cuotas generadas aún |
