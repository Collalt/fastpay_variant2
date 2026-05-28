# FastPay, вариант 2

Интеграционное тестирование API платежа и мокирование внешнего банковского шлюза.

Проект сделан по практическому заданию **"Управление качеством и тестированием в FinTech"**, вариант 2.  
Цель демо: показать, как FastPay проверяет обработку платежа через реальный HTTP API, но без обращения к настоящему банку.

## Что тестируем

Эндпоинт:

```text
POST /v1/payment
```

Вход:

```json
{
  "card_number": "4111111111111111",
  "expiry": "12/30",
  "cvv": "123",
  "amount": "100.00",
  "merchant_id": "m_1001"
}
```

Выход:

```json
{
  "transaction_id": "bank_txn_001",
  "status": "authorized"
}
```

Проверяем не отдельную функцию, а цепочку:

```text
pytest + requests -> FastPay HTTP API -> validation -> bank gateway client -> mocked bank
```

## Наглядная карта тестов

| Тест | Что проверяет | Почему важно для FinTech |
|---|---|---|
| `unittest.mock.patch` в тестах | Подменяет `fastpay.gateway.requests.post` | Внешний банк имитируется mock-объектом, реальные сетевые вызовы не выполняются |
| `test_successful_authorization` | Банк вернул `approved`, FastPay отвечает `authorized` | Основной сценарий оплаты работает корректно |
| `test_insufficient_funds_returns_declined` | Банк вернул `declined`, API не считает это технической ошибкой | Нет ложной успешной оплаты при нехватке средств |
| `test_invalid_cvv_validation_error_and_no_gateway_call` | Некорректный CVV отклоняется до вызова банка | Меньше fraud-рисков и лишних внешних запросов |
| `test_gateway_timeout_is_retried_then_authorized` | Первый вызов банка падает по timeout, второй успешен | Проверена retry logic при временном сбое |
| `test_gateway_timeout_after_retry_returns_504` | Оба вызова банка падают по timeout | API возвращает понятный `504`, а не зависает |
| `test_pan_and_cvv_are_not_written_to_logs` | Полный PAN и CVV не попадают в логи | Снижается риск нарушения PCI DSS |

## Принятые решения

- **Интеграционные тесты запускают реальный HTTP-сервер FastPay.**  
  Тесты обращаются к API через `requests`, поэтому проверяется настоящий HTTP-контракт.

- **Внешний банк заменён mock-объектом через `unittest.mock`.**  
  Это даёт стабильные тесты: можно гарантированно воспроизвести `approved`, `declined`, timeout и retry.

- **Retry ограничен одной повторной попыткой.**  
  Это демонстрирует устойчивость к краткому сбою, но не создаёт бесконечную нагрузку на банк.

- **PAN и CVV маскируются перед логированием.**  
  В логах остаётся диагностическая информация, но не сохраняются чувствительные данные.

- **CI/CD настроен через GitHub Actions.**  
  При каждом `push` и `pull_request` автоматически устанавливаются зависимости и запускаются интеграционные тесты.

## Структура

```text
fastpay_variant2/
|-- fastpay/
|   |-- app.py              # HTTP API и бизнес-сценарий платежа
|   |-- gateway.py          # клиент внешнего банковского шлюза
|   |-- logging_utils.py    # маскирование PAN/CVV
|   |-- config.py
|   `-- __init__.py
|-- tests/
|   |-- conftest.py         # запуск тестового HTTP-сервера
|   `-- test_payment_api.py # интеграционные тесты
|-- docs/
|   `-- test-log.txt        # лог локального запуска тестов
|-- .github/workflows/tests.yml
|-- .gitlab-ci.yml
|-- pyproject.toml
|-- requirements.txt
`-- README.md
```

## Как запустить

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

Для Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -v
```

## Лог выполнения тестов

Актуальный лог сохранён в [docs/test-log.txt](docs/test-log.txt).

Краткий результат:

```text
10 passed
```

## CI/CD

GitHub Actions workflow: [.github/workflows/tests.yml](.github/workflows/tests.yml)

Pipeline выполняет:

1. checkout репозитория;
2. установку Python;
3. установку зависимостей;
4. запуск `python -m pytest -v`;
5. сохранение `docs/test-log.txt` как артефакта CI.

Такой pipeline предотвращает регрессии: если разработчик случайно сломает обработку `declined`, retry logic, валидацию CVV или маскирование логов, merge будет виден как неготовый из-за упавших тестов.

Для демо удобно открыть **Actions -> fastpay-tests -> integration-tests -> Run FastPay integration tests**.  
В начале CI-лога выводится чеклист требований из задания:

```text
FASTPAY VARIANT 2 - CI DEMO CHECKLIST
1. REQUIREMENT: Use mocks for the external bank gateway
   COVERED BY:  unittest.mock.patch replaces fastpay.gateway.requests.post
   EXPECTED:    Bank responses are simulated; no real bank network call is made.
```

А перед каждым тестом выводится карточка:

```text
SCENARIO: Gateway timeout is retried and then succeeds
CHECKING: The first mocked bank call raises timeout, the second returns approved.
EXPECTED: HTTP 200, status=authorized, exactly two gateway calls.
PASSED
```

Так видно не только зелёный статус, но и смысл проверки.

## Test Double в проекте

| Вид | Где применён | Зачем |
|---|---|---|
| Stub | мок банка возвращает заранее заданный `approved` или `declined` | Проверить реакцию FastPay на известный ответ |
| Mock | проверяется `call_count` и факт отсутствия вызова банка при плохом CVV | Проверить протокол взаимодействия |
| Fake | тестовый HTTP-сервер FastPay в памяти | Поднять API без отдельной инфраструктуры |

## Вывод

Вариант 2 показывает главный риск интеграций в платёжной системе: ошибка часто возникает не внутри одной функции, а на границе компонентов.  
Интеграционные тесты здесь проверяют весь путь платежа, контролируют поведение внешнего банка через mock, подтверждают retry logic и защищают логи от утечки PAN/CVV. Для демо это компактный, быстрый и наглядный пример того, как автоматизация в CI/CD снижает риск финансовых и security-регрессий.
