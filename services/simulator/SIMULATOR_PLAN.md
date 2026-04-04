# Telemetry Simulator — Plan

> Сервис генерации реалистичной телеметрии для парка ~1700 локомотивов КТЖ.
> Цель: покрыть демо дашборда, нагрузочный тест (10×), сценарии деградации и аварий.

---

## 1. Контекст и цели

| Требование | Детали |
|---|---|
| Парк | ~1700 локомотивов, разброс по всему Казахстану |
| Типы | TE33A (дизель, ~60 %), KZ8A (электровоз, ~40 %) |
| Базовая нагрузка | 1 Гц на лок → 1 700 событий/с |
| Пиковая нагрузка | ×10 → ~17 000 событий/с |
| Доставка | `POST /telemetry/ingest/batch` → `processor` |
| Формат | `shared.schemas.telemetry.TelemetryReading` (Pydantic JSON) |

---

## 2. Архитектура сервиса

```
services/simulator/
├── Dockerfile
├── pyproject.toml              # зависимости: httpx, pydantic, uvicorn, typer
├── main.py                     # FastAPI app (health + control endpoints)
├── simulator/
│   ├── core/
│   │   ├── config.py           # SimulatorSettings (env-vars)
│   │   └── client.py           # httpx.AsyncClient + retry/backoff
│   ├── models/
│   │   ├── locomotive_state.py # State machine + физическая модель
│   │   └── fleet.py            # Генерация 1700 локомотивов, GPS-маршруты
│   ├── generators/
│   │   ├── te33a.py            # Физика TE33A (8 ноч, масло, охладитель)
│   │   ├── kz8a.py             # Физика KZ8A (контактная сеть, IGBT, рекуперация)
│   │   └── noise.py            # Гауссов шум + редкие случайные выбросы (ЭМИ)
│   ├── scenarios/
│   │   ├── normal.py           # Штатный режим 1 Гц
│   │   ├── highload.py         # Burst ×10: массовый одновременный запуск
│   │   ├── degradation.py      # Постепенный перегрев IGBT / масло
│   │   └── emergency.py        # Разрыв тормозной магистрали, юз колёс
│   └── runner.py               # Оркестратор: asyncio.gather + batching
```

---

## 3. Машина состояний локомотива

Каждый локомотив в любой момент находится в одном из состояний:

```
DEPOT ──► DEPARTURE ──► CRUISING ──► ARRIVAL ──► DEPOT
              │               │
              ▼               ▼
           AESS_SLEEP     EMERGENCY
              │               │
              └───────────────┘
                   RECOVERY
```

| Состояние | Длительность | Описание |
|---|---|---|
| `DEPOT` | 10–120 мин | Локомотив стоит, все параметры на холостом ходу |
| `DEPARTURE` | 3–10 мин | Разгон, рост оборотов/тока |
| `CRUISING` | 30–180 мин | Крейсерская скорость 60–100 км/ч |
| `ARRIVAL` | 3–10 мин | Торможение, рекуперация (KZ8A), снижение RPM |
| `AESS_SLEEP` | 5–30 мин | TE33A: двигатель выключен, RPM=0, масло=0 |
| `EMERGENCY` | 1–5 мин | Резкое падение давления / юз / перегрев |
| `RECOVERY` | 5–15 мин | Параметры возвращаются в норму |

### Переходы
- `CRUISING → EMERGENCY`: вероятность 0.0001 за тик (≈1 событие / 3 ч на лок)
- `CRUISING → AESS_SLEEP`: только TE33A, вероятность 0.0005
- `EMERGENCY → RECOVERY → CRUISING`: автоматически

---

## 4. Физические модели

### 4.1 TE33A — дизель GE GEVO12

Восемь ноч-позиций двигателя (Notch 0–8):

| Notch | RPM | fuel_rate (л/ч) | coolant_temp (°C) | Скорость (км/ч) |
|---|---|---|---|---|
| 0 (idle) | 300 | 15 | 72 | 0 |
| 1 | 400 | 25 | 74 | 15 |
| 2 | 500 | 40 | 76 | 30 |
| 4 | 700 | 80 | 82 | 60 |
| 6 | 850 | 130 | 88 | 90 |
| 8 (full) | 1050 | 180 | 92 | 115 |

**Формулы зависимостей:**
```python
# Нотч → физика
notch = state.notch  # 0..8

diesel_rpm        = 300 + notch * 93.75  # linear 300→1050
fuel_rate         = 15 + (notch/8)**1.5 * 165    # нелинейный рост
coolant_temp      = 72 + notch * 2.5     # тепловая инерция (EMA α=0.05)
oil_pressure      = 1.5 + (diesel_rpm / 1050) * 3.0  # зависит от RPM
traction_motor_temp = 40 + (notch/8) * 70  # инерция α=0.03
fuel_level       -= fuel_rate / 3600      # расход per tick

# Давление в тормозной магистрали: стабильно с малым шумом
brake_pipe_pressure = 5.1 + gaussian(0, 0.02)

# Пробуксовка: только при разгоне на влажном пути (редко)
wheel_slip_ratio = 0.0  # в норме
```

**AESS sleep:**
```python
if state == AESS_SLEEP:
    diesel_rpm = 0
    oil_pressure = 0
    fuel_rate = 0
    # НЕ генерировать алерты — маскируется в processor
```

### 4.2 KZ8A — электровоз Alstom

```python
speed = state.speed  # 0..120 км/ч

# Тяга — ток токоприёмника
pantograph_current = 50 + (speed / 120) * 300  # 50→350 А

# Контактная сеть: номинал 25 кВ с просадкой под нагрузкой
catenary_voltage = 25000 - pantograph_current * 8 + gaussian(0, 200)

# IGBT: тепловая инерция (медленный рост, медленный спад)
igbt_temp_target  = 35 + (pantograph_current / 400) * 40  # 35→75 °C
igbt_temp        += (igbt_temp_target - igbt_temp) * 0.05  # EMA α=0.05

# Трансформатор: ещё медленнее
transformer_temp_target = 45 + (pantograph_current / 400) * 35
transformer_temp       += (transformer_temp_target - transformer_temp) * 0.03

# DC-звено
dc_link_voltage = 2800 + gaussian(0, 50)

# Рекуперация: только при торможении (speed убывает)
if state == ARRIVAL and speed > 20:
    recuperation_current = (120 - speed) / 120 * 200  # до 200 А
else:
    recuperation_current = 0
```

### 4.3 Общий шум (оба типа)

```python
# Гауссов шум — имитация ЭМИ от инверторов
value += gaussian(0, sigma=spec.p_nom * 0.005)   # 0.5% от номинала

# Редкие выбросы (ЭМИ-спайк): вероятность 0.001 за тик
if random() < 0.001:
    value += gaussian(0, sigma=spec.p_nom * 0.05)  # 5% выброс
```

---

## 5. Парк 1700 локомотивов

### 5.1 Распределение по типам

```
TE33A: ~1020 (60%) — грузовые маршруты
KZ8A:  ~680  (40%) — электрифицированные участки
```

### 5.2 Маршруты Казахстана (GPS-координаты)

Реальные ж/д участки КТЖ для GPS трека локомотива:

```python
ROUTES = [
    # (название, lat_start, lon_start, lat_end, lon_end, электрифицирован)
    ("Алматы – Астана",      43.26, 76.95, 51.16, 71.47, True),   # KZ8A
    ("Астана – Петропавловск", 51.16, 71.47, 54.86, 69.14, False), # TE33A
    ("Астана – Экибастуз",   51.16, 71.47, 51.72, 75.32, False),
    ("Алматы – Шымкент",     43.26, 76.95, 42.34, 69.59, True),
    ("Шымкент – Туркестан",  42.34, 69.59, 43.29, 68.27, False),
    ("Экибастуз – Павлодар", 51.72, 75.32, 52.28, 76.97, False),
    ("Актобе – Атырау",      50.28, 57.20, 47.12, 51.88, False),
    ("Актобе – Костанай",    50.28, 57.20, 53.21, 63.62, False),
    ("Алматы – Балхаш",      43.26, 76.95, 46.84, 74.98, False),
    ("Астана – Кокшетау",    51.16, 71.47, 53.28, 69.39, False),
]
```

### 5.3 Генерация fleet

```python
def generate_fleet(n: int = 1700) -> list[LocomotiveState]:
    locos = []
    te33a_count = int(n * 0.6)
    for i in range(n):
        loco_type = "TE33A" if i < te33a_count else "KZ8A"
        # Распределяем по маршрутам: электровозы — только электрифицированные
        route = pick_compatible_route(loco_type)
        locos.append(LocomotiveState(
            id=uuid4(),
            loco_type=loco_type,
            route=route,
            # Случайная фаза по маршруту — не все стартуют одновременно
            route_progress=random(),
            state=random_initial_state(),
        ))
    return locos
```

---

## 6. Сценарии нагрузки

### 6.1 Normal — штатный режим

```
1700 локомотивов × 1 Гц = 1 700 событий/с
Батч: 100 локомотивов → 17 POST /telemetry/ingest/batch / с
```

### 6.2 Highload ×10 — утренний пик / шторм реконнектов

**Смысл:** Утром диспетчерская получает одновременный доклад от всего парка + некоторые локомотивы переходят на HF-режим (50 Гц) из-за активных манёвров.

```
Фаза 1 (0–30 с):  все 1700 лок. разом выходят на связь → burst 1700 батчей за 1 с
Фаза 2 (30–120 с): 200 активных лок. переходят на 10 Гц → 2000 событий/с от них
                   1500 остальных — 1 Гц → 1500 событий/с
                   Итого: ~3500 событий/с ≈ 2× normal
Фаза 3 (120–180 с): 50 лок. в HF-режиме 50 Гц (манёвры) → 2500 + 1650 = 4150
Суммарный пик:  ~5000 событий/с + jitter → имитируем 10× batching сжатием времени
```

**Реализация для демо:** параметр `--burst-multiplier 10` — уменьшает интервал между тиками в 10 раз (tick_interval = 0.1 с вместо 1 с), все 1700 лок. активны.

```
tick_interval = 1.0 / burst_multiplier  # 0.1 с при ×10
events/s = 1700 / 0.1 = 17 000
batch_size = 200  → 85 batch requests/s к processor
```

### 6.3 Degradation — постепенная деградация

```
Выбирается 1 KZ8A лок., запускается сценарий перегрева IGBT:
  t=0:   igbt_temp = 57°C (норма)
  t=5m:  igbt_temp = 70°C (safe zone ends at 75°C)
  t=10m: igbt_temp = 78°C → WARNING alert, HI падает до ~75
  t=15m: igbt_temp = 84°C → HI ≈ 62, CRITICAL alert
  t=20m: igbt_temp = 87°C → EMERGENCY, HI < 40
Montsinger accumulator в processor нарастает все 20 минут.
```

### 6.4 Emergency — разрыв тормозной магистрали

```
Выбирается 1 лок. на скорости 80 км/ч:
  brake_pipe_pressure: 5.1 → 3.5 → 2.5 → 1.8 bar
  Время падения: 10 секунд (имитация разрыва)
  Ожидаемый ответ processor: severity=EMERGENCY, HI → 0
```

### 6.5 AESS Demo — автозапуск/останов двигателя

```
TE33A встаёт на остановке:
  diesel_rpm: 700 → 300 → 0
  oil_pressure: 3.5 → 0 (masked in processor — нет алертов)
  Через 15 мин: двигатель автозапуск, RPM растёт обратно
```

---

## 7. Стратегия батчинга и backpressure

```
Нормальный режим:
  batch_size   = 100 локомотивов
  tick_interval = 1.0 с
  → 17 запросов/с

Highload ×10:
  batch_size   = 200 локомотивов
  tick_interval = 0.1 с
  → 85 запросов/с

Backpressure (processor перегружен):
  HTTP 429 / 503 → экспоненциальный backoff: 0.5 → 1 → 2 → 4 с
  Буфер в памяти: до 10 000 событий (deque maxlen)
  Индикация "нет связи" в логах и метриках
```

### Пул соединений httpx

```python
# Один AsyncClient на весь runner, переиспользуем TCP-соединения
client = httpx.AsyncClient(
    base_url=settings.processor_url,
    timeout=5.0,
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
)
```

---

## 8. Конфигурация (env + CLI)

```env
# .env
SIMULATOR_PROCESSOR_URL=http://processor:8000
SIMULATOR_FLEET_SIZE=1700
SIMULATOR_TICK_INTERVAL=1.0      # секунд между тиками
SIMULATOR_BATCH_SIZE=100          # локомотивов на батч
SIMULATOR_BURST_MULTIPLIER=1.0   # ×10 для highload
SIMULATOR_SCENARIO=normal         # normal | highload | degradation | emergency | aess
SIMULATOR_SEED=42                 # воспроизводимость рандома
SIMULATOR_LOG_LEVEL=INFO
```

### Control API (FastAPI)

```
GET  /health                   → статус симулятора
GET  /metrics                  → events/s, errors, buffer size
POST /scenario/{name}          → переключить сценарий на лету
POST /fleet/resize?n=100       → изменить размер парка
GET  /fleet/sample?n=5         → посмотреть состояние 5 лок.
POST /burst?multiplier=10&duration=60  → burst на N секунд
```

---

## 9. Docker-интеграция

```yaml
# docker-compose.yml (добавить)
simulator:
  build:
    context: .
    dockerfile: services/simulator/Dockerfile
  env_file: .env
  environment:
    - SIMULATOR_PROCESSOR_URL=http://processor:8000
    - SIMULATOR_FLEET_SIZE=1700
    - SIMULATOR_SCENARIO=normal
  depends_on:
    processor:
      condition: service_healthy
  ports:
    - "8003:8000"   # control API
```

---

## 10. Пошаговая реализация

### Шаг 1 — Фундамент (2–3 ч)
- [ ] `pyproject.toml` — зависимости: `httpx`, `pydantic-settings`, `fastapi`, `uvicorn`
- [ ] `simulator/core/config.py` — `SimulatorSettings`
- [ ] `simulator/core/client.py` — `httpx.AsyncClient` + retry с backoff
- [ ] `simulator/models/locomotive_state.py` — датакласс состояния + enum состояний

### Шаг 2 — Физика (2–3 ч)
- [ ] `simulator/generators/noise.py` — гауссов шум, редкие выбросы, `random.seed()`
- [ ] `simulator/generators/te33a.py` — notch-модель, AESS
- [ ] `simulator/generators/kz8a.py` — тяговая модель, рекуперация

### Шаг 3 — Парк и маршруты (1–2 ч)
- [ ] `simulator/models/fleet.py` — `generate_fleet(n=1700)`, GPS-маршруты KZ

### Шаг 4 — Раннер и батчинг (2–3 ч)
- [ ] `simulator/runner.py` — `asyncio.gather` по всем лок., батчинг, backpressure-буфер
- [ ] `simulator/scenarios/normal.py` — 1 Гц, все лок.
- [ ] `simulator/scenarios/highload.py` — ×10 burst параметр

### Шаг 5 — Сценарии деградации (1–2 ч)
- [ ] `simulator/scenarios/degradation.py` — IGBT overheating
- [ ] `simulator/scenarios/emergency.py` — brake pipe drop
- [ ] `simulator/scenarios/aess_demo.py` — AESS sleep/wake

### Шаг 6 — Control API и Docker (1 ч)
- [ ] `main.py` — FastAPI endpoints `/health`, `/metrics`, `/scenario/{name}`, `/burst`
- [ ] `Dockerfile`
- [ ] добавить `simulator` в `docker-compose.yml`

---

## 11. Расчёт нагрузки

| Режим | Лок. | Тик, с | События/с | Батч | Запросов/с |
|---|---|---|---|---|---|
| Normal | 1700 | 1.0 | 1 700 | 100 | **17** |
| Highload ×10 | 1700 | 0.1 | 17 000 | 200 | **85** |
| HF 50 Гц (50 лок.) | 50 | 0.02 | 2 500 | 50 | **50** |
| Демо minimal | 10 | 1.0 | 10 | 10 | **1** |

> Processor может обрабатывать батч 200 событий за ~10–20 мс (SQLAlchemy bulk insert).
> При 85 запросах/с и 20 мс обработки = 1.7 ядра CPU → комфортно для одного экземпляра.
> Для реального highload: горизонтальное масштабирование processor за nginx upstream.

---

## 12. Воспроизводимость и демо

```python
# Фиксированный seed для презентации
random.seed(SIMULATOR_SEED)
numpy.random.seed(SIMULATOR_SEED)

# Pre-generated scenario: через 2 мин после старта — IGBT degradation на лок. #42
# Через 5 мин — brake pipe emergency на лок. #137
# Через 8 мин — AESS sleep на лок. #7
```

Это позволяет на демо показать конкретные алерты и падение HI в нужный момент.

---

## 13. Метрики для демо-видео

Simulator должен логировать каждые 5 секунд:

```
[SIMULATOR] tick=42 | events_sent=1700 | errors=0 | buffer=0 | events/s=1700
[SIMULATOR] tick=43 | events_sent=1700 | errors=2 | buffer=0 | events/s=1698
[SIMULATOR] BURST START | multiplier=10 | target_rate=17000
[SIMULATOR] tick=44 | events_sent=17000 | errors=0 | buffer=0 | events/s=17000
```
