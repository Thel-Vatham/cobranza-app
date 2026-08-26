# 03 · Motor financiero

El motor financiero está centralizado en `app/services/financial.py` y es
independiente de la interfaz. Toda regla que afecta capital, interés, saldo o
vencimiento debe mantenerse aquí para ser determinística y testeable.

## 1. Cálculo del plan de pagos (amortización francesa)

La cuota es fija. Se calcula con tasa periódica:

```
i = tasa_anual / 12
cuota = principal × i / (1 − (1 + i)^(−n))
```

Para cada cuota `k`:

```
interés_k   = saldo_{k−1} × i
capital_k   = cuota − interés_k
saldo_k     = saldo_{k−1} − capital_k
```

En la última cuota se ajusta el capital al saldo restante para cerrar la
amortización exacta (se evita residuo por redondeo). Los valores se redondean a
dos decimales (`ROUND_HALF_UP`).

### 1.1 Ejemplo

- Principal: `1.000.000`
- Interés anual: `24%` → `i = 0.02`
- Cuotas: `12`
- Frecuencia: `30` días

```
cuota = 1.000.000 × 0.02 / (1 − 1.02^−12) ≈ 94.559,60
```

Resultado validado en `tests/test_smoke.py` (tolerancia 0,01).

## 2. Aplicación de pagos (transaccional)

Al registrar un pago, el valor se distribuye sobre las obligaciones pendientes
en orden de vencimiento (más antigua primero) y, dentro de cada obligación:

1. Primero **interés pendiente**.
2. Luego **capital pendiente**.
3. El remanente continúa con la siguiente obligación.

### 2.1 Actualización de estados

- Si el saldo pendiente de la obligación llega a cero → `pagada` y se registra `paid_date`.
- Si se abona parcialmente → `parcial`.
- Si el saldo total del préstamo llega a cero → `pagado`.
- Si existen obligaciones vencidas → `mora`.
- En otro caso → `activo`.

### 2.2 Regla de reversión (anulación de pago)

Al anular un pago se devuelve a cada obligación el capital e interés aplicados,
se restablece el estado a `pendiente`, se limpia `paid_date` y el préstamo vuelve
a `activo`. Todo dentro de la misma sesión transaccional.

## 3. Reglas parametrizables

Los siguientes parámetros están en `app/parameters` (entidad `Parameter`) y
pueden editarse desde **Administración → Parámetros**:

| Clave | Valor por defecto | Descripción |
|---|---|---|
| `metodo_interes` | `frances` | Método de amortización |
| `periodicidad_interes` | `mensual` | Periodicidad del interés |
| `orden_aplicacion_pago` | `interes_primero` | Orden de aplicación |
| `tasa_mora_diaria` | `0.001` | Tasa de mora diaria referencial |

## 4. Score de comportamiento

Definido en `app/services/scoring.py`. Se calcula sobre el historial verificable
del cliente (0–100):

```
score = 100 × (0.45 × puntualidad + 0.35 × cumplimiento + 0.20 × score_mora)
```

- **Puntualidad**: proporción de obligaciones pagadas a tiempo.
- **Cumplimiento**: proporción de obligaciones pagadas.
- **Score de mora**: penaliza según días máximos de mora (escala a 90 días) y
  número de obligaciones vencidas.

Bandas: Excelente (≥80), Bueno (≥60), Regular (≥40), Riesgo alto (<40).
