# Mortgage Decision Assistant

> **Sistema de apoyo a la decisión para el análisis y estructuración de operaciones hipotecarias**

Mortgage Decision Assistant es un prototipo académico desarrollado como Trabajo Fin de Máster para ayudar a asesores inmobiliarios e hipotecarios a realizar un preanálisis estructurado de una operación, detectar sus principales restricciones, explorar alternativas financieramente consistentes y contrastar la estructura con criterios públicos documentados de entidades financieras.

El sistema **no predice la aprobación de una hipoteca**, **no sustituye el criterio profesional del asesor** y **no realiza intermediación hipotecaria**.

---

## 🎯 Problema

El análisis inicial de una operación hipotecaria obliga a combinar múltiples variables:

- precio de compra
- ahorro disponible
- entrada prevista
- gastos asociados a la compra
- importe solicitado
- plazo e interés
- cuota hipotecaria
- deuda mensual existente
- liquidez residual
- financiación sobre valor (LTV)
- ratio de endeudamiento (DSTI)
- valoración del inmueble
- posibles alternativas de reestructuración

En la práctica, este análisis puede apoyarse en hojas de cálculo, calculadoras aisladas, documentación bancaria y experiencia profesional.

El problema no consiste únicamente en calcular una cuota, sino en responder preguntas como:

> **¿Qué está limitando esta operación?**

> **¿Qué tendría que cambiar para mejorar su estructura financiera?**

> **¿Cómo encaja la operación con criterios públicos documentados de diferentes entidades?**

---

## ✨ Solución

Mortgage Decision Assistant combina cálculo financiero determinista con diferentes capas de apoyo a la decisión.

El sistema permite:

1. **Calcular** de forma consistente la estructura financiera de la operación.
2. **Diagnosticar** qué restricciones afectan al caso.
3. **Identificar una estructura viable** dentro de objetivos financieros configurados.
4. **Evaluar estrategias alternativas** de reestructuración.
5. **Simular escenarios** modificando variables relevantes.
6. **Contrastar la operación con criterios públicos documentados de entidades financieras.**
7. **Mantener trazabilidad** sobre cálculos, supuestos, criterios y fuentes utilizadas.

El asesor conserva siempre la decisión final.

---

## 🧩 Arquitectura de decisión

El proyecto separa las responsabilidades en distintos componentes:

```text
FinancialScenario
        │
        ▼
Financial Engine
        │
        ├──────────────► FinancialResult
        │
        ▼
Boundary Solver
        │
        ▼
Recommendation Engine
        │
        ├──────────────► Alternatives Engine
        │
        └──────────────► Bank Fit Engine
                              │
                              ▼
                     BankFitResult[]
```

Esta separación permite mantener independiente el cálculo financiero de las capas posteriores de diagnóstico y apoyo a la decisión.

---

## ⚙️ Financial Engine

Es la base matemática del sistema.

A partir del escenario introducido calcula, entre otros:

- costes estimados de compra
- efectivo disponible para la operación
- entrada prevista
- préstamo necesario
- importe financiado
- cuota mensual
- liquidez residual
- déficit de liquidez
- LTV
- DSTI
- margen mensual
- intereses totales estimados

El cálculo utiliza `Decimal` para mantener precisión financiera y registra:

- inputs ausentes
- supuestos utilizados
- fallbacks
- modos de cálculo
- completitud
- confianza técnica

---

## 📐 Boundary Solver

Cuando la estructura inicial no cumple los objetivos configurados, el Boundary Solver busca límites financieros factibles.

En la versión actual trabaja principalmente sobre:

- precio del inmueble
- entrada prevista

El objetivo principal configurado es:

> **Conservar el mayor precio de compra posible dentro de los objetivos financieros analizados.**

Las estructuras encontradas son recalculadas mediante el Financial Engine para comprobar su consistencia antes de mostrarse.

---

## 🧠 Recommendation Engine

Transforma los resultados financieros y las fronteras calculadas en una propuesta comprensible para el asesor.

Puede identificar situaciones como:

- operación dentro de los objetivos
- necesidad de reestructuración
- ausencia de una estructura viable dentro de las restricciones
- información incompleta

La recomendación principal no pretende ser la única solución posible, sino una estructura financieramente consistente con el objetivo definido.

---

## 🔀 Alternatives Engine

Además de la recomendación principal, el sistema analiza estrategias diferentes.

Entre ellas:

- reducir el precio manteniendo la entrada
- mantener el precio modificando la entrada
- ampliar el plazo cuando el problema está relacionado con capacidad mensual

Cada estrategia puede clasificarse como:

- viable
- no viable
- no relevante para el problema detectado
- equivalente a la recomendación principal

El resultado es un mapa de decisión, no una única cifra.

---

## 🏦 Bank Fit Engine

Bank Fit es una capa adicional del modo profesional.

Su objetivo es comparar una estructura hipotecaria con **criterios públicos documentados de productos financieros**.

El prototipo académico incorpora criterios de:

- Banco Santander
- BBVA
- CaixaBank
- Banco Sabadell
- Bankinter

Los criterios pueden incluir:

- financiación máxima
- base de cálculo del LTV
- plazo máximo
- edad al vencimiento
- residencia
- uso de la vivienda
- ingresos mínimos publicados
- ratios de endeudamiento cuando existen públicamente

La evaluación utiliza cuatro estados:

```text
MATCH
MISMATCH
UNKNOWN
NOT_APPLICABLE
```

En la interfaz se muestran como:

```text
✅ Dentro
⚠️ Fuera
❔ No evaluable
— No aplica
```

Un criterio desconocido nunca se convierte automáticamente en cumplimiento.

Además, cada criterio puede registrar:

- tipo de evidencia
- fuente oficial
- fecha de verificación
- fecha recomendada de revisión
- estado de la fuente
- posibles conflictos documentales

### Alcance jurídico del Bank Fit

La funcionalidad **Bank Fit queda circunscrita al ámbito académico del TFM**.

Su utilización operativa con prestatarios reales, su eventual integración en procesos profesionales de intermediación o su explotación comercial **no se consideran jurídicamente validadas en este proyecto** y quedan condicionadas a una **revisión legal y regulatoria específica previa**, incluyendo su posible encaje en la Ley 5/2019 de contratos de crédito inmobiliario (LCCI).

Por tanto, Bank Fit:

- no calcula probabilidad de aprobación;
- no recomienda una entidad;
- no tramita operaciones;
- no envía información a bancos;
- no sustituye la decisión profesional del asesor.

---

## 🖥️ Aplicación Streamlit

La aplicación dispone de dos modos de uso.

### Lite

Orientado a un preanálisis rápido para perfiles inmobiliarios.

Permite obtener una primera valoración estructural de la operación con una experiencia simplificada.

### Pro

Orientado al análisis de un asesor hipotecario o financiero.

El flujo se divide en tres pestañas:

#### 1. Análisis y recomendación

Muestra:

- situación actual
- diagnóstico
- principales restricciones
- recomendación de reestructuración
- comparación actual vs recomendada
- otras estrategias
- trazabilidad técnica

#### 2. Bank Fit

Compara la estructura analizada con criterios públicos documentados de productos financieros.

Para cada producto muestra:

```text
Criterio | Esta operación | Criterio público | Resultado
```

La información técnica y las fuentes quedan disponibles en un nivel adicional de trazabilidad.

#### 3. Escenarios

Permite modificar variables y observar su impacto:

- tipo de interés
- ingresos
- entrada
- precio
- plazo
- tasación
- porcentaje de financiación

Esta sección realiza simulaciones libres y no modifica automáticamente la recomendación principal.

---

## 💡 Ejemplo de operación

Supongamos una operación con:

```text
Precio del inmueble:      300.000 €
Ahorros disponibles:      100.000 €
Entrada prevista:          60.000 €
Ingresos netos conjuntos:   4.000 €/mes
Deuda mensual actual:         300 €/mes
Plazo:                         30 años
Tipo de interés:                3 %
```

El sistema puede detectar que una determinada estructura no preserva la liquidez deseada o supera alguno de los objetivos configurados.

A partir de ahí puede:

1. diagnosticar la restricción;
2. calcular una posible estructura alternativa;
3. comprobarla mediante el Financial Engine;
4. estudiar otras estrategias;
5. comparar el escenario resultante con criterios públicos documentados;
6. realizar simulaciones adicionales.

---

## 🧪 Validación

El proyecto incluye una suite automatizada de tests.

Se han creado casos específicos para comprobar:

- cálculo financiero
- situaciones límite
- reglas de liquidez
- LTV
- DSTI
- recomendaciones
- fronteras de precio y entrada
- estrategias alternativas
- Bank Fit
- ausencia de tasación
- reglas de edad de múltiples titulares
- criterios con información desconocida
- fuentes en conflicto
- separación entre criterios públicos duros y orientaciones públicas

Los tests se ejecutan automáticamente mediante GitHub Actions.

---

## 📂 Estructura del proyecto

```text
mortgage-decision-assistant/
│
├── src/
│   └── mortgage_decision_assistant/
│       ├── domain.py
│       ├── financial_engine.py
│       ├── boundary_solver.py
│       ├── recommendation_engine.py
│       ├── alternatives_engine.py
│       ├── bank_fit_engine.py
│       └── presentation.py
│
├── config/
│   ├── financial_defaults.yaml
│   └── bank_criteria_v0_1.yaml
│
├── tests/
├── docs/
├── app.py
├── app_ui.py
├── requirements.txt
└── README.md
```

---

## 🔎 Principios de diseño

### Separación entre cálculo y decisión

El Financial Engine realiza cálculos. Las capas posteriores interpretan esos resultados.

### Trazabilidad

Las recomendaciones pueden rastrearse hasta los cálculos, supuestos y criterios utilizados.

### Ausencia de información ≠ resultado negativo

Cuando un criterio no puede evaluarse, el sistema devuelve `UNKNOWN`.

No se inventa información ni se transforma la ausencia de evidencia en cumplimiento o incumplimiento.

### Restricciones verificadas por el motor

Las estructuras propuestas son recalculadas por el Financial Engine antes de mostrarse como viables.

### Decisión humana

La herramienta apoya al profesional. No sustituye su decisión.

---

## 📚 Contexto académico y capa EFF

Como parte del TFM se ha desarrollado una línea de investigación estadística independiente basada en la **Encuesta Financiera de las Familias (EFF)** para estudiar cómo el benchmarking poblacional podría complementar el análisis determinista.

Esta capa tiene una separación deliberada y estricta respecto de la aplicación:

- **permanece exclusivamente en Google Colab;**
- **no forma parte del repositorio GitHub;**
- **no se integra en la aplicación Streamlit desplegada;**
- **no forma parte del Bank Fit Engine;**
- **no se utiliza como componente operativo o comercial.**

Los microdatos, variables derivadas, transformaciones, modelos, artefactos y resultados específicos de la EFF se mantienen fuera de este repositorio y se utilizan únicamente en el entorno académico de Colab.

Su función dentro del TFM es investigadora: explorar el potencial de una futura capa de inteligencia estadística, no proporcionar scoring, aprobación bancaria ni decisiones automáticas.

---

## ⚠️ Alcance y limitaciones

Mortgage Decision Assistant es actualmente un **prototipo académico**.

No:

- predice la aprobación de una operación hipotecaria;
- representa las políticas internas completas de las entidades;
- garantiza condiciones comerciales;
- sustituye la evaluación profesional;
- realiza intermediación hipotecaria;
- envía operaciones a entidades financieras;
- utiliza la capa EFF en la aplicación desplegada.

Los criterios de Bank Fit proceden de información pública documentada y están sujetos a cambios, revisiones y posibles conflictos entre fuentes.

La funcionalidad Bank Fit forma parte exclusivamente del alcance académico del TFM. Cualquier uso posterior con clientes reales requeriría una revisión jurídica y regulatoria específica antes de su utilización operativa.

---

## ✅ Estado actual

El prototipo funcional incluye:

- modo Lite
- modo Pro
- Financial Engine
- cálculo de cuota mediante amortización francesa
- análisis de liquidez
- cálculo de LTV y DSTI
- Boundary Solver
- Recommendation Engine
- Alternatives Engine
- comparación actual vs recomendación
- simulación de escenarios
- Bank Fit Engine
- criterios públicos documentados para cinco entidades
- trazabilidad de fuentes
- tests automatizados
- aplicación Streamlit

Con este alcance se considera **congelada la versión funcional utilizada para el TFM**.

---

## 🔮 Evolución futura

Una eventual evolución del prototipo podría incorporar:

- gestión de expedientes
- histórico de decisiones del asesor
- reporting
- control de versiones de políticas bancarias
- automatización de actualización de criterios
- seguimiento de resultados reales
- integración con sistemas profesionales
- modelos supervisados únicamente cuando existan datos reales correctamente etiquetados
- benchmarking estadístico compatible con un entorno productivo y jurídicamente validado

Estas líneas forman parte del roadmap futuro y no del alcance validado del TFM.

---

## Autor

Proyecto desarrollado como Trabajo Fin de Máster.

**Mortgage Decision Assistant**
