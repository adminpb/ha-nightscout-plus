# 🩸 Nightscout Plus for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Розширена інтеграція Nightscout для Home Assistant. Форк оригінальної інтеграції `nightscout` з підтримкою **treatments, notes, IOB, COB** та інших даних, які стандартний компонент ігнорує.

## Чому не стандартна інтеграція?

Вбудована інтеграція `nightscout` створює лише **1 сенсор** — `sensor.blood_glucose`. При цьому Nightscout API має значно більше даних. Крім того, бібліотека `py-nightscout`, яку використовує оригінал, **не включає поле `notes`** в моделі Treatment.

## Що додає Nightscout Plus?

| # | Сенсор | Стан | Одиниця | Атрибути |
|---|--------|------|---------|----------|
| 1 | **Blood Glucose** | SGV (mg/dL) | mg/dL | `value_mmol`, `direction`, `delta`, `delta_mmol`, `device`, `noise`, `date` |
| 2 | **Last Treatment** | eventType | — | Всі поля treatment: `notes`, `carbs`, `insulin`, `created_at`, `enteredBy`… |
| 3 | **Last Note** | Текст замітки (≤255 символів) | — | `eventType`, `created_at`, `enteredBy`… |
| 4 | **Last Meal** | Кількість вуглеводів | g | `foodType`, `notes`, `created_at`… |
| 5 | **Last Bolus** | Доза інсуліну | U | `eventType`, `programmed`, `duration`… |
| 6 | **Last Exercise** | Тривалість | min | `notes`, `created_at`… |
| 7 | **Insulin On Board** | IOB | U | — (з devicestatus, потрібен Loop/OpenAPS) |
| 8 | **Carbs On Board** | COB | g | — (з devicestatus, потрібен Loop/OpenAPS) |

## Установка

### Через HACS (рекомендовано)

1. Відкрийте HACS → Integrations → ⋮ (три крапки) → **Custom repositories**
2. Додайте URL репозиторію: `https://github.com/adminpb/ha-nightscout-plus`
3. Категорія: **Integration**
4. Натисніть **Add** → знайдіть "Nightscout Plus" → **Install**
5. Перезавантажте Home Assistant

### Вручну

Скопіюйте папку `custom_components/nightscout_plus/` у вашу директорію `config/custom_components/`.

## Налаштування

1. Settings → Devices & Services → **Add Integration**
2. Знайдіть **Nightscout Plus**
3. Введіть:
   - **URL** — адреса вашого Nightscout (напр. `https://my-ns.fly.dev`)
   - **API Secret** — (необов'язково) якщо ваш сайт потребує автентифікації
   - **Treatments count** — к-сть останніх treatments для завантаження (за замовч. 15)

## Співіснування зі стандартною інтеграцією

Nightscout Plus працює **паралельно** зі стандартною інтеграцією `nightscout`. Можна використовувати обидві, або вимкнути стандартну — як зручніше. Домен інтеграції `nightscout_plus` не конфліктує з `nightscout`.

## Приклади автоматизацій

```yaml
# Сповіщення про нову замітку
automation:
  - alias: "Nightscout нова замітка"
    trigger:
      - trigger: state
        entity_id: sensor.nightscout_last_note
    action:
      - action: notify.mobile_app
        data:
          title: "📝 Nightscout"
          message: "{{ states('sensor.nightscout_last_note') }}"

# TTS оголошення про їжу
  - alias: "Meal announced"
    trigger:
      - trigger: state
        entity_id: sensor.nightscout_last_meal
    condition:
      - condition: template
        value_template: "{{ states('sensor.nightscout_last_meal') | float(0) > 0 }}"
    action:
      - action: tts.speak
        target:
          entity_id: tts.google
        data:
          message: >
            Зафіксовано прийом їжі:
            {{ states('sensor.nightscout_last_meal') }} грам вуглеводів.
            {% if state_attr('sensor.nightscout_last_meal', 'notes') %}
            Примітка: {{ state_attr('sensor.nightscout_last_meal', 'notes') }}
            {% endif %}
```

## Використання в шаблонах

```yaml
# Глюкоза в mmol/L
{{ state_attr('sensor.nightscout_blood_glucose', 'value_mmol') }} ммоль/л

# Тренд
{{ state_attr('sensor.nightscout_blood_glucose', 'direction') }}

# Остання замітка
{{ states('sensor.nightscout_last_note') }}

# Час останнього болюсу
{{ state_attr('sensor.nightscout_last_bolus', 'created_at') }}

# IOB (якщо є Loop/OpenAPS)
{{ states('sensor.nightscout_insulin_on_board') }} U
```

## Технічні деталі

- **Не використовує** бібліотеку `py-nightscout` — працює напряму з Nightscout REST API v1
- Використовує `DataUpdateCoordinator` з HA — один HTTP запит для всіх сенсорів
- Паралельні запити до `/entries`, `/treatments`, `/devicestatus` через `asyncio.gather`
- Повністю async, не блокує event loop
- Config Flow з UI — налаштування через інтерфейс, не потрібно редагувати YAML

## Структура файлів

```
custom_components/nightscout_plus/
├── __init__.py         # Entry setup / unload
├── api.py              # HTTP client для Nightscout API
├── config_flow.py      # UI конфігурація
├── const.py            # Константи
├── coordinator.py      # DataUpdateCoordinator
├── manifest.json       # HA manifest
├── sensor.py           # 8 sensor entities
└── strings.json        # Переклади для config flow
```

## Ліцензія

Apache License 2.0 (як і Home Assistant core)
