# vex

**vex** — это инструмент для автоматической генерации версии проекта  
(`C/C++` / `make` / `cmake`) на основе `Git` и упрощённой модели `Semantic Versioning`

---

## Описание

**vex** решает проблему отсутствия дисциплины в версиях:

- версия увеличивается автоматически при `git merge` в ветку `main`
- тип изменения определяется по `commit message`
- генерируется `version.h` для использования в `C/C++`
- поддерживается локальная разработка без CI

---

## Установка (временно с использованием pipx)

```bash
pipx install -e .
pipx ensurepath
```

## Удаление (временно с использованием pipx)

```bash
pipx uninstall vex
```

---

## Быстрый старт

```bash
git init -b main
git commit -m "chore: initial commit"
vex init
git checkout -b dev
# <changes>
git commit -m "feat: useful function"
git checkout main
git merge dev
```

---

## Взаимодействие с **vex**

### Инициализация в директории проекта

```bash
vex init
```

### Генерация файла version.h перед сборкой проекта

#### Требуется добавить вызов перед `make`:

```bash
vex sync --build
```

### Валидация commit message

#### Содержится в `$(cwd)/.git/hooks/commit-msg`

```bash
#!/bin/sh
vex sync --git-commit-msg
```

### Обновление версии при соблюдении условий

#### Содержится в `$(cwd)/.git/hooks/post-merge`

```bash
#!/bin/sh
vex sync --git-post-merge
```

---

## Правила версионирования

    feat!    -> MAJOR
    feat     -> MINOR
    fix      -> PATCH
    perf     -> PATCH
    refactor -> PATCH

### Примечание

При `git commit` с префиксом `feat!` необходимо
использовать `одинарные кавычки`:

    git commit -m 'feat!: api changed'

---